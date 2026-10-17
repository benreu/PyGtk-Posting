import unittest
from datetime import date
from decimal import Decimal
from harness import DBTestCase

DAY = date(2026, 6, 15)
OTHER_DAY = date(2026, 8, 1)


class UnbalancedTransactionsTest(DBTestCase):
	'''a transaction is sound when its debits and its credits agree. Nothing in
	the schema enforces that - the only CHECK is that a line names at least one
	account - so this is the detector, and what it has to get right is the
	several shapes a line comes in: two sided, one of a sibling pair, zero
	amount, negative'''

	def setUp(self):
		super().setUp()
		self.cash = self.new_account('Unbalanced cash', 1)
		self.revenue = self.new_account('Unbalanced revenue', 4)
		self.contact_id = self.one("SELECT id FROM contacts ORDER BY id LIMIT 1")

	def new_account(self, name, type_):
		number = self.one("SELECT COALESCE(MAX(number), %s) + 1 "
							"FROM gl_accounts WHERE number BETWEEN %s AND %s",
							(type_ * 1000, type_ * 1000, type_ * 1000 + 999))
		return self.one("INSERT INTO gl_accounts (name, type, number, "
						"parent_number) VALUES (%s, %s, %s, %s) "
						"RETURNING number", (name, type_, number, type_ * 1000))

	def new_transaction(self, day = DAY):
		return self.one("INSERT INTO gl_transactions (date_inserted) "
						"VALUES (%s) RETURNING id", (day,))

	def entry(self, transaction_id, amount, debit = None, credit = None,
				day = DAY, reconciled = False):
		return self.one("INSERT INTO gl_entries (date_inserted, amount, "
						"debit_account, credit_account, gl_transaction_id, "
						"reconciled) VALUES (%s, %s, %s, %s, %s, %s) "
						"RETURNING id",
						(day, amount, debit, credit, transaction_id, reconciled))

	def attach_credit_memo(self, entry_id):
		'''the cheapest document link that counts as a claim:
		credit_memos.gl_entries_id. A memo can be posted again from the memo,
		so its line really is the document's half of the story'''
		return self.one("INSERT INTO credit_memos (customer_id, date_created, "
						"gl_entries_id) VALUES (%s, %s, %s) RETURNING id",
						(self.contact_id, DAY, entry_id))

	def attach_loan(self, entry_id):
		'''loans.gl_entries_id, which is a document link and deliberately not a
		claim - see ledger.unbalanced_transactions'''
		return self.one("INSERT INTO loans (description, contact_id, "
						"date_received, amount, period, gl_entries_id, "
						"last_payment_date) "
						"VALUES ('test loan', %s, %s, 1.00, 'monthly', %s, %s) "
						"RETURNING id",
						(self.contact_id, DAY, entry_id, DAY))

	def claim_header(self, transaction_id):
		'''a document owning the transaction but none of its lines'''
		return self.one("INSERT INTO incoming_invoices (contact_id, "
						"gl_transaction_id) VALUES (%s, %s) RETURNING id",
						(self.contact_id, transaction_id))

	def found(self):
		from db import ledger
		return {row[0]: row for row in ledger.unbalanced_transactions()}

	def lines_of(self, transaction_id):
		from db import ledger
		return ledger.transaction_entries([transaction_id])

	def safety(self, row):
		from reports.unbalanced_transactions import safety_of
		return safety_of(row[2], row[8], row[9])

	# ---------------------------------------------------------------- balanced

	def test_a_two_sided_entry_is_not_listed(self):
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('50.00'), debit = self.cash,
					credit = self.revenue)
		self.DB.commit()
		self.assertNotIn(transaction_id, self.found())

	def test_a_balanced_sibling_pair_is_not_listed(self):
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('50.00'), debit = self.cash)
		self.entry(transaction_id, Decimal('50.00'), credit = self.revenue)
		self.DB.commit()
		self.assertNotIn(transaction_id, self.found())

	# -------------------------------------------------------------- unbalanced

	def test_a_one_sided_entry_is_listed_as_an_orphan(self):
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('75.00'), debit = self.cash)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[2], 1)                      # lines
		self.assertEqual(row[3], Decimal('75.00'))       # debits
		self.assertEqual(row[4], Decimal('0.00'))        # credits
		self.assertEqual(self.safety(row), 'Orphan')

	def test_a_two_sided_line_beside_a_one_sided_sibling(self):
		'''the shape a single sided join gets wrong: the two sided line has to
		count on both sides, so this is out by the sibling, not by nothing'''
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('30.00'), debit = self.cash,
					credit = self.revenue)
		self.entry(transaction_id, Decimal('30.00'), debit = self.cash)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[3], Decimal('60.00'))       # debits
		self.assertEqual(row[4], Decimal('30.00'))       # credits

	def test_a_zero_amount_counter_line_is_still_a_line(self):
		'''the counter line exists, it was just written as nothing. The
		transaction is out, but it is not a missing half and must not be
		repaired as one, so the line count has to say two'''
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('20.00'), debit = self.cash)
		self.entry(transaction_id, Decimal('0.00'), credit = self.revenue)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[2], 2)
		self.assertEqual(row[3], Decimal('20.00'))
		self.assertEqual(row[4], Decimal('0.00'))

	def test_a_negative_amount_is_reported_as_it_stands(self):
		'''nothing stops a negative amount and this ledger holds some. A
		negative debit is arithmetically a credit, which is what the totals
		have to say rather than taking an absolute value somewhere'''
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('-40.00'), debit = self.cash)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[3], Decimal('-40.00'))
		self.assertEqual(row[4], Decimal('0.00'))

	def test_a_header_with_no_lines_at_all_is_listed(self):
		'''invisible to a GROUP BY over gl_entries - it falls out of the
		grouping - so the query has to come at it from gl_transactions'''
		transaction_id = self.new_transaction()
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[2], 0)
		self.assertEqual(row[3], Decimal('0.00'))
		self.assertEqual(self.safety(row), 'Empty header')

	# ------------------------------------------------------- repair safety

	def test_a_line_a_document_claims_is_attached_and_named(self):
		transaction_id = self.new_transaction()
		entry_id = self.entry(transaction_id, Decimal('90.00'),
								credit = self.revenue)
		memo_id = self.attach_credit_memo(entry_id)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(self.safety(row), 'Attached')
		lines = self.lines_of(transaction_id)
		self.assertEqual(lines[0][11], 'Credit memo %s' % memo_id)

	def test_a_loans_own_entry_is_repairable_but_still_named(self):
		'''the loan window posted one sided until 0.7.34, and a loan records
		only its liability account - so the debit cannot be re-derived from the
		loan the way an invoice's entries can be re-derived from the invoice.
		This report is the only place that half can be written, so a loan must
		not come back as somewhere else's business. It is still named, which is
		what tells whoever repairs it what they are looking at'''
		transaction_id = self.new_transaction()
		entry_id = self.entry(transaction_id, Decimal('2500.00'),
								credit = self.revenue)
		loan_id = self.attach_loan(entry_id)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[8], 0)                      # attached lines
		self.assertEqual(self.safety(row), 'Orphan')
		lines = self.lines_of(transaction_id)
		self.assertEqual(lines[0][11], 'Loan %s' % loan_id)

	def test_a_claimed_header_over_orphan_lines(self):
		'''the nastiest class: a document owns the transaction but none of its
		lines, so adding a line changes that document's ledger footprint with
		nothing pointing at the line that did it'''
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('15.00'), debit = self.cash)
		self.claim_header(transaction_id)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[8], 0)              # attached lines
		self.assertEqual(row[9], True)           # header claimed
		self.assertEqual(self.safety(row), 'Header claimed')

	def test_some_lines_attached_and_some_not_is_mixed(self):
		transaction_id = self.new_transaction()
		attached = self.entry(transaction_id, Decimal('60.00'),
								credit = self.revenue)
		self.entry(transaction_id, Decimal('25.00'), debit = self.cash)
		self.attach_credit_memo(attached)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(self.safety(row), 'Mixed')

	def test_a_reconciled_line_is_counted(self):
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('10.00'), debit = self.cash,
					reconciled = True)
		self.entry(transaction_id, Decimal('99.00'), credit = self.revenue)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[7], 1)              # reconciled lines
		self.assertEqual(row[2], 2)

	def test_lines_dated_apart_report_their_span(self):
		'''a different defect from a missing half, and it would otherwise hide
		behind the imbalance'''
		transaction_id = self.new_transaction()
		self.entry(transaction_id, Decimal('45.00'), debit = self.cash)
		self.entry(transaction_id, Decimal('12.00'), credit = self.revenue,
					day = OTHER_DAY)
		self.DB.commit()
		row = self.found()[transaction_id]
		self.assertEqual(row[5], DAY)            # first line date
		self.assertEqual(row[6], OTHER_DAY)      # last line date
		self.assertNotEqual(row[5], row[6])


class UnbalancedTransactionsWindowTest(DBTestCase):
	'''the window over the top: that it builds, and that its footer is what its
	own rows add up to'''

	def test_the_footer_is_what_the_rows_add_up_to(self):
		from reports import unbalanced_transactions as report
		gui = report.UnbalancedTransactionsGUI()
		self.assertTrue(len(gui.store) > 0, 'nothing listed')
		self.assertEqual(len(gui.store), len(gui.transactions))
		gross = Decimal()
		net = Decimal()
		for row in gui.transactions:
			imbalance = row[3] - row[4]
			gross += abs(imbalance)
			net += imbalance
		self.assertEqual(gui.get_object('gross_total_label').get_label(),
							report.money(gross))
		self.assertEqual(gui.get_object('net_total_label').get_label(),
							report.money(net))
		self.assertEqual(gui.get_object('transaction_count_label').get_label(),
							str(len(gui.transactions)))

	def test_every_line_is_hung_under_its_own_transaction(self):
		from reports import unbalanced_transactions as report
		gui = report.UnbalancedTransactionsGUI()
		listed = 0
		for row in gui.store:
			for child in row.iterchildren():
				listed += 1
				self.assertEqual(child[0], row[0],
								'a line is under the wrong transaction')
		self.assertEqual(listed, len(gui.entries))


if __name__ == '__main__':
	unittest.main()
