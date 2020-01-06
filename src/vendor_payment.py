# vendor_payment.py
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

from gi.repository import Gtk
from decimal import Decimal
import subprocess, printing
from dateutils import DateTimeCalendar
from check_writing import get_written_check_amount_text, get_check_number
from db.transactor import VendorPayment, vendor_check_payment, \
							vendor_debit_payment, post_purchase_order_accounts
from constants import ui_directory, DB, template_dir

class Item(object):#this is used by py3o library see their example for more info
	pass

UI_FILE = ui_directory + "/vendor_payment.ui"


class GUI:
	def __init__(self, po_id = None):
		'''Id of purchase order to pay (optional)'''
		self.po_id = po_id
		self.payment_type_id = 0
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.calendar = DateTimeCalendar ()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		check_number = get_check_number(None)
		self.builder.get_object('entry2').set_text(str(check_number))

		self.vendor_id = 0
		self.vendor_store = self.builder.get_object('vendor_store')
		self.c_c_multi_payment_store = self.builder.get_object('c_c_multi_payment_store')
		self.vendor_invoice_store = self.builder.get_object(
														'vendor_invoice_store')
		
		total_column = self.builder.get_object ('treeviewcolumn2')
		total_renderer = self.builder.get_object ('cellrenderertext2')
		total_column.set_cell_data_func(total_renderer, self.total_cell_func)
		
		split_column = self.builder.get_object ('treeviewcolumn4')
		split_renderer = self.builder.get_object ('cellrendererspin4')
		split_column.set_cell_data_func(split_renderer, self.split_cell_func)
		
		self.populate_vendor_liststore ()
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy(self, window):
		self.cursor.close()

	def refresh_clicked (self, button):
		self.populate_vendor_liststore()

	def split_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 0)
		cellrenderer.set_property("text", str(price))

	def total_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 2)
		cellrenderer.set_property("text", str(price))

	def populate_vendor_liststore (self):
		self.vendor_store.clear()
		self.cursor.execute("SELECT contacts.id::text, contacts.name "
							"FROM purchase_orders "
							"JOIN contacts ON contacts.id = "
							"purchase_orders.vendor_id "
							"WHERE (canceled, closed, invoiced, paid) = "
							"(False, True, True, False) "
							"GROUP BY contacts.id, contacts.name "
							"ORDER BY contacts.name")
		for row in self.cursor.fetchall():
			self.vendor_store.append(row)
		DB.rollback()

	def vendor_combo_changed (self, combo):
		vendor_id = combo.get_active_id()
		if vendor_id == None:
			return
		self.vendor_id = vendor_id
		path = combo.get_active ()
		self.vendor_name = self.vendor_store[path][1]
		self.populate_vendor_invoice_store ()
		self.check_credit_card_entries_valid ()
		self.check_cash_entries_valid ()

	def vendor_completion_match_selected (self, completion, model, iter_):
		self.vendor_id = model[iter_][0]
		self.vendor_name = model[iter_][1]
		self.populate_vendor_invoice_store ()

	def view_all_togglebutton_toggled (self, togglebutton):
		self.populate_vendor_invoice_store ()

	def populate_vendor_invoice_store (self):
		self.vendor_invoice_store.clear()
		self.c_c_multi_payment_store.clear()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute ("SELECT id, invoice_description, amount_due, "
								"date_created::text, "
								"format_date(date_created) "
								"FROM purchase_orders "
								"WHERE (canceled, invoiced, paid) = "
								"(False, True, False) "
								"ORDER BY date_created")
		else:
			self.cursor.execute ("SELECT id, invoice_description, amount_due, "
								"date_created::text, "
								"format_date(date_created) "
								"FROM purchase_orders "
								"WHERE (vendor_id, canceled, invoiced, paid) = "
								"(%s, False, True, False) "
								"ORDER BY date_created", (self.vendor_id, ))
		for row in self.cursor.fetchall():
			self.vendor_invoice_store.append(row)
		self.check_cash_entries_valid ()
		self.check_credit_card_entries_valid ()
		self.check_cheque_entries_valid ()
		DB.rollback()

	def focus (self, winow, event):
		self.populate_credit_card_combo ()
		self.populate_bank_combo ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()
	
	def view_attachment_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		file_id = model[path][0]
		self.cursor.execute("SELECT attached_pdf FROM purchase_orders "
							"WHERE id = %s", (file_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/Attachment.pdf"
			file_data = row[0]
			if file_data == None:
				return
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.call("xdg-open %s" % file_name, shell = True)
			f.close()
		DB.rollback()

	def populate_bank_combo (self):
		bank_combo = self.builder.get_object('comboboxtext3')
		bank_id = bank_combo.get_active_id()
		bank_combo.remove_all()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE check_writing = True")
		for row in self.cursor.fetchall():
			bank_number = row[0]
			bank_name = row[1]
			bank_combo.append(bank_number, bank_name)
		bank_combo.set_active_id(bank_id)
		DB.rollback()

	def populate_credit_card_combo(self):
		credit_card_combo = self.builder.get_object('comboboxtext2')
		card_id = credit_card_combo.get_active_id()
		credit_card_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE credit_card_account = True")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			credit_card_combo.append(str(number), name)
		credit_card_combo.set_active_id(card_id)
		cash_combo = self.builder.get_object('comboboxtext1')
		cash_id = cash_combo.get_active_id()
		cash_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE cash_account = True")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			cash_combo.append(str(number), name)
		cash_combo.set_active_id(cash_id)
		DB.rollback()

	def c_c_invoice_name_changed (self, entry):
		self.builder.get_object('comboboxtext2').set_sensitive(True)

	def bank_combo_changed (self, combo):
		bank_account = combo.get_active_id()
		if bank_account != None:
			self.bank_account = bank_account
			check_number = get_check_number(bank_account)
			self.builder.get_object('entry2').set_text(str(check_number))
			self.builder.get_object('entry4').set_sensitive(True)
		self.check_cheque_entries_valid ()

	def transaction_number_changed (self, entry):
		if entry.get_text() == '':
			self.builder.get_object('button2').set_sensitive(False)
		else:
			self.builder.get_object('button2').set_sensitive(True)

	def invoice_selection_changed (self, selection):
		model, paths = selection.get_selected_rows()
		self.c_c_multi_payment_store.clear()
		if paths == []:
			self.builder.get_object('comboboxtext3').set_sensitive(False)
			self.builder.get_object('box11').set_sensitive(False)
			self.builder.get_object('box14').set_sensitive(False)
			self.builder.get_object('button6').set_sensitive(False)
			self.builder.get_object('button3').set_sensitive(False)
			return
		if len (paths) == 1:
			path = paths[0]
			invoice_name = self.vendor_invoice_store[path][1]
			self.builder.get_object ('entry5').set_text(invoice_name)
			total = self.vendor_invoice_store[path][2]
		else:
			total = Decimal()
			for path in paths:
				total += model[path][2]
			self.builder.get_object ('entry5').set_text("Multiple invoices")
		self.builder.get_object('comboboxtext3').set_sensitive(True)
		self.check_cheque_entries_valid ()
		self.selected_invoices_total = round(total, 2)
		self.add_multi_payment (total)
		self.check_cash_entries_valid ()
		self.total = total
		self.builder.get_object('entry3').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry6').set_text('${:,.2f}'.format(total))

	def debit_payment_clicked (self, button):
		combo = self.builder.get_object('comboboxtext3')
		checking_account_number = combo.get_active_id()
		transaction_number = self.builder.get_object('entry4').get_text()
		vendor_debit_payment (self.date, self.total, 
								checking_account_number, transaction_number)
		self.mark_invoices_paid ()
		DB.commit ()
		self.populate_vendor_invoice_store ()

	def post_check_without_printing_clicked (self, button):
		self.post_check()
		
	def print_check_clicked (self, button):
		check_number =  self.builder.get_object('entry2').get_text()
		combo = self.builder.get_object('comboboxtext3')
		checking_account_number = combo.get_active_id ()
		self.cursor.execute("SELECT "
								"name, "
								"checks_payable_to, "
								"address, "
								"city, "
								"state, "
								"zip, "
								"phone "
							"FROM contacts WHERE id = %s",(self.vendor_id,))
		vendor = Item()
		for line in self.cursor.fetchall():
			vendor.name = line[0]
			vendor.pay_to = line[1]
			vendor.street = line[2]
			vendor.city = line[3]
			vendor.state = line[4]
			vendor.zip = line[5]
			vendor.phone = line[6]
			pay_to = line[1].split()[0]
		items = list()
		for row in self.vendor_invoice_store:
			if row[3] == True:
				item = Item()
				item.po_number = row[0] 
				item.amount = row[2]
				item.date = row[4]
				items.append(item)
		check = Item()
		check.check_number = check_number
		check.checking_account = checking_account_number
		check.date = self.date
		check.amount = self.amount 
		check.amount_text = self.amount_text
		from py3o.template import Template
		data = dict(contact = vendor, check = check, items = items)
		self.tmp_file = "/tmp/check" + pay_to +".odt"
		self.tmp_file_pdf = "/tmp/check" + pay_to + ".pdf"
		t = Template(template_dir+"/vendor_check_template.odt", self.tmp_file, True)
		t.render(data)
		subprocess.call(["odt2pdf", self.tmp_file])
		p = printing.Operation(settings_file = 'Vendor check')
		p.set_file_to_print(self.tmp_file_pdf)
		p.set_parent(self.window)
		result = p.print_dialog()
		if result != "user canceled":
			self.post_check()

	def post_check (self):
		check_number =  self.builder.get_object('entry2').get_text()
		combo = self.builder.get_object('comboboxtext3')
		checking_account_number = combo.get_active_id ()
		vendor_check_payment (self.date, self.total, 
								checking_account_number, check_number, 
								self.vendor_name)
		self.mark_invoices_paid ()
		DB.commit()
		self.populate_vendor_invoice_store ()
		self.builder.get_object('box14').set_sensitive(False)

	def mark_invoices_paid (self ):
		self.cursor.execute("SELECT accrual_based FROM settings")
		accrual_based = self.cursor.fetchone()[0] 
		selection = self.builder.get_object('treeview-selection1')
		model, paths = selection.get_selected_rows()
		for path in paths:
			po_id = model[path][0]
			self.cursor.execute("UPDATE purchase_orders "
								"SET (paid, date_paid) = "
								"(True, %s) WHERE id = %s", 
								(self.date, po_id))
			if accrual_based == False:
				post_purchase_order_accounts (po_id, self.date)

	def credit_card_changed(self, widget):
		self.check_credit_card_entries_valid ()

	def cash_account_changed (self, combo):
		self.check_cash_entries_valid ()
	
	def pay_with_credit_card_clicked (self, widget):
		self.mark_invoices_paid()
		c_c_combo = self.builder.get_object('comboboxtext2')
		c_c_account_number = c_c_combo.get_active_id()
		description = self.builder.get_object('entry5').get_text()
		payment = VendorPayment(self.date, 
								self.total, 
								description)
		for row in self.c_c_multi_payment_store:
			amount = row[0]
			date = row[1]
			payment.credit_card(c_c_account_number, amount, date)
		DB.commit()
		self.populate_vendor_liststore ()
		self.populate_vendor_invoice_store ()
		self.check_credit_card_entries_valid ()
		self.check_cash_entries_valid ()
		
	def pay_with_cash_clicked (self, button):
		self.mark_invoices_paid()
		cash_combo = self.builder.get_object('comboboxtext1')
		cash_account_number = cash_combo.get_active_id()
		description = self.builder.get_object('entry5').get_text()
		payment = VendorPayment(self.date, 
								self.total, 
								description)
		payment.cash (cash_account_number)
		DB.commit()
		self.populate_vendor_liststore ()
		self.populate_vendor_invoice_store ()
		self.check_credit_card_entries_valid ()
		self.check_cash_entries_valid ()

	def check_amount_changed(self, widget):
		self.amount = widget.get_text()
		self.amount_text = get_written_check_amount_text (self.amount)
		self.builder.get_object('label13').set_label(self.amount_text)

	def multi_payment_spin_amount_edited (self, renderer, path, text):
		self.c_c_multi_payment_store[path][0] = Decimal(text)
		self.calculate_multi_payment_amount ()
		
	def add_multi_payment_button_clicked (self, button):
		self.add_multi_payment (Decimal(1.00))

	def add_multi_payment (self, amount):
		self.cursor.execute("SELECT format_date(%s)", (self.date,))
		date = self.cursor.fetchone()[0]
		self.c_c_multi_payment_store.append([amount, str(self.date), date])
		self.calculate_multi_payment_amount ()

	def remove_multi_payment_button_clicked (self, button):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = model.get_iter(path)
		model.remove(iter_)
		self.calculate_multi_payment_amount ()

	def calculate_multi_payment_amount (self):
		total = Decimal()
		for row in self.c_c_multi_payment_store:
			total += row[0]
		self.multi_payment_total = round(total, 2)
		text = '${:,.2f}'.format(self.multi_payment_total)
		self.builder.get_object ('entry7').set_text(text)
		self.builder.get_object ('entry8').set_text(text)
		self.check_credit_card_entries_valid ()

	def check_cheque_entries_valid (self):
		error_label = self.builder.get_object ('error_label')
		error_label.set_visible(True)
		if self.builder.get_object('comboboxtext3').get_active_id() == None:
			error_label.set_label("No bank account selected")
			self.builder.get_object('box11').set_sensitive(False)
			self.builder.get_object('box14').set_sensitive(False)
			return
		if self.date == None:
			error_label.set_label("No date selected")
			self.builder.get_object('box11').set_sensitive(False)
			self.builder.get_object('box14').set_sensitive(False)
			return
		self.builder.get_object('box11').set_sensitive(True)
		self.builder.get_object('box14').set_sensitive(True)
		error_label.set_visible(False)
		
	def check_credit_card_entries_valid (self):
		button = self.builder.get_object ('button3')
		button.set_sensitive (False)
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			button.set_label("No invoice selected")
			return
		if self.date == None:
			button.set_label("No date selected")
			return
		if self.builder.get_object('entry5').get_text() == "":
			button.set_label("No invoice name / number")
			return
		if self.builder.get_object('comboboxtext2').get_active_id() == None:
			button.set_label("No credit card selected")
			return
		if self.selected_invoices_total != self.multi_payment_total :
			button.set_label("Invoice and payment do not match")
			return
		button.set_label ("Pay")
		button.set_sensitive(True)

	def check_cash_entries_valid (self):
		button = self.builder.get_object ('button6')
		button.set_sensitive (False)
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			button.set_label("No invoice selected")
			return
		if self.date == None:
			button.set_label("No date selected")
			return
		if self.builder.get_object('entry5').get_text() == "":
			button.set_label("No invoice name / number")
			return
		if self.builder.get_object('comboboxtext1').get_active_id() == None:
			button.set_label("No cash account selected")
			return
		button.set_label ("Pay")
		button.set_sensitive(True)

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)
		self.check_cash_entries_valid ()
		self.check_credit_card_entries_valid ()
		self.check_cheque_entries_valid ()

	def entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()





