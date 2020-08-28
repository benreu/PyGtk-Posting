
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
import psycopg2
from datetime import datetime
from db import transactor
from decimal import Decimal
from dateutils import DateTimeCalendar
from constants import ui_directory, DB
from accounts import expense_account

UI_FILE = ui_directory + "/bank_statement.ui"

class GUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.get_object('treeview2').set_model(expense_account)

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		self.reconcile_calendar = DateTimeCalendar()
		self.reconcile_calendar.connect('day-selected', 
										self.reconcile_calendar_day_selected)
		self.reconcile_calendar.set_relative_to(self.get_object('entry6'))
		self.reconcile_date = None
		self.voided_cheque_calendar = DateTimeCalendar()
		self.voided_cheque_calendar.connect('day-selected', 
												self.voided_cheque_day_selected)
		self.voided_cheque_calendar.set_relative_to(self.get_object('entry5'))
		self.voided_cheque_date = None
		self.account_number = 0
		self.bank_transaction_store = self.get_object(
											'bank_transaction_store')
		self.bank_account_store = self.get_object(
											'bank_account_store')
		self.expense_store = self.get_object(
											'expense_account_store')
		self.transaction_description_store = self.get_object(
											'transaction_description_store')
		self.populate_account_stores ()

		self.window = self.get_object('window1')
		self.window.show_all()

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def view_closed_items(self, check_button):
		self.populate_treeview ()

	def voided_cheque_activated (self, menuitem):
		dialog = self.get_object('check_dialog')
		response = dialog.run()
		dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			bank_account = self.get_object('combobox3').get_active_id()
			cheque_number = self.get_object('entry3').get_text()
			transactor.post_voided_check(bank_account, 
											self.voided_cheque_date, 
											cheque_number)

	def date_entry_icon_release (self, entry, entryiconposition, event):
		if self.account_number != 0:
			self.reconcile_calendar.show()

	def reconcile_calendar_day_selected (self, calendar):
		c = DB.cursor()
		entry = self.get_object('entry6')
		date = calendar.get_date()
		c.execute("SELECT COUNT(id) FROM gl_entries "
							"WHERE date_reconciled = %s", (date,))
		if c.fetchone()[0] != 0:
			entry.set_text("Date already used !")
			self.reconcile_date = None
		else:
			entry.set_text(calendar.get_text())
			self.reconcile_date = calendar.get_date()
		self.account_statement_difference ()
		c.close()
		DB.rollback()

	def voided_cheque_day_selected (self, calendar):
		self.voided_cheque_date = calendar.get_date()
		date = calendar.get_text()
		self.get_object('entry5').set_text(date)
		self.check_voided_cheque_entries_valid ()

	def voided_cheque_bank_account_changed (self, combobox):
		self.check_voided_cheque_entries_valid ()

	def voided_cheque_number_changed (self, entry):
		self.check_voided_cheque_entries_valid ()

	def voided_check_date_entry_icon_released (self, entry, icon, position):
		self.voided_cheque_calendar.show()

	def check_voided_cheque_entries_valid (self):
		button = self.get_object('button6')
		button.set_sensitive(False)
		if self.get_object('combobox3').get_active_id() == None:
			button.set_label('No bank account selected')
			return
		if self.get_object('entry3').get_text() == '':
			button.set_label('No check number entered')
			return
		if self.voided_cheque_date == None:
			button.set_label('No date selected')
			return
		button.set_sensitive (True)
		button.set_label('Apply voided check')

	def populate_bank_charge_stores (self):
		c = DB.cursor()
		self.expense_store.clear()
		c.execute("SELECT number, name FROM gl_accounts "
					"WHERE type = 3 AND parent_number IS NULL")
		for row in c.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent_tree = self.expense_store.append(None,[account_number, 
															account_name])
			self.get_child_accounts (self.expense_store, 
										account_number, 
										parent_tree)
		self.transaction_description_store.clear()
		c.execute("SELECT transaction_description AS td "
					"FROM gl_entries "
					"WHERE (debit_account = %s OR credit_account = %s) "
					"AND transaction_description IS NOT NULL "
					"AND fees_rewards = True "
					"GROUP BY td ORDER BY td",
					(self.account_number, self.account_number))
		for row in c.fetchall():
			description = row[0]
			self.transaction_description_store.append([description])
		c.close()
		DB.rollback()

	def populate_account_stores(self):
		c = DB.cursor()
		c.execute("SELECT number::text, name FROM gl_accounts "
					"WHERE bank_account = True")
		for row in c.fetchall():
			self.bank_account_store.append(row)
		c.close()
		DB.rollback()

	def get_child_accounts (self, store, parent_number, parent_tree):
		c = DB.cursor()
		c.execute("SELECT number, name FROM gl_accounts "
					"WHERE parent_number = %s", (parent_number,))
		for row in c.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent = store.append(parent_tree,[account_number, account_name])
			self.get_child_accounts (store, account_number, parent)
		c.close()
		DB.rollback()

	def bank_account_changed (self, combo):
		c = DB.cursor()
		account_number = combo.get_active_id()
		if account_number == None:
			self.account_number = 0
			self.bank_transaction_store.clear()
			return
		c.execute("CREATE OR REPLACE TEMP VIEW "
					"bank_statement_view AS "
					"WITH account_numbers AS "
						"(SELECT number FROM gl_accounts "
						"WHERE number = %s OR parent_number = %s"
						") "
						"SELECT id, amount, debit_account, "
						"credit_account, check_number, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, TRUE AS debit, FALSE AS credit "
						"FROM gl_entries WHERE debit_account "
						"IN (SELECT * FROM account_numbers) "
						"UNION "
						"SELECT id, amount, debit_account, "
						"credit_account, check_number, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, FALSE AS debit, TRUE AS credit "
						"FROM gl_entries WHERE credit_account "
						"IN (SELECT * FROM account_numbers)"
						, (account_number, account_number))
		c.close()
		DB.commit()
		self.calculate_bank_account_total(account_number)
		self.get_object('button2').set_sensitive(True)
		self.get_object('refresh_button').set_sensitive(True)
		self.get_object('label13').set_label(str(self.bank_account_total))
		self.account_number = account_number
		self.populate_treeview ()
		self.calculate_reconciled_balance ()

	def calculate_bank_account_total(self, account_number): 
		c = DB.cursor()
		c.execute("SELECT SUM(debits - credits) AS total FROM "
					"(SELECT COALESCE(SUM(amount),0.00) AS debits "
					"FROM bank_statement_view "
					"WHERE debit = True) d, "
					"(SELECT COALESCE(SUM(amount),0.00) AS credits "
					"FROM bank_statement_view "
					"WHERE credit = True) c  ")
		bank_account_total = c.fetchone()[0]
		c.close()
		self.bank_account_total = bank_account_total

	def refresh_clicked (self, button):
		self.populate_treeview()

	def populate_treeview(self ):
		c = DB.cursor()
		self.bank_transaction_store.clear()
		c.execute("SELECT ge.id, "
					"COALESCE(ge.check_number::text, ''), "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN contacts.name IS NOT NULL "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END "
					"FROM bank_statement_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					"WHERE date_reconciled IS NULL "
					"ORDER BY date_inserted;", 
					(self.account_number, self.account_number))
		for row in c.fetchall():
			self.bank_transaction_store.append(row)
		c.close()
		DB.rollback()

	def on_reconciled_toggled(self, widget, path):
		iter_ = self.bank_transaction_store.get_iter(path)
		c = DB.cursor()
		active = not self.bank_transaction_store[iter_][5]
		self.bank_transaction_store[iter_][5] = active #toggle the button state
		row_id = self.bank_transaction_store[iter_][0]
		c.execute("UPDATE gl_entries "
					"SET reconciled = %s WHERE id = %s", 
					(active, row_id))
		DB.commit()
		self.calculate_reconciled_balance ()
		self.account_statement_difference ()
		c.close()
		
	def calculate_reconciled_balance(self):
		c = DB.cursor()
		c.execute("SELECT SUM(debits - credits) AS total FROM "
					"(SELECT COALESCE(SUM(amount),0.00) AS debits "
					"FROM bank_statement_view "
					"WHERE (reconciled, debit) = (True, True)"
					") d, "
					"(SELECT COALESCE(SUM(amount),0.00) AS credits "
					"FROM bank_statement_view "
					"WHERE (reconciled, credit) = (True, True)"
					") c ")
		self.reconciled_total = c.fetchone()[0]
		t = '${:,.2f}'.format(float(self.reconciled_total))
		self.get_object('entry2').set_text(t)
		c.close()
		DB.rollback()

	def statement_balance_spinbutton_changed (self, entry):
		self.account_statement_difference ()

	def account_statement_difference(self ):
		button = self.get_object('button1')
		statement_amount = Decimal(self.get_object('spinbutton1').get_text())
		diff = statement_amount - self.reconciled_total
		self.get_object('entry4').set_text('${:,.2f}'.format(diff))
		if diff == Decimal('0.00') and statement_amount != Decimal('0.00'):
			button.set_label("Save reconciled items")
			button.set_sensitive(True)
		else:
			button.set_label("Reconciled amount does not match")
			button.set_sensitive(False)
			return
		if self.reconcile_date == None:
			button.set_label("No reconcile date")
			button.set_sensitive(False)
		else:
			button.set_label("Save reconciled items")
			button.set_sensitive(True)

	def save_reconciled_items_clicked (self, button):
		c = DB.cursor()
		c.execute("WITH account_numbers AS "
					"(SELECT number FROM gl_accounts "
						"WHERE number = %s OR parent_number = %s"
						") "
					"UPDATE gl_entries "
					"SET date_reconciled = %s "
					"WHERE "
						"(debit_account IN "
							"(SELECT * FROM account_numbers) "
						"OR credit_account IN "
							"(SELECT * FROM account_numbers)"
						") "
					"AND date_reconciled IS NULL "
					"AND reconciled = True", 
					(self.account_number, self.account_number,
					self.reconcile_date))
		DB.commit()
		c.close()
		self.populate_treeview ()
		self.get_object('spinbutton1').set_value(0.00)

	def add_bank_charge_clicked (self, button):
		if self.account_number == 0:
			return
		self.populate_bank_charge_stores ()
		dialog = self.get_object('dialog1')
		self.check_bank_charge_validity ()
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			selection = self.get_object('treeview-selection2')
			model, path = selection.get_selected_rows()
			iter_ = self.bank_transaction_store.get_iter(path)
			expense_account_number = model[iter_][0]
			transactor.bank_charge(self.account_number, 
									self.date, self.amount, 
									self.description, expense_account_number)
			DB.commit()
			self.calculate_bank_account_total(self.account_number)
			self.get_object('label13').set_label(str(self.bank_account_total))
			self.populate_treeview()

	def number_edited (self, renderer, path, text):
		iter_ = self.bank_transaction_store.get_iter(path)
		row_id = self.bank_transaction_store[iter_][0]
		c = DB.cursor()
		try:
			c.execute("UPDATE gl_entries SET check_number = %s "
						"WHERE id = %s", (text, row_id))
			c.close()
			DB.commit()
			self.bank_transaction_store[iter_][1] = text
		except psycopg2.DataError as e:
			DB.rollback()
			self.get_object('label10').set_label(str(e))
			dialog = self.get_object('date_error_dialog')
			dialog.run()
			dialog.hide()

	def description_edited (self, renderer, path, text):
		iter_ = self.bank_transaction_store.get_iter(path)
		c = DB.cursor()
		row_id = self.bank_transaction_store[iter_][0]
		c.execute("UPDATE gl_entries SET transaction_description = %s "
					"WHERE id = %s", (text, row_id))
		DB.commit()
		c.close()
		self.bank_transaction_store[iter_][4] = text

	def date_renderer_editing_started (self, renderer, entry, path):
		date = self.bank_transaction_store[path][3]
		entry.set_text(date)

	def date_renderer_edited (self, renderer, path, text):
		c = DB.cursor()
		transaction_id = self.bank_transaction_store[path][0]
		try:
			c.execute("UPDATE gl_entries "
						"SET date_inserted = %s WHERE id = %s",
						(text, transaction_id))
		except psycopg2.DataError as e:
			DB.rollback()
			print (e)
			self.get_object('label10').set_label(str(e))
			dialog = self.get_object('dialog2')
			dialog.run()
			dialog.hide()
		DB.commit()
		c.close()
		self.populate_treeview ()

	def expense_treeview_row_activate (self, treeview, path, treeview_column):
		self.check_bank_charge_validity()

	def bank_charge_spinbutton_amount_changed (self, button):
		self.check_bank_charge_validity()

	def description_entry_changed (self, entry):
		self.check_bank_charge_validity()
		
	def check_bank_charge_validity (self):
		button = self.get_object('button3')
		button.set_sensitive(False)
		self.amount = self.get_object('spinbutton2').get_value()
		if self.amount == 0.00:
			button.set_label('No amount entered')
			return
		self.description = self.get_object('combobox-entry').get_text()
		if self.description == '':
			button.set_label('No description')
			return
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path != []:
			iter_ = model.get_iter(path)
			if model.iter_has_child(iter_) == True:
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
		self.get_object('entry1').set_text(day_text)

	def calendar_entry_icon_released (self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()

	def credit_card_statement_activated (self, menuitem):
		import credit_card_statements
		credit_card_statements.CreditCardStatementGUI()
	
	def miscellaneous_revenue_activated (self, button):
		import miscellaneous_revenue
		miscellaneous_revenue.MiscellaneousRevenueGUI ()

	def loan_payment_activated (self, widget):
		import loan_payment
		loan_payment.LoanPaymentGUI()

	def double_entry_transaction_activated (self, menuitem):
		import double_entry_transaction
		double_entry_transaction.DoubleEntryTransactionGUI()

	def incoming_invoices_activated (self, menuitem):
		import incoming_invoice
		incoming_invoice.IncomingInvoiceGUI()

	
