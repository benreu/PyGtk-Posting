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

from gi.repository import Gtk, GLib, Gdk
import re
from decimal import Decimal, ROUND_HALF_UP
from dateutils import DateTimeCalendar
from check_writing import set_written_ck_amnt_text, get_check_number
from db import transactor

UI_FILE = "src/incoming_invoice.ui"

class IncomingInvoiceGUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		main.connect ("contacts_changed", self.populate_service_providers )
		self.expense_account_store = main.expense_acc
		self.builder.get_object('cellrenderercombo1').set_property('model', main.expense_acc)
		
		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None

		price_column = self.builder.get_object ('treeviewcolumn2')
		price_renderer = self.builder.get_object ('cellrenderertext1')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)
		
		self.populating = False
		self.service_provider_store = self.builder.get_object(
													'service_provider_store')
		self.expense_percentage_store = self.builder.get_object(
													'expense_percentage_store')
		self.bank_account_store = self.builder.get_object('bank_account_store')
		self.cash_account_store = self.builder.get_object('cash_account_store')
		self.credit_card_store = self.builder.get_object('credit_card_store')
		self.populate_stores ()
		self.populate_service_providers ()
		self.expense_percentage_store.append([0, Decimal('0.00'), 0, ""])
		self.calculate_percentages ()
	
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def amount_focus_in_event (self, entry, event):
		GLib.idle_add(self.highlight, entry)

	def highlight (self, entry):
		entry.select_region(0, -1)

	def focus (self, window, event):
		pass
		self.populating = False

	def populate_service_providers (self, m=None, i=None):
		self.populating = True
		combo = self.builder.get_object('combobox1')
		active_sp = combo.get_active_id()
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id, name, c_o FROM contacts "
							"WHERE service_provider = True "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			contact_co = row[2]
			self.service_provider_store.append([str(contact_id),
												contact_name,
												contact_co])
		combo.set_active_id(active_sp)
		self.populating = False

	def populate_stores (self):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE bank_account = True ORDER BY name ")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.bank_account_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE cash_account = True ORDER BY name ")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.cash_account_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE credit_card_account = True ORDER BY name ")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.credit_card_store.append([str(account_number), account_name])

	def service_provider_clicked (self, button):
		import contacts
		contacts.GUI(self.main)

	def service_provider_combo_changed (self, combo):
		if self.populating == True:
			return
		self.check_if_all_entries_valid ()
		a_iter = combo.get_active_iter()
		path = self.service_provider_store.get_path(a_iter)
		contact_name = self.service_provider_store[path][1]
		self.builder.get_object('label14').set_label(contact_name)

	def add_percentage_row_clicked (self, button):
		self.expense_percentage_store.append([0, Decimal('0.00'), 0, ""])
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
		percentage = Decimal('100') / lines
		invoice_amount = self.builder.get_object('spinbutton1').get_text()
		percent = Decimal(percentage) / Decimal('100')
		split_amount = Decimal(invoice_amount) * percent
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
			percent = Decimal(percentage) / 100
			split_amount = Decimal(invoice_amount) * percent
			row[1] = split_amount
		self.add_expense_totals ()

	def expense_amount_edited (self, renderer, path, text):
		value = Decimal(text).quantize(Decimal('0.01'), rounding = ROUND_HALF_UP)
		self.expense_percentage_store[path][1] = value
		self.add_expense_totals ()

	def price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 1)
		cellrenderer.set_property("text" , str(price))

	def percent_render_edited (self, renderer, path, text):
		self.expense_percentage_store[path][0] = int(text)
		invoice_amount = self.builder.get_object('spinbutton1').get_text()
		percent = Decimal(text) / Decimal('100')
		split_amount = Decimal(invoice_amount) * percent
		self.expense_percentage_store[path][1] = split_amount
		self.add_expense_totals ()

	def add_expense_totals (self):
		total = Decimal()
		for row in self.expense_percentage_store:
			total += row[1]
		money_text = set_written_ck_amnt_text (total)
		self.builder.get_object('label10').set_label(money_text)
		self.builder.get_object('entry4').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry5').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry6').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry8').set_text('${:,.2f}'.format(total))
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

	def credit_card_changed (self, combo):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		check_button = self.builder.get_object('button3')
		transfer_button = self.builder.get_object('button4')
		cash_button = self.builder.get_object('button5')
		credit_card_button = self.builder.get_object('button7')
		check_button.set_sensitive(False)
		#transfer_button.set_sensitive(False)
		cash_button.set_sensitive(False)
		credit_card_button.set_sensitive(False)
		if self.builder.get_object('combobox1').get_active() == -1:
			self.set_button_message('No service provider')
			return # no service provider selected
		if self.date == None:
			self.set_button_message('No date selected')
			return
		invoice_amount = Decimal(self.builder.get_object('spinbutton1'
																).get_text())
		if invoice_amount == 0.00:
			self.set_button_message('No invoice amount')
			return
		text = self.builder.get_object('entry4').get_text()
		payment_amount = Decimal(re.sub("[^0-9.]", "", text))
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
		if self.builder.get_object('combobox4').get_active() > -1:
			#cash account selected
			credit_card_button.set_label('Credit card payment')
			credit_card_button.set_sensitive(True)
		else:
			credit_card_button.set_label('No credit card selected')
		if self.builder.get_object('combobox2').get_active() > -1:
			# bank / credit card selected
			check_button.set_label('Check payment')
			check_button.set_sensitive(True)
			transfer_button.set_label('Transfer payment')
			transfer_button.set_sensitive(True)
			'''if self.builder.get_object('entry3').get_text() != "":
				transfer_button.set_label('Transfer payment')
				transfer_button.set_sensitive(True)
			else:
				transfer_button.set_label('No transfer number')'''
		else:
			check_button.set_label('No bank account selected')
			transfer_button.set_label('No bank account selected')

	def set_button_message (self, message):
		self.builder.get_object('button3').set_label(message)
		self.builder.get_object('button4').set_label(message)
		self.builder.get_object('button5').set_label(message)
		self.builder.get_object('button7').set_label(message)

	def cash_payment_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		cash_account = self.builder.get_object('combobox3').get_active_id()
		self.invoice.cash_payment (total, cash_account)
		self.db.commit()
		self.window.destroy()

	def credit_card_payment_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		credit_card = self.builder.get_object('combobox4').get_active_id()
		transfer_number = self.builder.get_object('entry3').get_text()
		active = self.builder.get_object('combobox1').get_active()
		service_provider = self.service_provider_store[active][1]
		description = "%s : %s" % (service_provider, transfer_number)
		self.invoice.credit_card_payment (total, description, credit_card)
		self.db.commit()
		self.window.destroy()

	def transfer_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		checking_account = self.builder.get_object('combobox2').get_active_id()
		transfer_number = self.builder.get_object('entry3').get_text()
		active = self.builder.get_object('combobox1').get_active()
		service_provider = self.service_provider_store[active][1]
		description = "%s : %s" % (service_provider, transfer_number)
		self.invoice.transfer (total, description, checking_account)
		self.db.commit()
		self.window.destroy()

	def print_check_clicked (self, button):
		invoice_id, total = self.save_incoming_invoice ()
		checking_account = self.builder.get_object('combobox2').get_active_id()
		check_number = self.builder.get_object('entry7').get_text()
		active = self.builder.get_object('combobox1').get_active()
		description = self.service_provider_store[active][1]
		self.invoice.check_payment(total, check_number, checking_account, description)
		self.db.commit()
		self.window.destroy()

	def save_incoming_invoice (self):
		contact_id = self.builder.get_object('combobox1').get_active_id()
		description = self.builder.get_object('entry1').get_text()
		total = Decimal(self.builder.get_object('spinbutton1').get_text())
		self.invoice = transactor.ServiceProviderPayment (self.db, 
															self.date, 
															total)
		self.cursor.execute("INSERT INTO incoming_invoices "
							"(contact_id, date_created, amount, description) "
							"VALUES (%s, %s, %s, %s) RETURNING id", 
							(contact_id, self.date, total, description))
		invoice_id = self.cursor.fetchone()[0]
		for row in self.expense_percentage_store:
			amount = row[1]
			expense_account = row[2]
			self.invoice.expense(amount, expense_account)
		return invoice_id, total

	def balance_this_row_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_sum = Decimal()
		for row in self.expense_percentage_store:
			if row.path != path[0]:
				tree_sum += row[1]
		total = Decimal(self.builder.get_object('spinbutton1').get_text())
		model[path][1] = (total - tree_sum)
		self.add_expense_totals ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry2').set_text(day_text)
		self.check_if_all_entries_valid ()

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()
		

		