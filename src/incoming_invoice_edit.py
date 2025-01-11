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

UI_FILE = ui_directory + "/incoming_invoice_edit.ui"

class EditIncomingInvoiceGUI(Gtk.Builder):
	__gsignals__ = { 
	'invoice_applied': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ())
	}
	"""the invoice_applied signal is used to send a message to the parent 
		window that the incoming invoice is now finished"""
	def __init__(self, invoice_id):

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

		self.invoice_id = invoice_id
		
		provider_completion = self.get_object('provider_completion')
		provider_completion.set_match_func(self.provider_match_func)
		
		self.populating = False
		self.service_provider_store = self.get_object(
													'service_provider_store')
		self.expense_percentage_store = self.get_object(
													'expense_percentage_store')
		self.cash_account_store = self.get_object('cash_account_store')
		self.populate_stores ()
		self.populate_service_providers ()
	
		self.window = self.get_object('window1')
		self.window.show_all()
		self.file_data = None
		
		self.populate_incoming_invoice ()
		DB.rollback()

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

	def populate_incoming_invoice (self):
		cursor = DB.cursor()
		cursor.execute("SELECT contact_id::text, description, amount, "
						"date_created, attached_pdf FROM incoming_invoices "
						"WHERE id = %s", (self.invoice_id,))
		for row in cursor.fetchall():
			self.get_object('contact_combobox').set_active_id(row[0])
			self.get_object('entry1').set_text(row[1])
			self.get_object('spinbutton1').set_value(row[2])
			self.calendar.set_date(row[3])
			attached_pdf = row[4]
		cursor.execute("SELECT ge.id, 0, ge.amount, ge.amount::text, "
						"ga.number, ga.name, 'N/A', iigeei.remark "
						"FROM gl_entries ge "
						"JOIN incoming_invoices_gl_entry_expenses_ids iigeei "
						"ON ge.id = iigeei.gl_entry_expense_id "
						"JOIN gl_accounts ga ON ga.number = ge.debit_account "
						"WHERE iigeei.incoming_invoices_id = %s", (self.invoice_id,))
		for row in cursor.fetchall():
			self.expense_percentage_store.append(row)
		cursor.execute("SELECT credit_account::text, "
							"COALESCE(transaction_description, ''), "
							"COALESCE(check_number, 0) "
						"FROM gl_entries ge "
						"JOIN incoming_invoices ii "
						"ON ii.gl_entry_id = ge.id "
						"WHERE ii.id = %s", (self.invoice_id,))
		for row in cursor.fetchall():
			self.get_object('payment_combo').set_active_id(row[0])
			self.get_object('transaction_description_entry').set_text(row[1])
			self.get_object('cheque_number_spin').set_value(row[2])
		self.add_expense_totals ()
		if attached_pdf != None:
			dialog = self.get_object('attachment_dialog')
			response = dialog.run()
			dialog.hide()
			if response == Gtk.ResponseType.ACCEPT:
				self.file_data = attached_pdf

	def populate_service_providers (self, m=None, i=None):
		self.populating = True
		combo = self.get_object('contact_combobox')
		active_sp = combo.get_active_id()
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE service_provider = True "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.service_provider_store.append(row)
		combo.set_active_id(active_sp)
		self.populating = False

	def populate_stores (self):
		store = self.get_object('payment_store')
		store.clear()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE check_writing = True "
							"UNION "
							"SELECT number::text, name FROM gl_accounts "
							"WHERE cash_account = True "
							"UNION "
							"SELECT number::text, name FROM gl_accounts "
							"WHERE credit_card_account = True "
							"ORDER BY name ")
		for row in self.cursor.fetchall():
			store.append(row)

	def set_shipping_description (self, text):
		self.get_object('entry1').set_text(text)

	def set_date (self, date):
		self.calendar.set_date(date)

	def service_provider_clicked (self, button):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()
		
	def provider_match_selected(self, completion, model, iter_):
		self.provider_id = model[iter_][0]
		self.get_object('contact_combobox').set_active_id(self.provider_id)

	def service_provider_combo_changed (self, combo):
		if self.populating == True:
			return
		a_iter = combo.get_active_iter()
		if a_iter == None:
			return
		name = self.get_object('contact_name_entry').get_text()
		self.get_object('transaction_description_entry').set_text(name)
		self.check_if_all_entries_valid ()

	def add_percentage_row_clicked (self, button):
		self.expense_percentage_store.append([0, 1, 1.00, '1.00', 0, "", "", ""])
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
			row[1] = percentage
			row[2] = split_amount
			row[3] = str(split_amount)
		self.add_expense_totals ()

	def invoice_spinbutton_changed (self, spinbutton):
		self.add_expense_totals ()

	def expense_amount_edited (self, renderer, path, text):
		value = Decimal(text).quantize(Decimal('0.01'), rounding = ROUND_HALF_UP)
		self.expense_percentage_store[path][2] = value
		self.expense_percentage_store[path][3] = str(value)
		self.add_expense_totals ()

	def percent_render_edited (self, renderer, path, text):
		self.expense_percentage_store[path][1] = int(text)
		invoice_amount = self.get_object('spinbutton1').get_text()
		percent = Decimal(text) / Decimal('100')
		split_amount = Decimal(invoice_amount) * percent
		self.expense_percentage_store[path][2] = split_amount
		self.expense_percentage_store[path][3] = str(split_amount)
		self.add_expense_totals ()

	def add_expense_totals (self):
		total = Decimal()
		for row in self.expense_percentage_store:
			total += Decimal(row[2])
		self.get_object('total_entry').set_text('${:,.2f}'.format(total))
		self.check_if_all_entries_valid ()

	def expense_account_render_changed (self, renderer, path, tree_iter):
		account_number = self.expense_account_store[tree_iter][0]
		account_name = self.expense_account_store[tree_iter][1]
		account_path = self.expense_account_store[tree_iter][2]
		self.expense_percentage_store[path][4] = int(account_number)
		self.expense_percentage_store[path][5] = account_name
		self.expense_percentage_store[path][6] = account_path
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
		treeview_model[path][4] = int(account_number)
		treeview_model[path][5] = account_name
		treeview_model[path][6] = account_path
		self.check_if_all_entries_valid()

	def remark_edited (self, cellrenderertext, path, text):
		self.expense_percentage_store[path][7] = text

	def payment_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		payment_button = self.get_object('button7')
		payment_button.set_sensitive(False)
		if self.get_object('contact_combobox').get_active() == -1:
			payment_button.set_label('No service provider')
			return # no service provider selected
		if self.date == None:
			payment_button.set_label('No date selected')
			return
		invoice_amount = Decimal(self.get_object('spinbutton1').get_text())
		if invoice_amount == 0.00:
			payment_button.set_label('No invoice amount')
			return
		payment_amount = Decimal('0.00')
		for row in self.expense_percentage_store:
			payment_amount += Decimal(row[3])
		if invoice_amount != payment_amount:
			payment_button.set_label('Invoice amount does not match payment')
			return
		for row in self.expense_percentage_store:
			if row[4] == 0:
				payment_button.set_label('Missing expense accounts')
				return
		if self.get_object('payment_combo').get_active() >= 0:
			# bank / credit card selected
			payment_button.set_label('Save edits')
			payment_button.set_sensitive(True)
		else:
			payment_button.set_label('No payment account selected')

	def save_edits_clicked (self, button):
		c = DB.cursor()
		contact_id = self.get_object('contact_combobox').get_active_id()
		contact_name = self.get_object('contact_name_entry').get_text()
		description = self.get_object('entry1').get_text()
		total = Decimal(self.get_object('spinbutton1').get_text())
		tx_description = self.get_object('transaction_description_entry').get_text()
		cheque_number = self.get_object('cheque_number_spin').get_text()
		if tx_description == '':
			tx_description = None
		if cheque_number == 0:
			cheque_number = None
		c.execute(	"UPDATE incoming_invoices SET "
						"(contact_id, "
						"date_created, "
						"amount, "
						"description, "
						"attached_pdf) "
					"= (%s, %s, %s, %s, %s) WHERE id = %s;"
					"UPDATE gl_entries SET "
					"(transaction_description, check_number) = (%s, %s) "
					"WHERE id = (SELECT gl_entry_id "
						"FROM incoming_invoices WHERE id = %s)", 
					(contact_id, self.date, total, description, 
					self.file_data, self.invoice_id, 
					tx_description, cheque_number, self.invoice_id))
		for row in self.expense_percentage_store:
			row_id = row[0]
			amount = row[3]
			account = row[4]
			remark = row[7]
			c.execute("UPDATE gl_entries SET (amount, debit_account) = "
						"(%s, %s) WHERE id = %s; "
						"UPDATE incoming_invoices_gl_entry_expenses_ids "
						"SET remark = %s WHERE gl_entry_expense_id = %s",
						(amount, account, row_id, remark, row_id))
		DB.commit()
		c.close()
		self.window.destroy()

	def balance_this_row_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_sum = Decimal()
		for row in self.expense_percentage_store:
			if row.path != path[0]:
				tree_sum += Decimal(row[3])
		total = Decimal(self.get_object('spinbutton1').get_text())
		model[path][2] = total - tree_sum
		model[path][3] = str(total - tree_sum)
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



