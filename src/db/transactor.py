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
from db_connection import DB

class Deposit:
	def __init__(self, date):
		
		self.date = date
		c = DB.cursor()
		c.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = c.fetchone()[0]
		c.close()

	def cash (self, cash_deposit, cash_account):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s)", 
					(cash_account, cash_deposit, self.transaction_id))
		c.close()

	def check (self, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), %s, %s)", 
					(amount, self.transaction_id))
		c.close()

	def bank (self, amount, checking_account):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id", 
					(checking_account,  amount, self.date,  "Deposit",
					self.transaction_id))
		deposit_id = c.fetchone()[0]
		c.close()
		return deposit_id

class CustomerInvoicePayment:
	def __init__ (self, date, total):

		self.date = date
		self.total = total
		c = DB.cursor()
		c.execute ("INSERT INTO gl_transactions (date_inserted) "
							"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = c.fetchone()[0]
		c.close()

	def bank_check (self, payment_id):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id", 
					(self.total, self.transaction_id))
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def cash (self, payment_id):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'cash_payment'), "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id", 
					(self.total, self.transaction_id)) 
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def credit_card (self, payment_id, account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES (%s, "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s) RETURNING id",
					(account_number, self.total, self.transaction_id))
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def post_offset (self, account_number, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, gl_transaction_id) "
					"VALUES (%s, (SELECT account FROM gl_account_flow "
					"WHERE function = 'post_invoice'), %s, %s)", 
					(account_number, amount, self.transaction_id))
		c.close()

	def customer_discount (self, discount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, gl_transaction_id) "
					"VALUES ((SELECT account FROM gl_account_flow "
						"WHERE function = 'post_invoice'), "
						"(SELECT account FROM gl_account_flow "
						"WHERE function = 'customer_discount'), %s, %s)", 
					(discount, self.transaction_id))
		c.close()

class ServiceProviderPayment :
	def __init__ (self, date, total):

		self.date = date
		self.total = total
		c = DB.cursor()
		c.execute ("INSERT INTO gl_transactions (date_inserted) "
					"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = c.fetchone()[0]
		c.close()
		self.incoming_invoice_id = None # updated from the rest of Posting
		
	def check_payment(self, amount, check_number, checking_account, description):
		c = DB.cursor()
		c.execute("WITH cte AS "
							"(INSERT INTO gl_entries "
							"(credit_account, amount, check_number, "
							"gl_transaction_id, date_inserted, "
							"transaction_description) "
							"VALUES (%s, %s, %s, %s, %s, %s) "
							"RETURNING id) "
						"UPDATE incoming_invoices "
						"SET gl_entry_id = (SELECT id FROM cte) "
						"WHERE id = %s", 
						(checking_account, amount, check_number, 
						self.transaction_id, self.date, description, 
						self.incoming_invoice_id))
		c.close()
	
	def transfer (self, amount, description, checking_account):
		c = DB.cursor()
		c.execute("WITH cte AS "
							"(INSERT INTO gl_entries "
							"(credit_account, amount, date_inserted, "
							"transaction_description, gl_transaction_id) "
							"VALUES (%s, %s, %s, %s, %s) "
							"RETURNING id) "
						"UPDATE incoming_invoices "
						"SET gl_entry_id = (SELECT id FROM cte) "
						"WHERE id = %s", 
						(checking_account, amount, self.date, description, 
						self.transaction_id, self.incoming_invoice_id))
		c.close()

	def credit_card_payment (self, amount, description, credit_card):
		c = DB.cursor()
		c.execute("WITH cte AS "
							"(INSERT INTO gl_entries "
							"(credit_account, amount, date_inserted, "
							"transaction_description, gl_transaction_id) "
							"VALUES (%s, %s, %s, %s, %s) "
							"RETURNING id) "
						"UPDATE incoming_invoices "
						"SET gl_entry_id = (SELECT id FROM cte) "
						"WHERE id = %s", 
						(credit_card, amount, self.date, description, 
						self.transaction_id, self.incoming_invoice_id))
		c.close()

	def cash_payment (self, amount, cash_account):
		c = DB.cursor()
		c.execute("WITH cte AS "
							"(INSERT INTO gl_entries "
							"(credit_account, amount, date_inserted, "
							"gl_transaction_id) VALUES (%s, %s, %s, %s) "
							"RETURNING id) "
						"UPDATE incoming_invoices "
						"SET gl_entry_id = (SELECT id FROM cte) "
						"WHERE id = %s", 
						(cash_account, amount, self.date, 
						self.transaction_id, self.incoming_invoice_id))
		c.close()

	def expense (self, amount, expense_account_number, remark):
		c = DB.cursor()
		c.execute("WITH cte AS "
							"(INSERT INTO gl_entries "
							"(debit_account, amount, date_inserted, "
							"gl_transaction_id) VALUES (%s, %s, %s, %s) "
							"RETURNING id) "
						"INSERT INTO incoming_invoices_gl_entry_expenses_ids "
						"(gl_entry_expense_id, incoming_invoices_id, remark) "
						"VALUES ((SELECT id FROM cte), %s, %s) ", 
						(expense_account_number, amount, self.date, 
						self.transaction_id, self.incoming_invoice_id, remark))
		c.close()

class LoanPayment:
	def __init__(self, date, total, contact_id):

		self.total = total
		self.date = date
		c = DB.cursor()
		c.execute ("INSERT INTO gl_transactions "
							"(date_inserted, contact_id) "
							"VALUES (%s, %s) RETURNING id", 
							(date, contact_id))
		self.transaction_id = c.fetchone()[0]
		c.close()
		
	def credit_card (self, credit_card_account):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(credit_card_account, self.total, self.transaction_id))
		value = c.fetchone()[0]
		c.close()
		return value

	def bank_check (self, checking_account, check_number, contact_name):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, check_number, gl_transaction_id, "
					"date_inserted, transaction_description) "
					"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", 
					(checking_account, self.total, check_number, 
					self.transaction_id, self.date, contact_name))
		value = c.fetchone()[0]
		c.close()
		return value

	def cash (self, cash_account):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(cash_account, self.total, self.transaction_id))
		value = c.fetchone()[0]
		c.close()
		return value

	def bank_transfer (self, checking_account, transaction_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, transaction_description, "
					"date_inserted, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id", 
					(checking_account, self.total, transaction_number, 
					self.date, self.transaction_id))
		value = c.fetchone()[0]
		c.close()
		return value

	def principal (self, principal_account, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(principal_account, amount, self.transaction_id))
		value = c.fetchone()[0]
		c.close()
		return value

	def interest (self, expense_account, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, amount, gl_transaction_id) "
					"VALUES (%s, %s, %s) RETURNING id", 
					(expense_account, amount, self.transaction_id))
		value = c.fetchone()[0]
		c.close()
		return value
					
class VendorPayment :
	def __init__ (self, date, total, description = ''):

		self.date = date
		self.total = total
		c = DB.cursor()
		c.execute ("INSERT INTO gl_transactions (date_inserted) "
					"VALUES (%s) RETURNING id", (date,))
		self.transaction_id = c.fetchone()[0]
		c.execute("INSERT INTO gl_entries (debit_account, amount, "
					"gl_transaction_id, transaction_description) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s)",
					(total, self.transaction_id, description))
		c.close()
		
	def credit_card (self, c_c_account_number, amount, date, vendor_name):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, date_inserted, "
					" gl_transaction_id, transaction_description) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id",
					(c_c_account_number, amount, date, self.transaction_id,
					vendor_name))
		row_id = c.fetchone()[0]
		c.close()
		return row_id

	def cash (self, cash_account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, date_inserted, "
					" gl_transaction_id) "
					"VALUES (%s, %s, %s, %s) RETURNING id", 
					(cash_account_number, self.total, 
					self.date, self.transaction_id))
		row_id = c.fetchone()[0]
		c.close()
		return row_id

	def check (self, checking_account_number, check_number, customer_name):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, date_inserted, "
					"check_number, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, (SELECT account FROM gl_account_flow "
								"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s, %s, %s) "
					"RETURNING id", 
					(checking_account_number, self.total, self.date,
					check_number, customer_name, self.transaction_id))
		row_id = c.fetchone()[0]
		c.close()
		return row_id

	def debit (self, checking_account, transaction_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, " 
						"(SELECT account FROM gl_account_flow "
						"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s, %s) RETURNING id", 
					(checking_account, self.total, self.date, 
					transaction_number, self.transaction_id))
		row_id = c.fetchone()[0]
		c.close()
		return row_id

def cancel_invoice (datetime, invoice_id):
	c = DB.cursor()
	c.execute("SELECT gt.id FROM gl_transactions AS gt "
				"JOIN gl_entries AS ge ON ge.gl_transaction_id = gt.id "
				"JOIN invoices ON invoices.gl_entries_id = ge.id "
				"WHERE invoices.id = %s", (invoice_id,))
	row = c.fetchone()
	if row is None:
		# Cash-basis invoices have no GL transaction until paid,
		# so there's nothing to reverse.
		c.close()
		return
	t_id = row[0]
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

def post_credit_memo(credit_memo_id):
	c = DB.cursor()
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

def post_invoice_receivables ():
	pass

def post_inventory_adjustment (date, description, amount, debit_account, credit_account):
	cursor = DB.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions (date_inserted) "
						"VALUES (%s) RETURNING id) "
					"INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s, (SELECT id FROM new_row)) "
					"RETURNING id",
					(date, debit_account, credit_account, amount, date, description))
	gl_entries_id = cursor.fetchone()[0]
	cursor.close()
	return gl_entries_id

def post_invoice_accounts (date, invoice_id, amount, gl_entries_id = None):
	cursor = DB.cursor()
	if gl_entries_id != None: # used for updates
		cursor.execute ("SELECT gl_transactions.id FROM gl_transactions "
						"JOIN gl_entries "
							"ON gl_entries.gl_transaction_id = gl_transactions.id "
						"JOIN invoices ON invoices.gl_entries_id = gl_entries.id "
						"WHERE invoices.id = %s", (invoice_id,))
		transaction_id = cursor.fetchone()[0]
		cursor.execute("UPDATE gl_entries SET amount = 0.00 "
						"WHERE gl_transaction_id = %s;"
						"UPDATE gl_entries SET amount = %s WHERE id = %s", 
						(transaction_id, amount, gl_entries_id))
	else:
		cursor.execute("WITH new_row AS "
								"(INSERT INTO gl_transactions (date_inserted) "
								"VALUES (%s) RETURNING id), "
							"entry_row AS (INSERT INTO gl_entries "
								"(debit_account, amount, gl_transaction_id) "
								"VALUES ((SELECT account FROM gl_account_flow "
								"WHERE function = 'post_invoice'), %s, "
								"(SELECT id FROM new_row)) RETURNING id), "
							"update AS (UPDATE invoices SET (gl_entries_id) = "
								"((SELECT id FROM entry_row)) WHERE id = %s) "
						"SELECT id FROM new_row",
						(date, amount, invoice_id))
		transaction_id = cursor.fetchone()[0]
	# update or insert tax
	cursor.execute("SELECT SUM(tax) AS tax, tax_received_account "
					"FROM invoice_items AS ili "
					"JOIN tax_rates ON tax_rates.id = ili.tax_rate_id "
					"WHERE invoice_id = %s "
					"GROUP BY tax_rates.tax_received_account", 
					(invoice_id,))
	for row in cursor.fetchall():
		tax = row[0]
		account = row[1]
		cursor.execute("UPDATE gl_entries SET amount = %s "
						"WHERE (gl_transaction_id, credit_account) = (%s, %s) "
						"RETURNING amount", (tax, transaction_id, account))
		for row in cursor.fetchall(): # check for update
			break
		else: # no entry, insert a new one
			cursor.execute("INSERT INTO gl_entries "
							"(amount, credit_account, gl_transaction_id, "
							"date_inserted) VALUES "
							"(%s, %s, %s, %s)", 
							(tax, account, transaction_id, date))
	# insert invoice_items with no gl_entry
	cursor.execute("SELECT ili.id, ext_price, revenue_account "
					"FROM invoice_items AS ili "
					"JOIN products ON products.id = ili.product_id "
					"WHERE (invoice_id, canceled) = (%s, False) "
					"AND gl_entries_id IS NULL", 
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
	# update invoice_items with a gl_entry
	cursor.execute("SELECT ext_price, gl_entries_id "
					"FROM invoice_items AS ili "
					"WHERE (invoice_id, canceled) = (%s, False) "
					"AND gl_entries_id IS NOT NULL", 
					(invoice_id,))
	for row in cursor.fetchall():
		revenue = row[0]
		gl_entries_id = row[1]
		cursor.execute("UPDATE gl_entries SET amount = %s WHERE id = %s", 
						(revenue, gl_entries_id))
	cursor.close()
	
def post_purchase_order (amount, po_id):
	cursor = DB.cursor()
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

def post_purchase_order_accounts (po_id, date):
	cursor = DB.cursor()
	cursor.execute ("SELECT gl_transactions.id FROM gl_transactions "
					"JOIN gl_entries "
						"ON gl_entries.gl_transaction_id = gl_transactions.id "
					"JOIN purchase_orders "
						"ON purchase_orders.gl_entries_id = gl_entries.id "
					"WHERE purchase_orders.id = %s", (po_id,))
	gl_transaction_id = cursor.fetchone()[0]
	#skip lines that already carry an entry, so a purchase order that was
	#corrected before payment does not get its expenses posted twice, and skip
	#canceled lines, which carry a zeroed entry of their own
	cursor.execute("SELECT id, ext_price, expense_account "
							"FROM purchase_order_items "
							"WHERE (purchase_order_id, canceled) = (%s, False) "
							"AND gl_entries_id IS NULL ", (po_id,))
	for row in cursor.fetchall():
		row_id = row[0]
		amount = row[1]
		expense_account_number = row[2]
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
						"(amount, debit_account, gl_transaction_id, "
						"date_inserted) VALUES "
						"(%s, %s, %s, %s) RETURNING id) "
						"UPDATE purchase_order_items SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(amount, expense_account_number,
						gl_transaction_id, date, row_id))
	cursor.close()

def purchase_order_correction_blocked (po_id):
	'''returns a message explaining why this purchase order must not be
	corrected, or None when correcting it is safe'''
	cursor = DB.cursor()
	cursor.execute("SELECT "
						"po.paid OR po.gl_transaction_payment_id IS NOT NULL, "
						"po.canceled, "
						"po.closed, "
						"COALESCE((SELECT bool_or(g.reconciled) "
							"FROM gl_entries AS g "
							"WHERE g.gl_transaction_id = "
								"h.gl_transaction_id), False), "
						"EXISTS (SELECT 1 FROM purchase_order_items "
							"WHERE (purchase_order_id, canceled) = "
								"(po.id, False) "
							"AND expense_account IS NULL) "
					"FROM purchase_orders AS po "
					"LEFT JOIN gl_entries AS h ON h.id = po.gl_entries_id "
					"WHERE po.id = %s", (po_id,))
	row = cursor.fetchone()
	cursor.close()
	DB.rollback()
	if row == None:
		return "This purchase order no longer exists"
	paid, canceled, closed, reconciled, missing_account = row
	if paid == True:
		return "This purchase order is already paid"
	if canceled == True:
		return "This purchase order is canceled"
	if closed == False:
		return "This purchase order is not posted yet"
	if reconciled == True:
		return "The ledger entries for this purchase order are reconciled"
	if missing_account == True:
		return "Every line needs an expense account"
	return None

def repost_purchase_order_accounts (po_id):
	'''re-syncs the ledger entries of an already posted purchase order to its
	current line items. Safe on a purchase order that has no entries yet'''
	cursor = DB.cursor()
	cursor.execute("UPDATE purchase_orders AS po SET (total, amount_due) = "
						"(t.sum, t.sum) "
					"FROM (SELECT COALESCE(SUM(ext_price), 0.00) AS sum "
							"FROM purchase_order_items "
							"WHERE (purchase_order_id, canceled) = "
								"(%s, False)) AS t "
					"WHERE po.id = %s "
					"RETURNING po.total, po.gl_entries_id", (po_id, po_id))
	total, header_gl_entries_id = cursor.fetchone()
	if header_gl_entries_id == None: #closed but not invoiced, nothing posted
		cursor.close()
		return total
	#the accounts payable credit always carries the whole document
	cursor.execute("UPDATE gl_entries SET amount = %s WHERE id = %s "
					"RETURNING gl_transaction_id, date_inserted",
					(total, header_gl_entries_id))
	gl_transaction_id, date = cursor.fetchone()
	cursor.execute("SELECT gl_entries_id, "
						"CASE WHEN canceled THEN 0.00 ELSE ext_price END, "
						"expense_account "
					"FROM purchase_order_items "
					"WHERE purchase_order_id = %s "
					"AND gl_entries_id IS NOT NULL", (po_id,))
	for row in cursor.fetchall():
		cursor.execute("UPDATE gl_entries SET (amount, debit_account) = "
						"(%s, %s) WHERE id = %s", (row[1], row[2], row[0]))
	#lines added after posting only get an expense debit when this document is
	#already carrying them, otherwise a cash based purchase order would
	#recognize the expense before the vendor is paid. The second test catches
	#documents back posted by switch_to_accrual_based
	cursor.execute("SELECT (SELECT accrual_based FROM settings) "
					"OR EXISTS (SELECT 1 FROM purchase_order_items "
						"WHERE purchase_order_id = %s "
						"AND gl_entries_id IS NOT NULL)", (po_id,))
	if cursor.fetchone()[0] == True:
		cursor.execute("SELECT id, ext_price, expense_account "
							"FROM purchase_order_items "
							"WHERE (purchase_order_id, canceled) = (%s, False) "
							"AND gl_entries_id IS NULL", (po_id,))
		for row in cursor.fetchall():
			#reuse the header date so both legs land in the same period
			cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
							"(amount, debit_account, gl_transaction_id, "
							"date_inserted) VALUES "
							"(%s, %s, %s, %s) RETURNING id) "
							"UPDATE purchase_order_items SET gl_entries_id = "
								"((SELECT id FROM new_row)) WHERE id = %s",
							(row[1], row[2], gl_transaction_id, date, row[0]))
	cursor.close()
	return total

def cancel_purchase_order_item (line_id):
	'''soft cancels a line. The ledger entry is zeroed rather than deleted,
	nothing in this program deletes from gl_entries'''
	cursor = DB.cursor()
	cursor.execute("WITH canceled AS "
						"(UPDATE purchase_order_items "
						"SET (qty, price, ext_price, canceled) = "
							"(0, 0.00, 0.00, True) "
						"WHERE id = %s RETURNING id, gl_entries_id), "
					"zeroed AS "
						"(UPDATE gl_entries SET amount = 0.00 "
						"WHERE id = (SELECT gl_entries_id FROM canceled)) "
					"UPDATE inventory_transactions SET qty_in = 0 "
					"WHERE purchase_order_item_id = "
						"(SELECT id FROM canceled)", (line_id,))
	cursor.close()

def purchase_order_inventory_blocked (po_id):
	'''returns a message when the corrected quantities cannot be applied to
	inventory, or None. This reads the corrections already written in the open
	transaction, so it must not commit or roll back; the caller decides'''
	cursor = DB.cursor()
	cursor.execute("SELECT p.name FROM inventory_transactions AS it "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE it.product_id IN (SELECT product_id "
						"FROM purchase_order_items "
						"WHERE purchase_order_id = %s) "
					"GROUP BY p.name "
					"HAVING SUM(it.qty_in) - SUM(it.qty_out) < 0", (po_id,))
	row = cursor.fetchone()
	if row != None:
		cursor.close()
		return "'%s' would go negative in inventory" % row[0]
	cursor.execute("SELECT poli.id FROM purchase_order_items AS poli "
					"JOIN serial_numbers AS sn "
						"ON sn.purchase_order_item_id = poli.id "
					"WHERE poli.purchase_order_id = %s "
					"GROUP BY poli.id, poli.qty "
					"HAVING COUNT(sn.id) > poli.qty", (po_id,))
	row = cursor.fetchone()
	cursor.close()
	if row != None:
		return "Line %s has more serial numbers than its new quantity" % row[0]
	return None

def resync_purchase_order_inventory (po_id):
	'''follows corrected quantities and prices into inventory. Purchase order
	receipts carry no ledger entry, so the receipt rows are updated in place
	rather than offset with an adjusting row'''
	cursor = DB.cursor()
	cursor.execute("SELECT received FROM purchase_orders WHERE id = %s",
					(po_id,))
	if cursor.fetchone()[0] == False: #receive() will pick these up later
		cursor.close()
		return
	cursor.execute("UPDATE inventory_transactions AS it SET (qty_in, price) = "
						"(CASE WHEN poli.canceled THEN 0 "
							"ELSE poli.qty::int END, poli.price) "
					"FROM purchase_order_items AS poli "
					"WHERE it.purchase_order_item_id = poli.id "
					"AND poli.purchase_order_id = %s", (po_id,))
	#lines added after the purchase order was received still need a receipt
	cursor.execute("INSERT INTO inventory_transactions "
						"(purchase_order_item_id, qty_in, product_id, price, "
						"location_id, date_inserted) "
					"SELECT poli.id, poli.qty::int, poli.product_id, poli.price, "
						"COALESCE((SELECT it.location_id "
							"FROM inventory_transactions AS it "
							"JOIN purchase_order_items AS sibling "
								"ON sibling.id = it.purchase_order_item_id "
							"WHERE sibling.purchase_order_id = %s "
							"ORDER BY it.id DESC LIMIT 1), "
							"(SELECT id FROM locations ORDER BY id LIMIT 1)), "
						"CURRENT_DATE "
					"FROM purchase_order_items AS poli "
					"JOIN products AS p ON p.id = poli.product_id "
					"WHERE (poli.purchase_order_id, poli.canceled, "
						"p.inventory_enabled) = (%s, False, True) "
					"AND NOT EXISTS (SELECT 1 FROM inventory_transactions "
						"WHERE purchase_order_item_id = poli.id)",
					(po_id, po_id))
	cursor.close()

def bank_to_credit_card_transfer(bank_account, credit_card_account, amount,
								date, transaction_number):
	cursor = DB.cursor()
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

def credit_card_fee_reward(date, credit_card_account, gl_account, amount, 
																description):
	cursor = DB.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, date_inserted, debit_account, amount, "
				"transaction_description, fees_rewards, gl_transaction_id) "
				"VALUES (%s, %s, %s, %s, %s, True, (SELECT id FROM new_row))", 
				(date, credit_card_account, date, gl_account, amount, description))
	cursor.close()

def bank_charge(bank_account, date, amount, description, account_number):
	cursor = DB.cursor()
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

def post_voided_check (bank_account, date, cheque_number):
	cursor = DB.cursor()
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

class DoubleEntryTransaction :
	def __init__(self, date, description):
		self.date = date
		self.desc = description
		c = DB.cursor()
		c.execute("INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id", 
					(date,))
		self.trans_id = c.fetchone()[0]
		c.close()

	def post_credit_entry (self, amount, account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s)", 
					(account_number, amount, self.date, 
					self.desc, self.trans_id))
		c.close()

	def post_debit_entry (self, amount, account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id) "
					"VALUES (%s, %s, %s, %s, %s)", 
					(account_number, amount, self.date, 
					self.desc, self.trans_id))
		c.close()

class MiscRevenueTransaction :
	def __init__ (self, date):
		self.date = date
		c = DB.cursor()
		c.execute("INSERT INTO gl_transactions "
					"(date_inserted) VALUES (now()) RETURNING id")
		self.trans_id = c.fetchone()[0]
		c.close()

	def post_misc_check_payment (self, amount, payment_id):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
				"(date_inserted, gl_transaction_id, debit_account, amount) "
				"VALUES (%s, %s, "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), %s) RETURNING id", 
				(self.date, self.trans_id, amount))
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def post_misc_cash_payment (self, amount, payment_id):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
				"(date_inserted, gl_transaction_id, debit_account, amount) "
				"VALUES (%s, %s, "
					"(SELECT account FROM gl_account_flow "
					"WHERE function = 'cash_payment'), %s) RETURNING id", 
				(self.date, self.trans_id, amount))
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def post_misc_credit_card_payment (self, amount, payment_id, account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
				"(date_inserted, gl_transaction_id, debit_account, amount) "
				"VALUES (%s, %s, %s, %s) RETURNING id",
				(self.date, self.trans_id, account_number, amount))
		pi_id = c.fetchone()[0]
		c.execute("UPDATE payments_incoming "
					"SET gl_entries_id = %s "
					"WHERE id = %s", (pi_id, payment_id))
		c.close()

	def post_credit_entry (self, revenue_account, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
				"(date_inserted, gl_transaction_id, credit_account, amount) "
				"VALUES (%s, %s, %s, %s)", 
				(self.date, self.trans_id, revenue_account, amount))
		c.close()

def switch_to_accrual_based ():
	cursor = DB.cursor()
	cursor.execute ("SELECT id, amount_due FROM invoices "
					"WHERE (canceled, posted, paid) = (False, True, False)")
	for row in cursor.fetchall():
		invoice_id = row[0]
		amount = row[1]
		post_invoice_accounts (datetime.today(), invoice_id, amount)
	cursor.execute ("SELECT id FROM purchase_orders "
					"WHERE (paid, canceled, closed, invoiced) = "
					"(False, False, True, True)")
	for row in cursor.fetchall():
		po_id = row[0]
		post_purchase_order_accounts (po_id, datetime.today())
	cursor.close()

def post_finance_charge(invoice_id):
	c = DB.cursor()
	c.execute("WITH gl_transaction AS "
					"(INSERT INTO gl_transactions (date_inserted) "
					"VALUES (CURRENT_DATE) RETURNING id), "
				"gl_entry AS "
				"(INSERT INTO gl_entries "
					"(debit_account, credit_account, amount, "
					"gl_transaction_id, date_inserted) "
				"VALUES "
					"((SELECT account FROM gl_account_flow "
						"WHERE function = 'post_invoice'), "
					"(SELECT account FROM gl_account_flow "
						"WHERE function = 'finance_charge_income'), "
					"(SELECT total FROM invoices WHERE id = %s), "
					"(SELECT id FROM gl_transaction), "
					"CURRENT_DATE) RETURNING id) "
				"UPDATE invoices "
				"SET gl_entries_id = (SELECT id FROM gl_entry) "
				"WHERE id = %s",
				(invoice_id, invoice_id))
	c.close()

def create_loan (date, amount, liability_account):
	cursor = DB.cursor()
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




