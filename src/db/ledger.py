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
	holds a positive amount and two nullable account columns, so the side is
	which column is set, not a sign, and a row may be two sided - a whole
	balanced entry on one row - or one of a pair of siblings under the same
	gl_transaction_id. Emitting one row per non null side counts a two sided row
	on both sides and a one sided row once, in a single scan of the table.

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
