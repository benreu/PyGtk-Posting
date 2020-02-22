# incoming_invoices.py
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


from gi.repository import Gtk
import subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/incoming_invoices.ui"

class IncomingInvoiceGUI(Gtk.Builder):
	service_provider_id = None
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.service_provider_store = self.get_object('service_provider_store')
		self.incoming_invoice_store = self.get_object('incoming_invoice_store')
		self.invoice_items_store = self.get_object('invoice_items_store')
		sp_completion = self.get_object('service_provider_completion')
		sp_completion.set_match_func(self.sp_match_func)

		self.populate_service_provider_store ()

		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def view_attachment_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		file_id = model[path][0]
		self.cursor.execute("SELECT attached_pdf FROM incoming_invoices "
							"WHERE id = %s "
							"AND attached_pdf IS NOT NULL", (file_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/Attachment.pdf"
			file_data = row[0]
			with open(file_name,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_name])
			DB.rollback()
			break
		else: # no pdf found, give the user the option to attach one
			import pdf_attachment
			paw = pdf_attachment.PdfAttachmentWindow(self.window)
			paw.connect("pdf_optimized", self.optimized_callback, file_id)

	def optimized_callback (self, pdf_attachment_window, file_id):
		file_data = pdf_attachment_window.get_pdf ()
		self.cursor.execute("UPDATE incoming_invoices "
							"SET attached_pdf = %s "
							"WHERE id = %s", (file_data, file_id))
		DB.commit()

	def populate_service_provider_store (self):
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id::text, name FROM contacts "
							"WHERE service_provider = True ORDER BY name")
		for row in self.cursor.fetchall():
			self.service_provider_store.append(row)
		DB.rollback()

	def sp_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.service_provider_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def service_provider_combo_changed (self, combo):
		service_provider_id = combo.get_active_id()
		if service_provider_id != None:
			self.get_object('checkbutton1').set_active (False)
			self.service_provider_id = service_provider_id
			self.populate_incoming_invoice_store()

	def service_provider_match_selected (self, completion, model, iter_):
		sp_id = model[iter_][0]
		self.get_object('combobox1').set_active_id (sp_id)

	def view_all_toggled (self, checkbutton):
		self.populate_incoming_invoice_store()

	def populate_incoming_invoice_store (self):
		self.incoming_invoice_store.clear()
		self.invoice_items_store.clear()
		if self.get_object('checkbutton1').get_active () == True:
			self.cursor.execute("SELECT "
									"i.id, "
									"c.name, "
									"date_created::text, "
									"format_date(date_created), "
									"description, "
									"amount, "
									"amount::text "
								"FROM incoming_invoices AS i "
								"JOIN contacts AS c ON c.id = i.contact_id "
								"ORDER BY date_created, i.id")
		elif self.service_provider_id == None:
			return
		else:
			self.cursor.execute("SELECT "
									"i.id, "
									"c.name, "
									"date_created::text, "
									"format_date(date_created), "
									"description, "
									"amount, "
									"amount::text "
								"FROM incoming_invoices AS i "
								"JOIN contacts AS c ON c.id = i.contact_id "
								"WHERE contact_id = %s "
								"ORDER BY date_created, i.id", 
								(self.service_provider_id,))
		for row in self.cursor.fetchall():
			self.incoming_invoice_store.append(row)
		DB.rollback()

	def incoming_invoice_selection_changed (self, treeselection):
		model, path = treeselection.get_selected_rows()
		if path == []:
			return
		self.invoice_items_store.clear()
		row_id = model[path][0]
		self.cursor.execute("SELECT "
								"iige.id, "
								"ge.amount, "
								"ge.amount::text, "
								"ga.name, "
								"iige.remark "
							"FROM "
							"incoming_invoices_gl_entry_expenses_ids AS iige "
							"JOIN gl_entries AS ge ON ge.id = "
								"iige.gl_entry_expense_id "
							"JOIN gl_accounts AS ga ON ga.number = "
								"ge.debit_account "
							"WHERE incoming_invoices_id = %s",
							(row_id,))
		for row in self.cursor.fetchall():
			self.invoice_items_store.append(row)
		DB.rollback()




