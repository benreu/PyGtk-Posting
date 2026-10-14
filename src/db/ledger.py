# ledger.py
#
# Copyright (C) 2026 - Reuben Rissler
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

'''read side queries over the general ledger.

net_worth.py, profit_loss_report.py and account_transactions.py each carry their
own near duplicate of the balance query, recursing a generator and spending one
round trip per leaf account. They should move onto account_balances () when
somebody next has reason to touch them; the abs () they all apply to a leaf
balance is the sign bug to drop when they do'''

from db_connection import DB


def account_balances (start_date, end_date):
	'''every gl_account with its opening balance, its debits and its credits for
	the period, as (number, name, type, is_parent, opening, debits, credits).
	Opening is signed - debits less credits - so a credit balance account comes
	back negative. The closing balance is deliberately not returned: the caller
	derives it as opening + debits - credits, so the figure a reader checks by
	hand always reconciles with the figure printed.

	Three things here are decisions rather than accidents.

	The LATERAL (VALUES ...) is how an entry is split into sides. gl_entries
	holds an amount and two nullable account columns, so the side is which
	column is set, not a sign, and a row may be two sided - a whole balanced
	entry on one row - or one of a pair of siblings under the same
	gl_transaction_id. Emitting one row per non null side counts a two sided row
	on both sides and a one sided row once, in a single scan of the table.

	The amount is only expected positive, not guaranteed: nothing constrains it
	but credit_or_debit_is_not_null, and a real ledger here holds negative and
	zero amounts both. Subtracting credits from debits is right either way, a
	negative debit being a credit, which is why this returns a signed figure and
	leaves the presentation to the caller.

	The date filtered on is the entry's own date_inserted, not the parent
	transaction's. The entry date is what the entry is filed under, it is what
	profit_loss_report already reports by, and the two can differ: using the
	transaction date would re-date individual halves of a document whose halves
	were written with dates of their own.

	There is no is_parent filter. A parent account can hold postings of its own -
	insert_basic.sql hangs Credit Memos off Accounts Payable, which makes 5100 a
	parent, and gl_account_flow sends every purchase order to 5100 - so filtering
	parents out would drop accounts payable from the ledger entirely. Nothing is
	double counted by including them, because this returns each account's own
	balance and rolls nothing up.

	No rollback: this has to stay safe to call from inside a write transaction.
	The caller rolls back, which is also what every read path in the app does'''
	cursor = DB.cursor()
	cursor.execute("WITH ledger AS "
						"(SELECT side.account, e.date_inserted, "
								"side.debit, side.credit "
							"FROM gl_entries AS e "
							"CROSS JOIN LATERAL (VALUES "
									"(e.debit_account, e.amount, 0.00::numeric), "
									"(e.credit_account, 0.00::numeric, e.amount)) "
								"AS side (account, debit, credit) "
							"WHERE side.account IS NOT NULL "
								"AND e.date_inserted <= %(end_date)s ) "
					"SELECT a.number, "
						"a.name, "
						"a.type, "
						"a.is_parent, "
						"COALESCE(SUM(l.debit - l.credit) "
							"FILTER (WHERE l.date_inserted < %(start_date)s), "
							"0.00) AS opening, "
						"COALESCE(SUM(l.debit) "
							"FILTER (WHERE l.date_inserted >= %(start_date)s), "
							"0.00) AS period_debits, "
						"COALESCE(SUM(l.credit) "
							"FILTER (WHERE l.date_inserted >= %(start_date)s), "
							"0.00) AS period_credits "
					"FROM gl_accounts AS a "
					"LEFT JOIN ledger AS l ON l.account = a.number "
					# number is the primary key, so grouping by it alone is
					# enough for the other gl_accounts columns
					"GROUP BY a.number "
					"ORDER BY a.number",
					{'start_date': start_date, 'end_date': end_date})
	rows = cursor.fetchall()
	cursor.close()
	return rows


def unbalanced_transactions ():
	'''every gl_transaction whose debits and credits do not agree, as
	(id, date, lines, debits, credits, first_line_date, last_line_date,
	reconciled_lines, attached_lines, header_claimed).

	Which of them can safely be touched is the point of this, not the list. A
	line referenced by a posted invoice, purchase order or loan is that
	document's half of the story, and writing the missing side by hand changes
	the document's ledger footprint behind its back - the app's own way of
	correcting posted entries is to re-derive them from the document, the way
	transactor.resync_invoice_accounts does. So attached_lines and
	header_claimed come back with the totals and the caller labels the row
	rather than discovering it per transaction.

	Driven from gl_transactions outward, not from gl_entries inward, so that a
	header carrying no lines at all comes back in the same pass. Those are
	invisible to a GROUP BY over gl_entries - they fall out of the grouping -
	and they are a defect of their own, an empty journal entry nothing
	references.

	The sides are summed with CASE WHEN rather than the LATERAL account_balances
	uses: grouping by transaction needs no row splitting, and a two sided row
	adding its amount to both sums is already what double entry means here.
	count(*) then stays the true line count.

	No rollback, as account_balances'''
	cursor = DB.cursor()
	cursor.execute("WITH attached AS "
							# every column in the schema that claims an entry as
							# a document's own. Four of them match nothing in
							# the ledger this was written against; they stay
							# because the next defect may land there
						"(SELECT gl_entries_id AS entry_id FROM invoice_items "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM invoices "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_tax_id FROM invoices "
							"WHERE gl_entries_tax_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM purchase_order_items "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM purchase_orders "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entry_id FROM incoming_invoices "
							"WHERE gl_entry_id IS NOT NULL "
						"UNION SELECT gl_entry_expense_id "
							"FROM incoming_invoices_gl_entry_expenses_ids "
						"UNION SELECT gl_entries_id FROM payments_incoming "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_deposit_id FROM payments_incoming "
							"WHERE gl_entries_deposit_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM credit_memos "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_tax_id FROM credit_memos "
							"WHERE gl_entries_tax_id IS NOT NULL "
						"UNION SELECT gl_entry_id FROM credit_memo_items "
							"WHERE gl_entry_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM inventory_transactions "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_id FROM loans "
							"WHERE gl_entries_id IS NOT NULL "
						"UNION SELECT gl_entries_total_id FROM loan_payments "
							"WHERE gl_entries_total_id IS NOT NULL "
						"UNION SELECT gl_entries_principal_id FROM loan_payments "
							"WHERE gl_entries_principal_id IS NOT NULL "
						"UNION SELECT gl_entries_interest_id FROM loan_payments "
							"WHERE gl_entries_interest_id IS NOT NULL), "
						# and the columns that claim a whole transaction rather
						# than one of its lines
						"claimed AS "
						"(SELECT gl_transaction_id AS transaction_id "
							"FROM incoming_invoices "
							"WHERE gl_transaction_id IS NOT NULL "
						"UNION SELECT gl_transaction_payment_id "
							"FROM purchase_orders "
							"WHERE gl_transaction_payment_id IS NOT NULL "
						"UNION SELECT account_transaction_id "
							"FROM payroll.emp_payments "
							"WHERE account_transaction_id IS NOT NULL) "
					"SELECT t.id, "
						"t.date_inserted, "
						"count(e.id) AS lines, "
						"COALESCE(SUM(CASE WHEN e.debit_account IS NOT NULL "
							"THEN e.amount ELSE 0 END), 0.00) AS debits, "
						"COALESCE(SUM(CASE WHEN e.credit_account IS NOT NULL "
							"THEN e.amount ELSE 0 END), 0.00) AS credits, "
						"min(e.date_inserted) AS first_line_date, "
						"max(e.date_inserted) AS last_line_date, "
						"count(*) FILTER (WHERE e.reconciled) AS reconciled_lines, "
						"count(a.entry_id) AS attached_lines, "
						"(t.id IN (SELECT transaction_id FROM claimed)) "
							"AS header_claimed "
					"FROM gl_transactions AS t "
					"LEFT JOIN gl_entries AS e ON e.gl_transaction_id = t.id "
					"LEFT JOIN attached AS a ON a.entry_id = e.id "
					"GROUP BY t.id "
					"HAVING count(e.id) = 0 "
						"OR COALESCE(SUM(CASE WHEN e.debit_account IS NOT NULL "
							"THEN e.amount ELSE 0 END), 0.00) "
						"<> COALESCE(SUM(CASE WHEN e.credit_account IS NOT NULL "
							"THEN e.amount ELSE 0 END), 0.00) "
					"ORDER BY t.date_inserted, t.id")
	rows = cursor.fetchall()
	cursor.close()
	return rows


def transaction_entries (transaction_ids):
	'''the lines of the given transactions, as (id, transaction_id, date,
	amount, debit_account, debit_name, credit_account, credit_name, reconciled,
	check_number, description, documents). An account number comes back 0 and a
	name '' on the side an entry does not have.

	documents names whichever source documents claim the line, comma separated,
	or '' for a line nothing references. Every column in the schema that points
	at gl_entries.id gets a branch, each selecting the entry id so a document
	can be traced back to the line that produced it - which is what stops this
	being gl_entry_lookup, whose deduplicating UNION leaves the entry id out
	and so cannot say which of several entries a document belongs to. UNION ALL
	and string_agg rather than picking one: an entry really can be claimed
	twice, and hiding that would hide the reason it cannot be repaired.

	Restricting each branch to the lines in scope is what makes this quick. The
	same query resolving through a correlated subquery per row took ninety times
	as long on the same data'''
	cursor = DB.cursor()
	cursor.execute("WITH scope AS "
						"(SELECT id FROM gl_entries "
							"WHERE gl_transaction_id = ANY (%(ids)s)), "
					"docs AS "
						"(SELECT gl_entries_id AS entry_id, "
								"'Invoice ' || invoice_id::text AS document "
							"FROM invoice_items "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, 'Invoice ' || id::text "
							"FROM invoices "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_tax_id, "
								"'Invoice ' || id::text || ' tax' "
							"FROM invoices "
							"WHERE gl_entries_tax_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, "
								"'Purchase order ' || purchase_order_id::text "
							"FROM purchase_order_items "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, "
								"'Purchase order ' || id::text "
							"FROM purchase_orders "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entry_id, "
								"'Incoming invoice ' || id::text "
							"FROM incoming_invoices "
							"WHERE gl_entry_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entry_expense_id, "
								"'Incoming invoice ' "
								"|| incoming_invoices_id::text || ' expense' "
							"FROM incoming_invoices_gl_entry_expenses_ids "
							"WHERE gl_entry_expense_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, 'Payment ' || id::text "
							"FROM payments_incoming "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_deposit_id, "
								"'Deposit of payment ' || id::text "
							"FROM payments_incoming "
							"WHERE gl_entries_deposit_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, "
								"'Credit memo ' || id::text "
							"FROM credit_memos "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_tax_id, "
								"'Credit memo ' || id::text || ' tax' "
							"FROM credit_memos "
							"WHERE gl_entries_tax_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entry_id, "
								"'Credit memo ' || credit_memo_id::text "
							"FROM credit_memo_items "
							"WHERE gl_entry_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, "
								"'Inventory movement ' || id::text "
							"FROM inventory_transactions "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_id, 'Loan ' || id::text "
							"FROM loans "
							"WHERE gl_entries_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_total_id, "
								"'Loan payment ' || id::text "
							"FROM loan_payments "
							"WHERE gl_entries_total_id IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_principal_id, "
								"'Loan payment ' || id::text || ' principal' "
							"FROM loan_payments "
							"WHERE gl_entries_principal_id "
								"IN (SELECT id FROM scope) "
						"UNION ALL SELECT gl_entries_interest_id, "
								"'Loan payment ' || id::text || ' interest' "
							"FROM loan_payments "
							"WHERE gl_entries_interest_id "
								"IN (SELECT id FROM scope)) "
					"SELECT e.id, "
						"e.gl_transaction_id, "
						"e.date_inserted, "
						"e.amount, "
						"COALESCE(e.debit_account, 0), "
						"COALESCE(da.name, ''), "
						"COALESCE(e.credit_account, 0), "
						"COALESCE(ca.name, ''), "
						"e.reconciled, "
						"COALESCE(e.check_number, 0), "
						"COALESCE(e.transaction_description, ''), "
						"COALESCE(string_agg(DISTINCT d.document, ', '), '') "
					"FROM gl_entries AS e "
					"LEFT JOIN gl_accounts AS da ON da.number = e.debit_account "
					"LEFT JOIN gl_accounts AS ca ON ca.number = e.credit_account "
					"LEFT JOIN docs AS d ON d.entry_id = e.id "
					"WHERE e.gl_transaction_id = ANY (%(ids)s) "
					"GROUP BY e.id, da.name, ca.name "
					"ORDER BY e.gl_transaction_id, e.id",
					{'ids': list(transaction_ids)})
	rows = cursor.fetchall()
	cursor.close()
	return rows
