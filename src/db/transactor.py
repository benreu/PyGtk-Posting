# transactor.py
#
# Copyright (C) 2016 - reuben
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


from datetime import datetime

class Deposit:
	def __init__(self, db, date):
		
		self.db = db
		self.cursor = db.cursor()
		self.date = date
		self.cursor.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = self.cursor.fetchone()[0]

	def cash (self, cash_deposit, cash_account):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s)", 
					(cash_account, cash_deposit, self.transaction_id))

	def check (self, amount):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), %s, %s)", 
					(amount, self.transaction_id))

	def bank (self, amount, checking_account):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id", 
					(checking_account,  amount, self.date,  "Deposit",
					self.transaction_id))
		deposit_id = self.cursor.fetchone()[0]
		return deposit_id

class CustomerInvoicePayment:
	def __init__ (self, db, date, total):

		self.db = db
		self.cursor = db.cursor()
		self.date = date
		self.total = total
		self.cursor.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = self.cursor.fetchone()[0]

	def bank_check (self, payment_id):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id", 
					(self.total, self.transaction_id))
		pi_id = self.cursor.fetchone()[0]
		self.cursor.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))

	def cash (self, payment_id):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'cash_payment'), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id", 
					(self.total, self.transaction_id)) 
		pi_id = self.cursor.fetchone()[0]
		self.cursor.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))

	def credit_card (self, payment_id):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'credit_card_payment'), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id", 
					(self.total, self.transaction_id)) 
		pi_id = self.cursor.fetchone()[0]
		self.cursor.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))

	def post_offset (self, account_number, amount):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES (%s, (SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s)", 
					(account_number, amount, self.transaction_id))

	def customer_discount (self, discount):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
						"WHERE function = 'post_invoice'), "
						"(SELECT account FROM gl_account_flow "
						"WHERE function = 'customer_discount'), %s, %s)", 
					(discount, self.transaction_id))

class ServiceProviderPayment :
	def __init__ (self, db, date, total):

		self.db = db
		self.cursor = db.cursor()
		self.date = date
		self.total = total
		self.cursor.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = self.cursor.fetchone()[0]
		
	def check_payment(self, amount, check_number, checking_account, description):
		self.cursor.execute("INSERT INTO gl_entries "
							"(credit_account, amount, check_number, "
							"gl_transaction_id, date_inserted, "
							"transaction_description) "
							"VALUES (%s, %s, %s, %s, %s, %s)", 
							(checking_account, amount, check_number, 
							self.transaction_id, self.date, description))
	
	def transfer (self, amount, description, checking_account):
		self.cursor.execute("INSERT INTO gl_entries "
							"(credit_account, amount, date_inserted, "
							"transaction_description, gl_transaction_id) "
							"VALUES (%s, %s, %s, %s, %s)", 
							(checking_account, amount, self.date, description, 
							self.transaction_id))

	def credit_card_payment (self, amount, description, credit_card):
		self.cursor.execute("INSERT INTO gl_entries "
							"(credit_account, amount, date_inserted, "
							"transaction_description, gl_transaction_id) "
							"VALUES (%s, %s, %s, %s, %s)", 
							(credit_card, amount, self.date, description, 
							self.transaction_id))

	def cash_payment (self, amount, cash_account):
		self.cursor.execute("INSERT INTO gl_entries "
							"(credit_account, amount, "
							"gl_transaction_id) VALUES (%s, %s, %s)", 
							(cash_account, amount, self.transaction_id))

	def expense (self, amount, expense_account_number):
		self.cursor.execute("INSERT INTO gl_entries "
							"(debit_account, amount, "
							"gl_transaction_id) VALUES (%s, %s, %s)", 
							(expense_account_number, amount, 
							self.transaction_id))

class LoanPayment:
	def __init__(self, db, date, total, contact_id):

		self.db = db
		self.cursor = db.cursor()
		self.total = total
		self.date = date
		self.cursor.execute ("INSERT INTO gl_transactions "
							"(date_inserted, contact_id) "
							"VALUES (%s, %s) RETURNING id", 
							(date, contact_id))
		self.transaction_id = self.cursor.fetchone()[0]
		
	def credit_card (self, credit_card_account):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(credit_card_account, self.total, self.transaction_id))
		return self.cursor.fetchone()[0]

	def bank_check (self, checking_account, check_number, contact_name):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, check_number, gl_transaction_id, "
					"date_inserted, transaction_description) "
					"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", 
					(checking_account, self.total, check_number, 
					self.transaction_id, self.date, contact_name))
		return self.cursor.fetchone()[0]

	def cash (self, cash_account):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(cash_account, self.total, self.transaction_id))
		return self.cursor.fetchone()[0]

	def bank_transfer (self, checking_account, transaction_number):
		self.cursor.execute("INSERT INTO gl_entries "
					"(credit_account, amount, transaction_description, "
					"date_inserted, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id", 
					(checking_account, self.total, transaction_number, 
					self.date, self.transaction_id))
		return self.cursor.fetchone()[0]

	def principal (self, principal_account, amount):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(principal_account, amount, self.transaction_id))
		return self.cursor.fetchone()[0]

	def interest (self, expense_account, amount):
		self.cursor.execute("INSERT INTO gl_entries "
					"(debit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(expense_account, amount, self.transaction_id))
		return self.cursor.fetchone()[0]
					
class VendorPayment :
	def __init__ (self, db, date, total, description):

		self.db = db
		self.cursor = db.cursor()
		self.date = date
		self.total = total
		self.cursor.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = self.cursor.fetchone()[0]
		self.cursor.execute("INSERT INTO gl_entries (debit_account, amount, "
							"gl_transaction_id, transaction_description) "
							"VALUES ((SELECT account FROM gl_account_flow "
							"WHERE function = 'post_purchase_order'), "
							"%s, %s, %s)",
							(total, self.transaction_id, description))
		
	def credit_card (self, c_c_account_number, amount, date):
		self.cursor.execute("INSERT INTO gl_entries "
						"(credit_account, amount, date_inserted, "
						" gl_transaction_id) "
						"VALUES (%s, %s, %s, %s)", 
						(c_c_account_number, amount, date, self.transaction_id))

	def cash (self, cash_account_number):
		self.cursor.execute("INSERT INTO gl_entries "
						"(credit_account, amount, date_inserted, "
						" gl_transaction_id) "
						"VALUES (%s, %s, %s, %s)", 
						(cash_account_number, self.total, self.date, self.transaction_id))

def cancel_invoice (db, datetime, invoice_id):
	c = db.cursor()
	c.execute("SELECT gt.id FROM gl_transactions AS gt "
					"JOIN gl_entries AS ge ON ge.gl_transaction_id = gt.id "
					"JOIN invoices ON invoices.gl_entries_id = ge.id "
					"WHERE invoices.id = %s", (invoice_id,))
	t_id = c.fetchone()[0]
	c.execute("WITH credits AS "
				"(SELECT amount, credit_account, gl_transaction_id FROM gl_entries "
				"WHERE gl_transaction_id = %s AND credit_account IS NOT NULL"
					"), "
				"debits AS "
				"(SELECT amount, debit_account, gl_transaction_id FROM gl_entries "
				"WHERE gl_transaction_id = %s AND debit_account IS NOT NULL"
					"),"
				"insert_debits AS "
				"(INSERT INTO gl_entries "
					"(amount, debit_account, gl_transaction_id) "
					"SELECT * FROM credits"
				") "
				"INSERT INTO gl_entries "
					"(amount, credit_account, gl_transaction_id) "
					"SELECT * FROM debits"
				, (t_id, t_id))
	c.close()

def post_credit_memo(db, credit_memo_id):
	c = db.cursor()
	c.execute ("WITH gl_transaction AS "
					"(INSERT INTO gl_transactions (date_inserted) "
					"VALUES (CURRENT_DATE) RETURNING id), "
				"gl_entry AS "
				"(INSERT INTO gl_entries "
					"(credit_account,"
					"amount, "
					"gl_transaction_id, "
					"date_inserted"
					") "
					"VALUES "
					"((SELECT account FROM gl_account_flow "
						"WHERE function = 'post_credit_memo'), "
					"(SELECT amount_owed FROM credit_memos WHERE id = %s), "
					"(SELECT id FROM gl_transaction), "
					"CURRENT_DATE"
					")RETURNING id "
				"), "
				"gl_tax_entry AS "
				"(INSERT INTO gl_entries "
					"(debit_account,"
					"amount, "
					"gl_transaction_id, "
					"date_inserted"
					") "
					"VALUES "
					"((SELECT account FROM gl_account_flow "
						"WHERE function = 'credit_memo_returned_taxes'), "
					"(SELECT tax FROM credit_memos WHERE id = %s), "
					"(SELECT id FROM gl_transaction), "
					"CURRENT_DATE"
					")RETURNING id "
				"), "
				"update_credit_memos_entry_ids AS "
				"(UPDATE credit_memos "
					"SET (gl_entries_id, gl_entries_tax_id) = "
					"((SELECT id FROM gl_entry), (SELECT id FROM gl_tax_entry))"
					"WHERE id = %s)"
				"SELECT default_expense_account, cmi.ext_price, cmi.id, "
					"(SELECT id FROM gl_transaction) "
					"FROM products AS p "
					"JOIN invoice_items AS ii ON ii.product_id = p.id "
					"JOIN credit_memo_items AS cmi "
						"ON cmi.invoice_item_id = ii.id "
					"WHERE (cmi.credit_memo_id, cmi.deleted) = (%s, False) "
					"ORDER BY cmi.id", 
				(credit_memo_id, credit_memo_id, credit_memo_id, credit_memo_id)) 
	for row in c.fetchall():
		account = row[0]
		amount = row[1]
		cmi_id = row[2]
		transaction_id = row[3]
		c.execute(	"WITH cte AS "
						"(INSERT INTO gl_entries AS ge "
						"(debit_account, amount, gl_transaction_id) VALUES "
						"(%s, %s, %s) RETURNING id "
						") "
					"UPDATE credit_memo_items SET gl_entry_id = "
					"(SELECT id FROM cte) "
					"WHERE id = %s", 
					(account, amount, transaction_id, cmi_id))
		
	c.close()

def post_invoice_receivables (db, amount, date, invoice_id, gl_entries_id):
	cursor = db.cursor()
	if gl_entries_id != None:
		cursor.execute("UPDATE gl_entries SET amount = %s WHERE id = %s", 
														(amount, gl_entries_id))
	else:
		cursor.execute("WITH new_row AS "
								"(INSERT INTO gl_transactions (date_inserted) "
								"VALUES (%s) RETURNING id), "
							"entry_row AS (INSERT INTO gl_entries "
								"(debit_account, amount, gl_transaction_id) "
								"VALUES ((SELECT account FROM gl_account_flow "
								"WHERE function = 'post_invoice'), %s, "
								"(SELECT id FROM new_row)) RETURNING id) "
						"UPDATE invoices SET (gl_entries_id) = "
						"((SELECT id FROM entry_row)) WHERE id = %s",
						(date, amount, invoice_id))
	cursor.close()

def post_invoice_accounts (db, date, invoice_id):
	cursor = db.cursor()
	cursor.execute ("SELECT gl_transactions.id FROM gl_transactions "
					"JOIN gl_entries "
						"ON gl_entries.gl_transaction_id = gl_transactions.id "
					"JOIN invoices ON invoices.gl_entries_id = gl_entries.id "
					"WHERE invoices.id = %s", (invoice_id,))
	transaction_id = cursor.fetchone()[0]
	cursor.execute("SELECT SUM(tax) AS tax, tax_received_account AS account "
					"FROM invoice_items AS ili "
					"JOIN tax_rates ON tax_rates.id = ili.tax_rate_id "
					"WHERE invoice_id = %s AND gl_entries_id IS NULL "
					"GROUP BY tax_rates.tax_received_account", 
					(invoice_id,))
	for row in cursor.fetchall():
		tax = row[0]
		account = row[1]
		cursor.execute("INSERT INTO gl_entries "
						"(amount, credit_account, gl_transaction_id, "
						"date_inserted) VALUES "
						"(%s, %s, %s, %s)", 
						(tax, account, transaction_id, date))
	cursor.execute("SELECT ili.id, ext_price, revenue_account "
					"FROM invoice_items AS ili "
					"JOIN products ON products.id = ili.product_id "
					"WHERE invoice_id = %s AND gl_entries_id IS NULL", 
					(invoice_id,))
	for row in cursor.fetchall():
		line_id = row[0]
		revenue = row[1]
		account = row[2]
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
						"(amount, credit_account, gl_transaction_id, "
						"date_inserted) VALUES "
						"(%s, %s, %s, %s) RETURNING id) "
						"UPDATE invoice_items SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s", 
						(revenue, account, transaction_id, date, line_id))
	cursor.close()
	
def post_purchase_order (db, amount, po_id):
	cursor = db.cursor()
	cursor.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (CURRENT_DATE) RETURNING id")
	transaction_id = cursor.fetchone()[0]
	cursor.execute("INSERT INTO gl_entries "
				"(credit_account, amount, gl_transaction_id, date_inserted) "
				"VALUES ((SELECT account FROM gl_account_flow "
				"WHERE function = 'post_purchase_order'), %s, %s, CURRENT_DATE) RETURNING id", 
				(amount, transaction_id)) 
	gl_entries_id = cursor.fetchone()[0]
	cursor.execute("UPDATE purchase_orders SET gl_entries_id = "
					"%s WHERE id = %s", (gl_entries_id, po_id))
	cursor.close()

def post_purchase_order_accounts (db, po_id, date):
	cursor = db.cursor()
	cursor.execute ("SELECT gl_transactions.id FROM gl_transactions "
					"JOIN gl_entries "
						"ON gl_entries.gl_transaction_id = gl_transactions.id "
					"JOIN purchase_orders "
						"ON purchase_orders.gl_entries_id = gl_entries.id "
					"WHERE purchase_orders.id = %s", (po_id,))
	gl_transaction_id = cursor.fetchone()[0]
	cursor.execute("SELECT id, ext_price, expense_account "
							"FROM purchase_order_line_items "
							"WHERE purchase_order_id = %s ", (po_id,))
	for row in cursor.fetchall():
		row_id = row[0]
		amount = row[1]
		expense_account_number = row[2]
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
						"(amount, debit_account, gl_transaction_id, "
						"date_inserted) VALUES "
						"(%s, %s, %s, %s) RETURNING id) "
						"UPDATE purchase_order_line_items SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(amount, expense_account_number, 
						gl_transaction_id, date, row_id))
	cursor.close()

def vendor_check_payment(db, date, amount, checking_account_number,
												check_number, customer_name):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, debit_account, amount, check_number, "
				"transaction_description, gl_transaction_id) "
				"VALUES (%s, (SELECT account FROM gl_account_flow "
				"WHERE function = 'post_purchase_order'), %s, %s, %s, "
					"(SELECT id FROM new_row))", 
				(date, checking_account_number, amount, check_number, 
				customer_name))
	cursor.close()

def vendor_debit_payment (db, date, amount, checking_account_number,
															transaction_number):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, debit_account, amount, "
				"transaction_description, gl_transaction_id) "
				"VALUES (%s, (SELECT account FROM gl_account_flow "
				"WHERE function = 'post_purchase_order'), %s, %s, "
					"(SELECT id FROM new_row))", 
				(date, checking_account_number, amount, transaction_number))
	cursor.close()

def bank_to_credit_card_transfer(db, bank_account, credit_card_account, amount, 
								date, transaction_number):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
					"INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, NULL, %s, %s, %s, (SELECT id FROM new_row)), "
					"(NULL, %s, %s, %s, %s, (SELECT id FROM new_row))", 
					(date, bank_account, amount, date, transaction_number, 
					credit_card_account, amount, date, transaction_number))
	cursor.close()

def credit_card_fee_reward(db, date, credit_card_account, gl_account, amount, 
																description):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, debit_account, amount, "
				"transaction_description, fees_rewards, gl_transaction_id) "
				"VALUES (%s, %s, %s, %s, True, (SELECT id FROM new_row))", 
				(date, credit_card_account, gl_account, amount, description))
	cursor.close()

def bank_charge(db, bank_account, date, amount, description, account_number):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, debit_account, amount, "
				"transaction_description, fees_rewards, gl_transaction_id) "
				"VALUES (%s, %s, %s, %s, True, "
					"(SELECT id FROM new_row))", 
				(date, bank_account, account_number, amount, description))
	cursor.close()

def post_voided_check (db, bank_account, date, cheque_number):
	cursor = db.cursor()
	cursor.execute(	"WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
					"INSERT INTO gl_entries "
					"(debit_account, credit_account, check_number, amount, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, 0.00, 'Voided check', "
					"(SELECT id FROM new_row))", 
					(date, bank_account, bank_account, cheque_number))
	cursor.close()

def double_entry_transaction (db, date, debit_account, credit_account, 
													amount, description):
	cursor = db.cursor()
	cursor.execute(	"WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
					"INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, (SELECT id FROM new_row))", 
					(date, credit_account, debit_account, amount, description))
	cursor.close()

def post_misc_check_payment (db, date, amount, payment_id, revenue_account):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(gl_transaction_id, debit_account, credit_account, amount) "
				"VALUES ((SELECT id FROM new_row), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), %s, %s) RETURNING id", 
				(date, revenue_account, amount))
	pi_id = cursor.fetchone()[0]
	cursor.execute("UPDATE payments_incoming "
				"SET gl_entries_id = %s "
				"WHERE id = %s", (pi_id, payment_id))
	cursor.close()

def post_misc_cash_payment (db, date, amount, payment_id, revenue_account):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(gl_transaction_id, debit_account, credit_account, amount) "
				"VALUES ((SELECT id FROM new_row), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'cash_payment'), %s, %s) RETURNING id", 
				(date, revenue_account, amount))
	pi_id = cursor.fetchone()[0]
	cursor.execute("UPDATE payments_incoming "
				"SET gl_entries_id = %s "
				"WHERE id = %s", (pi_id, payment_id))
	cursor.close()

def post_misc_credit_card_payment (db, date, amount, payment_id, revenue_account):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(gl_transaction_id, debit_account, credit_account, amount) "
				"VALUES ((SELECT id FROM new_row), "
				"(SELECT account FROM gl_account_flow "
				"WHERE function = 'credit_card_payment'), %s, %s) RETURNING id", 
				(date, revenue_account, amount))
	pi_id = cursor.fetchone()[0]
	cursor.execute("UPDATE payments_incoming "
				"SET gl_entries_id = %s "
				"WHERE id = %s", (pi_id, payment_id))
	cursor.close()

def switch_to_accrual_based (db):
	cursor = db.cursor()
	cursor.execute ("SELECT id FROM invoices "
					"WHERE (canceled, posted, paid) = (False, True, False)")
	for row in cursor.fetchall():
		invoice_id = row[0]
		post_invoice_accounts (db, datetime.today(), invoice_id)
	cursor.execute ("SELECT id FROM purchase_orders "
					"WHERE (paid, canceled, closed) = (False, False, True)")
	for row in cursor.fetchall():
		po_id = row[0]
		post_purchase_order_accounts (db, po_id)
	cursor.close()

def create_loan (db, date, amount, liability_account):
	cursor = db.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(gl_transaction_id, credit_account, amount) "
				"VALUES ((SELECT id FROM new_row), %s, %s) RETURNING id", 
				(date, liability_account, amount))
	gl_entries_id = cursor.fetchone()[0]
	cursor.close()
	return gl_entries_id




