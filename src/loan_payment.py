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
from check_writing import set_written_ck_amnt_text, get_check_number
from dateutils import DateTimeCalendar
from db import transactor 

UI_FILE = "src/loan_payment.ui"

class LoanPaymentGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.calendar = DateTimeCalendar(self.db)		
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		self.contact_id = None
		contact_completion = self.builder.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		self.contact_store = self.builder.get_object('contact_store')
		self.cash_store = self.builder.get_object('cash_store')
		self.loan_store = self.builder.get_object('loan_store')
		self.bank_store = self.builder.get_object('bank_store')
		self.expense_store = self.builder.get_object('expense_store')
		self.populate_stores()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(self.highlight, entry)

	def highlight (self, entry):
		entry.select_region(0, -1)

	def populate_stores (self):
		self.cursor.execute("SELECT id, name, c_o FROM contacts "
							"WHERE (deleted, service_provider) = (False, True) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			contact_co = row[2]
			self.contact_store.append([str(contact_id), contact_name, contact_co])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE bank_account = True")
		for row in self.cursor.fetchall():
			bank_account = row[0]
			bank_name = row[1]
			self.bank_store.append([str(bank_account), bank_name])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE cash_account = True")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.cash_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE type = 3 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent_tree = self.expense_store.append(None,[account_number, 
																account_name])
			self.get_child_accounts (self.expense_store, account_number, parent_tree)
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE type = 5 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent_tree = self.loan_store.append(None,[account_number, 
																account_name])
			self.get_child_accounts (self.loan_store, account_number, parent_tree)

	def get_child_accounts (self, store, parent_number, parent_tree):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE parent_number = %s", (parent_number,))
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent = store.append(parent_tree,[account_number, account_name])
			self.get_child_accounts (store, account_number, parent)

	def contact_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[tree_iter][1].lower():
				return False
		return True

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		iter_ = combo.get_active()
		if contact_id != None:
			self.contact_id = contact_id
			contact_name = self.contact_store[iter_][1]
			self.builder.get_object('label16').set_label(contact_name)
			self.check_if_all_requirements_valid ()

	def contact_match_selected (self, completion, model, iter_):
		self.contact_id = model[iter_][0]
		contact_name = model[iter_][1]
		self.builder.get_object('label16').set_label(contact_name)
		self.check_if_all_requirements_valid ()

	def bank_combo_changed (self, combo):
		bank_account = combo.get_active_id()
		if bank_account != None:
			self.builder.get_object('entry3').set_sensitive(True)
			check_number = get_check_number(self.db, bank_account)
			self.builder.get_object('entry7').set_text(str(check_number))
		self.check_if_all_requirements_valid ()

	def check_if_all_requirements_valid (self):
		check_button = self.builder.get_object('button3')
		transfer_button = self.builder.get_object('button4')
		cash_button = self.builder.get_object('button5')
		check_button.set_sensitive(False)
		transfer_button.set_sensitive(False)
		cash_button.set_sensitive(False)
		if self.contact_id == None:
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
		self.loan_payment.cash (cash_account)
		self.db.commit()
		self.window.destroy()

	def transfer_payment_clicked (self, button):
		self.principal_and_interest_payment ()
		transaction_number = self.builder.get_object('entry3').get_text()
		bank_account = self.builder.get_object('combobox4').get_active_id()
		self.loan_payment.bank_transfer(bank_account, transaction_number)
		self.db.commit()
		self.window.destroy()

	def check_payment_clicked (self, button):
		self.principal_and_interest_payment ()
		bank_account = self.builder.get_object('combobox4').get_active_id()
		check_number = self.builder.get_object('entry7').get_text()
		contact_name = self.builder.get_object('combobox-entry').get_text()
		self.loan_payment.bank_check (bank_account, check_number, contact_name)
		self.db.commit()
		self.window.destroy()

	def principal_and_interest_payment (self):
		self.loan_payment = transactor.LoanPayment(self.db, self.date, 
													self.total, self.contact_id)
		#### interest
		interest = self.builder.get_object('spinbutton2').get_value()
		interest_selection = self.builder.get_object('treeview-selection3')
		model, path = interest_selection.get_selected_rows()
		interest_account = model[path][0]
		self.loan_payment.interest (interest_account, interest)
		#### principal
		principal = self.builder.get_object('spinbutton1').get_value()
		principal_selection = self.builder.get_object('treeview-selection2')
		model, path = principal_selection.get_selected_rows()
		principal_account = model[path][0]
		self.loan_payment.principal (principal_account, principal)

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
		money_text = set_written_ck_amnt_text (self.total)
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

	def calendar_entry_icon_released(self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()




		
