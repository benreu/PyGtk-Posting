import unittest
from harness import DBTestCase

class StockReturnTest(DBTestCase):
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.product_id = 19
		self.location_id = self.new_location()
		self.other_location_id = self.new_location('other')
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True, cost = 3 WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("DELETE FROM inventory_transactions WHERE product_id = %s",
							(self.product_id,))
		customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (customer_id,))
		self.line_id = self.invoice_line(10)
		self.add_stock(10)
		self.inventorying.sell(
			[[self.line_id, '4.00', self.product_id, '', '', '', '5.00']],
			self.location_id, customer_id, '2026-01-01')
		self.credit_memo_id = self.one("INSERT INTO credit_memos "
										"(customer_id, date_created) "
										"VALUES (%s, CURRENT_DATE) RETURNING id",
										(customer_id,))

	def invoice_line(self, qty):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id) "
						"VALUES (%s, %s, %s, %s) RETURNING id",
						(self.invoice_id, qty, self.product_id, self.tax_rate_id))

	def add_stock(self, qty):
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
							(self.product_id, qty, self.other_location_id))

	def credit_item(self, qty, deleted = False):
		self.cursor.execute("INSERT INTO credit_memo_items "
							"(credit_memo_id, qty, invoice_item_id, price, "
							"date_returned, tax, deleted) "
							"VALUES (%s, %s, %s, 5, CURRENT_DATE, 0, %s)",
							(self.credit_memo_id, qty, self.line_id, deleted))

	def test_sale_reduced_stock(self):
		self.assertEqual(self.on_hand(self.product_id), 6)

	def test_cancel_puts_stock_back(self):
		self.inventorying.unsell(self.invoice_id)
		self.assertEqual(self.on_hand(self.product_id), 10)

	def test_cancel_leaves_other_invoices_alone(self):
		customer_id = self.one("SELECT customer_id FROM invoices WHERE id = %s",
								(self.invoice_id,))
		other_invoice = self.one("INSERT INTO invoices (customer_id) "
								"VALUES (%s) RETURNING id", (customer_id,))
		other_line = self.one("INSERT INTO invoice_items "
							"(invoice_id, qty, product_id, tax_rate_id) "
							"VALUES (%s, 1, %s, %s) RETURNING id",
							(other_invoice, self.product_id, self.tax_rate_id))
		self.inventorying.sell(
			[[other_line, '1.00', self.product_id, '', '', '', '5.00']],
			self.location_id, customer_id, '2026-01-01')
		self.inventorying.unsell(self.invoice_id)
		self.assertEqual(self.on_hand(self.product_id), 9)

	def test_credit_memo_restocks_to_the_sale_location(self):
		self.credit_item(3)
		self.inventorying.restock(self.credit_memo_id)
		self.assertEqual(self.on_hand(self.product_id), 9)
		self.assertEqual(self.one("SELECT location_id FROM inventory_transactions "
								"WHERE reason = 'Credit memo returned'"),
						self.location_id)

	def test_deleted_credit_rows_are_not_restocked(self):
		self.credit_item(3, deleted = True)
		self.inventorying.restock(self.credit_memo_id)
		self.assertEqual(self.on_hand(self.product_id), 6)

	def test_sale_that_never_reached_the_ledger_is_not_restocked(self):
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE invoice_line_id = %s", (self.line_id,))
		self.credit_item(3)
		self.inventorying.restock(self.credit_memo_id)
		self.assertEqual(self.on_hand(self.product_id), 10)

if __name__ == '__main__':
	unittest.main()
