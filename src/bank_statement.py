
# bank_statement.py
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

from gi.repository import Gtk, GLib
import os, sys, psycopg2
from datetime import datetime
from db import transactor
from dateutils import datetime_to_text, DateTimeCalendar

UI_FILE = "src/bank_statement.ui"

class GUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.builder.get_object('treeview2').set_model(main.expense_acc)

		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		self.account_number = 0
		self.bank_transaction_store = self.builder.get_object(
											'bank_transaction_store')
		self.bank_account_store = self.builder.get_object(
											'bank_account_store')
		self.expense_store = self.builder.get_object(
											'expense_account_store')
		self.transaction_description_store = self.builder.get_object(
											'transaction_description_store')
		self.populate_account_stores ()

		self.window = self.builder.get_object('window1')
		'''header = Gtk.HeaderBar()
		header.set_title("Bank Statement")
		header.add(self.builder.get_object('menubutton1'))
		header.set_show_close_button(True)
		self.window.set_titlebar(header)'''
		self.window.show_all()

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(self.highlight, entry)

	def highlight (self, entry):
		entry.select_region(0, -1)		

	def view_closed_items(self, check_button):
		self.populate_treeview ()

	def populate_bank_charge_stores (self):
		self.expense_store.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE type = 3 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent_tree = self.expense_store.append(None,[account_number, 
																account_name])
			self.get_child_accounts (self.expense_store, account_number, parent_tree)
		self.transaction_description_store.clear()
		self.cursor.execute("SELECT transaction_description AS td "
							"FROM gl_entries "
							"WHERE (debit_account = %s OR credit_account = %s) "
							"AND transaction_description IS NOT NULL "
							"AND fees_rewards = True "
							"GROUP BY td ORDER BY td",
							(self.account_number, self.account_number))
		for row in self.cursor.fetchall():
			description = row[0]
			self.transaction_description_store.append([description])

	def populate_account_stores(self):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE bank_account = True")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			account_total = self.get_bank_account_total (account_number)
			self.bank_account_store.append([str(account_number), account_name, 
											'${:,.2f}'.format(account_total)])
		

	def get_child_accounts (self, store, parent_number, parent_tree):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE parent_number = %s", (parent_number,))
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent = store.append(parent_tree,[account_number, account_name])
			self.get_child_accounts (store, account_number, parent)

	def bank_account_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None:
			self.account_number = 0
			self.bank_transaction_store.clear()
			return
		self.bank_account_total = self.get_bank_account_total(account_number)
		self.builder.get_object('button2').set_sensitive(True)
		self.account_number = account_number
		self.populate_treeview ()
		self.calculate_reconciled_balance ()

	def get_bank_account_total(self, account_number): 
		self.cursor.execute("SELECT SUM(debits - credits) AS total FROM "
								"(SELECT COALESCE(SUM(amount),0.00) AS debits "
								"FROM gl_entries "
								"WHERE debit_account = %s) d, "
								"(SELECT COALESCE(SUM(amount),0.00) AS credits "
								"FROM gl_entries "
								"WHERE credit_account= %s) c  ", 
								(account_number, account_number))
		bank_account_total = float(self.cursor.fetchone()[0]) 
		return bank_account_total

	def populate_treeview(self ):
		self.bank_transaction_store.clear()
		view_history = self.builder.get_object('checkbutton1').get_active()
		if view_history == True:
			self.cursor.execute("SELECT ge.id, ge.amount, ge.debit_account, "
							"ge.credit_account, ge.check_number, "
							"ge.date_inserted, reconciled, contacts.name, "
							"transaction_description "
							"FROM gl_entries AS ge "
							"LEFT JOIN payments_incoming AS pi "
							"ON ge.id = pi.gl_entries_id "
							"LEFT JOIN contacts ON contacts.id = "
							"pi.customer_id "
							"WHERE debit_account = %s OR credit_account = %s "
							"ORDER BY date_inserted;", 
							(self.account_number, self.account_number))
		else:
			self.cursor.execute("SELECT ge.id, ge.amount, ge.debit_account, "
							"ge.credit_account, ge.check_number, "
							"ge.date_inserted, reconciled, contacts.name, "
							"transaction_description "
							"FROM gl_entries AS ge "
							"LEFT JOIN payments_incoming AS pi "
							"ON ge.id = pi.gl_entries_id "
							"LEFT JOIN contacts ON contacts.id = "
							"pi.customer_id "
							"WHERE (debit_account = %s OR credit_account = %s) "
							"AND date_reconciled IS NULL "
							"ORDER BY date_inserted;", 
							(self.account_number, self.account_number))
		for row in self.cursor.fetchall(): 
			row_id = row[0]
			amount = row[1]
			if str(row[3]) == self.account_number:
				debit_amount = amount
				credit_amount = ''
			else:
				debit_amount = ''
				credit_amount = amount
			check_number = str(row[4])
			if check_number == 'None':
				check_number = ''
			date = row[5]
			date_formatted = datetime_to_text(date)
			reconciled = row[6]
			description = row[7]
			if description == None:
				description = row[8]
			self.bank_transaction_store.append([row_id, check_number, date_formatted, 
												str(date), description, 
												reconciled, str(debit_amount), 
												str(credit_amount)])

	def on_reconciled_toggled(self, widget, path):
		if self.builder.get_object('checkbutton1').get_active() == False: 
			#we are not viewing reconciled or canceled transactions
			active = not self.bank_transaction_store[path][5]
			self.bank_transaction_store[path][5] = active #toggle the button state
			if self.bank_transaction_store[path][5] == True: #the transaction got marked as cleared
				if self.bank_transaction_store[path][6] != '':#the transaction is a debit
					self.reconciled_total -= float(self.bank_transaction_store[path][6])
				else:  #the transaction is a credit
					self.reconciled_total += float(self.bank_transaction_store[path][7])
			else: #the transaction is not cleared
				if self.bank_transaction_store[path][6] != '': 
					self.reconciled_total += float(self.bank_transaction_store[path][6])
				else:
					self.reconciled_total -= float(self.bank_transaction_store[path][7])
			row_id = self.bank_transaction_store[path][0]
			self.cursor.execute("UPDATE gl_entries "
								"SET reconciled = %s WHERE id = %s", 
								(active, row_id))
			self.builder.get_object('entry2').set_text('${:,.2f}'.format(self.reconciled_total))
			self.account_statement_difference ()
			self.db.commit()
		
	def calculate_reconciled_balance(self):
		self.cursor.execute("SELECT SUM(debits - credits) AS total FROM "
								"(SELECT COALESCE(SUM(amount),0.00) AS debits "
								"FROM gl_entries "
								"WHERE (debit_account, reconciled) "
								"= (%s, True))  d, "
								"(SELECT COALESCE(SUM(amount),0.00) AS credits "
								"FROM gl_entries "
								"WHERE (credit_account, reconciled) "
								"= (%s, True)) c ", 
								(self.account_number, self.account_number))
		self.reconciled_total = float(self.cursor.fetchone()[0])
		self.builder.get_object('entry2').set_text('${:,.2f}'.format(self.reconciled_total))

	def statement_balance_spinbutton_changed (self, entry):
		self.account_statement_difference ()

	def account_statement_difference(self ):
		statement_amount = self.builder.get_object('spinbutton1').get_value()
		difference = statement_amount - self.reconciled_total
		self.builder.get_object('entry4').set_text('${:,.2f}'.format(difference))
		if difference == 0.00 and statement_amount != 0.00:
			self.builder.get_object('button1').set_sensitive(True)
		else:
			self.builder.get_object('button1').set_sensitive(False)

	def save_reconciled_items_clicked (self, button):
		self.cursor.execute("UPDATE gl_entries "
							"SET date_reconciled = %s "
							"WHERE ((debit_account, reconciled) = (%s, True) "
								"OR (credit_account, reconciled) = (%s, True)) "
							"AND date_reconciled IS NULL", 
							(datetime.today(), self.account_number, 
							self.account_number))
		self.db.commit()
		self.populate_treeview ()
		self.builder.get_object('spinbutton1').set_value(0.00)

	def add_bank_charge_clicked (self, button):
		if self.account_number == 0:
			return
		self.populate_bank_charge_stores ()
		dialog = self.builder.get_object('dialog1')
		self.check_bank_charge_validity ()
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			selection = self.builder.get_object('treeview-selection2')
			model, path = selection.get_selected_rows()
			expense_account_number = model[path][0]
			transactor.bank_charge(self.db, self.account_number, 
									self.date, self.amount, 
									self.description, expense_account_number)
			self.populate_treeview()
			bank_total = self.get_bank_account_total (self.account_number)		
			path = self.builder.get_object("combobox1").get_active()
			self.bank_account_store[path][2] = '${:,.2f}'.format(self.bank_account_total)
			self.db.commit()

	def number_edited (self, renderer, path, text):
		row_id = self.bank_transaction_store[path][0]
		try:
			self.cursor.execute("UPDATE gl_entries SET check_number = %s "
								"WHERE id = %s", (text, row_id))
			self.db.commit()
			self.bank_transaction_store[path][0] = text
		except psycopg2.DataError as e:
			self.db.rollback()
			print (e)
			self.builder.get_object('label10').set_label(str(e))
			dialog = self.builder.get_object('date_error_dialog')
			dialog.run()
			dialog.hide()

	def description_edited (self, renderer, path, text):
		row_id = self.bank_transaction_store[path][0]
		self.cursor.execute("UPDATE gl_entries SET transaction_description = %s "
							"WHERE id = %s", (text, row_id))
		self.db.commit()
		self.bank_transaction_store[path][4] = text

	def date_renderer_editing_started (self, renderer, entry, path):
		date = self.bank_transaction_store[path][3]
		entry.set_text(date)

	def date_renderer_edited (self, renderer, path, text):
		transaction_id = self.bank_transaction_store[path][0]
		try:
			self.cursor.execute("UPDATE gl_entries "
								"SET date_inserted = %s WHERE id = %s",
								(text, transaction_id))
		except psycopg2.DataError as e:
			self.db.rollback()
			print (e)
			self.builder.get_object('label10').set_label(str(e))
			dialog = self.builder.get_object('dialog2')
			dialog.run()
			dialog.hide()
		self.db.commit()
		self.populate_treeview ()

	def expense_treeview_row_activate (self, treeview, path, treeview_column):
		self.check_bank_charge_validity()

	def bank_charge_spinbutton_amount_changed (self, button):
		self.check_bank_charge_validity()

	def description_entry_changed (self, entry):
		self.check_bank_charge_validity()
		
	def check_bank_charge_validity (self):
		button = self.builder.get_object('button3')
		button.set_sensitive(False)
		self.amount = self.builder.get_object('spinbutton2').get_value()
		if self.amount == 0.00:
			button.set_label('No amount entered')
			return
		self.description = self.builder.get_object('combobox-entry').get_text()
		if self.description == '':
			button.set_label('No description')
			return
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				button.set_label ('Expense parent account selected')
				return # parent account selected
		else:
			button.set_label ('No expense account selected')
			return # no account selected
		button.set_sensitive(True)
		button.set_label('Add bank charge')

	def calendar_day_selected(self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)

	def calendar_entry_icon_released (self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()

	def credit_card_statement_activated (self, menuitem):
		import credit_card_statements
		credit_card_statements.CreditCardStatementGUI(self.db)
	
	def miscellaneous_income_activated (self, button):
		import miscellaneous_income
		miscellaneous_income.MiscellaneousIncomeGUI (self.main)

	def loan_payment_activated (self, widget):
		import loan_payment
		loan_payment.LoanPaymentGUI(self.db)

	def double_entry_transaction_activated (self, menuitem):
		import double_entry_transaction
		double_entry_transaction.DoubleEntryTransactionGUI(self.db)

	def incoming_invoices_activated (self, menuitem):
		import incoming_invoice
		incoming_invoice.IncomingInvoiceGUI(self.db)

	
