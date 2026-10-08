import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
COMPONENT_ACCOUNT = 1762
EXPENSE_ACCOUNT = 3876

class ManufactureGlTest(DBTestCase):
	'''a build moves value between inventory accounts, it does not spend it, so
	the only thing that may reach the profit and loss is the variance between
	what the components were carried at and what the built product is carried at'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.cursor.execute("SELECT mp.id, mp.product_id, mp.qty "
							"FROM manufacturing_projects AS mp "
							"WHERE (SELECT count(*) FROM manufacturing_items "
							"WHERE manufacturing_project_id = mp.id AND qty > 0) >= 2 "
							"AND mp.qty > 0 LIMIT 1")
		self.project_id, self.product_id, self.project_qty = self.cursor.fetchone()
		# the built product and its components sit on different accounts, so the
		# transfer is visible rather than netting out on one account
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, inventory_enabled = True "
							"WHERE id IN (SELECT product_id FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s)",
							(COMPONENT_ACCOUNT, EXPENSE_ACCOUNT, self.project_id))
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, inventory_enabled = True "
							"WHERE id = %s",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.product_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE manufacturing_id = %s", (self.project_id,))
		self.DB.commit()

	def transaction_id(self):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"WHERE ge.id = (SELECT gl_entries_id "
							"FROM inventory_transactions "
							"WHERE manufacturing_id = %s "
							"AND gl_entries_id IS NOT NULL ORDER BY id LIMIT 1)",
						(self.project_id,))

	def net(self, account):
		return self.one("SELECT COALESCE(SUM(CASE WHEN debit_account = %s "
								"THEN amount ELSE 0 END), 0) "
							"- COALESCE(SUM(CASE WHEN credit_account = %s "
								"THEN amount ELSE 0 END), 0) "
						"FROM gl_entries WHERE gl_transaction_id = %s",
						(account, account, self.transaction_id()))

	def sides(self):
		debits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND debit_account IS NOT NULL",
							(self.transaction_id(),))
		credits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND credit_account IS NOT NULL",
							(self.transaction_id(),))
		return debits, credits

	def expected(self):
		'''what the stock rows say the two sides come to'''
		return self.one("SELECT COALESCE(SUM(ROUND(qty_in * price, 2)), 0) "
						"FROM inventory_transactions WHERE manufacturing_id = %s",
						(self.project_id,)), \
				self.one("SELECT COALESCE(SUM(ROUND(qty_out * price, 2)), 0) "
						"FROM inventory_transactions WHERE manufacturing_id = %s",
						(self.project_id,))

	def test_the_build_balances(self):
		self.inventorying.manufacture(self.project_id)
		debits, credits = self.sides()
		self.assertEqual(debits, credits)

	def test_value_moves_from_components_to_the_finished_product(self):
		self.inventorying.manufacture(self.project_id)
		finished, components = self.expected()
		self.assertEqual(self.net(INVENTORY_ACCOUNT), finished)
		self.assertEqual(self.net(COMPONENT_ACCOUNT), -components)

	def test_each_entry_values_the_stock_row_it_hangs_on(self):
		self.inventorying.manufacture(self.project_id)
		mismatched = self.one("SELECT count(*) FROM inventory_transactions AS it "
								"JOIN gl_entries AS ge ON ge.id = it.gl_entries_id "
								"WHERE it.manufacturing_id = %s "
								"AND ge.amount <> ROUND((it.qty_in + it.qty_out) "
													"* it.price, 2)",
								(self.project_id,))
		self.assertEqual(mismatched, 0)

	def test_the_variance_is_the_difference_between_the_two_sides(self):
		self.inventorying.manufacture(self.project_id)
		finished, components = self.expected()
		variance = self.one("SELECT COALESCE(SUM(CASE WHEN debit_account IS NOT NULL "
									"THEN amount ELSE -amount END), 0) "
							"FROM gl_entries "
							"WHERE transaction_description = 'Manufacturing variance' "
							"AND gl_transaction_id = %s", (self.transaction_id(),))
		self.assertEqual(variance, components - finished)

	def test_posting_twice_does_not_double_the_value(self):
		self.inventorying.manufacture(self.project_id)
		first = self.net(INVENTORY_ACCOUNT)
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.net(INVENTORY_ACCOUNT), first)
		debits, credits = self.sides()
		self.assertEqual(debits, credits)

	# ---------------- one transaction per project ----------------

	def test_a_rebuild_keeps_the_one_transaction(self):
		# the earlier transaction cannot be found once the stock rows that point
		# at it are dropped, so a rebuild used to start a fresh one and leave the
		# old one behind zeroed, with nothing reaching it ever again
		high_water = self.one("SELECT COALESCE(MAX(id), 0) FROM gl_transactions")
		self.inventorying.manufacture(self.project_id)
		first = self.transaction_id()
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.transaction_id(), first)
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_transactions "
									"WHERE id > %s", (high_water,)), 1)

	def test_a_rebuild_writes_no_entry_outside_that_transaction(self):
		high_water = self.one("SELECT COALESCE(MAX(id), 0) FROM gl_entries")
		self.inventorying.manufacture(self.project_id)
		self.inventorying.manufacture(self.project_id)
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_entries "
									"WHERE id > %s AND gl_transaction_id <> %s",
									(high_water, self.transaction_id())), 0)
		debits, credits = self.sides()
		self.assertEqual(debits, credits)

	def test_a_rebuild_moves_the_transaction_to_the_new_build(self):
		self.inventorying.manufacture(self.project_id)
		transaction_id = self.transaction_id()
		# as though the first build had been posted in another period
		self.cursor.execute("UPDATE gl_transactions SET date_inserted = "
							"'2026-01-05' WHERE id = %s", (transaction_id,))
		self.cursor.execute("UPDATE gl_entries SET date_inserted = '2026-01-05' "
							"WHERE gl_transaction_id = %s", (transaction_id,))
		self.inventorying.manufacture(self.project_id)
		# the rebuild re-dates the stock rows, so the ledger follows them rather
		# than leaving new entries inside a transaction dated the first build
		self.assertEqual(self.one("SELECT date_inserted FROM gl_transactions "
									"WHERE id = %s", (transaction_id,)),
						self.one("SELECT CURRENT_DATE"))
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_entries "
									"WHERE gl_transaction_id = %s "
									"AND date_inserted <> CURRENT_DATE",
									(transaction_id,)), 0)
		self.assertEqual(self.one("SELECT COUNT(*) FROM inventory_transactions "
									"WHERE manufacturing_id = %s "
									"AND date_inserted <> CURRENT_DATE",
									(self.project_id,)), 0)

	def test_a_rebuild_zeroes_the_variance_of_the_one_before(self):
		self.inventorying.manufacture(self.project_id)
		first = self.net(EXPENSE_ACCOUNT)
		self.inventorying.manufacture(self.project_id)
		# the whole transaction is zeroed now, so the variance goes with it
		# rather than being singled out by its description. Left live inside the
		# transaction the build is now rewriting, it would be counted twice
		self.assertEqual(self.net(EXPENSE_ACCOUNT), first)
		debits, credits = self.sides()
		self.assertEqual(debits, credits)

	def test_an_untracked_component_posts_no_value(self):
		product_id = self.one("SELECT product_id FROM manufacturing_items "
								"WHERE manufacturing_project_id = %s AND qty > 0 "
								"AND product_id <> %s ORDER BY product_id LIMIT 1",
								(self.project_id, self.product_id))
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (product_id,))
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.one("SELECT count(*) FROM inventory_transactions "
									"WHERE manufacturing_id = %s AND product_id = %s",
									(self.project_id, product_id)), 0)
		debits, credits = self.sides()
		self.assertEqual(debits, credits)

if __name__ == '__main__':
	unittest.main()
