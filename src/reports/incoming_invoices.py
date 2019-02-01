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
import main

UI_FILE = main.ui_directory + "/reports/incoming_invoices.ui"

class IncomingInvoiceGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()

		self.service_provider_store = self.builder.get_object('service_provider_store')
		self.incoming_invoice_store = self.builder.get_object('incoming_invoice_store')
		sp_completion = self.builder.get_object('service_provider_completion')
		sp_completion.set_match_func(self.sp_match_func)

		self.populate_service_provider_store ()

		window = self.builder.get_object('window1')
		window.show_all()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def view_attachment_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		file_id = model[path][0]
		self.cursor.execute("SELECT attached_pdf FROM incoming_invoices "
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

	def populate_service_provider_store (self):
		self.service_provider_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE service_provider = True ORDER BY name")
		for row in self.cursor.fetchall():
			sp_id = row[0]
			sp_name = row[1]
			self.service_provider_store.append([str(sp_id), sp_name])

	def sp_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.service_provider_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def service_provider_combo_changed (self, combo):
		service_provider_id = combo.get_active_id()
		if service_provider_id != None:
			self.builder.get_object('checkbutton1').set_active (False)
			self.service_provider_id = service_provider_id
			self.populate_incoming_invoice_store()

	def service_provider_match_selected (self, completion, model, iter_):
		sp_id = model[iter_][0]
		self.builder.get_object('combobox1').set_active_id (sp_id)

	def view_all_toggled (self, checkbutton):
		self.populate_incoming_invoice_store()

	def populate_incoming_invoice_store (self):
		self.incoming_invoice_store.clear()
		if self.builder.get_object('checkbutton1').get_active () == True:
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



	
