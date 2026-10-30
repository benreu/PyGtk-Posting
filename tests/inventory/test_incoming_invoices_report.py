import unittest
from datetime import date
from decimal import Decimal
from harness import DBTestCase

DAY = date(2026, 6, 15)


class IncomingInvoicesPaidWithTest(DBTestCase):
	'''Reports > Incoming invoices shows how each bill was paid, read off the
	credit line incoming_invoices.gl_entry_id points at, and can be narrowed to
	one payment account'''

	def setUp(self):
		super().setUp()
		from db import transactor
		self.transactor = transactor
		self.bank = self.new_account('Paid with bank', 'check_writing')
		self.card = self.new_account('Paid with card', 'credit_card_account')
		self.cash = self.new_account('Paid with cash', 'cash_account')
		self.expense = self.new_account('Paid with expense', 'expense_account', 3)
		self.contact_id = self.one("SELECT id FROM contacts ORDER BY id LIMIT 1")
		self.cheque = self.bill(lambda p: p.check_payment(p.total, 2411,
														self.bank, 'cheque'))
		self.transfer = self.bill(lambda p: p.transfer(p.total, 'transfer',
														self.bank))
		# older rows carry 0 for no cheque, which the edit window treats the
		# same as NULL
		self.zero_cheque = self.bill(lambda p: p.check_payment(p.total, 0,
														self.bank, 'zero'))
		self.card_bill = self.bill(lambda p: p.credit_card_payment(p.total,
														'card', self.card))
		self.cash_bill = self.bill(lambda p: p.cash_payment(p.total, self.cash))
		# bills from before payments were recorded have no gl_entry_id
		self.unpaid = self.one("INSERT INTO incoming_invoices "
								"(contact_id, date_created, amount, description) "
								"VALUES (%s, %s, 9.00, 'no payment') "
								"RETURNING id", (self.contact_id, DAY))
		self.ours = (self.cheque, self.transfer, self.zero_cheque,
						self.card_bill, self.cash_bill, self.unpaid)
		self.DB.commit()
		from reports import incoming_invoices
		self.gui = incoming_invoices.IncomingInvoiceGUI()

	def new_account(self, name, flag, type_ = 1):
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
						"parent_number, %s) VALUES (%%s, %%s, %%s, %%s, True) "
						"RETURNING number" % flag,
						(name, type_, number, type_ * 1000))

	def bill(self, pay):
		'''what incoming_invoice.save_incoming_invoice and one of its payment
		buttons do between them'''
		payment = self.transactor.ServiceProviderPayment(DAY, Decimal('25.00'))
		invoice_id = self.one("INSERT INTO incoming_invoices (contact_id, "
							"date_created, amount, description, "
							"gl_transaction_id) VALUES (%s, %s, %s, 'paid with', "
							"%s) RETURNING id", (self.contact_id, DAY,
							payment.total, payment.transaction_id))
		payment.incoming_invoice_id = invoice_id
		payment.expense(payment.total, self.expense, '')
		pay(payment)
		return invoice_id

	def listed(self):
		"invoice id: row, for this test's bills that the report shows"
		return {row[0]: row for row in self.gui.incoming_invoice_store
				if row[0] in self.ours}

	def test_each_bill_says_how_it_was_paid(self):
		self.gui.populate_incoming_invoice_store()
		paid_with = {i: row[9] for i, row in self.listed().items()}
		self.assertEqual(paid_with, {
			self.cheque: 'Cheque 2411 · Paid with bank',
			self.transfer: 'Transfer · Paid with bank',
			self.zero_cheque: 'Transfer · Paid with bank',
			self.card_bill: 'Credit card · Paid with card',
			self.cash_bill: 'Cash · Paid with cash',
			self.unpaid: ''})

	def test_reconciled_still_comes_from_the_payment(self):
		self.cursor.execute("UPDATE gl_entries SET reconciled = True "
							"WHERE id = (SELECT gl_entry_id FROM "
							"incoming_invoices WHERE id = %s)", (self.card_bill,))
		self.DB.commit()
		self.gui.populate_incoming_invoice_store()
		rows = self.listed()
		self.assertTrue(rows[self.card_bill][8])
		self.assertFalse(rows[self.cash_bill][8])

	def test_payment_accounts_are_offered(self):
		ids = [row[0] for row in self.gui.get_object('pay_with_account_store')]
		self.assertEqual(ids[0], '0')
		for account in (self.bank, self.card, self.cash):
			self.assertIn(str(account), ids)
		self.assertNotIn(str(self.expense), ids)

	def test_choosing_an_account_keeps_only_its_bills(self):
		combo = self.gui.get_object('payment_account_combobox')
		combo.set_active_id(str(self.bank))
		self.assertEqual(set(self.listed()),
						{self.cheque, self.transfer, self.zero_cheque})
		combo.set_active_id(str(self.card))
		self.assertEqual(set(self.listed()), {self.card_bill})
		combo.set_active_id('0')
		self.assertEqual(set(self.listed()), set(self.ours))

if __name__ == '__main__':
	unittest.main()
