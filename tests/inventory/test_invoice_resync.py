import unittest
from decimal import Decimal
from harness import DBTestCase

class InvoiceResyncTest(DBTestCase):
	'''a posted invoice can still be edited, so the ledger has to follow'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.product_id = 19
		self.other_product_id = 962
		self.location_id = self.new_location()
		self.other_location_id = self.new_location('other')
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True, cost = 3 "
							"WHERE id IN (%s, %s)",
							(self.product_id, self.other_product_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id IN (%s, %s)",
							(self.product_id, self.other_product_id))
		self.customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.invoice_id = self.new_invoice()
		# the sale matches the line, so a resync only follows what a test changes
		self.line_id = self.invoice_line(4)
		self.add_stock(self.product_id, 10)
		self.add_stock(self.other_product_id, 10)
		self.inventorying.sell(
			[[self.line_id, '4.00', self.product_id, '', '', '', '5.00']],
			self.location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit() # the application rolls back after reading

	def new_invoice(self):
		return self.one("INSERT INTO invoices (customer_id) "
						"VALUES (%s) RETURNING id", (self.customer_id,))

	def invoice_line(self, qty, invoice_id = None, product_id = None):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id, price) "
						"VALUES (%s, %s, %s, %s, 5) RETURNING id",
						(invoice_id or self.invoice_id, qty,
						product_id or self.product_id, self.tax_rate_id))

	def add_stock(self, product_id, qty):
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
							(product_id, qty, self.other_location_id))

	def resync(self, location_id = None, date = None):
		self.inventorying.resync_invoice_inventory (self.invoice_id,
													location_id, date)

	def ledger_rows(self, invoice_id = None):
		self.cursor.execute("SELECT it.invoice_line_id, it.product_id, "
								"it.qty_out, it.location_id, it.price, "
								"it.date_inserted "
							"FROM inventory_transactions AS it "
							"JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
							"WHERE ii.invoice_id = %s ORDER BY it.id",
							(invoice_id or self.invoice_id,))
		return self.cursor.fetchall()

	def on_hand_at(self, product_id, location_id):
		return self.one("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
						"FROM inventory_transactions "
						"WHERE (product_id, location_id) = (%s, %s)",
						(product_id, location_id))

	def set_qty(self, qty, line_id = None):
		self.cursor.execute("UPDATE invoice_items SET qty = %s WHERE id = %s",
							(qty, line_id or self.line_id))

	# ---------------- the gate ----------------

	def test_a_draft_invoice_is_left_alone(self):
		self.cursor.execute("UPDATE invoices SET posted = False WHERE id = %s",
							(self.invoice_id,))
		self.set_qty(6)
		self.invoice_line(3) # a line sell () has never seen
		self.resync()
		self.assertEqual(self.ledger_rows(),
						[(self.line_id, self.product_id, 4,
							self.location_id, Decimal('5.000000'),
							self.date('2026-01-01'))])

	def test_an_invoice_that_does_not_exist_is_a_no_op(self):
		self.inventorying.resync_invoice_inventory (0)
		self.assertEqual(len(self.ledger_rows()), 1)

	def date(self, text):
		return self.one("SELECT %s::date", (text,))

	# ---------------- an edit follows into the ledger ----------------

	def test_quantity_change_follows_into_the_ledger(self):
		self.set_qty(6)
		self.resync()
		rows = self.ledger_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][2], 6)
		self.assertEqual(self.on_hand(self.product_id), 4)

	def test_price_change_follows_into_the_ledger(self):
		self.cursor.execute("UPDATE invoice_items SET price = 7.25 "
							"WHERE id = %s", (self.line_id,))
		self.resync()
		self.assertEqual(self.ledger_rows()[0][4], Decimal('7.250000'))

	def test_product_change_follows_into_the_ledger(self):
		self.cursor.execute("UPDATE invoice_items SET product_id = %s "
							"WHERE id = %s",
							(self.other_product_id, self.line_id))
		self.resync()
		self.assertEqual(len(self.ledger_rows()), 1)
		self.assertEqual(self.on_hand(self.product_id), 10)
		self.assertEqual(self.on_hand(self.other_product_id), 6)

	def test_a_canceled_line_releases_its_stock(self):
		# delete_line_item_activated soft deletes, so CASCADE never fires
		self.cursor.execute("UPDATE invoice_items SET (qty, canceled) = "
							"(0, True) WHERE id = %s", (self.line_id,))
		self.resync()
		self.assertEqual(self.ledger_rows(), [])
		self.assertEqual(self.on_hand(self.product_id), 10)

	def test_a_line_added_after_posting_takes_its_stock(self):
		line_id = self.invoice_line(3)
		self.resync()
		rows = self.ledger_rows()
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[1][0], line_id)
		self.assertEqual(rows[1][2], 3)
		self.assertEqual(self.on_hand(self.product_id), 3)

	# ---------------- idempotence ----------------

	def test_resync_twice_does_not_double_count(self):
		self.set_qty(6)
		self.invoice_line(3)
		self.resync()
		self.resync()
		self.assertEqual(len(self.ledger_rows()), 2)
		self.assertEqual(self.on_hand(self.product_id), 1)

	def test_sell_twice_does_not_double_count(self):
		self.inventorying.sell(
			[[self.line_id, '6.00', self.product_id, '', '', '', '5.00']],
			self.location_id, self.customer_id, '2026-01-01')
		rows = self.ledger_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][2], 6)

	# ---------------- tracking turned off and back on ----------------

	def test_a_product_no_longer_tracked_loses_its_ledger_row(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.resync()
		self.assertEqual(self.ledger_rows(), [])

	def test_tracking_turned_back_on_gets_a_new_ledger_row(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.resync()
		self.cursor.execute("UPDATE products SET inventory_enabled = True "
							"WHERE id = %s", (self.product_id,))
		self.resync()
		rows = self.ledger_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][2], 4) # the line's own quantity

	def test_a_fractional_quantity_is_truncated_not_rounded(self):
		self.set_qty(Decimal('5.60'))
		self.resync()
		self.assertEqual(self.ledger_rows()[0][2], 5)

	# ---------------- location ----------------

	def test_location_change_moves_the_stock(self):
		self.resync(self.other_location_id)
		self.assertEqual(self.on_hand_at(self.product_id, self.location_id), 0)
		self.assertEqual(self.on_hand_at(self.product_id,
											self.other_location_id), 6)

	def test_a_null_location_leaves_the_rows_where_they_are(self):
		self.set_qty(6)
		self.resync()
		self.assertEqual(self.ledger_rows()[0][3], self.location_id)

	def test_a_new_line_with_no_location_given_follows_its_siblings(self):
		self.invoice_line(3)
		self.resync()
		self.assertEqual(self.ledger_rows()[1][3], self.location_id)

	# ---------------- dates ----------------

	def test_a_rewritten_row_keeps_its_ledger_date(self):
		self.set_qty(6)
		self.resync()
		# an edit must not move a posted sale into another month
		self.assertEqual(self.ledger_rows()[0][5], self.date('2026-01-01'))

	def test_a_line_added_after_posting_takes_the_invoice_date(self):
		self.cursor.execute("UPDATE invoices SET dated_for = '2026-02-03' "
							"WHERE id = %s", (self.invoice_id,))
		self.invoice_line(3)
		self.resync()
		self.assertEqual(self.ledger_rows()[1][5], self.date('2026-02-03'))

	# ---------------- isolation ----------------

	def test_other_invoices_rows_are_left_alone(self):
		other_invoice_id = self.new_invoice()
		other_line_id = self.invoice_line(2, invoice_id = other_invoice_id)
		self.inventorying.sell(
			[[other_line_id, '2.00', self.product_id, '', '', '', '5.00']],
			self.other_location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(other_invoice_id,))
		self.set_qty(6)
		self.resync()
		self.assertEqual(self.ledger_rows(other_invoice_id),
						[(other_line_id, self.product_id, 2,
							self.other_location_id, Decimal('5.000000'),
							self.date('2026-01-01'))])


class ResyncNegativeStockTest(InvoiceResyncTest):
	'''negative_stock_message is only right once the resync has committed'''

	def test_a_canceled_line_is_not_counted_as_stock_taken(self):
		self.cursor.execute("UPDATE invoice_items SET (qty, canceled) = "
							"(0, True) WHERE id = %s", (self.line_id,))
		self.resync()
		# the line is gone from the store too, so it cannot be excluded by id
		self.assertEqual(self.inventorying.negative_stock_message (
							[], self.location_id), None)

	def test_the_resynced_quantity_is_not_counted_twice(self):
		self.set_qty(8)
		self.resync(self.other_location_id)
		store = [[self.line_id, '8.00', self.product_id, '', '', '', '5.00']]
		self.assertEqual(self.inventorying.negative_stock_message (
							store, self.other_location_id), None)

	def test_a_product_no_longer_tracked_never_warns(self):
		self.set_qty(500)
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.resync()
		store = [[self.line_id, '500.00', self.product_id, '', '', '', '5.00']]
		self.assertEqual(self.inventorying.negative_stock_message (
							store, self.location_id), None)


if __name__ == '__main__':
	unittest.main()
