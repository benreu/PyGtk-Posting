import unittest
from datetime import date
from decimal import Decimal
from harness import DBTestCase

LOAN_DAY = date(2026, 3, 9) # not today: the entry's own default is now ()


class CreateLoanTest(DBTestCase):
	'''a loan is money borrowed, which is a liability and an asset at once.
	transactor.create_loan wrote only the liability until 0.7.34, so every loan
	ever entered put the trial balance out by its own amount'''

	def setUp(self):
		super().setUp()
		from db import transactor
		from db import ledger
		self.transactor = transactor
		self.ledger = ledger
		self.liability = self.new_account('Test note payable', 5)
		self.bank = self.new_account('Test loan proceeds', 1, bank = True)

	def new_account(self, name, type_, bank = False):
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
						"parent_number, bank_account) "
						"VALUES (%s, %s, %s, %s, %s) RETURNING number",
						(name, type_, number, type_ * 1000, bank))

	def post(self, amount = Decimal('2500.00'), day = LOAN_DAY):
		entry_id = self.transactor.create_loan(day, amount, self.liability,
												self.bank)
		self.DB.commit()
		return entry_id

	def test_both_sides_are_posted(self):
		entry_id = self.post()
		self.cursor.execute("SELECT debit_account, credit_account, amount "
							"FROM gl_entries WHERE id = %s", (entry_id,))
		debit, credit, amount = self.cursor.fetchone()
		self.assertEqual(debit, self.bank, 'the money went nowhere')
		self.assertEqual(credit, self.liability)
		self.assertEqual(amount, Decimal('2500.00'))

	def test_the_entry_is_dated_the_day_the_loan_started(self):
		'''gl_entries.date_inserted defaults to now (), so leaving it out dated
		the ledger line today while its header carried the loan's start date -
		the two halves of one transaction filed into different periods'''
		entry_id = self.post()
		self.cursor.execute("SELECT e.date_inserted, t.date_inserted "
							"FROM gl_entries AS e "
							"JOIN gl_transactions AS t "
								"ON t.id = e.gl_transaction_id "
							"WHERE e.id = %s", (entry_id,))
		entry_date, header_date = self.cursor.fetchone()
		self.assertEqual(entry_date, LOAN_DAY)
		self.assertEqual(header_date, LOAN_DAY)

	def test_the_loan_is_one_entry_and_balances(self):
		'''one row carrying both accounts, not a sibling pair:
		loans.gl_entries_id is a single reference to it'''
		entry_id = self.post()
		transaction_id = self.one("SELECT gl_transaction_id FROM gl_entries "
									"WHERE id = %s", (entry_id,))
		self.assertEqual(self.one("SELECT count(*) FROM gl_entries "
									"WHERE gl_transaction_id = %s",
									(transaction_id,)), 1)
		listed = [row[0] for row in self.ledger.unbalanced_transactions()]
		self.assertNotIn(transaction_id, listed,
							'a new loan still unbalances the ledger')


class LoanWindowTest(DBTestCase):
	'''the window has to ask where the money landed, and must not offer to save
	a loan before it has'''

	def setUp(self):
		super().setUp()
		self.liability = self.new_account('Window note payable', 5)
		self.bank = self.new_account('Window loan proceeds', 1, bank = True)
		self.contact_id = self.one("SELECT id FROM contacts "
									"WHERE deleted = False ORDER BY id LIMIT 1")
		self.before = self.one("SELECT COALESCE(MAX(id), 0) FROM loans")
		self.DB.commit() # survive the window's own rollback after it reads

	new_account = CreateLoanTest.new_account

	def window(self):
		import loans
		gui = loans.LoanGUI()
		self.addCleanup(gui.window.destroy)
		return gui

	def find(self, store, treeiter, number):
		'''the liability picker is a tree, and the account wanted is a child of
		its type 5 root, so set_active_id - which only walks the top level -
		cannot reach it'''
		while treeiter != None:
			if store[treeiter][0] == number:
				return treeiter
			child = self.find(store, store.iter_children(treeiter), number)
			if child != None:
				return child
			treeiter = store.iter_next(treeiter)
		return None

	def fill_in(self, gui):
		'''everything the window asks for before the deposit account'''
		gui.builder.get_object('combobox1').set_active_id(str(self.contact_id))
		gui.builder.get_object('entry2').set_text('Test loan')
		gui.builder.get_object('spinbutton1').set_value(500)
		gui.builder.get_object('comboboxtext1').set_active_id('month')
		store = gui.builder.get_object('liability_account_store')
		treeiter = self.find(store, store.get_iter_first(), str(self.liability))
		self.assertIsNotNone(treeiter, 'the liability account is not listed')
		gui.builder.get_object('combobox2').set_active_iter(treeiter)

	def test_the_deposit_account_is_listed(self):
		gui = self.window()
		numbers = [row[0] for row in
					gui.builder.get_object('debit_account_store')]
		self.assertIn(str(self.bank), numbers)
		self.assertNotIn(str(self.liability), numbers,
							'a liability account is not where money lands')

	def test_save_waits_for_the_deposit_account(self):
		gui = self.window()
		save = gui.builder.get_object('button1')
		combo = gui.builder.get_object('debit_account_combo')
		self.assertFalse(combo.get_sensitive())
		self.assertFalse(save.get_sensitive())
		self.fill_in(gui)
		self.assertTrue(combo.get_sensitive(),
						'the liability account did not hand on to it')
		self.assertFalse(save.get_sensitive(),
						'a loan could be saved without saying where the money went')
		combo.set_active_id(str(self.bank))
		self.assertTrue(save.get_sensitive())

	def test_saving_writes_both_sides_and_the_liability_account(self):
		'''loans.liability_account is what the loan report's totals join on, and
		the window never filled it in, so every loan entered since 0.6.4 added
		it showed no totals at all'''
		gui = self.window()
		self.fill_in(gui)
		gui.builder.get_object('debit_account_combo').set_active_id(str(self.bank))
		gui.save_clicked(gui.builder.get_object('button1'))
		self.cursor.execute("SELECT l.liability_account, l.amount, "
								"e.debit_account, e.credit_account, e.amount "
							"FROM loans AS l "
							"JOIN gl_entries AS e ON e.id = l.gl_entries_id "
							"WHERE l.id > %s", (self.before,))
		rows = self.cursor.fetchall()
		self.assertEqual(len(rows), 1, 'one loan, one entry')
		liability, loan_amount, debit, credit, entry_amount = rows[0]
		self.assertEqual(liability, self.liability)
		self.assertEqual(debit, self.bank)
		self.assertEqual(credit, self.liability)
		self.assertEqual(entry_amount, loan_amount)


if __name__ == '__main__':
	unittest.main()
