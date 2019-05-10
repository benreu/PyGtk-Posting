# open_invoices.py
# Copyright (C) 2016 reuben
# 
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
import constants

UI_FILE = constants.ui_directory + "/open_invoices.ui"

class OpenInvoicesGUI:
	def __init__(self):

		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()
		self.open_invoice_store = self.builder.get_object('open_invoice_store')
		self.populate_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def present (self):
		self.window.present()

	def delete_event (self, window, event):
		window.hide()
		return True

	def focus_in_event (self, window, event):
		self.populate_store()
		
	def contact_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][6]
		import contact_hub
		contact_hub.ContactHubGUI(customer_id)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def new_invoice_clicked (self, button):
		import invoice_window
		invoice_window.InvoiceGUI()

	def open_invoice_row_activated (self, treeview, path, treeview_column):
		invoice_id = self.open_invoice_store[path][0]
		import invoice_window
		invoice_window.InvoiceGUI(invoice_id)

	def populate_store (self):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.open_invoice_store.clear()
		self.cursor.execute("SELECT "
								"i.id, "
								"i.name, "
								"c.name, "
								"date_created::text, "
								"format_date(date_created), "
								"COUNT(ili.id), "
								"c.id "
							"FROM invoices AS i JOIN contacts AS c "
							"ON i.customer_id = c.id "
							"JOIN invoice_items AS ili "
							"ON ili.invoice_id = i.id "
							"WHERE (i.canceled, posted, i.active) "
							"= (False, False, True) "
							"GROUP BY (i.id, c.name, c.id)")
		for row in self.cursor.fetchall():
			self.open_invoice_store.append(row)
		if path != []:
			selection.select_path(path)


	def open_invoice_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][0]
		import invoice_window
		invoice_window.InvoiceGUI(invoice_id)




		
