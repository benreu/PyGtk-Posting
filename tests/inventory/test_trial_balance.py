import unittest
from datetime import date
from decimal import Decimal
from harness import DBTestCase

START = date(2026, 6, 1)
END = date(2026, 6, 30)
INSIDE = date(2026, 6, 15)
BEFORE = date(2026, 5, 31)
AFTER = date(2026, 7, 1)


class TrialBalanceTest(DBTestCase):
	'''gl_entries carries an entry's side as which of two nullable account
	columns is set, and one document's two halves can be separate rows carrying
	separate dates. Getting that right is the whole job of account_balances,
	so this works it from both shapes of row'''

	def setUp(self):
		super().setUp()
		self.cash = self.new_account('Trial balance cash', 1)
		self.revenue = self.new_account('Trial balance revenue', 4)

	def new_account(self, name, type_):
		'''a leaf hung off the type's root, numbered above everything else in
		that type's band so no other account's postings land in it'''
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
						"parent_number) VALUES (%s, %s, %s, %s) "
						"RETURNING number", (name, type_, number, type_ * 1000))

	def new_transaction(self, day):
		return self.one("INSERT INTO gl_transactions (date_inserted) "
						"VALUES (%s) RETURNING id", (day,))

	def entry(self, day, amount, debit = None, credit = None,
				transaction_id = None):
		if transaction_id is None:
			transaction_id = self.new_transaction(day)
		return self.one("INSERT INTO gl_entries (date_inserted, amount, "
						"debit_account, credit_account, gl_transaction_id) "
						"VALUES (%s, %s, %s, %s, %s) RETURNING id",
						(day, amount, debit, credit, transaction_id))

	def balances(self, start = START, end = END):
		from db import ledger
		return {row[0]: row for row in ledger.account_balances(start, end)}

	def figures(self, number, start = START, end = END):
		'''(opening, debits, credits, closing) for one account, closing derived
		the way the report derives it'''
		row = self.balances(start, end)[number]
		opening, debits, credits = row[4], row[5], row[6]
		return opening, debits, credits, opening + debits - credits

	def test_a_two_sided_entry_counts_on_both_sides(self):
		'''both account columns set on one row is a whole balanced entry, and
		the row has to be counted once as a debit and once as a credit'''
		self.entry(INSIDE, Decimal('125.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		self.assertEqual(self.figures(self.cash),
						(Decimal('0.00'), Decimal('125.00'), Decimal('0.00'),
						Decimal('125.00')))
		self.assertEqual(self.figures(self.revenue),
						(Decimal('0.00'), Decimal('0.00'), Decimal('125.00'),
						Decimal('-125.00')))

	def test_a_one_sided_sibling_pair_counts_once_each(self):
		'''the other shape: two rows under one transaction, each naming only
		its own side. Reads identically to the two sided row above'''
		transaction_id = self.new_transaction(INSIDE)
		self.entry(INSIDE, Decimal('125.00'), debit = self.cash,
					transaction_id = transaction_id)
		self.entry(INSIDE, Decimal('125.00'), credit = self.revenue,
					transaction_id = transaction_id)
		self.DB.commit()
		self.assertEqual(self.figures(self.cash),
						(Decimal('0.00'), Decimal('125.00'), Decimal('0.00'),
						Decimal('125.00')))
		self.assertEqual(self.figures(self.revenue),
						(Decimal('0.00'), Decimal('0.00'), Decimal('125.00'),
						Decimal('-125.00')))

	def test_an_entry_before_the_start_is_brought_forward(self):
		'''it belongs in the opening balance, and in neither period column'''
		self.entry(BEFORE, Decimal('40.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		self.assertEqual(self.figures(self.cash),
						(Decimal('40.00'), Decimal('0.00'), Decimal('0.00'),
						Decimal('40.00')))

	def test_an_entry_after_the_end_is_left_out_entirely(self):
		'''not in opening, not in either period column, and so - closing being
		derived from those three - not in closing either'''
		self.entry(AFTER, Decimal('70.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		self.assertEqual(self.figures(self.cash),
						(Decimal('0.00'), Decimal('0.00'), Decimal('0.00'),
						Decimal('0.00')))
		self.assertEqual(self.figures(self.revenue),
						(Decimal('0.00'), Decimal('0.00'), Decimal('0.00'),
						Decimal('0.00')))

	def test_an_account_with_children_still_reports_its_own_postings(self):
		'''a parent account can hold postings of its own - insert_basic hangs
		Credit Memos off Accounts Payable, and gl_account_flow sends every
		purchase order to that same 5100 - so filtering is_parent out of the
		query would drop accounts payable from the trial balance and put a
		sound ledger out of balance. This is the regression test for that.

		The child goes in before the posting: before_accounts_edited refuses to
		parent an account that already has entries'''
		self.new_account('Trial balance cash child', 1)
		self.one("UPDATE gl_accounts SET parent_number = %s "
					"WHERE number = (SELECT MAX(number) FROM gl_accounts "
						"WHERE number BETWEEN 1000 AND 1999) "
					"RETURNING number", (self.cash,))
		self.entry(INSIDE, Decimal('90.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		row = self.balances()[self.cash]
		self.assertTrue(row[3], 'the account should now be a parent')
		self.assertEqual(self.figures(self.cash),
						(Decimal('0.00'), Decimal('90.00'), Decimal('0.00'),
						Decimal('90.00')))

	def test_a_balanced_transaction_nets_to_nothing_across_accounts(self):
		'''the property the report's in-balance label rests on: a transaction
		whose halves are both present adds nothing to the signed total of every
		account, there being no year end closing entries to carry anything out.

		Asserted over this test's own accounts rather than the whole ledger,
		because a real company's ledger may hold one sided entries from years
		back and the whole-ledger total is then legitimately not zero - which
		is the condition the report exists to report, not one to assert away'''
		self.entry(INSIDE, Decimal('125.00'), debit = self.cash,
					credit = self.revenue)
		self.entry(BEFORE, Decimal('40.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		mine = [self.figures(self.cash), self.figures(self.revenue)]
		self.assertEqual(sum(f[3] for f in mine), Decimal('0.00'))
		for opening, debits, credits, closing in mine:
			self.assertEqual(closing, opening + debits - credits)


class TrialBalanceWindowTest(DBTestCase):
	'''the window over the top of it: that it builds, and that what it puts in
	the footer is what its own rows add up to'''

	def test_the_window_reports_what_its_rows_add_up_to(self):
		from reports import trial_balance
		gui = trial_balance.TrialBalanceGUI()
		self.assertTrue(len(gui.store) > 0, 'no accounts listed')
		closing = sum((opening + debits - credits
						for _, _, _, _, opening, debits, credits in gui.rows),
						Decimal())
		self.assertEqual(gui.get_object('closing_total_label').get_label(),
							trial_balance.money(closing))
		status = gui.get_object('balance_status_label').get_text()
		if closing == 0:
			self.assertIn('In balance', status)
		else:
			# what this company's ledger actually does, and the reason the
			# label is here
			self.assertIn('Out of balance', status)


if __name__ == '__main__':
	unittest.main()
