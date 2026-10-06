import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
COGS_ACCOUNT = 3876

class CreditMemoCogsTest(DBTestCase):
	'''a return is the sale run backwards: it reverses revenue and puts the cost
	of the goods back on the inventory account'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		from db import transactor
		self.inventorying = inventorying
		self.transactor = transactor
		self.product_id = 19
		self.location_id = self.new_location()
		self.cursor.execute("UPDATE products SET cost = 3, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, COGS_ACCOUNT, self.product_id))
		self.revenue_account = self.one("SELECT revenue_account FROM products "
										"WHERE id = %s", (self.product_id,))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id = %s", (self.product_id,))
		self.customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (self.customer_id,))
		self.line_id = self.one("INSERT INTO invoice_items "
								"(invoice_id, qty, product_id, tax_rate_id, price) "
								"VALUES (%s, 4, %s, %s, 5) RETURNING id",
								(self.invoice_id, self.product_id, self.tax_rate_id))
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, 10, 3, %s, CURRENT_DATE, 'test')",
							(self.product_id, self.location_id))
		self.inventorying.sell(
			[[self.line_id, '4.00', self.product_id, '', '', '', '5.00']],
			self.location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.credit_memo_id = self.one("INSERT INTO credit_memos "
										"(customer_id, date_created, amount_owed, tax) "
										"VALUES (%s, CURRENT_DATE, 10, 0) RETURNING id",
										(self.customer_id,))
		self.DB.commit()

	def credit_item(self, qty, deleted = False):
		return self.one("INSERT INTO credit_memo_items "
						"(credit_memo_id, qty, invoice_item_id, price, "
						"date_returned, tax, deleted, ext_price) "
						"VALUES (%s, %s, %s, 5, CURRENT_DATE, 0, %s, %s) "
						"RETURNING id",
						(self.credit_memo_id, qty, self.line_id, deleted,
						qty * 5))

	def post(self):
		'''the order credit_memo.py uses: stock back first, then the ledger'''
		self.inventorying.restock(self.credit_memo_id)
		self.transactor.post_credit_memo(self.credit_memo_id)

	def transaction_id(self):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"JOIN credit_memos AS cm ON cm.gl_entries_id = ge.id "
						"WHERE cm.id = %s", (self.credit_memo_id,))

	def net(self, account):
		return self.one("SELECT COALESCE(SUM(CASE WHEN debit_account = %s "
								"THEN amount ELSE 0 END), 0) "
							"- COALESCE(SUM(CASE WHEN credit_account = %s "
								"THEN amount ELSE 0 END), 0) "
						"FROM gl_entries WHERE gl_transaction_id = %s",
						(account, account, self.transaction_id()))

	def test_the_return_debits_revenue_not_the_cost_account(self):
		# a return reverses the sale, so the retail amount comes off revenue;
		# debiting the expense account would charge retail to cost of goods sold
		self.credit_item(2)
		self.post()
		self.assertEqual(self.net(self.revenue_account), Decimal('10.00'))

	def test_the_cost_goes_back_on_inventory(self):
		self.credit_item(2)
		self.post()
		self.assertEqual(self.net(INVENTORY_ACCOUNT), Decimal('6.00')) # 2 at 3
		self.assertEqual(self.net(COGS_ACCOUNT), Decimal('-6.00'))

	def test_stock_comes_back_at_the_cost_it_left_at(self):
		self.cursor.execute("UPDATE products SET cost = 50 WHERE id = %s",
							(self.product_id,))
		self.credit_item(2)
		self.post()
		# valuing the return at today's cost would leave the inventory account
		# holding more than the sale ever took off it
		self.assertEqual(self.net(INVENTORY_ACCOUNT), Decimal('6.00'))

	def test_a_deleted_credit_row_posts_nothing(self):
		self.credit_item(2, deleted = True)
		self.post()
		self.assertEqual(self.net(INVENTORY_ACCOUNT), 0)
		self.assertEqual(self.on_hand(self.product_id), 6)

	def test_restocking_twice_returns_the_stock_once(self):
		self.credit_item(2)
		self.inventorying.restock(self.credit_memo_id)
		self.inventorying.restock(self.credit_memo_id)
		self.assertEqual(self.on_hand(self.product_id), 8) # 10 out 4, back 2

	def test_an_untracked_product_posts_no_cost(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.credit_item(2)
		self.post()
		self.assertEqual(self.net(INVENTORY_ACCOUNT), 0)
		self.assertEqual(self.net(self.revenue_account), Decimal('10.00'))

if __name__ == '__main__':
	unittest.main()
