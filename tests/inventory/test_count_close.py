import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
EXPENSE_ACCOUNT = 3876

class CloseCountTest(DBTestCase):
	'''closing a count makes the books agree with what was counted, at the one
	location the summary names, and values the difference in the ledger'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.location_id = self.new_location('Count close location')
		self.summary_id = self.new_summary()
		self.cursor.execute("SELECT id FROM products "
							"WHERE NOT deleted AND stock ORDER BY id LIMIT 3")
		self.products = [row[0] for row in self.cursor.fetchall()]
		self.product_id = self.products[0]
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, inventory_enabled = True, "
							"cost = 2.50 WHERE id = ANY(%s)",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.products))
		self.DB.commit()

	def new_summary(self, name = 'close unit test'):
		return self.one("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, location_id) VALUES (%s, %s, %s) "
						"RETURNING id", (name, self.fiscal_id, self.location_id))

	def stock(self, product_id, qty, location_id = None):
		'''put qty on the shelf without going through any document'''
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, location_id, price, reason, "
							"date_inserted) VALUES (%s, %s, %s, 2.50, 'test', "
							"CURRENT_DATE)",
							(product_id, qty,
							location_id if location_id else self.location_id))

	def count(self, product_id, qty, cost = '2.50', retail = '4.00',
				summary_id = None):
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, %s, %s, %s)",
							(summary_id if summary_id else self.summary_id,
							product_id, qty, cost, retail))

	def close(self, summary_id = None):
		return self.inventorying.close_count(
							summary_id if summary_id else self.summary_id)

	def correction(self, product_id):
		'''the stock row this close wrote for a product, with its entry'''
		self.cursor.execute("SELECT it.qty_in, it.qty_out, it.price, it.reason, "
								"it.location_id, ge.debit_account, "
								"ge.credit_account, ge.amount, "
								"ge.transaction_description "
							"FROM inventory_transactions AS it "
							"LEFT JOIN gl_entries AS ge ON ge.id = it.gl_entries_id "
							"WHERE it.count_summary_id = %s AND it.product_id = %s",
							(self.summary_id, product_id))
		rows = self.cursor.fetchall()
		self.assertEqual(len(rows), 1, 'expected exactly one correction row')
		return rows[0]

	def corrections(self):
		return self.one("SELECT count(*) FROM inventory_transactions "
						"WHERE count_summary_id = %s", (self.summary_id,))

	def transaction_id(self):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"WHERE ge.id = (SELECT gl_entries_id "
							"FROM inventory_transactions "
							"WHERE count_summary_id = %s "
							"AND gl_entries_id IS NOT NULL ORDER BY id LIMIT 1)",
						(self.summary_id,))

	def sides(self):
		debits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND debit_account IS NOT NULL", (self.transaction_id(),))
		credits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND credit_account IS NOT NULL", (self.transaction_id(),))
		return debits, credits

	def high_water(self):
		return self.one("SELECT COALESCE(MAX(id), 0) FROM gl_transactions")

	# what the close corrects

	def test_an_overage_adds_stock_and_debits_inventory(self):
		self.stock(self.product_id, 5)
		self.count(self.product_id, 8)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		qty_in, qty_out, price, reason = self.correction(self.product_id)[0:4]
		self.assertEqual((qty_in, qty_out), (3, 0))
		self.assertEqual(reason, 'Inventory count')
		debit, credit, amount = self.correction(self.product_id)[5:8]
		self.assertEqual(debit, INVENTORY_ACCOUNT)
		self.assertEqual(credit, EXPENSE_ACCOUNT)
		self.assertEqual(amount, Decimal('7.50'))
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 8)

	def test_a_shortage_removes_stock_and_debits_expense(self):
		self.stock(self.product_id, 5)
		self.count(self.product_id, 2)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		qty_in, qty_out = self.correction(self.product_id)[0:2]
		self.assertEqual((qty_in, qty_out), (0, 3))
		debit, credit, amount = self.correction(self.product_id)[5:8]
		self.assertEqual(debit, EXPENSE_ACCOUNT)
		self.assertEqual(credit, INVENTORY_ACCOUNT)
		self.assertEqual(amount, Decimal('7.50'))
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 2)

	def test_a_count_that_agrees_writes_nothing(self):
		self.stock(self.product_id, 5)
		self.count(self.product_id, 5)
		self.DB.commit()
		before = self.high_water()
		self.assertEqual(self.close(), 0)
		self.assertEqual(self.corrections(), 0)
		self.assertEqual(self.high_water(), before) # no empty transaction
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 5)

	def test_counting_zero_writes_the_whole_stock_off(self):
		'''inventory_compare seeds rows at zero to say the shelf is empty'''
		self.stock(self.product_id, 4)
		self.count(self.product_id, 0)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		self.assertEqual(self.correction(self.product_id)[0:2], (0, 4))
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 0)

	def test_an_uncounted_product_is_left_alone(self):
		other = self.products[1]
		self.stock(self.product_id, 5)
		self.stock(other, 7)
		self.count(self.product_id, 8)
		self.DB.commit()
		self.close()
		self.assertEqual(self.on_hand(other, self.location_id), 7)
		self.assertEqual(self.corrections(), 1)

	def test_the_variance_is_against_the_summary_location(self):
		elsewhere = self.new_location('Somewhere else')
		self.stock(self.product_id, 3, elsewhere)
		self.count(self.product_id, 2)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		self.assertEqual(self.correction(self.product_id)[0:2], (2, 0))
		self.assertEqual(self.correction(self.product_id)[4], self.location_id)
		self.assertEqual(self.on_hand(self.product_id, elsewhere), 3)
		self.assertEqual(self.on_hand(self.product_id), 5)

	def test_a_fractional_count_is_truncated(self):
		self.count(self.product_id, '2.5')
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		self.assertEqual(self.correction(self.product_id)[0:2], (2, 0))

	# products the close cannot correct

	def test_an_untracked_product_gets_opening_stock(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.count(self.product_id, 6)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		self.assertEqual(self.correction(self.product_id)[0:2], (6, 0))
		self.assertEqual(self.correction(self.product_id)[5], INVENTORY_ACCOUNT)
		self.assertTrue(self.one("SELECT inventory_enabled FROM products "
									"WHERE id = %s", (self.product_id,)))

	def test_an_untracked_product_without_an_account_is_skipped(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"inventory_account = NULL WHERE id = %s",
							(self.product_id,))
		self.count(self.product_id, 6)
		self.DB.commit()
		message = self.inventorying.uncorrectable_count_message(self.summary_id)
		self.assertIn('no inventory account', message)
		self.assertEqual(self.close(), 0)
		self.assertEqual(self.corrections(), 0)
		self.assertFalse(self.one("SELECT inventory_enabled FROM products "
									"WHERE id = %s", (self.product_id,)))

	def test_an_untracked_non_stock_product_is_skipped(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"stock = False WHERE id = %s", (self.product_id,))
		self.count(self.product_id, 6)
		self.DB.commit()
		message = self.inventorying.uncorrectable_count_message(self.summary_id)
		self.assertIn('not a stocked product', message)
		self.assertEqual(self.close(), 0)
		self.assertFalse(self.one("SELECT inventory_enabled FROM products "
									"WHERE id = %s", (self.product_id,)))

	def test_a_tracked_non_stock_product_is_still_corrected(self):
		'''its stock is already real, so the count is the authority on it'''
		self.cursor.execute("UPDATE products SET stock = False WHERE id = %s",
							(self.product_id,))
		self.stock(self.product_id, 1)
		self.count(self.product_id, 4)
		self.DB.commit()
		self.assertIsNone(
			self.inventorying.uncorrectable_count_message(self.summary_id))
		self.assertEqual(self.close(), 1)
		self.assertEqual(self.correction(self.product_id)[0:2], (3, 0))

	def test_a_skipped_product_still_counts_toward_the_totals(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"inventory_account = NULL WHERE id = %s",
							(self.product_id,))
		self.count(self.product_id, 6)
		self.DB.commit()
		self.close()
		self.assertEqual(self.one("SELECT total_cost FROM "
									"inventory.count_summaries WHERE id = %s",
									(self.summary_id,)), Decimal('15.00'))

	# the summary itself

	def test_the_close_sets_the_summary_fields(self):
		self.count(self.products[0], 3, cost = '2.00', retail = '5.00')
		self.count(self.products[1], 2, cost = '1.50', retail = '4.00')
		self.DB.commit()
		self.close()
		self.cursor.execute("SELECT active, date_ended, total_cost, total_retail "
							"FROM inventory.count_summaries WHERE id = %s",
							(self.summary_id,))
		active, date_ended, total_cost, total_retail = self.cursor.fetchone()
		self.assertFalse(active)
		self.assertEqual(date_ended, self.one("SELECT CURRENT_DATE"))
		self.assertEqual(total_cost, Decimal('9.00'))  # 3*2.00 + 2*1.50
		self.assertEqual(total_retail, Decimal('23.00')) # 3*5.00 + 2*4.00

	def test_an_empty_count_closes_without_a_ledger_entry(self):
		self.DB.commit()
		before = self.high_water()
		self.assertEqual(self.close(), 0)
		self.assertFalse(self.one("SELECT active FROM inventory.count_summaries "
									"WHERE id = %s", (self.summary_id,)))
		self.assertEqual(self.one("SELECT total_cost FROM "
									"inventory.count_summaries WHERE id = %s",
									(self.summary_id,)), Decimal('0.00'))
		self.assertEqual(self.high_water(), before)

	def test_a_summary_with_no_location_refuses_to_close(self):
		self.cursor.execute("ALTER TABLE inventory.count_summaries "
							"ALTER COLUMN location_id DROP NOT NULL")
		self.cursor.execute("UPDATE inventory.count_summaries "
							"SET location_id = NULL WHERE id = %s",
							(self.summary_id,))
		self.count(self.product_id, 6)
		self.DB.commit()
		self.assertRaises(ValueError, self.close)
		self.assertTrue(self.one("SELECT active FROM inventory.count_summaries "
									"WHERE id = %s", (self.summary_id,)))
		self.assertEqual(self.corrections(), 0)

	def test_closing_twice_corrects_once(self):
		self.stock(self.product_id, 5)
		self.count(self.product_id, 8)
		self.DB.commit()
		self.assertEqual(self.close(), 1)
		transaction_id = self.transaction_id()
		total = self.one("SELECT SUM(amount) FROM gl_entries "
							"WHERE gl_transaction_id = %s", (transaction_id,))
		after = self.high_water()
		self.assertEqual(self.close(), 0)
		self.assertEqual(self.corrections(), 1)
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 8)
		self.assertEqual(self.one("SELECT SUM(amount) FROM gl_entries "
									"WHERE gl_transaction_id = %s",
									(transaction_id,)), total)
		self.assertEqual(self.high_water(), after) # no second transaction

	# the ledger

	def test_every_correction_carries_its_own_entry(self):
		self.stock(self.products[0], 5)
		self.stock(self.products[1], 9)
		self.count(self.products[0], 8)
		self.count(self.products[1], 4)
		self.DB.commit()
		self.assertEqual(self.close(), 2)
		self.assertEqual(self.one("SELECT count(*) FROM inventory_transactions "
									"WHERE count_summary_id = %s "
									"AND gl_entries_id IS NULL",
									(self.summary_id,)), 0)

	def test_one_transaction_for_the_whole_close(self):
		self.stock(self.products[0], 5)
		self.stock(self.products[1], 9)
		self.count(self.products[0], 8)
		self.count(self.products[1], 4)
		self.DB.commit()
		self.close()
		self.assertEqual(self.one("SELECT count(DISTINCT ge.gl_transaction_id) "
									"FROM gl_entries AS ge "
									"JOIN inventory_transactions AS it "
										"ON it.gl_entries_id = ge.id "
									"WHERE it.count_summary_id = %s",
									(self.summary_id,)), 1)

	def test_the_close_balances(self):
		self.stock(self.products[0], 5)
		self.stock(self.products[1], 9)
		self.count(self.products[0], 8) # an overage
		self.count(self.products[1], 4) # and a shortage
		self.DB.commit()
		self.close()
		debits, credits = self.sides()
		self.assertEqual(debits, credits)
		self.assertNotEqual(debits, 0)

	def test_each_entry_values_the_row_it_hangs_on(self):
		self.stock(self.products[0], 5)
		self.stock(self.products[1], 9)
		self.count(self.products[0], 8)
		self.count(self.products[1], 4)
		self.DB.commit()
		self.close()
		self.assertEqual(self.one("SELECT count(*) FROM inventory_transactions AS it "
									"JOIN gl_entries AS ge ON ge.id = it.gl_entries_id "
									"WHERE it.count_summary_id = %s AND ge.amount "
									"<> ROUND((it.qty_in + it.qty_out) * it.price, 2)",
									(self.summary_id,)), 0)

	def test_the_correction_is_valued_at_the_counted_cost(self):
		'''editing a cost afterwards must not restate a closed count'''
		self.stock(self.product_id, 1)
		self.count(self.product_id, 3, cost = '2.00')
		self.cursor.execute("UPDATE products SET cost = 99.00 WHERE id = %s",
							(self.product_id,))
		self.DB.commit()
		self.close()
		price, amount = (self.correction(self.product_id)[2],
							self.correction(self.product_id)[7])
		self.assertEqual(price, Decimal('2.000000'))
		self.assertEqual(amount, Decimal('4.00')) # 2 units at the counted cost

	def test_the_entry_names_the_count(self):
		self.stock(self.product_id, 1)
		self.count(self.product_id, 3)
		self.DB.commit()
		self.close()
		self.assertEqual(self.correction(self.product_id)[8],
							'Inventory count: close unit test')

if __name__ == '__main__':
	unittest.main()
