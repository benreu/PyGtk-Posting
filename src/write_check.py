# incoming_invoice.py
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

from gi.repository import Gtk, GdkPixbuf, Gdk
import os, sys, re
from datetime import datetime, timedelta
from dateutils import DateTimeCalendar
from check_writing import convert_numeric_to_text, get_check_number
from db.transactor import post_incoming_invoice_expense,\
							service_provider_check_payment,\
							service_provider_transfer ,\
							service_provider_cash_payment
import contacts
import main

UI_FILE = main.ui_directory + "/incoming_invoice.ui"

class WriteCheckGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		date_text = self.calendar.get_text ()
		self.builder.get_object('entry2').set_text(date_text)
		
		self.populating = False
		self.service_provider_store = self.builder.get_object(
													'service_provider_store')
		self.expense_account_store = self.builder.get_object(  
													'expense_account_store')
		self.expense_percentage_store = self.builder.get_object(
													'expense_percentage_store')
		self.bank_account_store = self.builder.get_object('bank_account_store')
		self.cash_account_store = self.builder.get_object('cash_account_store')
		self.populate_stores ()
		self.expense_percentage_store.append([0, 0.00, 0, ""])
		self.calculate_percentages ()
	
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def focus (self, window, event):
		self.populating = True
		self.expense_account_store.clear()
		self.cursor.execute("SELECT number, name FROM accounts "
							" WHERE number > 3000 AND number < 4000 "
							"AND is_parent = False")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.expense_account_store.append([str(account_number), account_name])
		combo = self.builder.get_object('combobox1')
		active_sp = combo.get_active_id()
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE service_provider = True")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			self.service_provider_store.append([str(contact_id), contact_name])
		combo.set_active_id(active_sp)
		self.populating = False

	def populate_stores (self):
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE service_provider = True")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			self.service_provider_store.append([str(contact_id), contact_name])
		self.cursor.execute("SELECT number, name FROM accounts "
							"WHERE bank_account = True ")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.bank_account_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM accounts "
							"WHERE cash_account = True ")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.cash_account_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM accounts "
							" WHERE number > 3000 AND number < 4000")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.expense_account_store.append([str(account_number), account_name])

	def service_provider_clicked (self, button):
		contacts.GUI(self.db)

	def service_provider_combo_changed (self, combo):
		if self.populating == True:
			return
		self.check_if_all_entries_valid ()
		a_iter = combo.get_active_iter()
		path = self.service_provider_store.get_path(a_iter)
		contact_name = self.service_provider_store[path][1]
		self.builder.get_object('label14').set_label(contact_name)

	def add_percentage_row_clicked (self, button):
		self.expense_percentage_store.append([0, 0.00, 0, ""])
		self.calculate_percentages ()

	def delete_percentage_row_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			tree_iter = model.get_iter(path)
			self.expense_percentage_store.remove(tree_iter)
		self.calculate_percentages ()

	def calculate_percentages (self):
		lines = self.expense_percentage_store.iter_n_children()
		if lines == 0:
			return
		percentage = 100 / lines
		invoice_amount = self.builder.get_object('spinbutton1').get_text()
		percent = float(percentage) / 100.00
		split_amount = float(invoice_amount) * percent
		for row in self.expense_percentage_store:
			row[0] = percentage
			row[1] = split_amount
		self.add_expense_totals ()

	def invoice_spinbutton_changed (self, spinbutton):
		self.update_expense_amounts ()

	def update_expense_amounts (self):
		invoice_amount = self.builder.get_object('spinbutton1').get_text()
		for row in self.expense_percentage_store:
			percentage = row[0]
			percent = float(percentage) / 100.00
			split_amount = float(invoice_amount) * percent
			row[1] = split_amount
		self.add_expense_totals ()

	def percent_render_edited (self, renderer, path, text):
		self.expense_percentage_store[path][0] = int(text)
		invoice_amount = self.builder.get_object('spinbutton1').get_text()
		percent = float(text) / 100.00
		split_amount = float(invoice_amount) * percent
		self.expense_percentage_store[path][1] = split_amount
		self.add_expense_totals ()

	def add_expense_totals (self):
		total = 0.00
		for row in self.expense_percentage_store:
			total += row[1]
		cents = '{:.2f}'.format(total % 1)
		self.builder.get_object('label11').set_label(cents[2:])
		money_text = convert_numeric_to_text (total)
		self.builder.get_object('label10').set_label(money_text)
		self.builder.get_object('entry4').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry5').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry6').set_text('${:,.2f}'.format(total))
		self.check_if_all_entries_valid ()

	def expense_account_render_changed (self, renderer, path, tree_iter):
		account_number = self.expense_account_store[tree_iter][0]
		account_name = self.expense_account_store[tree_iter][1]
		self.expense_percentage_store[path][2] = int(account_number)
		self.expense_percentage_store[path][3] = account_name
		self.check_if_all_entries_valid ()

	def bank_credit_card_combo_changed (self, combo):
		if combo.get_active() == None:
			self.builder.get_object('entry3').set_sensitive(False)
			self.builder.get_object('entry5').set_sensitive(False)
		else:
			self.builder.get_object('entry3').set_sensitive(True)
			self.builder.get_object('entry5').set_sensitive(True)
			bank_account = combo.get_active_id()
			check_number = get_check_number(self.db, bank_account)
			self.builder.get_object('entry7').set_text(str(check_number))
		self.check_if_all_entries_valid ()

	def cash_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def transaction_entry_changed (self, entry):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		check_button = self.builder.get_object('button3')
		transfer_button = self.builder.get_object('button4')
		cash_button = self.builder.get_object('button5')
		check_button.set_sensitive(False)
		transfer_button.set_sensitive(False)
		cash_button.set_sensitive(False)
		if self.builder.get_object('combobox1').get_active() == -1:
			self.set_button_message('No service provider')
			return # no service provider selected
		invoice_amount = float(self.builder.get_object('spinbutton1'
																).get_text())
		if invoice_amount == 0.00:
			self.set_button_message('No invoice amount')
			return
		text = self.builder.get_object('entry4').get_text()
		payment_amount = float(re.sub("[^0-9.]", "", text))
		if invoice_amount != payment_amount:
			self.set_button_message('Invoice amount does not match payment')
			return
		for row in self.expense_percentage_store:
			if row[2] == 0:
				self.set_button_message('Missing expense accounts')
				return
		if self.builder.get_object('combobox3').get_active() > -1:
			#cash account selected
			cash_button.set_label('Cash payment')
			cash_button.set_sensitive(True)
		else:
			cash_button.set_label('No cash account selected')
		if self.builder.get_object('combobox2').get_active() > -1:
			# bank / credit card selected
			check_button.set_label('Check payment')
			check_button.set_sensitive(True)
			if self.builder.get_object('entry3').get_text() != "":
				transfer_button.set_label('Transfer payment')
				transfer_button.set_sensitive(True)
			else:
				transfer_button.set_label('No transfer number')
		else:
			check_button.set_label('No bank account selected')
			transfer_button.set_label('No bank account selected')

	def set_button_message (self, message):
		self.builder.get_object('button3').set_label(message)
		self.builder.get_object('button4').set_label(message)
		self.builder.get_object('button5').set_label(message)

	def cash_payment_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		cash_account = self.builder.get_object('combobox3').get_active_id()
		service_provider_cash_payment (self.db, self.datetime, total, 
										cash_account)
		self.db.commit()
		self.window.destroy()

	def transfer_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		checking_account = self.builder.get_object('combobox2').get_active_id()
		transfer_number = self.builder.get_object('entry3').get_text()
		service_provider_transfer (self.db, self.datetime, total, 
										transfer_number, checking_account)
		self.db.commit()
		self.window.destroy()

	def print_check_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		checking_account = self.builder.get_object('combobox2').get_active_id()
		check_number = self.builder.get_object('entry7').get_text()
		service_provider_check_payment(self.db, self.datetime, total, 
										check_number, checking_account)
		self.db.commit()
		self.window.destroy()

	def save_incoming_invoice (self):
		contact_id = self.builder.get_object('combobox1').get_active_id()
		description = self.builder.get_object('entry1').get_text()
		total = float(self.builder.get_object('spinbutton1').get_text())
		self.cursor.execute("INSERT INTO incoming_invoices "
							"(contact_id, date_created, amount, description) "
							"VALUES (%s, %s, %s, %s) RETURNING id", 
							(contact_id, self.datetime, total, description))
		invoice_id = self.cursor.fetchone()[0]
		for row in self.expense_percentage_store:
			amount = row[1]
			expense_account = row[2]
			post_incoming_invoice_expense(self.db, self.datetime, amount, 
															expense_account)
		return invoice_id, total

	def calendar_day_selected (self, calendar):
		self.datetime = calendar.get_datetime()
		day_text = calendar.get_text()
		self.builder.get_object('entry2').set_text(day_text)

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()
		

		
