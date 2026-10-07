import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # 1710 is receivables, it must not double as inventory
COGS_ACCOUNT = 3876

class InvoiceAccountsResyncTest(DBTestCase):
	'''a posted invoice can still be edited, so the receivable, the sales tax and
	the revenue of every line have to follow the edit the way the cost already
	does. One line of 4 at 5.00 on an 8% rate: 20.00 revenue, 1.60 tax, 21.60
	receivable, and 12.00 of cost at a cost of 3'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		from db import transactor
		self.inventorying = inventorying
		self.transactor = transactor
		self.product_id = 19
		self.other_product_id = 962
		self.location_id = self.new_location()
		self.cursor.execute("UPDATE products SET cost = 3, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id IN (%s, %s)",
							(INVENTORY_ACCOUNT, COGS_ACCOUNT,
							self.product_id, self.other_product_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id IN (%s, %s)",
							(self.product_id, self.other_product_id))
		self.customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates "
									"WHERE (rate, deleted) = (8.00, False) "
									"ORDER BY id LIMIT 1")
		self.receivable = self.one("SELECT account FROM gl_account_flow "
									"WHERE function = 'post_invoice'")
		self.revenue_account = self.one("SELECT revenue_account FROM products "
										"WHERE id = %s", (self.product_id,))
		self.tax_account = self.one("SELECT tax_received_account FROM tax_rates "
									"WHERE id = %s", (self.tax_rate_id,))
		self.invoice_id = self.new_invoice()
		self.line_id = self.invoice_line(4)
		self.add_stock(self.product_id, 10)
		self.post()
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
							"VALUES (%s, %s, 3, %s, CURRENT_DATE, 'test')",
							(product_id, qty, self.location_id))

	def save_totals(self, invoice_id = None):
		'''what calculate_totals writes on every keystroke'''
		invoice_id = invoice_id or self.invoice_id
		self.cursor.execute("UPDATE invoices AS i SET (subtotal, tax, total) = "
								"(t.subtotal, t.tax, t.total) "
							"FROM (SELECT COALESCE(SUM(ext_price), 0.00) "
										"AS subtotal, "
									"COALESCE(SUM(tax), 0.00) AS tax, "
									"COALESCE(SUM(ext_price) + SUM(tax), 0.00) "
										"AS total "
									"FROM invoice_items "
									"WHERE invoice_id = %s) AS t "
							"WHERE i.id = %s", (invoice_id, invoice_id))

	def post(self, invoice_id = None, line_id = None, product_id = None):
		'''what invoice_window and invoice_create do: the stock moves, the totals
		are saved, the total becomes the amount due, then the ledger is written'''
		invoice_id = invoice_id or self.invoice_id
		self.inventorying.sell([[line_id or self.line_id, '4.00',
								product_id or self.product_id,
								'', '', '', '5.00']],
								self.location_id, self.customer_id, '2026-01-01')
		self.save_totals(invoice_id)
		self.cursor.execute("UPDATE invoices "
							"SET (posted, amount_due, dated_for) = "
								"(True, total, '2026-01-01') "
							"WHERE id = %s RETURNING total", (invoice_id,))
		total = self.cursor.fetchone()[0]
		self.transactor.post_invoice_accounts('2026-01-01', invoice_id, total)
		return total

	def invoice_total(self, invoice_id = None):
		return self.one("SELECT total FROM invoices WHERE id = %s",
						(invoice_id or self.invoice_id,))

	def amount_due(self):
		return self.one("SELECT amount_due FROM invoices WHERE id = %s",
						(self.invoice_id,))

	def transaction_id(self, invoice_id = None):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"JOIN invoices AS i ON i.gl_entries_id = ge.id "
						"WHERE i.id = %s", (invoice_id or self.invoice_id,))

	def receivable_amount(self, invoice_id = None):
		return self.one("SELECT ge.amount FROM gl_entries AS ge "
						"JOIN invoices AS i ON i.gl_entries_id = ge.id "
						"WHERE i.id = %s", (invoice_id or self.invoice_id,))

	def revenue_of(self, line_id):
		'''the amount, account and date of one line's revenue entry'''
		self.cursor.execute("SELECT ge.amount, ge.credit_account, "
								"ge.date_inserted, ge.gl_transaction_id "
							"FROM gl_entries AS ge "
							"JOIN invoice_items AS ii ON ii.gl_entries_id = ge.id "
							"WHERE ii.id = %s", (line_id,))
		return self.cursor.fetchone()

	def tax_on(self, account):
		'''the one sided credits of this transaction on a tax account'''
		return self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
						"WHERE (gl_transaction_id, credit_account) = (%s, %s) "
						"AND debit_account IS NULL",
						(self.transaction_id(), account))

	def entry_count(self):
		return self.one("SELECT COUNT(*) FROM gl_entries "
						"WHERE gl_transaction_id = %s", (self.transaction_id(),))

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

	def test_the_fixture_posts_what_the_tests_assume(self):
		self.assertEqual(self.invoice_total(), Decimal('21.60'))
		self.assertEqual(self.receivable_amount(), Decimal('21.60'))
		self.assertEqual(self.revenue_of(self.line_id)[0], Decimal('20.00'))
		self.assertEqual(self.tax_on(self.tax_account), Decimal('1.60'))
		self.assertBalances()

	# ---------------- the guard ----------------

	def test_a_draft_invoice_is_left_alone(self):
		draft = self.new_invoice()
		self.invoice_line(3, draft)
		self.assertEqual(self.transactor.resync_invoice_accounts(draft), None)
		# invoice_create.post owns the first posting, not this
		self.assertEqual(self.invoice_total(draft), Decimal('0.00'))
		self.assertEqual(self.one("SELECT COUNT(*) FROM invoice_items "
									"WHERE invoice_id = %s "
									"AND gl_entries_id IS NOT NULL", (draft,)), 0)

	def test_a_canceled_invoice_is_left_alone(self):
		transaction_id = self.transaction_id()
		self.transactor.cancel_invoice('2026-02-01', self.invoice_id)
		self.inventorying.unsell(self.invoice_id)
		self.cursor.execute("UPDATE invoices SET canceled = True WHERE id = %s",
							(self.invoice_id,))
		before = self.entry_count()
		self.cursor.execute("UPDATE invoice_items SET qty = 9 WHERE id = %s",
							(self.line_id,))
		self.assertEqual(
			self.transactor.resync_invoice_accounts(self.invoice_id), None)
		# the mirror entries cancel_invoice wrote still have to net the document
		# out; restating the originals under them would leave it unbalanced
		self.assertEqual(self.entry_count(), before)
		self.assertEqual(self.net(self.receivable), 0)
		self.assertEqual(self.net(self.revenue_account), 0)
		self.assertEqual(self.transaction_id(), transaction_id)
		self.assertBalances()

	def test_a_paid_invoice_is_left_alone(self):
		self.cursor.execute("UPDATE invoices SET paid = True WHERE id = %s",
							(self.invoice_id,))
		self.cursor.execute("UPDATE invoice_items SET qty = 9 WHERE id = %s",
							(self.line_id,))
		self.assertEqual(
			self.transactor.resync_invoice_accounts(self.invoice_id), None)
		# the receivable is already offset in the payment's own transaction
		self.assertEqual(self.receivable_amount(), Decimal('21.60'))
		self.assertEqual(self.invoice_total(), Decimal('21.60'))

	def test_a_finance_charge_invoice_is_left_alone(self):
		# post_finance_charge gives it a single two sided entry and no line items
		# at all, so recomputing its total from the lines would zero both legs
		charge = self.one("INSERT INTO invoices (customer_id, finance_charge, "
							"posted, subtotal, total, amount_due) "
							"VALUES (%s, True, True, 50, 50, 50) RETURNING id",
							(self.customer_id,))
		self.transactor.post_finance_charge(charge)
		entry_id = self.one("SELECT gl_entries_id FROM invoices WHERE id = %s",
							(charge,))
		self.assertEqual(self.transactor.resync_invoice_accounts(charge), None)
		self.assertEqual(self.invoice_total(charge), Decimal('50.00'))
		self.assertEqual(self.one("SELECT amount FROM gl_entries WHERE id = %s",
									(entry_id,)), Decimal('50.00'))

	def test_a_cash_basis_invoice_with_no_entries_is_left_alone(self):
		# under cash basis the ledger is not touched until the invoice is paid,
		# so there is no transaction to re-sync and no revenue due yet
		unpaid = self.new_invoice()
		line_id = self.invoice_line(4, unpaid)
		self.add_stock(self.product_id, 10)
		self.inventorying.sell([[line_id, '4.00', self.product_id,
								'', '', '', '5.00']],
								self.location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(unpaid,))
		self.assertEqual(self.transactor.resync_invoice_accounts(unpaid), None)
		self.assertEqual(self.one("SELECT gl_entries_id FROM invoice_items "
									"WHERE id = %s", (line_id,)), None)

	def test_an_invoice_that_does_not_exist_is_a_no_op(self):
		self.assertEqual(self.transactor.resync_invoice_accounts(0), None)

	# ---------------- revenue ----------------

	def test_a_quantity_edit_restates_the_revenue(self):
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.assertEqual(
			self.transactor.resync_invoice_accounts(self.invoice_id),
			Decimal('37.80'))
		amount, account, date, transaction_id = self.revenue_of(self.line_id)
		self.assertEqual(amount, Decimal('35.00')) # 7 at 5.00
		self.assertEqual(account, self.revenue_account)
		self.assertEqual(transaction_id, self.transaction_id())
		self.assertBalances()

	def test_a_price_edit_restates_the_revenue(self):
		self.cursor.execute("UPDATE invoice_items SET price = 9 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.revenue_of(self.line_id)[0], Decimal('36.00'))
		self.assertBalances()

	def test_a_line_added_after_posting_gets_a_revenue_entry(self):
		added = self.invoice_line(2)
		self.transactor.resync_invoice_accounts(self.invoice_id)
		amount, account, date, transaction_id = self.revenue_of(added)
		self.assertEqual(amount, Decimal('10.00')) # 2 at 5.00
		self.assertEqual(account, self.revenue_account)
		self.assertEqual(transaction_id, self.transaction_id())
		self.assertEqual(self.net(self.revenue_account), Decimal('-30.00'))
		self.assertBalances()

	def test_a_canceled_line_zeroes_its_revenue(self):
		added = self.invoice_line(2)
		self.transactor.resync_invoice_accounts(self.invoice_id)
		# what delete_line_item_activated writes
		self.cursor.execute("UPDATE invoice_items SET "
							"(qty, price, ext_price, tax, canceled) = "
							"(0, 0, 0, 0, True) WHERE id = %s", (added,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.revenue_of(added)[0], Decimal('0.00'))
		self.assertEqual(self.net(self.revenue_account), Decimal('-20.00'))
		self.assertEqual(self.receivable_amount(), Decimal('21.60'))
		self.assertBalances()

	def test_another_line_is_not_restated_by_an_edit(self):
		other = self.invoice_line(2)
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.revenue_of(other)[0], Decimal('10.00'))
		self.assertEqual(self.revenue_of(self.line_id)[0], Decimal('35.00'))
		self.assertBalances()

	# ---------------- the receivable and the tax ----------------

	def test_the_receivable_carries_the_whole_invoice(self):
		self.invoice_line(2)
		self.transactor.resync_invoice_accounts(self.invoice_id)
		# 30.00 of goods on an 8% rate
		self.assertEqual(self.receivable_amount(), Decimal('32.40'))
		self.assertEqual(self.net(self.receivable), Decimal('32.40'))
		self.assertBalances()

	def test_the_tax_entry_follows_the_edit(self):
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.tax_on(self.tax_account), Decimal('2.80'))
		self.assertBalances()

	def test_a_tax_account_that_leaves_the_invoice_is_zeroed(self):
		# the per rate loop only visits an account still on the invoice, so the
		# blanket zeroing is the only thing that retires the one it left behind
		other_rate = self.one("INSERT INTO tax_rates (name, rate, standard, "
								"tax_letter, tax_received_account) "
								"VALUES ('test rate', 8.00, False, 'T', 5200) "
								"RETURNING id")
		self.cursor.execute("UPDATE invoice_items SET tax_rate_id = %s "
							"WHERE invoice_id = %s",
							(other_rate, self.invoice_id))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.tax_on(self.tax_account), Decimal('0.00'))
		self.assertEqual(self.tax_on(5200), Decimal('1.60'))
		self.assertBalances()

	# ---------------- the totals ----------------

	def test_the_totals_are_recomputed_from_the_lines(self):
		# refresh_all_prices_clicked writes the line price and never calls
		# calculate_totals, so the invoice header cannot be trusted here
		self.cursor.execute("UPDATE invoice_items SET price = 9 WHERE id = %s",
							(self.line_id,))
		self.assertEqual(self.invoice_total(), Decimal('21.60')) # still stale
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.invoice_total(), Decimal('38.88')) # 36.00 and 8%
		self.assertEqual(self.one("SELECT subtotal FROM invoices WHERE id = %s",
									(self.invoice_id,)), Decimal('36.00'))
		self.assertEqual(self.receivable_amount(), Decimal('38.88'))

	def test_amount_due_follows_the_total(self):
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.amount_due(), Decimal('37.80'))

	def test_a_hand_typed_discount_does_not_survive_an_edit(self):
		# total less amount_due is posted as a customer discount when the invoice
		# is paid, and the payment window recomputes it from the terms anyway
		self.cursor.execute("UPDATE invoices SET amount_due = 20 WHERE id = %s",
							(self.invoice_id,))
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.amount_due(), Decimal('37.80'))

	# ---------------- dates ----------------

	def test_an_existing_entry_keeps_its_date(self):
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(str(self.revenue_of(self.line_id)[2]), '2026-01-01')

	def test_a_new_entry_takes_the_transaction_date_not_dated_for(self):
		# invoice_create.post rewrites dated_for on every post, a re-post
		# included, while the entries keep the date they were written under
		self.cursor.execute("UPDATE invoices SET dated_for = '2026-09-09' "
							"WHERE id = %s", (self.invoice_id,))
		added = self.invoice_line(2)
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(str(self.revenue_of(added)[2]), '2026-01-01')

	# ---------------- idempotence and isolation ----------------

	def test_resyncing_twice_changes_nothing(self):
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.cursor.execute("SELECT id, amount, debit_account, credit_account, "
								"date_inserted FROM gl_entries "
							"WHERE gl_transaction_id = %s ORDER BY id",
							(self.transaction_id(),))
		before = self.cursor.fetchall()
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.cursor.execute("SELECT id, amount, debit_account, credit_account, "
								"date_inserted FROM gl_entries "
							"WHERE gl_transaction_id = %s ORDER BY id",
							(self.transaction_id(),))
		self.assertEqual(self.cursor.fetchall(), before)

	def test_another_invoice_is_left_alone(self):
		other = self.new_invoice()
		other_line = self.invoice_line(4, other, self.other_product_id)
		self.add_stock(self.other_product_id, 10)
		self.post(other, other_line, self.other_product_id)
		before = self.receivable_amount(other)
		self.cursor.execute("UPDATE invoice_items SET qty = 7 WHERE id = %s",
							(self.line_id,))
		self.transactor.resync_invoice_accounts(self.invoice_id)
		self.assertEqual(self.receivable_amount(other), before)
		self.assertEqual(self.revenue_of(other_line)[0], Decimal('20.00'))
		self.assertEqual(self.invoice_total(other), Decimal('21.60'))

if __name__ == '__main__':
	unittest.main()
