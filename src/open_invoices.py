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

UI_FILE = "src/open_invoices.ui"

class OpenInvoicesGUI:
	def __init__(self, main):

		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.parent = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.open_invoice_store = self.builder.get_object('open_invoice_store')
		self.populate_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		main.open_invoices_window = self.window

	def delete_event (self, window, event):
		self.parent.open_invoices_window = None

	def focus_in_event (self, window, event):
		self.populate_store()

	def new_invoice_clicked (self, button):
		import invoice_window
		invoice_window.InvoiceGUI(self.parent)

	def open_invoice_row_activated (self, treeview, path, treeview_column):
		invoice_id = self.open_invoice_store[path][0]
		import invoice_window
		invoice_window.InvoiceGUI(self.parent, invoice_id)

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
								"COUNT(ili.id) "
							"FROM invoices AS i JOIN contacts AS c "
							"ON i.customer_id = c.id "
							"JOIN invoice_items AS ili "
							"ON ili.invoice_id = i.id "
							"WHERE (i.canceled, posted, i.active) "
							"= (False, False, True) "
							"GROUP BY (i.id, c.name)")
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
		invoice_window.InvoiceGUI(self.parent, invoice_id)




		