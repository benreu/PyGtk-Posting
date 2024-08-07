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

from gi.repository import Gtk, GLib, GObject
import re
from decimal import Decimal, ROUND_HALF_UP
from dateutils import DateTimeCalendar
from check_writing import get_written_check_amount_text, get_check_number
from db import transactor
from constants import ui_directory, DB, broadcaster, template_dir
from accounts import expense_list, expense_tree
import subprocess, printing


class Item(object):#this is used by py3o library see their example for more info
	pass

UI_FILE = ui_directory + "/incoming_invoice.ui"

class IncomingInvoiceGUI(Gtk.Builder):
	__gsignals__ = { 
	'invoice_applied': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ())
	}
	"""the invoice_applied signal is used to send a message to the parent 
		window that the incoming invoice is now finished"""
	def __init__(self):

		GObject.GObject.__init__(self)
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_service_providers ),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.expense_account_store = expense_tree
		self.get_object('cellrenderercombo1').set_property('model', expense_tree)
		self.get_object('account_completion').set_model(expense_list)
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None

		price_column = self.get_object ('treeviewcolumn2')
		price_renderer = self.get_object ('cellrenderertext1')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)
		provider_completion = self.get_object('provider_completion')
		provider_completion.set_match_func(self.provider_match_func)
		
		self.populating = False
		self.service_provider_store = self.get_object(
													'service_provider_store')
		self.expense_percentage_store = self.get_object(
													'expense_percentage_store')
		self.bank_account_store = self.get_object('bank_account_store')
		self.cash_account_store = self.get_object('cash_account_store')
		self.credit_card_store = self.get_object('credit_card_store')
		self.populate_stores ()
		self.populate_service_providers ()
		self.expense_percentage_store.append([0, Decimal('1.00'), 0, "", "", ""])
	
		self.window = self.get_object('window1')
		self.window.show_all()
		self.file_data = None

	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def provider_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.service_provider_store[iter_][1].lower():
				return False
		return True

	def amount_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def focus (self, window, event):
		pass
		self.populating = False

	def populate_service_providers (self, m=None, i=None):
		self.populating = True
		combo = self.get_object('combobox1')
		active_sp = combo.get_active_id()
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE service_provider = True "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.service_provider_store.append(row)
		combo.set_active_id(active_sp)
		self.populating = False
		DB.rollback()

	def populate_stores (self):
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE check_writing = True ORDER BY name ")
		for row in self.cursor.fetchall():
			self.bank_account_store.append(row)
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE cash_account = True ORDER BY name ")
		for row in self.cursor.fetchall():
			self.cash_account_store.append(row)
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE credit_card_account = True ORDER BY name ")
		for row in self.cursor.fetchall():
			self.credit_card_store.append(row)
		DB.rollback()

	def set_shipping_description (self, text):
		self.get_object('entry1').set_text(text)

	def set_date (self, date):
		self.calendar.set_date(date)

	def service_provider_clicked (self, button):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()
		
	def provider_match_selected(self, completion, model, iter_):
		self.provider_id = model[iter_][0]
		self.get_object('combobox1').set_active_id(self.provider_id)

	def service_provider_combo_changed (self, combo):
		if self.populating == True:
			return
		a_iter = combo.get_active_iter()
		if a_iter == None:
			return
		self.check_if_all_entries_valid ()
		contact_name = self.service_provider_store[a_iter][1]
		self.get_object('label14').set_label(contact_name)

	def add_percentage_row_clicked (self, button):
		self.expense_percentage_store.append([0, Decimal('1.00'), 0, "", "", ""])
		self.add_expense_totals ()

	def delete_percentage_row_clicked (self, button):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			tree_iter = model.get_iter(path)
			self.expense_percentage_store.remove(tree_iter)
		self.add_expense_totals ()

	def equalize_amounts_clicked (self, button):
		lines = self.expense_percentage_store.iter_n_children()
		if lines == 0:
			return
		percentage = Decimal('100') / lines
		invoice_amount = self.get_object('spinbutton1').get_text()
		percent = Decimal(percentage) / Decimal('100')
		split_amount = Decimal(invoice_amount) * percent
		for row in self.expense_percentage_store:
			row[0] = percentage
			row[1] = split_amount
		self.add_expense_totals ()

	def invoice_spinbutton_changed (self, spinbutton):
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
		invoice_amount = self.get_object('spinbutton1').get_text()
		percent = Decimal(text) / Decimal('100')
		split_amount = Decimal(invoice_amount) * percent
		self.expense_percentage_store[path][1] = split_amount
		self.add_expense_totals ()

	def add_expense_totals (self):
		total = Decimal()
		for row in self.expense_percentage_store:
			total += row[1]
		money_text = get_written_check_amount_text (total)
		self.get_object('label10').set_label(money_text)
		self.get_object('entry4').set_text('${:,.2f}'.format(total))
		self.get_object('entry5').set_text('${:,.2f}'.format(total))
		self.get_object('entry6').set_text('${:,.2f}'.format(total))
		self.get_object('entry8').set_text('${:,.2f}'.format(total))
		self.check_if_all_entries_valid ()

	def expense_account_render_changed (self, renderer, path, tree_iter):
		account_number = self.expense_account_store[tree_iter][0]
		account_name = self.expense_account_store[tree_iter][1]
		account_path = self.expense_account_store[tree_iter][2]
		self.expense_percentage_store[path][2] = int(account_number)
		self.expense_percentage_store[path][3] = account_name
		self.expense_percentage_store[path][4] = account_path
		self.check_if_all_entries_valid ()

	def expense_combo_editing_started (self, cellrenderer, celleditable, path):
		entry = celleditable.get_child()
		entry.set_completion(self.get_object('account_completion'))

	def account_match_selected (self, entrycompletion, model, treeiter):
		selection = self.get_object('treeview-selection1')
		treeview_model, path = selection.get_selected_rows()
		if path == []:
			return
		account_number = model[treeiter][0]
		account_name = model[treeiter][1]
		account_path = model[treeiter][2]
		treeview_model[path][2] = int(account_number)
		treeview_model[path][3] = account_name
		treeview_model[path][4] = account_path
		self.check_if_all_entries_valid()

	def remark_edited (self, cellrenderertext, path, text):
		self.expense_percentage_store[path][5] = text

	def bank_credit_card_combo_changed (self, combo):
		if combo.get_active() == None:
			self.get_object('entry3').set_sensitive(False)
			self.get_object('entry5').set_sensitive(False)
		else:
			self.get_object('entry3').set_sensitive(True)
			self.get_object('entry5').set_sensitive(True)
			bank_account = combo.get_active_id()
			check_number = get_check_number(bank_account)
			self.get_object('entry7').set_text(str(check_number))
		self.check_if_all_entries_valid ()

	def cash_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def transaction_entry_changed (self, entry):
		self.check_if_all_entries_valid ()

	def credit_card_changed (self, combo):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		check_button = self.get_object('button3')
		print_and_post_button = self.get_object('button9')
		transfer_button = self.get_object('button4')
		cash_button = self.get_object('button5')
		credit_card_button = self.get_object('button7')
		check_button.set_sensitive(False)
		print_and_post_button.set_sensitive(False)
		cash_button.set_sensitive(False)
		credit_card_button.set_sensitive(False)
		if self.get_object('combobox1').get_active() == -1:
			self.set_button_message('No service provider')
			return # no service provider selected
		if self.date == None:
			self.set_button_message('No date selected')
			return
		invoice_amount = Decimal(self.get_object('spinbutton1').get_text())
		if invoice_amount == 0.00:
			self.set_button_message('No invoice amount')
			return
		text = self.get_object('entry4').get_text()
		payment_amount = Decimal(re.sub("[^0-9.]", "", text))
		if invoice_amount != payment_amount:
			self.set_button_message('Invoice amount does not match payment')
			return
		for row in self.expense_percentage_store:
			if row[2] == 0:
				self.set_button_message('Missing expense accounts')
				return
		if self.get_object('combobox3').get_active() > -1:
			#cash account selected
			cash_button.set_label('Cash payment')
			cash_button.set_sensitive(True)
		else:
			cash_button.set_label('No cash account selected')
		if self.get_object('combobox4').get_active() > -1:
			#cash account selected
			credit_card_button.set_label('Credit card payment')
			credit_card_button.set_sensitive(True)
		else:
			credit_card_button.set_label('No credit card selected')
		if self.get_object('combobox2').get_active() > -1:
			# bank / credit card selected
			check_button.set_label('Post cheque payment')
			check_button.set_sensitive(True)
			print_and_post_button.set_label('Print cheque & post payment')
			print_and_post_button.set_sensitive(True)
			transfer_button.set_label('Transfer payment')
			transfer_button.set_sensitive(True)
		else:
			check_button.set_label('No bank account selected')
			print_and_post_button.set_label('No bank account selected')
			transfer_button.set_label('No bank account selected')

	def set_button_message (self, message):
		self.get_object('button3').set_label(message)
		self.get_object('button4').set_label(message)
		self.get_object('button5').set_label(message)
		self.get_object('button7').set_label(message)
		self.get_object('button9').set_label("")

	def cash_payment_clicked (self, button):
		total = self.save_incoming_invoice ()
		cash_account = self.get_object('combobox3').get_active_id()
		self.invoice.cash_payment (total, cash_account)
		DB.commit()
		self.emit('invoice_applied')
		self.set_buttons_insensitive()

	def credit_card_payment_clicked (self, button):
		total = self.save_incoming_invoice ()
		credit_card = self.get_object('combobox4').get_active_id()
		transfer_number = self.get_object('entry3').get_text()
		active = self.get_object('combobox1').get_active()
		service_provider = self.service_provider_store[active][1]
		description = "%s : %s" % (service_provider, transfer_number)
		self.invoice.credit_card_payment (total, description, credit_card)
		DB.commit()
		self.emit('invoice_applied')
		self.set_buttons_insensitive()

	def transfer_clicked (self, button):
		total = self.save_incoming_invoice ()
		checking_account = self.get_object('combobox2').get_active_id()
		transfer_number = self.get_object('entry3').get_text()
		active = self.get_object('combobox1').get_active()
		service_provider = self.service_provider_store[active][1]
		description = "%s : %s" % (service_provider, transfer_number)
		self.invoice.transfer (total, description, checking_account)
		DB.commit()
		self.emit('invoice_applied')
		self.set_buttons_insensitive()

	def post_only_clicked (self,button):
		self.perform_cheque_payment()

	def perform_cheque_payment(self):
		total = self.save_incoming_invoice ()
		checking_account = self.get_object('combobox2').get_active_id()
		check_number = self.get_object('entry7').get_text()
		active = self.get_object('combobox1').get_active()
		description = self.service_provider_store[active][1]
		self.invoice.check_payment(total, check_number, checking_account, description)
		DB.commit()
		self.emit('invoice_applied')
		check_number = get_check_number(checking_account)
		self.get_object('entry7').set_text(str(check_number))
		self.file_data = None
		self.set_buttons_insensitive()

	def set_buttons_insensitive (self):
		self.get_object('button3').set_sensitive(False)
		self.get_object('button4').set_sensitive(False)
		self.get_object('button5').set_sensitive(False)
		self.get_object('button7').set_sensitive(False)
		self.get_object('button9').set_sensitive(False)

	def save_incoming_invoice (self):
		c = DB.cursor()
		contact_id = self.get_object('combobox1').get_active_id()
		description = self.get_object('entry1').get_text()
		total = Decimal(self.get_object('spinbutton1').get_text())
		self.invoice = transactor.ServiceProviderPayment (
															self.date, 
															total)
		c.execute(	"INSERT INTO incoming_invoices "
						"(contact_id, "
						"date_created, "
						"amount, "
						"description, "
						"gl_transaction_id, "
						"attached_pdf) "
					"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", 
					(contact_id, self.date, total, description, 
					self.invoice.transaction_id, self.file_data))
		self.invoice_id = c.fetchone()[0] # self.invoice_id is a public variable
		self.invoice.incoming_invoice_id = self.invoice_id
		for row in self.expense_percentage_store:
			amount = row[1]
			account = row[2]
			remark = row[5]
			self.invoice.expense(amount, account, remark)
		c.close()
		return total

	def balance_this_row_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_sum = Decimal()
		for row in self.expense_percentage_store:
			if row.path != path[0]:
				tree_sum += row[1]
		total = Decimal(self.get_object('spinbutton1').get_text())
		model[path][1] = (total - tree_sum)
		self.add_expense_totals ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry2').set_text(day_text)
		self.check_if_all_entries_valid ()

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def attach_button_clicked (self, button):
		import pdf_attachment
		paw = pdf_attachment.PdfAttachmentWindow(self.window)
		paw.connect("pdf_optimized", self.optimized_callback)

	def optimized_callback (self, pdf_attachment_window):
		self.file_data = pdf_attachment_window.get_pdf ()

	def print_and_post_clicked (self, button):
		total = Decimal(self.get_object('spinbutton1').get_text())
		check_number = self.get_object('entry7').get_text()
		bank_account = self.get_object('combobox2').get_active_id()
		contact_id = self.get_object('combobox1').get_active_id()
		self.cursor.execute("SELECT "
								"name, "
								"checks_payable_to, "
								"address, "
								"city, "
								"state, "
								"zip, "
								"phone "
							"FROM contacts WHERE id = %s",(contact_id,))
		provider = Item()
		for line in self.cursor.fetchall():
			provider.name = line[0]
			provider.pay_to = line[1]
			provider.street = line[2]
			provider.city = line[3]
			provider.state = line[4]
			provider.zip = line[5]
			provider.phone = line[6]
			pay_to = line[1].split()[0]
		items = list()
				
		item = Item()
		item.po_number = '' 
		item.amount = ''
		item.date = ''
		items.append(item)
		check = Item()
		check.check_number = check_number
		check.checking_account = bank_account
		check.date = self.date
		check.amount = total 
		check.amount_text = get_written_check_amount_text (total)
		from py3o.template import Template
		data = dict(contact = provider, check = check, items = items )
		self.tmp_file = "/tmp/check" + pay_to +".odt"
		self.tmp_file_pdf = "/tmp/check" + pay_to + ".pdf"
		t = Template(template_dir+"/vendor_check_template.odt", self.tmp_file, True)
		t.render(data)
		subprocess.call(["odt2pdf", self.tmp_file])
		p = printing.Operation(settings_file = 'Vendor_check')
		p.set_file_to_print(self.tmp_file_pdf)
		p.set_parent(self.window)
		result = p.print_dialog()
		if result != "user canceled":
			self.perform_cheque_payment()




