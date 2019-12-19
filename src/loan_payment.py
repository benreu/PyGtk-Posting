# loan_payment.py
#
# Copyright (C) 2017 - reuben
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

from gi.repository import Gtk, Gdk, GLib, GObject
from check_writing import get_written_check_amount_text, get_check_number
from dateutils import DateTimeCalendar
from db import transactor 
from constants import ui_directory, DB

UI_FILE = ui_directory + "/loan_payment.ui"

class LoanPaymentGUI:
	def __init__(self, loan_id = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		self.loan_id = None
		self.loan_store = self.builder.get_object('loan_store')
		self.cash_store = self.builder.get_object('cash_store')
		self.loan_account_store = self.builder.get_object('loan_account_store')
		self.bank_store = self.builder.get_object('bank_store')
		self.expense_store = self.builder.get_object('expense_store')
		self.populate_stores()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		if loan_id != None:
			self.builder.get_object('combobox1').set_active_id(str(loan_id))

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(entry.select_region, 0, -1)

	def destroy (self, widget):
		self.cursor.close()

	def populate_stores (self):
		self.cursor.execute("SELECT l.id::text, l.description, c.id::text, c.name "
							"FROM loans AS l "
							"JOIN contacts AS c ON c.id = l.contact_id "
							"WHERE finished = False ORDER BY description")
		for row in self.cursor.fetchall():
			self.loan_store.append(row)
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE bank_account = True")
		for row in self.cursor.fetchall():
			self.bank_store.append(row)
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE cash_account = True")
		for row in self.cursor.fetchall():
			self.cash_store.append(row)
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE type = 3 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			parent_tree = self.expense_store.append(None, row)
			self.get_child_accounts (self.expense_store, row[0], parent_tree)
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE type = 5 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			parent_tree = self.loan_account_store.append(None, row)
			self.get_child_accounts (self.loan_account_store, row[0], parent_tree)
		DB.rollback()

	def get_child_accounts (self, store, parent_number, parent_tree):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE parent_number = %s", (parent_number,))
		for row in self.cursor.fetchall():
			parent = store.append(parent_tree, row)
			self.get_child_accounts (store, row[0], parent)

	def loan_combo_changed (self, combo):
		loan_id = combo.get_active_id()
		iter_ = combo.get_active()
		if loan_id != None:
			iter_ = combo.get_active()
			self.contact_id = self.loan_store[iter_][2]
			self.loan_id = loan_id
			contact_name = self.loan_store[iter_][3]
			self.builder.get_object('label16').set_label(contact_name)
			self.check_if_all_requirements_valid ()

	def bank_combo_changed (self, combo):
		bank_account = combo.get_active_id()
		if bank_account != None:
			self.builder.get_object('entry3').set_sensitive(True)
			check_number = get_check_number(bank_account)
			self.builder.get_object('entry7').set_text(str(check_number))
		self.check_if_all_requirements_valid ()

	def check_if_all_requirements_valid (self):
		check_button = self.builder.get_object('button3')
		transfer_button = self.builder.get_object('button4')
		cash_button = self.builder.get_object('button5')
		check_button.set_sensitive(False)
		transfer_button.set_sensitive(False)
		cash_button.set_sensitive(False)
		if self.loan_id == None:
			self.set_button_message('No contact selected')
			return # no contact selected
		if self.date == None:
			self.set_button_message('No date selected')
			return # no date selected
		interest_selection = self.builder.get_object('treeview-selection3')
		model, path = interest_selection.get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				self.set_button_message('Interest parent account selected')
				return # parent account selected
		else:
			self.set_button_message ('No interest account selected')
			return # no account selected
		principal_selection = self.builder.get_object('treeview-selection2')
		model, path = principal_selection.get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				self.set_button_message('Principal parent account selected')
				return # parent account selected
		else:
			self.set_button_message ('No principal account selected')
			return # no account selected
		principal = self.builder.get_object('spinbutton1').get_value()
		interest = self.builder.get_object('spinbutton2').get_value()
		self.total = principal + interest
		if self.total == 0.00:
			self.set_button_message ('Principal + interest is $0.00')
			return # no account selected
		cash_account = self.builder.get_object('combobox3').get_active_id()
		if cash_account != None:
			self.builder.get_object('button5').set_label('Cash payment')
			self.builder.get_object('button5').set_sensitive(True)
		else:
			self.builder.get_object('button5').set_label('No cash account selected')
		bank_account = self.builder.get_object('combobox4').get_active_id()
		if bank_account != None:
			if self.builder.get_object('entry3').get_text() != '':
				self.builder.get_object('button4').set_label('Transfer payment')
				self.builder.get_object('button4').set_sensitive(True)
			else:
				self.builder.get_object('button4').set_label('No transfer number')
			self.builder.get_object('button3').set_sensitive(True)
			self.builder.get_object('button3').set_label('Check payment')
		else:
			self.builder.get_object('button3').set_label('No bank account selected')
			self.builder.get_object('button4').set_label('No bank account selected')

	def set_button_message (self, message):
		self.builder.get_object('button3').set_label(message)
		self.builder.get_object('button4').set_label(message)
		self.builder.get_object('button5').set_label(message)

	def cash_payment_clicked (self, button):
		self.principal_and_interest_payment ()
		cash_account = self.builder.get_object('combobox3').get_active_id()
		self.total_id = self.loan_payment.cash (cash_account)
		self.update_loan_payment_ids ()
		DB.commit()
		self.window.destroy()

	def transfer_payment_clicked (self, button):
		self.principal_and_interest_payment ()
		transaction_number = self.builder.get_object('entry3').get_text()
		bank_account = self.builder.get_object('combobox4').get_active_id()
		self.total_id = self.loan_payment.bank_transfer(bank_account, transaction_number)
		self.update_loan_payment_ids ()
		DB.commit()
		self.window.destroy()

	def check_payment_clicked (self, button):
		self.principal_and_interest_payment ()
		bank_account = self.builder.get_object('combobox4').get_active_id()
		check_number = self.builder.get_object('entry7').get_text()
		active = self.builder.get_object('combobox1').get_active()
		contact_name = self.loan_store[active][2]
		self.total_id = self.loan_payment.bank_check (bank_account, check_number, contact_name)
		self.update_loan_payment_ids ()
		DB.commit()
		self.window.destroy()

	def principal_and_interest_payment (self):
		self.loan_payment = transactor.LoanPayment(self.date, 
													self.total, self.loan_id)
		#### interest
		interest = self.builder.get_object('spinbutton2').get_value()
		interest_selection = self.builder.get_object('treeview-selection3')
		model, path = interest_selection.get_selected_rows()
		interest_account = model[path][0]
		self.interest_id = self.loan_payment.interest (interest_account, interest)
		#### principal
		principal = self.builder.get_object('spinbutton1').get_value()
		principal_selection = self.builder.get_object('treeview-selection2')
		model, path = principal_selection.get_selected_rows()
		principal_account = model[path][0]
		self.principal_id = self.loan_payment.principal (principal_account, principal)

	def update_loan_payment_ids (self):
		self.cursor.execute("INSERT INTO loan_payments "
								"(loan_id, "
								"gl_entries_principal_id, "
								"gl_entries_interest_id, "
								"gl_entries_total_id, "
								"contact_id "
								") "
							"VALUES (%s, %s, %s, %s, %s); "
							"UPDATE loans SET last_payment_date = CURRENT_DATE "
							"WHERE id = %s", 
							(self.loan_id,
							self.principal_id,
							self.interest_id,
							self.total_id, 
							self.contact_id, 
							self.loan_id))

	def row_activate (self, treeview, path, treeviewcolumn):
		self.check_if_all_requirements_valid ()

	def cash_combo_changed (self, combo):
		self.check_if_all_requirements_valid ()

	def transaction_number_changed (self, entry):
		self.check_if_all_requirements_valid ()

	def principal_spinbutton_changed (self, spinbutton):
		self.calculate_payment_total()

	def interest_spinbutton_changed (self, spinbutton):
		self.calculate_payment_total()

	def calculate_payment_total (self):
		principal = self.builder.get_object('spinbutton1').get_value()
		interest = self.builder.get_object('spinbutton2').get_value()
		self.total = principal + interest
		money_text = get_written_check_amount_text (self.total)
		self.builder.get_object('label15').set_label(money_text)
		formatted_total = '{:,.2f}'.format(self.total)
		self.builder.get_object('entry4').set_text(formatted_total)
		self.builder.get_object('entry5').set_text(formatted_total)
		self.builder.get_object('entry6').set_text(formatted_total)
		self.check_if_all_requirements_valid ()

	def calendar_day_selected(self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)
		self.check_if_all_requirements_valid()

	def calendar_entry_icon_released(self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()





