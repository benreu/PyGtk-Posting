import unittest
from datetime import date
from decimal import Decimal
from unittest import mock
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk

DAY = date(2026, 6, 15)

class LoanPaymentTest(DBTestCase):
	'''Accounting > Loan payment's Print button posted the check payment and
	printed nothing, and wrote the amount in words from a float total, so
	1.15 + 2.30 came out as 44 cents'''
	def setUp(self):
		super().setUp()
		import loan_payment
		self.loan_payment = loan_payment
		# no checks_payable_to: the check falls back to the contact's name
		self.lender_id = self.one("INSERT INTO contacts (name, "
										"markup_percent_id, terms_and_discounts_id) "
									"SELECT 'Test lender', "
									"(SELECT id FROM customer_markup_percent "
										"ORDER BY id LIMIT 1), "
									"(SELECT id FROM terms_and_discounts "
										"ORDER BY id LIMIT 1) "
									"RETURNING id")
		# top level accounts with no children, so the window takes them
		self.bank = self.new_account('Loan test bank', 1, bank_account = True)
		self.liability = self.new_account('Loan test liability', 5)
		self.interest = self.new_account('Loan test interest', 3)
		transaction_id = self.one("INSERT INTO gl_transactions (date_inserted) "
									"VALUES (%s) RETURNING id", (DAY,))
		entry_id = self.one("INSERT INTO gl_entries (date_inserted, amount, "
								"debit_account, credit_account, gl_transaction_id) "
							"VALUES (%s, 1000, %s, %s, %s) RETURNING id",
							(DAY, self.bank, self.liability, transaction_id))
		self.loan_id = self.one("INSERT INTO loans (description, contact_id, "
									"date_received, amount, period, gl_entries_id, "
									"last_payment_date) "
								"VALUES ('Test tractor loan', %s, %s, 1000, "
									"'monthly', %s, %s) RETURNING id",
								(self.lender_id, DAY, entry_id, DAY))
		self.DB.commit()

	def new_account(self, name, type_, bank_account = False):
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
							"bank_account) VALUES (%s, %s, %s, %s) "
						"RETURNING number", (name, type_, number, bank_account))

	def window(self):
		'''the window opened on the test loan with everything filled in, ready
		to pay 1.15 principal and 2.30 interest by check'''
		gui = self.loan_payment.LoanPaymentGUI(self.loan_id)
		gui.date = DAY
		self.select_account(gui, 'treeview-selection2', self.liability)
		self.select_account(gui, 'treeview-selection3', self.interest)
		gui.builder.get_object('spinbutton1').set_value(1.15)
		gui.builder.get_object('spinbutton2').set_value(2.30)
		gui.builder.get_object('combobox4').set_active_id(str(self.bank))
		gui.builder.get_object('entry7').set_text('5150')
		return gui

	def select_account(self, gui, selection_id, number):
		selection = gui.builder.get_object(selection_id)
		model = selection.get_tree_view().get_model()
		for row in model:
			if row[0] == number:
				selection.select_iter(row.iter)
				return
		self.fail('account %s is not in the window' % number)

	def click(self, gui, handler, result = Gtk.PrintOperationResult.APPLY):
		'''click a check button with the check stubbed out, so no odt is
		rendered and no print dialog opens'''
		with mock.patch('printing.Operation') as Operation, \
				mock.patch('py3o.template.Template') as Template, \
				mock.patch('subprocess.call') as call, \
				mock.patch.object(gui.window, 'destroy') as destroy:
			Operation.return_value.print_dialog.return_value = result
			getattr(gui, handler)(None)
		self.Operation, self.Template, self.call = Operation, Template, call
		return destroy

	def payments(self):
		self.cursor.execute("SELECT ge.credit_account, ge.amount, "
								"ge.check_number "
							"FROM loan_payments AS lp "
							"JOIN gl_entries AS ge "
								"ON ge.id = lp.gl_entries_total_id "
							"WHERE lp.loan_id = %s", (self.loan_id,))
		return self.cursor.fetchall()

	def test_the_check_buttons_wait_for_a_bank_account(self):
		gui = self.window()
		self.assertTrue(gui.builder.get_object('button3').get_sensitive())
		self.assertTrue(gui.builder.get_object('button6').get_sensitive())
		gui.builder.get_object('combobox4').set_active(-1)
		gui.check_if_all_requirements_valid()
		self.assertFalse(gui.builder.get_object('button3').get_sensitive())
		self.assertFalse(gui.builder.get_object('button6').get_sensitive())

	def test_print_check_prints_and_posts(self):
		gui = self.window()
		destroy = self.click(gui, 'print_check_clicked')
		self.Operation.assert_called_once_with(settings_file = 'Vendor_check')
		odt = self.call.call_args[0][0][1]
		self.assertEqual(self.call.call_args[0][0], ['odt2pdf', odt])
		self.Operation.return_value.set_file_to_print.assert_called_once_with(
											odt.replace('.odt', '.pdf'))
		self.assertEqual(self.payments(),
						[(self.bank, Decimal('3.45'), 5150)])
		destroy.assert_called_once()

	def test_the_check_is_written_out_to_the_cent(self):
		gui = self.window()
		self.click(gui, 'print_check_clicked')
		data = self.Template.return_value.render.call_args[0][0]
		self.assertEqual(data['contact'].pay_to, 'Test lender')
		check = data['check']
		self.assertEqual((check.check_number, check.checking_account,
							check.date, check.amount),
						('5150', str(self.bank), DAY, '3.45'))
		self.assertEqual(check.amount_text, 'Three dollars and 45 cents')
		self.assertEqual([(line.po_number, line.amount, line.date)
							for line in data['items']],
						[('Test tractor loan principal', '1.15', DAY),
						('Test tractor loan interest', '2.30', DAY)])
		# the check on screen says the same
		self.assertEqual(gui.builder.get_object('label15').get_label(),
						'Three dollars and 45 cents')

	def test_a_payable_to_name_goes_on_the_check(self):
		self.cursor.execute("UPDATE contacts SET checks_payable_to = "
							"'Test Lending Co.' WHERE id = %s", (self.lender_id,))
		self.DB.commit()
		gui = self.window()
		self.click(gui, 'print_check_clicked')
		data = self.Template.return_value.render.call_args[0][0]
		self.assertEqual(data['contact'].pay_to, 'Test Lending Co.')

	def test_a_canceled_print_posts_nothing(self):
		gui = self.window()
		destroy = self.click(gui, 'print_check_clicked', 'user canceled')
		self.assertEqual(self.payments(), [])
		destroy.assert_not_called()

	def test_the_dialogs_own_cancel_still_posts(self):
		gui = self.window()
		destroy = self.click(gui, 'print_check_clicked',
								Gtk.PrintOperationResult.CANCEL)
		self.assertEqual(len(self.payments()), 1)
		destroy.assert_called_once()

	def test_post_without_printing_prints_nothing(self):
		gui = self.window()
		destroy = self.click(gui, 'post_check_without_printing_clicked')
		self.Operation.assert_not_called()
		self.Template.assert_not_called()
		self.call.assert_not_called()
		self.assertEqual(self.payments(),
						[(self.bank, Decimal('3.45'), 5150)])
		destroy.assert_called_once()


if __name__ == '__main__':
	unittest.main()
