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
from constants import ui_directory, DB
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/open_invoices.ui"

class OpenInvoicesGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.open_invoice_store = self.get_object('open_invoice_store')
		self.populate_store ()
		self.window = self.get_object('window1')
		self.set_window_layout_from_settings ()
		self.window.show_all()

	def set_window_layout_from_settings(self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT value FROM open_invoices "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT value FROM open_invoices "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT value FROM open_invoices "
					"WHERE widget_id = 'sort_column'")
		sort_column = c.fetchone()[0]
		c.execute("SELECT value FROM open_invoices "
					"WHERE widget_id = 'sort_type'")
		sort_type = Gtk.SortType(c.fetchone()[0])
		store = self.get_object('open_invoice_store')
		store.set_sort_column_id(sort_column, sort_type)
		c.execute("SELECT widget_id, value FROM open_invoices WHERE "
					"widget_id IN ('number_column', "
									"'invoice_column', "
									"'contact_column', "
									"'date_created_column', "
									"'items_column')")
		for row in c.fetchall():
			column = self.get_object(row[0])
			width = row[1]
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()

	def present (self):
		self.window.present()

	def delete_event (self, window, event):
		self.set_window_layout_from_settings ()
		window.hide()
		return True

	def focus_in_event (self, window, event):
		self.populate_store()
		
	def contact_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][6]
		import contact_hub
		contact_hub.ContactHubGUI(customer_id)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def new_invoice_clicked (self, button):
		import invoice_window
		invoice_window.InvoiceGUI()

	def open_invoice_row_activated (self, treeview, path, treeview_column):
		invoice_id = self.open_invoice_store[path][0]
		self.open_invoice (invoice_id)

	def open_invoice (self, invoice_id):
		import invoice_window
		invoice_window.InvoiceGUI(invoice_id)
		if self.get_object('hide_checkbutton').get_active():
			self.window.hide()

	def populate_store (self):
		selection = self.get_object('treeview-selection1')
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
							"GROUP BY (i.id, c.name, c.id) "
							"ORDER BY i.id")
		for row in self.cursor.fetchall():
			self.open_invoice_store.append(row)
		if path != []:
			selection.select_path(path)
		DB.rollback()

	def open_invoice_clicked (self, button):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][0]
		self.open_invoice (invoice_id)

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO open_invoices (widget_id, value) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO open_invoices (widget_id, value) "
					"VALUES ('window_height', ?)", (height,))
		tuple_ = self.get_object('open_invoice_store').get_sort_column_id()
		sort_column = tuple_[0]
		if sort_column == None:
			sort_column = 0
			sort_type = 0
		else:
			sort_type = tuple_[1].numerator
		c.execute("REPLACE INTO open_invoices (widget_id, value) "
					"VALUES ('sort_column', ?)", (sort_column,))
		c.execute("REPLACE INTO open_invoices (widget_id, value) "
					"VALUES ('sort_type', ?)", (sort_type,))
		for column in ['number_column', 
						'invoice_column', 
						'contact_column', 
						'date_created_column', 
						'items_column']:
			try:
				width = self.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO open_invoices (widget_id, value) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




