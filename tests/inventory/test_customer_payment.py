
import unittest
from datetime import date
from decimal import Decimal
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase

PAY_DAY = date(2025, 2, 3) # not today: gl_entries.date_inserted defaults to now ()


class DiscountCashBackTest(DBTestCase):
	'''Customer payment's Discounts / cashback box was hidden and never read, so
	neither the ledger nor the customer's balance ever saw it. Below zero it is
	a discount charged to an expense account, above zero cash handed back from a
	cash account; either way the payment takes amount - discount_cash_back off
	the customer's receivable'''

	def setUp(self):
		super().setUp()
		import accounts
		self.cash = self.new_account('Test cash back drawer', 1,
										cash_account = True)
		self.expense_parent = self.new_account('Test discounts', 3)
		self.expense = self.new_account('Test discounts given', 3,
										parent = self.expense_parent)
		terms_id = self.one("INSERT INTO terms_and_discounts "
							"(name, cash_only, discount_percent, pay_in_days, "
							"pay_by_day_of_month, pay_in_days_active, "
							"pay_by_day_of_month_active, standard, plus_date) "
							"VALUES ('Test cash only', True, 0, 0, 1, False, "
							"False, False, 0) RETURNING id")
		self.customer_id = self.one("INSERT INTO contacts (name, customer, "
							"markup_percent_id, terms_and_discounts_id) "
							"SELECT 'Test payment customer', True, "
							"(SELECT id FROM customer_markup_percent "
								"ORDER BY id LIMIT 1), %s RETURNING id",
							(terms_id,))
		self.receivable = self.one("SELECT account FROM gl_account_flow "
									"WHERE function = 'post_invoice'")
		self.cursor.execute("UPDATE settings SET (enforce_exact_payment, "
							"accrual_based) = (True, True)")
		self.DB.commit() # survive the window's own rollback after it reads
		accounts.populate_accounts() # expense_tree is only filled at startup

	def new_account(self, name, type_, parent = None, cash_account = False):
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
						"parent_number, cash_account) "
						"VALUES (%s, %s, %s, %s, %s) RETURNING number",
						(name, type_, number, parent or type_ * 1000,
						cash_account))

	def new_invoice(self, total, dated_for = PAY_DAY):
		invoice_id = self.one("INSERT INTO invoices (name, customer_id, "
							"total, amount_due, posted, date_created, dated_for) "
							"VALUES ('Test payment invoice', %s, %s, %s, True, "
							"%s, %s) RETURNING id",
							(self.customer_id, total, total, dated_for,
							dated_for))
		self.DB.commit()
		return invoice_id

	def window(self):
		import customer_payment
		gui = customer_payment.GUI(self.customer_id)
		self.addCleanup(gui.window.destroy)
		gui.payment_method.check_entry.set_text('1234')
		return gui

	def find(self, store, treeiter, number):
		'''expense_tree is a tree, so set_active_id - which only walks the top
		level - cannot reach a child account'''
		while treeiter != None:
			if store[treeiter][0] == number:
				return treeiter
			child = self.find(store, store.iter_children(treeiter), number)
			if child != None:
				return child
			treeiter = store.iter_next(treeiter)
		return None

	def choose_account(self, gui, number):
		combo = gui.builder.get_object('combobox2')
		store = combo.get_model()
		treeiter = self.find(store, store.get_iter_first(), str(number))
		self.assertIsNotNone(treeiter, 'account %s is not offered' % number)
		combo.set_active_iter(treeiter)

	def pay(self, gui, amount, adjustment, account):
		'''select every listed invoice, then type the payment and adjustment'''
		gui.builder.get_object('treeview-selection1').select_all()
		gui.builder.get_object('amount_spinbutton').set_value(amount)
		gui.builder.get_object('spinbutton2').set_value(adjustment)
		if account != None:
			self.choose_account(gui, account)

	def post(self, gui):
		button = gui.builder.get_object('button1')
		self.assertTrue(button.get_sensitive(), button.get_label())
		gui.post_payment_clicked(button)
		self.cursor.execute("SELECT p.id, p.amount, p.discount_cash_back, "
								"p.gl_entries_discount_cash_back_id, "
								"e.gl_transaction_id "
							"FROM payments_incoming AS p "
							"JOIN gl_entries AS e ON e.id = p.gl_entries_id "
							"WHERE p.customer_id = %s", (self.customer_id,))
		rows = self.cursor.fetchall()
		self.assertEqual(len(rows), 1, 'one payment')
		return rows[0]

	def entry(self, entry_id):
		self.cursor.execute("SELECT debit_account, credit_account, amount, "
								"gl_transaction_id, date_inserted "
							"FROM gl_entries WHERE id = %s", (entry_id,))
		return self.cursor.fetchone()

	def receivable_credited(self, transaction_id):
		return self.one("SELECT "
							"SUM(CASE WHEN credit_account = %(r)s "
								"THEN amount ELSE 0 END) - "
							"SUM(CASE WHEN debit_account = %(r)s "
								"THEN amount ELSE 0 END) "
						"FROM gl_entries WHERE gl_transaction_id = %(t)s",
						{'r': self.receivable, 't': transaction_id})

	def test_the_box_is_shown(self):
		gui = self.window()
		self.assertTrue(gui.builder.get_object('expander1').get_visible(),
						'nobody could ever type an adjustment')

	def test_cash_back_is_posted_from_the_cash_account(self):
		invoice_id = self.new_invoice(100)
		gui = self.window()
		self.pay(gui, 120, 0, None)
		button = gui.builder.get_object('button1')
		self.assertEqual(button.get_label(), 'Totals do not match')
		self.pay(gui, 120, 20, self.cash)
		payment_id, amount, adjustment, entry_id, transaction_id = self.post(gui)
		self.assertEqual(amount, Decimal('120.00'), 'the check is banked whole')
		self.assertEqual(adjustment, Decimal('20.00'))
		self.assertIsNotNone(entry_id, 'the payment does not claim its line')
		debit, credit, entry_amount, entry_transaction, _ = self.entry(entry_id)
		self.assertEqual(debit, self.receivable)
		self.assertEqual(credit, self.cash)
		self.assertEqual(entry_amount, Decimal('20.00'))
		self.assertEqual(entry_transaction, transaction_id,
							'the line belongs to the payment\'s transaction')
		self.assertEqual(self.receivable_credited(transaction_id),
							Decimal('100.00'))
		self.assertTrue(self.one("SELECT paid FROM invoices WHERE id = %s",
								(invoice_id,)))

	def test_a_discount_is_charged_to_the_expense_account(self):
		self.new_invoice(100)
		gui = self.window()
		self.pay(gui, 95, -5, self.expense)
		payment_id, amount, adjustment, entry_id, transaction_id = self.post(gui)
		self.assertEqual(amount, Decimal('95.00'))
		self.assertEqual(adjustment, Decimal('-5.00'))
		debit, credit, entry_amount, _, _ = self.entry(entry_id)
		self.assertEqual(debit, self.expense)
		self.assertEqual(credit, self.receivable)
		self.assertEqual(entry_amount, Decimal('5.00'), 'stored positive')
		self.assertEqual(self.receivable_credited(transaction_id),
							Decimal('100.00'))

	def test_post_waits_for_the_account(self):
		self.new_invoice(100)
		gui = self.window()
		button = gui.builder.get_object('button1')
		self.pay(gui, 120, 20, None)
		self.assertFalse(button.get_sensitive())
		self.assertEqual(button.get_label(), 'No discount / cashback account')
		self.choose_account(gui, self.cash)
		self.assertTrue(button.get_sensitive(), button.get_label())
		self.pay(gui, 95, -5, None)
		self.assertFalse(button.get_sensitive(),
							'a cash account stayed chosen for a discount')
		self.assertEqual(button.get_label(), 'No discount / cashback account')

	def test_a_parent_account_is_refused(self):
		self.new_invoice(100)
		gui = self.window()
		button = gui.builder.get_object('button1')
		self.pay(gui, 95, -5, self.expense_parent)
		self.assertFalse(button.get_sensitive())
		self.assertEqual(button.get_label(), 'Parent account selected')
		self.choose_account(gui, self.expense)
		self.assertTrue(button.get_sensitive(), button.get_label())

	def test_oldest_first_counts_what_the_payment_took_off(self):
		'''the matching sums the customer's payments; counted at face value the
		$20 handed back would pay the second invoice too'''
		self.cursor.execute("UPDATE settings SET enforce_exact_payment = False")
		self.DB.commit()
		first = self.new_invoice(100, date(2025, 2, 1))
		second = self.new_invoice(20, date(2025, 2, 2))
		gui = self.window()
		gui.builder.get_object('amount_spinbutton').set_value(120)
		gui.builder.get_object('spinbutton2').set_value(20)
		self.choose_account(gui, self.cash)
		self.assertTrue(gui.builder.get_object('fifo_payment_checkbutton')
																.get_active())
		self.post(gui)
		self.cursor.execute("SELECT id, paid FROM invoices WHERE id IN (%s, %s)",
							(first, second))
		paid = dict(self.cursor.fetchall())
		self.assertTrue(paid[first])
		self.assertFalse(paid[second], 'the cash handed back paid an invoice')

	def test_every_line_is_dated_the_day_of_the_payment(self):
		'''the header always carried the payment date, but the lines were left to
		their now () default, filing a back dated payment in the wrong period'''
		self.cursor.execute("INSERT INTO fiscal_years (name, start_date, "
							"end_date, active) VALUES ('Test payment year', "
							"'2025-02-01', '2025-02-28', True)")
		self.DB.commit()
		self.new_invoice(100)
		gui = self.window()
		gui.calendar.set_date(PAY_DAY)
		self.assertEqual(gui.date, PAY_DAY)
		self.pay(gui, 120, 20, self.cash)
		_, _, _, _, transaction_id = self.post(gui)
		self.cursor.execute("SELECT DISTINCT date_inserted FROM gl_entries "
							"WHERE gl_transaction_id = %s", (transaction_id,))
		self.assertEqual(self.cursor.fetchall(), [(PAY_DAY,)])
		self.assertEqual(self.one("SELECT date_inserted FROM gl_transactions "
								"WHERE id = %s", (transaction_id,)), PAY_DAY)

	def test_the_ledger_names_the_payment_for_every_line(self):
		from db import ledger
		self.new_invoice(100)
		gui = self.window()
		self.pay(gui, 120, 20, self.cash)
		payment_id, _, _, entry_id, transaction_id = self.post(gui)
		documents = {row[0]: row[11] for row in
						ledger.transaction_entries([transaction_id])}
		self.assertEqual(len(documents), 2)
		self.assertEqual(documents[entry_id],
							'Payment %s discount / cashback' % payment_id)
		self.assertNotIn('', documents.values(), 'a line nothing claims')


if __name__ == '__main__':
	unittest.main()
