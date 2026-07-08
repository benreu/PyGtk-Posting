# open_purchase_orders.py
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

UI_FILE = ui_directory + "/draft_purchase_orders.ui"

class DraftPurchaseOrderGUI:
	def __init__(self):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.open_po_store = self.builder.get_object('open_po_store')
		self.populate_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def delete_event (self, window, event):
		window.hide()
		return True

	def new_po_clicked (self, button):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI()

	def p_o_name_edited (self, cellrenderertext, path, text):
		po_id = self.open_po_store[path][0]
		cursor = DB.cursor()
		cursor.execute("UPDATE purchase_orders SET name = %s "
							"WHERE id = %s", (text, po_id))
		cursor.close()
		DB.commit()
		self.open_po_store[path][1] = text

	def p_o_name_editing_canceled (self, cellrenderer):
		cursor = DB.cursor()
		cursor.execute("SELECT pg_advisory_unlock(id) "
							"FROM purchase_orders "
							"WHERE id = %s ",
							(self.po_id,))
		cursor.close()
		DB.commit()

	def p_o_name_editing_started (self, cellrenderer, celleditable, path):
		self.po_id = self.open_po_store[path][0]
		cursor = DB.cursor()
		cursor.execute("SELECT name FROM purchase_orders "
							"WHERE (id, closed, pg_try_advisory_lock(id)) = "
							"(%s, False, False)",
							(self.po_id,))
		for row in cursor.fetchall():
			celleditable.set_text(row[0])
			break
		else:
			cellrenderer.stop_editing(False)
		cursor.close()

	def focus_in_event (self, window, event):
		self.populate_store()

	def open_po_row_activated (self, treeview, path, treeview_column):
		po_id = self.open_po_store[path][0]
		self.open_po (po_id)

	def open_po (self, po_id):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI(po_id)
		if self.builder.get_object('hide_checkbutton').get_active():
			self.window.hide()

	def populate_store (self):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.open_po_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"p.id, "
								"p.name, "
								"c.name, "
								"date_created::text, "
								"format_date(date_created), "
								"COUNT(pli.id) "
							"FROM purchase_orders AS p JOIN contacts AS c "
							"ON p.vendor_id = c.id "
							"JOIN purchase_order_items AS pli "
							"ON pli.purchase_order_id = p.id "
							"WHERE (p.canceled, closed) "
							"= (False, False) "
							"GROUP BY (p.id, c.name)")
		for row in cursor.fetchall():
			self.open_po_store.append(row)
		cursor.close()
		if path != []:
			selection.select_path(path)
		DB.rollback()

	def open_po_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		po_id = model[path][0]
		self.open_po (po_id)





