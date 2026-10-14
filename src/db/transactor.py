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
from decimal import Decimal
import re
from db_connection import DB

def create_draft_purchase_order (vendor_id):
	'''always creates a new open purchase order for this vendor'''
	cursor = DB.cursor()
	cursor.execute("SELECT name FROM contacts WHERE id = %s", (vendor_id,))
	vendor_name = cursor.fetchone()[0]
	cursor.execute("INSERT INTO purchase_orders "
					"(vendor_id, closed, paid, canceled, "
					"received, date_created) "
					"VALUES (%s, False, False, False, False, CURRENT_DATE) "
					"RETURNING id, date_created", (vendor_id, ))
	po_id, date = cursor.fetchone()
	name_str = ""
	for i in vendor_name.split(' '):
		name_str = name_str + i[0:3]
	name = name_str.lower()
	po_date = re.sub("-", "_", str(date))
	document_name = "PO_" + str(po_id) + "_" + name + "_" + po_date
	cursor.execute("UPDATE purchase_orders SET name = %s WHERE id = %s",
					(document_name, po_id))
	cursor.close()
	return po_id

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
					"(credit_account, amount, gl_transaction_id, source_type) "
					"VALUES (%s, %s, %s, 'deposit_cash')", 
					(cash_account, cash_deposit, self.transaction_id))
		c.close()

	def check (self, amount):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, gl_transaction_id, source_type) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'check_payment'), %s, %s, "
					"'deposit_check')", 
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
					"gl_transaction_id, transaction_description, source_type) "
					"VALUES ((SELECT account FROM gl_account_flow "
					"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s, 'vendor_payment')",
					(total, self.transaction_id, description))
		c.close()
		
	def credit_card (self, c_c_account_number, amount, date, vendor_name):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, date_inserted, "
					" gl_transaction_id, transaction_description, source_type) "
					"VALUES (%s, %s, %s, %s, %s, 'vendor_payment') "
					"RETURNING id",
					(c_c_account_number, amount, date, self.transaction_id,
					vendor_name))
		row_id = c.fetchone()[0]
		c.close()
		return row_id

	def cash (self, cash_account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(credit_account, amount, date_inserted, "
					" gl_transaction_id, source_type) "
					"VALUES (%s, %s, %s, %s, 'vendor_payment') RETURNING id", 
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
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, (SELECT account FROM gl_account_flow "
								"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s, %s, %s, 'vendor_payment') "
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
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, " 
						"(SELECT account FROM gl_account_flow "
						"WHERE function = 'post_purchase_order'), "
					"%s, %s, %s, %s, 'vendor_payment') RETURNING id", 
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
	# date_inserted is passed rather than left to its default: the column is NOT
	# NULL DEFAULT now (), so after_gl_entries_inserted never fires and a reversal
	# would otherwise be dated today instead of the date the user canceled on,
	# which lands it in the wrong fiscal year on every report
	# a row carrying both accounts, as a cost of goods sold entry does, matches
	# both arms and so has each of its sides reversed exactly once
	c.execute("WITH credits AS "
				"(SELECT amount, credit_account, gl_transaction_id, %s::date "
				"FROM gl_entries "
				"WHERE gl_transaction_id = %s AND credit_account IS NOT NULL"
					"), "
				"debits AS "
				"(SELECT amount, debit_account, gl_transaction_id, %s::date "
				"FROM gl_entries "
				"WHERE gl_transaction_id = %s AND debit_account IS NOT NULL"
					"),"
				"insert_debits AS "
				"(INSERT INTO gl_entries "
					"(amount, debit_account, gl_transaction_id, date_inserted) "
					"SELECT * FROM credits"
				") "
				"INSERT INTO gl_entries "
					"(amount, credit_account, gl_transaction_id, date_inserted) "
					"SELECT * FROM debits"
				, (datetime, t_id, datetime, t_id))
	c.close()

def post_credit_memo(credit_memo_id):
	c = DB.cursor()
	# the date the memo prints with, the column credit_memo_template reads, so
	# the books cannot disagree with the document the customer is holding.
	# date_inserted is passed rather than left to its default, see cancel_invoice
	c.execute("SELECT COALESCE(dated_for, date_created), gl_entries_id "
				"FROM credit_memos WHERE id = %s", (credit_memo_id,))
	date, gl_entries_id = c.fetchone()
	# nothing re-posts a memo, the window can only ever load one that is not
	# posted yet, so a second call here is the print dialog's own main loop
	# letting a second click through. Posting again would insert a second
	# receivable credit, a second returned tax debit and a second debit per line,
	# then overwrite the links to the first set, leaving those live in the ledger
	# with nothing pointing at them: the customer credited twice and the revenue
	# reversed twice. restock and post_credit_memo_cogs already refuse to repeat
	if gl_entries_id != None:
		c.close()
		return
	c.execute ("WITH gl_transaction AS "
					"(INSERT INTO gl_transactions (date_inserted) "
					"VALUES (%s) RETURNING id), "
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
					"%s"
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
					"%s"
					")RETURNING id "
				"), "
				"update_credit_memos_entry_ids AS "
				"(UPDATE credit_memos "
					"SET (gl_entries_id, gl_entries_tax_id) = "
					"((SELECT id FROM gl_entry), (SELECT id FROM gl_tax_entry))"
					"WHERE id = %s)"
				"SELECT revenue_account, cmi.ext_price, cmi.id, "
					"(SELECT id FROM gl_transaction) "
					"FROM products AS p "
					"JOIN invoice_items AS ii ON ii.product_id = p.id "
					"JOIN credit_memo_items AS cmi "
						"ON cmi.invoice_item_id = ii.id "
					"WHERE (cmi.credit_memo_id, cmi.deleted) = (%s, False) "
					"ORDER BY cmi.id", 
				(date, credit_memo_id, date, credit_memo_id, date,
				credit_memo_id, credit_memo_id)) 
	for row in c.fetchall():
		account = row[0]
		amount = row[1]
		cmi_id = row[2]
		transaction_id = row[3]
		c.execute(	"WITH cte AS "
						"(INSERT INTO gl_entries AS ge "
						"(debit_account, amount, gl_transaction_id, "
						"date_inserted) VALUES "
						"(%s, %s, %s, %s) RETURNING id "
						") "
					"UPDATE credit_memo_items SET gl_entry_id = "
					"(SELECT id FROM cte) "
					"WHERE id = %s", 
					(account, amount, transaction_id, date, cmi_id))
	# read the transaction back rather than reusing the loop variable, which is
	# never set when every line of the memo is deleted
	c.execute("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
				"JOIN credit_memos AS cm ON cm.gl_entries_id = ge.id "
				"WHERE cm.id = %s", (credit_memo_id,))
	post_credit_memo_cogs (c, credit_memo_id, c.fetchone()[0], date)
	c.close()

def post_credit_memo_cogs (cursor, credit_memo_id, transaction_id, date):
	'''put back the cost the sale took out, one two sided entry per restocked row,
	debiting the product's inventory account and crediting its cost of goods sold
	account: the mirror of post_invoice_cogs. The restock rows are valued at the
	cost the sale left at, so this cancels the original entry exactly. Nothing is
	posted for a product that is not tracked, it has no restock row'''
	# date_inserted is passed rather than left to its default, see cancel_invoice
	cursor.execute("SELECT it.id, ROUND(it.qty_in * it.price, 2), "
						"p.inventory_account, p.default_expense_account "
					"FROM inventory_transactions AS it "
					"JOIN credit_memo_items AS cmi "
						"ON cmi.id = it.credit_memo_item_id "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE cmi.credit_memo_id = %s AND NOT cmi.deleted "
					"AND it.gl_entries_id IS NULL", (credit_memo_id,))
	for row in cursor.fetchall():
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
							"(amount, debit_account, credit_account, "
							"gl_transaction_id, date_inserted) "
							"VALUES (%s, %s, %s, %s, %s) RETURNING id) "
						"UPDATE inventory_transactions SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(row[1], row[2], row[3], transaction_id, date, row[0]))

def post_manufacturing_value (cursor, manufacturing_id, transaction_id = None):
	'''move the value of a build between inventory accounts: each component row
	credits the account its product is carried on, the finished row debits the
	account the built product is carried on. No cost reaches the profit and loss,
	a build only changes what form the stock is held in.

	The two sides are valued independently, components at the cost frozen on the
	line and the finished product at its own cost, so they rarely agree. The
	difference is a production variance and is posted to the built product's
	expense account as a period cost, rather than being hidden by forcing one
	side to match the other, which would leave the inventory accounts holding a
	value the stock rows do not support.

	Rerunning a project zeroes the entries of the previous post and writes the new
	ones into the same transaction, which manufacture () finds before it drops the
	rows that point at it, so a project holds one transaction however often it is
	built rather than a zeroed one per rebuild'''
	if transaction_id == None:
		cursor.execute("INSERT INTO gl_transactions (date_inserted) "
						"VALUES (CURRENT_DATE) RETURNING id")
		transaction_id = cursor.fetchone()[0]
	else:
		# the rebuild re-dated the stock rows, so the document follows them: the
		# alternative is new entries dated today inside a transaction still dated
		# the first build, which is the split post_invoice_accounts was fixed for
		cursor.execute("UPDATE gl_transactions SET date_inserted = CURRENT_DATE "
						"WHERE id = %s", (transaction_id,))
	cursor.execute("SELECT it.id, it.qty_in, ROUND(it.qty_out * it.price, 2), "
						"ROUND(it.qty_in * it.price, 2), p.inventory_account "
					"FROM inventory_transactions AS it "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE it.manufacturing_id = %s AND it.gl_entries_id IS NULL "
					"ORDER BY it.id", (manufacturing_id,))
	credits = Decimal()
	debits = Decimal()
	expense_account = None
	for row in cursor.fetchall():
		row_id, qty_in, out_amount, in_amount, account = row
		if qty_in > 0: # the finished product
			debits += in_amount
			amount, debit, credit = in_amount, account, None
		else:
			credits += out_amount
			amount, debit, credit = out_amount, None, account
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
							"(amount, debit_account, credit_account, "
							"gl_transaction_id, date_inserted) "
							"VALUES (%s, %s, %s, %s, CURRENT_DATE) RETURNING id) "
						"UPDATE inventory_transactions SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(amount, debit, credit, transaction_id, row_id))
	if debits == credits:
		return
	cursor.execute("SELECT p.default_expense_account "
					"FROM manufacturing_projects AS mp "
					"JOIN products AS p ON p.id = mp.product_id "
					"WHERE mp.id = %s", (manufacturing_id,))
	expense_account = cursor.fetchone()[0]
	variance = credits - debits
	cursor.execute("INSERT INTO gl_entries (amount, debit_account, "
						"credit_account, gl_transaction_id, date_inserted, "
						"transaction_description) "
					"VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)",
					(abs(variance),
					expense_account if variance > 0 else None,
					None if variance > 0 else expense_account,
					transaction_id, 'Manufacturing variance'))

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

def post_inventory_count (cursor, count_summary_id, date, transaction_id = None):
	'''value the corrections a count close wrote: one two sided entry per corrected
	product, debiting the product's inventory account and crediting its expense
	account where the count found more than the books, and the other way round
	where it found less, so a shortage reaches the profit and loss as the period
	cost it is. That is the same pair of sides a hand adjustment of the same size
	would post, so where the stock came from does not change what the ledger says.

	The rows are valued at the cost the count froze on them rather than at the cost
	the product carries now, the promise post_invoice_cogs makes as well, so
	editing a cost afterwards cannot restate a count that is already closed.

	One close is one transaction with one entry per product, which is what lets a
	report show what a single count cost. Both sides of an entry carry the same
	rounded amount, so no amount of rounding can leave the transaction out of
	balance and no balancing entry is needed. The transaction is made only once a
	row needing one has been found: a count that agreed with the books in every
	line has nothing to post and must not leave an empty transaction behind, and
	neither must a second close'''
	# date_inserted is passed rather than left to its default, see cancel_invoice
	cursor.execute("SELECT it.id, ROUND((it.qty_in + it.qty_out) * it.price, 2), "
						"it.qty_in, p.inventory_account, p.default_expense_account, "
						"cs.name "
					"FROM inventory_transactions AS it "
					"JOIN inventory.count_summaries AS cs "
						"ON cs.id = it.count_summary_id "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE it.count_summary_id = %s AND it.gl_entries_id IS NULL "
					"ORDER BY it.id", (count_summary_id,))
	rows = cursor.fetchall()
	if rows == []:
		return transaction_id
	if transaction_id == None:
		cursor.execute("INSERT INTO gl_transactions (date_inserted) "
						"VALUES (%s) RETURNING id", (date,))
		transaction_id = cursor.fetchone()[0]
	for row in rows:
		row_id = row[0]
		amount = row[1]
		# GREATEST leaves exactly one of the two quantities non zero
		qty_in = row[2]
		inventory_account = row[3]
		expense_account = row[4]
		description = 'Inventory count: ' + row[5]
		if qty_in > 0: # the count found more than the books, it is an asset
			debit_account, credit_account = inventory_account, expense_account
		else: # a shortage is written off the same way a breakage is
			debit_account, credit_account = expense_account, inventory_account
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
							"(amount, debit_account, credit_account, "
							"gl_transaction_id, date_inserted, "
							"transaction_description) "
							"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id) "
						"UPDATE inventory_transactions SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(amount, debit_account, credit_account, transaction_id, date,
						description, row_id))
	return transaction_id

def post_invoice_cogs (cursor, invoice_id, transaction_id, date):
	'''relieve inventory for the stock this invoice took. One two sided entry per
	sale row, debiting the product's cost of goods sold account and crediting its
	inventory account, valued at the cost the sale row recorded rather than at the
	cost the product carries now, so a re-post or a cash based payment months later
	cannot restate it. The entries go in the invoice's own transaction, which is
	what lets cancel_invoice reverse them along with everything else. A product
	that is not tracked has no sale row and so posts nothing'''
	# date_inserted is passed rather than left to its default, see cancel_invoice
	cursor.execute("SELECT it.id, ROUND(it.qty_out * it.price, 2), "
						"p.default_expense_account, p.inventory_account "
					"FROM inventory_transactions AS it "
					"JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE ii.invoice_id = %s AND NOT ii.canceled "
					"AND it.gl_entries_id IS NULL", (invoice_id,))
	for row in cursor.fetchall():
		row_id = row[0]
		amount = row[1]
		cogs_account = row[2]
		inventory_account = row[3]
		cursor.execute("WITH new_row AS (INSERT INTO gl_entries "
							"(amount, debit_account, credit_account, "
							"gl_transaction_id, date_inserted) "
							"VALUES (%s, %s, %s, %s, %s) RETURNING id) "
						"UPDATE inventory_transactions SET gl_entries_id = "
							"((SELECT id FROM new_row)) WHERE id = %s",
						(amount, cogs_account, inventory_account,
						transaction_id, date, row_id))
	# a re-post zeroed every entry of the transaction, so the rows that already
	# carry one have to be written back. A line canceled after posting keeps its
	# sale row until the next resync, so it is zeroed here rather than skipped
	cursor.execute("SELECT CASE WHEN ii.canceled THEN 0.00 "
							"ELSE ROUND(it.qty_out * it.price, 2) END, "
						"it.gl_entries_id, p.default_expense_account, "
						"p.inventory_account "
					"FROM inventory_transactions AS it "
					"JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
					"JOIN products AS p ON p.id = it.product_id "
					"WHERE ii.invoice_id = %s "
					"AND it.gl_entries_id IS NOT NULL", (invoice_id,))
	for row in cursor.fetchall():
		cursor.execute("UPDATE gl_entries SET "
						"(amount, debit_account, credit_account) = (%s, %s, %s) "
						"WHERE id = %s", (row[0], row[2], row[3], row[1]))

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
		# date_inserted is passed rather than left to its default, see
		# cancel_invoice: the column is NOT NULL DEFAULT now (), so a back dated
		# post dated the receivable the day it was written while the tax and
		# revenue entries below took the posting date, splitting one document
		# across two periods on every report that reads the entry date
		cursor.execute("WITH new_row AS "
								"(INSERT INTO gl_transactions (date_inserted) "
								"VALUES (%s) RETURNING id), "
							"entry_row AS (INSERT INTO gl_entries "
								"(debit_account, amount, gl_transaction_id, "
								"date_inserted) "
								"VALUES ((SELECT account FROM gl_account_flow "
								"WHERE function = 'post_invoice'), %s, "
								"(SELECT id FROM new_row), %s) RETURNING id), "
							"update AS (UPDATE invoices SET (gl_entries_id) = "
								"((SELECT id FROM entry_row)) WHERE id = %s) "
						"SELECT id FROM new_row",
						(date, amount, date, invoice_id))
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
		# debit_account IS NULL picks out the tax entry proper; a cost of goods
		# sold row carries a credit_account too and must not be clobbered here
		cursor.execute("UPDATE gl_entries SET amount = %s "
						"WHERE (gl_transaction_id, credit_account) = (%s, %s) "
						"AND debit_account IS NULL "
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
	post_invoice_cogs (cursor, invoice_id, transaction_id, date)
	cursor.close()
	
def resync_invoice_accounts (invoice_id):
	'''re-sync the ledger entries of an already posted invoice to its current line
	items, the revenue half of resync_invoice_inventory. The totals are recomputed
	here rather than trusted, not every handler that changes an amount refreshes
	them first'''
	cursor = DB.cursor()
	# the guard reads before anything is written. A finance charge carries no
	# invoice_items at all, so recomputing its total would zero the single two
	# sided entry post_finance_charge gave it, the same document customer_payment
	# refuses to post this way. A canceled invoice still holds the mirror entries
	# cancel_invoice wrote, and restating the originals under them would unbalance
	# the transaction. A paid invoice is settled, its receivable is already offset
	# in the payment's own transaction. A null gl_entries_id is cash basis before
	# payment, where no revenue is due yet, which is why settings.accrual_based
	# never has to be read here the way repost_purchase_order_accounts reads it
	cursor.execute("SELECT gl_entries_id FROM invoices "
					"WHERE (id, posted, canceled, paid) = (%s, True, False, False) "
					"AND COALESCE(finance_charge, False) = False "
					"AND gl_entries_id IS NOT NULL", (invoice_id,))
	row = cursor.fetchone()
	if row == None:
		cursor.close()
		return
	gl_entries_id = row[0]
	# the expression calculate_totals uses, canceled lines included: canceling a
	# line zeroes its amounts, so the two agree, and a filter here would only be a
	# second source of truth fighting it once per keystroke
	cursor.execute("UPDATE invoices AS i SET (subtotal, tax, total, amount_due) = "
						"(t.subtotal, t.tax, t.total, t.total) "
					"FROM (SELECT COALESCE(SUM(ext_price), 0.00) AS subtotal, "
							"COALESCE(SUM(tax), 0.00) AS tax, "
							"COALESCE(SUM(ext_price) + SUM(tax), 0.00) AS total "
							"FROM invoice_items WHERE invoice_id = %s) AS t "
					"WHERE i.id = %s "
					"RETURNING i.total", (invoice_id, invoice_id))
	total = cursor.fetchone()[0]
	# the transaction's date: it is the one the tax and revenue entries were
	# written under, so an entry born in this edit lands in the same period as its
	# siblings. Not dated_for, which invoice_create.post rewrites on every post, a
	# re-post included, while the entries keep the date they were written under.
	# And not the receivable's own date_inserted the way
	# repost_purchase_order_accounts reads it: post_purchase_order dates its header
	# entry explicitly, post_invoice_accounts does not, so an invoice receivable
	# carries the day it was written rather than the day it was posted for
	cursor.execute("SELECT gt.date_inserted FROM gl_transactions AS gt "
					"JOIN gl_entries AS ge ON ge.gl_transaction_id = gt.id "
					"WHERE ge.id = %s", (gl_entries_id,))
	date = cursor.fetchone()[0]
	cursor.close()
	# the update branch zeroes every entry of the transaction before it rewrites,
	# which is the only thing that retires an entry its per rate and per line loops
	# never visit: a tax account that has left the invoice, a line canceled after
	# posting, an orphaned cost row. The post_invoice_cogs call it ends with is
	# what writes the cost amounts back after that zeroing
	post_invoice_accounts (date, invoice_id, total, gl_entries_id)
	return total

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

def move_purchase_order_item_blocked (line_id, destination_po_id):
	'''returns a message explaining why this line cannot be moved, or None.
	The destination may have just been created in the open transaction, so
	this must not commit or roll back; the caller decides'''
	cursor = DB.cursor()
	cursor.execute("SELECT "
						"poli.canceled, "
						"dest.paid OR dest.canceled, "
						"dest.invoiced "
					"FROM purchase_order_items AS poli "
					"CROSS JOIN purchase_orders AS dest "
					"WHERE poli.id = %s AND dest.id = %s",
					(line_id, destination_po_id))
	row = cursor.fetchone()
	cursor.close()
	if row == None:
		return "That line or purchase order no longer exists"
	#the document the line is already on is left out of the chooser, so there
	#is no same purchase order case to report here. A line that already carries
	#an expense entry is not refused either; move_purchase_order_item zeroes
	#that entry and detaches it, see there
	canceled, dest_closed, dest_invoiced = row
	if canceled == True:
		return "That line is canceled"
	if dest_closed == True:
		return "The destination purchase order is paid or canceled"
	if dest_invoiced == True:
		return "The destination purchase order is already invoiced and may "\
				"not be edited afterwards"
	return None

def move_purchase_order_item (line_id, destination_po_id):
	'''moves a line to another purchase order and re-syncs the ledger of both.
	An expense entry belongs to the transaction of the document it was invoiced
	on, and a destination is never invoiced, so there is nowhere to carry it
	across: the entry is zeroed in place and the line is detached from it. The
	line is posted again, in the destination's own transaction, when that
	document is invoiced'''
	cursor = DB.cursor()
	cursor.execute("SELECT purchase_order_id, gl_entries_id "
					"FROM purchase_order_items WHERE id = %s", (line_id,))
	source_po_id, line_gl_entries_id = cursor.fetchone()
	if line_gl_entries_id != None:
		#the debit account is left alone so the row still reads sensibly in
		#the general ledger reports
		cursor.execute("UPDATE gl_entries SET (amount, transaction_description) "
							"= (0.00, %s) WHERE id = %s",
						("Line moved to purchase order %s" % destination_po_id,
						line_gl_entries_id))
	cursor.execute("UPDATE purchase_order_items "
						"SET (purchase_order_id, sort, gl_entries_id) "
						"= (%s, (SELECT COALESCE(MAX(sort), 0) + 1 "
								"FROM purchase_order_items "
								"WHERE purchase_order_id = %s), NULL) "
					"WHERE id = %s",
					(destination_po_id, destination_po_id, line_id))
	cursor.close()
	repost_purchase_order_accounts (source_po_id)
	repost_purchase_order_accounts (destination_po_id)
	return source_po_id

def purchase_order_inventory_blocked (po_id):
	'''returns a message when the corrected quantities cannot be applied to
	inventory, or None. This reads the corrections already written in the open
	transaction, so it must not commit or roll back; the caller decides'''
	cursor = DB.cursor()
	# per location, the way every writer takes its stock: stock the company
	# holds somewhere else is not stock this order can give back. Grouped on
	# p.id as well, or two products sharing a name are weighed as one
	cursor.execute("SELECT p.name, l.name FROM inventory_transactions AS it "
					"JOIN products AS p ON p.id = it.product_id "
					"JOIN locations AS l ON l.id = it.location_id "
					"WHERE it.product_id IN (SELECT product_id "
						"FROM purchase_order_items "
						"WHERE purchase_order_id = %s) "
					"GROUP BY p.id, p.name, l.id, l.name "
					"HAVING SUM(it.qty_in) - SUM(it.qty_out) < 0", (po_id,))
	row = cursor.fetchone()
	if row != None:
		cursor.close()
		return "'%s' would go negative in inventory at %s" % (row[0], row[1])
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

def trim_purchase_order_receipts (cursor, po_id):
	'''brings the receipts of an order back down when less arrived than has
	already been posted, or when the order itself was corrected downwards. A
	line's receipt is the count the receive window entered, and a line that
	window never counted is owed in full, the same reading receive () takes of
	a count that is NULL. The count is allocated over the line's receipt rows
	oldest first: each row keeps what the count still covers and the rest goes
	to zero, so the rows an earlier shipment wrote keep their own dates. A row
	is zeroed rather than deleted, the way unsell () and
	cancel_purchase_order_item leave theirs in place. This only ever takes a
	row down; what is still owed is put in by receive (), which dates a new row
	with the day the stock arrived, or by resync_purchase_order_inventory,
	which does not. The caller's cursor is used, the same as post_invoice_cogs ()'''
	cursor.execute("WITH posted AS "
						"(SELECT it.id, it.qty_in, "
							"COALESCE(poli.received, poli.qty)::int AS received, "
							"COALESCE(SUM(it.qty_in) OVER "
								"(PARTITION BY it.purchase_order_item_id "
								"ORDER BY it.id "
								"ROWS BETWEEN UNBOUNDED PRECEDING "
									"AND 1 PRECEDING), 0) AS earlier "
						"FROM inventory_transactions AS it "
						"JOIN purchase_order_items AS poli "
							"ON poli.id = it.purchase_order_item_id "
						"WHERE (poli.purchase_order_id, poli.canceled) = "
							"(%s, False)), "
					"trimmed AS "
						"(SELECT id, "
							"GREATEST(LEAST(qty_in, received - earlier), 0) "
								"AS qty_in "
						"FROM posted) "
					"UPDATE inventory_transactions AS it SET qty_in = t.qty_in "
					"FROM trimmed AS t "
					"WHERE it.id = t.id AND it.qty_in != t.qty_in", (po_id,))

def mark_purchase_order_received (po_id):
	'''marks the order received once everything it ordered has arrived, and says
	whether it did. A short shipment leaves the flag alone, so the order stays on
	the receive window's list and the rest of it can still be counted in and
	posted. A line nobody counted there counts as arrived, the same reading
	receive () takes of a count that is NULL, and a canceled line is not owed at
	all. The line items decide this rather than what the window has on screen:
	the window lists no expense product, and those lines are owed too'''
	cursor = DB.cursor()
	cursor.execute("UPDATE purchase_orders SET received = True "
					"WHERE id = %s "
					"AND NOT EXISTS (SELECT 1 FROM purchase_order_items AS poli "
						"WHERE poli.purchase_order_id = purchase_orders.id "
						"AND NOT poli.canceled "
						"AND COALESCE(poli.received, poli.qty) < poli.qty) "
					"RETURNING id", (po_id,))
	received = cursor.fetchone() != None
	cursor.close()
	return received

def resync_purchase_order_inventory (po_id):
	'''follows corrected quantities and prices into inventory. Purchase order
	receipts carry no ledger entry, so the receipt rows are updated in place
	rather than offset with an adjusting row: a correction is not a shipment,
	and only receive () writes a row dated the day stock arrived'''
	cursor = DB.cursor()
	#an order nothing has been received on is left to receive (). One received in
	#part carries rows while its received flag is still False, and they have to
	#follow a correction like any other
	cursor.execute("SELECT po.received OR EXISTS "
						"(SELECT 1 FROM inventory_transactions AS it "
						"JOIN purchase_order_items AS poli "
							"ON poli.id = it.purchase_order_item_id "
						"WHERE poli.purchase_order_id = po.id) "
					"FROM purchase_orders AS po WHERE po.id = %s", (po_id,))
	if cursor.fetchone()[0] == False:
		cursor.close()
		return
	#the price correction lands on every receipt row of the line, a partial
	#order's second and third shipment included
	cursor.execute("UPDATE inventory_transactions AS it "
						"SET price = COALESCE(poli.price, 0) "
					"FROM purchase_order_items AS poli "
					"WHERE it.purchase_order_item_id = poli.id "
					"AND poli.purchase_order_id = %s", (po_id,))
	cursor.execute("UPDATE inventory_transactions AS it SET qty_in = 0 "
					"FROM purchase_order_items AS poli "
					"WHERE it.purchase_order_item_id = poli.id "
					"AND (poli.purchase_order_id, poli.canceled) = (%s, True)",
					(po_id,))
	#an order corrected below what was counted in takes the count down with it:
	#the receive window cannot count a line past its quantity, so a count left
	#above it would hold stock the order no longer claims. A canceled line is
	#corrected to nothing, so this empties its count too
	cursor.execute("UPDATE purchase_order_items SET received = qty "
					"WHERE purchase_order_id = %s AND received > qty", (po_id,))
	trim_purchase_order_receipts (cursor, po_id)
	#what the correction added goes onto the line's newest row rather than into a
	#row of its own: no stock arrived today, the order was restated. The trim
	#above has already taken the rows down to the count, so the difference left
	#here can only be owed, never over
	cursor.execute("WITH short AS "
						"(SELECT DISTINCT ON (poli.id) it.id, "
							"COALESCE(poli.received, poli.qty)::int "
								"- SUM(it.qty_in) OVER (PARTITION BY poli.id) "
								"AS difference "
						"FROM purchase_order_items AS poli "
						"JOIN inventory_transactions AS it "
							"ON it.purchase_order_item_id = poli.id "
						"WHERE (poli.purchase_order_id, poli.canceled) = "
							"(%s, False) "
						"ORDER BY poli.id, it.id DESC) "
					"UPDATE inventory_transactions AS it "
						"SET qty_in = it.qty_in + short.difference "
					"FROM short "
					"WHERE it.id = short.id AND short.difference > 0", (po_id,))
	#lines added after the purchase order was received still need a receipt
	cursor.execute("INSERT INTO inventory_transactions "
						"(purchase_order_item_id, qty_in, product_id, price, "
						"location_id, date_inserted) "
					"SELECT poli.id, COALESCE(poli.received, poli.qty)::int, "
						"poli.product_id, COALESCE(poli.price, 0), "
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
					"AND COALESCE(poli.received, poli.qty)::int > 0 "
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
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, NULL, %s, %s, %s, (SELECT id FROM new_row), "
						"'bank_to_credit_card_transfer'), "
					"(NULL, %s, %s, %s, %s, (SELECT id FROM new_row), "
						"'bank_to_credit_card_transfer')", 
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
				"transaction_description, fees_rewards, gl_transaction_id, "
				"source_type) "
				"VALUES (%s, %s, %s, %s, %s, True, (SELECT id FROM new_row), "
					"'credit_card_fee_reward')", 
				(date, credit_card_account, date, gl_account, amount, description))
	cursor.close()

def bank_charge(bank_account, date, amount, description, account_number):
	cursor = DB.cursor()
	cursor.execute("WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
				"INSERT INTO gl_entries "
				"(credit_account, debit_account, amount, "
				"transaction_description, fees_rewards, gl_transaction_id, "
				"source_type) "
				"VALUES (%s, %s, %s, %s, True, "
					"(SELECT id FROM new_row), 'bank_charge')", 
				(date, bank_account, account_number, amount, description))
	cursor.close()

def post_voided_check (bank_account, date, cheque_number):
	cursor = DB.cursor()
	cursor.execute(	"WITH new_row AS "
						"(INSERT INTO gl_transactions "
						"(date_inserted) VALUES (%s) RETURNING id) "
					"INSERT INTO gl_entries "
					"(debit_account, credit_account, check_number, amount, "
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, %s, %s, 0.00, 'Voided check', "
					"(SELECT id FROM new_row), 'voided_check')", 
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
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, %s, %s, %s, %s, 'journal_entry')", 
					(account_number, amount, self.date, 
					self.desc, self.trans_id))
		c.close()

	def post_debit_entry (self, amount, account_number):
		c = DB.cursor()
		c.execute("INSERT INTO gl_entries "
					"(debit_account, amount, date_inserted, "
					"transaction_description, gl_transaction_id, source_type) "
					"VALUES (%s, %s, %s, %s, %s, 'journal_entry')", 
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
				"(date_inserted, gl_transaction_id, credit_account, amount, "
				"source_type) "
				"VALUES (%s, %s, %s, %s, 'misc_revenue')", 
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




