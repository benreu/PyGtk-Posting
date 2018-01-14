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
import subprocess
from dateutils import DateTimeCalendar, datetime_to_text
from check_writing import set_written_ck_amnt_text, get_check_number
from db.transactor import VendorPayment, vendor_check_payment, \
							vendor_debit_payment, post_purchase_order_accounts


UI_FILE = "src/vendor_payment.ui"


class GUI:
	def __init__(self, db, po_id = None):
		'''Id of purchase order to pay (optional)'''
		self.po_id = po_id
		self.payment_type_id = 0
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
		self.db = db
		self.cursor = self.db.cursor()
		
		self.calendar = DateTimeCalendar (self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		check_number = get_check_number(self.db, None)
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

	def split_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 0)
		cellrenderer.set_property("text", str(price))

	def total_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 2)
		cellrenderer.set_property("text", str(price))

	def populate_vendor_liststore (self):
		self.vendor_store.clear()
		self.cursor.execute("SELECT contacts.id, contacts.name "
							"FROM purchase_orders "
							"JOIN contacts ON contacts.id = "
							"purchase_orders.vendor_id "
							"WHERE (canceled, closed, invoiced, paid) = "
							"(False, True, True, False) "
							"GROUP BY contacts.id, contacts.name "
							"ORDER BY contacts.name")
		for row in self.cursor.fetchall():
			vendor_id = row[0]
			vendor_name = row[1]
			self.vendor_store.append([str(vendor_id), vendor_name])

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
								"date_created "
								"FROM purchase_orders "
								"WHERE (canceled, invoiced, paid) = "
								"(False, True, False) "
								"ORDER BY date_created")
		else:
			self.cursor.execute ("SELECT id, invoice_description, amount_due, "
								"date_created "
								"FROM purchase_orders "
								"WHERE (vendor_id, canceled, invoiced, paid) = "
								"(%s, False, True, False) "
								"ORDER BY date_created", (self.vendor_id, ))
		for row in self.cursor.fetchall():
			row_id = row[0]
			invoice_desc = row[1]
			amount_due = row[2]
			date_created = row[3]
			date_formatted = datetime_to_text(date_created)
			self.vendor_invoice_store.append([row_id, invoice_desc, 
													amount_due, False,
													str(date_created),
													date_formatted])
		self.check_cash_entries_valid ()
		self.check_credit_card_entries_valid ()

	def focus (self, winow, event):
		self.populate_credit_card_combo ()
		self.populate_bank_combo ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
	
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

	def populate_bank_combo (self):
		bank_combo = self.builder.get_object('comboboxtext3')
		bank_id = bank_combo.get_active_id()
		bank_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE bank_account = True")
		for row in self.cursor.fetchall():
			bank_number = row[0]
			bank_name = row[1]
			bank_combo.append(str(bank_number), bank_name)
		bank_combo.set_active_id(bank_id)

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

	def c_c_invoice_name_changed (self, entry):
		self.builder.get_object('comboboxtext2').set_sensitive(True)

	def bank_combo_changed (self, combo):
		bank_account = combo.get_active_id()
		if bank_account != None:
			self.builder.get_object('button1').set_sensitive(True)
			self.bank_account = bank_account
			check_number = get_check_number(self.db, bank_account)
			self.builder.get_object('entry2').set_text(str(check_number))
			self.builder.get_object('entry4').set_sensitive(True)

	def transaction_number_changed (self, entry):
		if entry.get_text() == '':
			self.builder.get_object('button2').set_sensitive(False)
		else:
			self.builder.get_object('button2').set_sensitive(True)

	def pay_renderer_toggled (self, renderer, path):
		active = self.vendor_invoice_store[path][3]
		self.vendor_invoice_store[path][3] = not active
		self.calculate_invoice_totals ()

	def calculate_invoice_totals (self):
		total = Decimal()
		for row in self.vendor_invoice_store:
			pay = row[3]
			if pay == True:
				total += row[2]
		self.multiple_invoice_total = total
		if total > 0.00:
			self.builder.get_object('comboboxtext3').set_sensitive(True)
		else:
			self.builder.get_object('comboboxtext3').set_sensitive(False)
			self.builder.get_object('button1').set_sensitive(False)
		self.checking_total = total
		self.builder.get_object('entry3').set_text('${:,.2f}'.format(total))
		self.builder.get_object('entry6').set_text('${:,.2f}'.format(total))

	def invoice_row_activated (self, treeview, path, treeviewcolumn):
		invoice_name = self.vendor_invoice_store[path][1]
		invoice_amount = self.vendor_invoice_store[path][2]
		self.single_invoice_total = round(invoice_amount, 2)
		self.builder.get_object ('entry5').set_text(invoice_name)
		self.c_c_multi_payment_store.clear()
		self.add_multi_payment (invoice_amount)
		self.check_cash_entries_valid ()

	def debit_payment_clicked (self, button):
		combo = self.builder.get_object('comboboxtext3')
		checking_account_number = combo.get_active_id()
		transaction_number = self.builder.get_object('entry4').get_text()
		vendor_debit_payment (self.db, self.date, self.multiple_invoice_total, 
								checking_account_number, transaction_number)
		self.mark_invoices_paid ()
		self.db.commit ()
		self.populate_vendor_invoice_store ()
		self.calculate_invoice_totals ()
		
	def print_check_clicked (self, button):
		check_number =  self.builder.get_object('entry2').get_text()
		combo = self.builder.get_object('comboboxtext3')
		checking_account_number = combo.get_active_id ()
		vendor_check_payment (self.db, self.date, self.multiple_invoice_total, 
								checking_account_number, check_number, 
								self.vendor_name)
		self.mark_invoices_paid ()
		self.db.commit ()
		self.populate_vendor_invoice_store ()
		self.calculate_invoice_totals ()

	def mark_invoices_paid (self ):
		for row in self.vendor_invoice_store:
			if row[3] == True:
				invoice_id = row[0]
				invoice_amount = row[2]
				self.cursor.execute("UPDATE purchase_orders "
									"SET (paid, date_paid) = "
									"(True, %s) WHERE id = %s", 
									(self.date, invoice_id))
				post_purchase_order_accounts (self.db, invoice_id, self.date)

	def pay_with_credit_card_focused (self, box, frame):
		if box == self.builder.get_object('box10'):
			self.builder.get_object ('treeviewcolumn3').set_visible(False)

	def pay_with_check_focused (self, box, frame):
		if box == self.builder.get_object('box2'):
			self.builder.get_object ('treeviewcolumn3').set_visible(True)

	def credit_card_changed(self, widget):
		self.check_credit_card_entries_valid ()

	def cash_account_changed (self, combo):
		self.check_cash_entries_valid ()
	
	def pay_with_credit_card_clicked (self, widget):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		po_id = model[path][0]
		c_c_combo = self.builder.get_object('comboboxtext2')
		c_c_account_number = c_c_combo.get_active_id()
		description = self.builder.get_object('entry5').get_text()
		self.cursor.execute("UPDATE purchase_orders SET (paid, date_paid) "
							"= (True, %s) WHERE id = %s", (self.date, po_id))
		post_purchase_order_accounts (self.db, po_id, self.date)
		payment = VendorPayment(self.db, self.date, 
									self.multi_payment_total, description)
		for row in self.c_c_multi_payment_store:
			amount = row[0]
			date = row[1]
			payment.credit_card(c_c_account_number, amount, date)
		self.db.commit()
		self.populate_vendor_liststore ()
		self.populate_vendor_invoice_store ()
		self.check_credit_card_entries_valid ()
		self.check_cash_entries_valid ()
		
	def pay_with_cash_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		po_id = model[path][0]
		cash_combo = self.builder.get_object('comboboxtext1')
		cash_account_number = cash_combo.get_active_id()
		description = self.builder.get_object('entry5').get_text()
		self.cursor.execute("UPDATE purchase_orders SET (paid, date_paid) "
							"= (True, %s) WHERE id = %s", (self.date, po_id))
		post_purchase_order_accounts (self.db, po_id, self.date)
		payment = VendorPayment(self.db, self.date, 
									self.multi_payment_total, description)
		payment.cash (cash_account_number)
		self.db.commit()
		self.populate_vendor_liststore ()
		self.populate_vendor_invoice_store ()
		self.check_credit_card_entries_valid ()
		self.check_cash_entries_valid ()

	def check_amount_changed(self, widget):
		amount = widget.get_text()
		amount_text = set_written_ck_amnt_text (amount)
		self.builder.get_object('label13').set_label(amount_text)

	def multi_payment_spin_amount_edited (self, renderer, path, text):
		self.c_c_multi_payment_store[path][0] = Decimal(text)
		self.calculate_multi_payment_amount ()
		
	def add_multi_payment_button_clicked (self, button):
		self.add_multi_payment (Decimal(1.00))

	def add_multi_payment (self, amount):
		self.c_c_multi_payment_store.append([ amount, 
										str(self.date), 
										datetime_to_text(self.date)])
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
		if self.single_invoice_total != self.multi_payment_total :
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

	def entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()




		
