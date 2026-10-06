import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
COGS_ACCOUNT = 3876

class CogsTest(DBTestCase):
	'''a sale of a tracked product relieves inventory at cost, in the invoice's
	own transaction, so the profit and loss carries the cost of the sale'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		from db import transactor
		self.inventorying = inventorying
		self.transactor = transactor
		self.product_id = 19
		self.untracked_id = 962
		self.location_id = self.new_location()
		self.cursor.execute("UPDATE products SET cost = 3, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, COGS_ACCOUNT, self.product_id))
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"cost = 3 WHERE id = %s", (self.untracked_id,))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id IN (%s, %s)",
							(self.product_id, self.untracked_id))
		self.customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (self.customer_id,))
		self.line_id = self.invoice_line(4)
		self.add_stock(self.product_id, 10)
		self.DB.commit()

	def invoice_line(self, qty, product_id = None):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id, price) "
						"VALUES (%s, %s, %s, %s, 5) RETURNING id",
						(self.invoice_id, qty,
						product_id or self.product_id, self.tax_rate_id))

	def add_stock(self, product_id, qty):
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 3, %s, CURRENT_DATE, 'test')",
							(product_id, qty, self.location_id))

	def store(self, rows = None):
		return rows or [[self.line_id, '4.00', self.product_id,
						'', '', '', '5.00']]

	def total(self):
		return self.one("SELECT COALESCE(SUM(ext_price + tax), 0) "
						"FROM invoice_items "
						"WHERE (invoice_id, canceled) = (%s, False)",
						(self.invoice_id,))

	def post(self, rows = None, gl_entries_id = None):
		'''what invoice_window does: stock first, then the ledger'''
		self.inventorying.sell(self.store(rows), self.location_id,
								self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		total = self.total()
		self.transactor.post_invoice_accounts('2026-01-01', self.invoice_id,
												total, gl_entries_id)
		return total

	def transaction_id(self):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"JOIN invoices AS i ON i.gl_entries_id = ge.id "
						"WHERE i.id = %s", (self.invoice_id,))

	def cogs_rows(self):
		self.cursor.execute("SELECT ge.amount, ge.debit_account, "
								"ge.credit_account, ge.gl_transaction_id, "
								"ge.date_inserted "
							"FROM inventory_transactions AS it "
							"JOIN gl_entries AS ge ON ge.id = it.gl_entries_id "
							"JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
							"WHERE ii.invoice_id = %s ORDER BY it.id",
							(self.invoice_id,))
		return self.cursor.fetchall()

	def net(self, account):
		'''debits less credits on an account across the invoice's transaction'''
		return self.one("SELECT COALESCE(SUM(CASE WHEN debit_account = %s "
								"THEN amount ELSE 0 END), 0) "
							"- COALESCE(SUM(CASE WHEN credit_account = %s "
								"THEN amount ELSE 0 END), 0) "
						"FROM gl_entries WHERE gl_transaction_id = %s",
						(account, account, self.transaction_id()))

	def assertBalances(self):
		debits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND debit_account IS NOT NULL",
							(self.transaction_id(),))
		credits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND credit_account IS NOT NULL",
							(self.transaction_id(),))
		self.assertEqual(debits, credits)

	def test_a_sale_relieves_inventory_at_cost(self):
		self.post()
		rows = self.cogs_rows()
		self.assertEqual(len(rows), 1)
		amount, debit, credit, transaction_id, date = rows[0]
		self.assertEqual(amount, Decimal('12.00')) # 4 at a cost of 3
		self.assertEqual(debit, COGS_ACCOUNT)
		self.assertEqual(credit, INVENTORY_ACCOUNT)
		self.assertEqual(transaction_id, self.transaction_id())
		self.assertBalances()

	def test_the_entry_is_dated_with_the_invoice(self):
		# gl_entries.date_inserted defaults to today, so an entry that does not
		# pass the date lands in whatever fiscal year the posting happens in
		self.post()
		self.assertEqual(str(self.cogs_rows()[0][4]), '2026-01-01')

	def test_an_untracked_product_posts_no_cost(self):
		line_id = self.invoice_line(2, self.untracked_id)
		self.post(rows = [[self.line_id, '4.00', self.product_id,
							'', '', '', '5.00'],
							[line_id, '2.00', self.untracked_id,
							'', '', '', '5.00']])
		self.assertEqual(len(self.cogs_rows()), 1) # only the tracked line
		self.assertBalances()

	def test_the_selling_price_does_not_reach_the_ledger(self):
		self.post()
		self.assertNotEqual(self.cogs_rows()[0][0], Decimal('20.00'))

	def test_reposting_rewrites_rather_than_duplicates(self):
		self.post()
		gl_entries_id = self.one("SELECT gl_entries_id FROM invoices "
									"WHERE id = %s", (self.invoice_id,))
		self.cursor.execute("UPDATE invoice_items SET qty = 6 WHERE id = %s",
							(self.line_id,))
		self.post(rows = [[self.line_id, '6.00', self.product_id,
							'', '', '', '5.00']],
					gl_entries_id = gl_entries_id)
		rows = self.cogs_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][0], Decimal('18.00')) # 6 at a cost of 3
		self.assertBalances()

	def test_cost_is_taken_from_the_sale_not_from_the_product_today(self):
		# the cash based path posts the ledger when the invoice is paid, which
		# can be long after the sale, so a later cost change must not restate it
		self.post()
		self.cursor.execute("UPDATE products SET cost = 99 WHERE id = %s",
							(self.product_id,))
		gl_entries_id = self.one("SELECT gl_entries_id FROM invoices "
									"WHERE id = %s", (self.invoice_id,))
		self.transactor.post_invoice_accounts('2026-01-01', self.invoice_id,
												self.total(), gl_entries_id)
		self.assertEqual(self.cogs_rows()[0][0], Decimal('12.00'))

	def test_canceling_the_invoice_nets_the_cost_back_out(self):
		self.post()
		transaction_id = self.transaction_id()
		self.transactor.cancel_invoice('2026-02-01', self.invoice_id)
		self.inventorying.unsell(self.invoice_id)
		self.assertEqual(self.net(COGS_ACCOUNT), 0)
		self.assertEqual(self.net(INVENTORY_ACCOUNT), 0)
		self.assertEqual(self.on_hand(self.product_id), 10)
		self.assertBalances()

	def test_editing_a_posted_quantity_follows_into_the_cost(self):
		self.post()
		self.cursor.execute("UPDATE invoice_items SET qty = 6 WHERE id = %s",
							(self.line_id,))
		self.inventorying.resync_invoice_inventory(self.invoice_id)
		self.assertEqual(self.cogs_rows()[0][0], Decimal('18.00')) # 6 at a cost of 3

	def test_a_canceled_line_zeroes_its_cost(self):
		self.post()
		self.cursor.execute("UPDATE invoice_items SET (qty, canceled) = "
							"(0, True) WHERE id = %s", (self.line_id,))
		self.inventorying.resync_invoice_inventory(self.invoice_id)
		# the sale row is gone, so the entry it carried has to have been zeroed
		self.assertEqual(self.net(COGS_ACCOUNT), 0)
		self.assertEqual(self.net(INVENTORY_ACCOUNT), 0)
		self.assertEqual(self.on_hand(self.product_id), 10)

	# ---------------- editing a posted invoice ----------------

	def test_a_line_added_after_posting_carries_its_own_cost(self):
		self.post()
		added = self.invoice_line(5)
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		rows = self.cogs_rows()
		self.assertEqual(len(rows), 2) # the stock moved, so the cost must too
		amount, debit, credit, transaction_id, _ = rows[1]
		self.assertEqual(amount, Decimal('15.00')) # 5 at a cost of 3
		self.assertEqual(debit, COGS_ACCOUNT)
		self.assertEqual(credit, INVENTORY_ACCOUNT)
		self.assertEqual(transaction_id, self.transaction_id())
		self.assertEqual(self.net(COGS_ACCOUNT), Decimal('27.00'))
		self.assertBalances()

	def test_tracking_turned_off_and_back_on_keeps_one_entry(self):
		self.post()
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		self.assertEqual(self.net(COGS_ACCOUNT), 0) # nothing tracked, no cost
		self.cursor.execute("UPDATE products SET inventory_enabled = True "
							"WHERE id = %s", (self.product_id,))
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		# the row was dropped and remade, so its entry had to be remade with it
		self.assertEqual(len(self.cogs_rows()), 1)
		self.assertEqual(self.net(COGS_ACCOUNT), Decimal('12.00'))
		self.assertBalances()

	def test_an_edit_does_not_restate_the_cost_of_another_line(self):
		other = self.invoice_line(2)
		self.post(rows = [[self.line_id, '4.00', self.product_id,
							'', '', '', '5.00'],
							[other, '2.00', self.product_id,
							'', '', '', '5.00']])
		self.assertEqual(self.net(COGS_ACCOUNT), Decimal('18.00')) # 6 at 3
		self.cursor.execute("UPDATE products SET cost = 99 WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("UPDATE invoice_items SET qty = 3 WHERE id = %s",
							(other,))
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		# only the quantity changed; neither line may be revalued at 99
		self.assertEqual(self.cogs_rows()[0][0], Decimal('12.00'))
		self.assertEqual(self.cogs_rows()[1][0], Decimal('9.00')) # 3 at 3
		self.assertBalances()

	def test_a_product_change_takes_the_new_product_cost(self):
		self.cursor.execute("UPDATE products SET cost = 8, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, COGS_ACCOUNT, self.untracked_id))
		self.post()
		self.cursor.execute("UPDATE invoice_items SET product_id = %s "
							"WHERE id = %s", (self.untracked_id, self.line_id))
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		# a different good was never relieved at the old cost
		self.assertEqual(self.cogs_rows()[0][0], Decimal('32.00')) # 4 at 8
		self.assertBalances()

class CashBasisCogsTest(CogsTest):
	'''under cash basis nothing reaches the ledger until the invoice is paid, and
	the cost has to follow the revenue rather than the stock'''
	def test_posting_alone_writes_no_cost(self):
		self.inventorying.sell(self.store(), self.location_id,
								self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.assertEqual(self.cogs_rows(), [])
		self.assertEqual(self.on_hand(self.product_id), 6) # the stock still moved

	def test_editing_an_unpaid_invoice_moves_stock_and_writes_no_cost(self):
		self.inventorying.sell(self.store(), self.location_id,
								self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.cursor.execute("UPDATE invoice_items SET qty = 6 WHERE id = %s",
							(self.line_id,))
		# there is no transaction to hang a cost entry on until it is paid
		self.inventorying.resync_invoice_inventory(self.invoice_id,
													self.location_id)
		self.assertEqual(self.cogs_rows(), [])
		self.assertEqual(self.on_hand(self.product_id), 4)

	def test_paying_writes_the_cost(self):
		self.inventorying.sell(self.store(), self.location_id,
								self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.transactor.post_invoice_accounts('2026-03-01', self.invoice_id,
												self.total())
		rows = self.cogs_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][0], Decimal('12.00'))
		self.assertBalances()

if __name__ == '__main__':
	unittest.main()
