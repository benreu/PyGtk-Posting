# product_edit_order_numbers.py
#
# Copyright (C) 2019 - Reuben
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
import psycopg2
from constants import DB, ui_directory

UI_FILE = ui_directory + "/product_edit_order_numbers.ui"

class ProductsEditOrderNumbersGUI (Gtk.Builder):
	product_id = 0
	def __init__(self, ):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		c = DB.cursor()
		vendor_store = self.get_object('vendor_store')
		vendor_store.clear()
		c.execute("SELECT id::text, name FROM contacts "	
							"WHERE (deleted, vendor) = (False, True) "
							"ORDER BY name")
		for row in c.fetchall():
			vendor_store.append(row)
		c.close()
		self.window = self.get_object('window')
		self.window.show_all()

	def populate_product_order_numbers(self):
		c = DB.cursor()
		store = self.get_object('order_number_store')
		store.clear()
		try:
			c.execute("SELECT vpn.id, c.id, c.name, vendor_sku, "
						"vendor_barcode, qty::int, price::text "
						"FROM vendor_product_numbers AS vpn "
						"JOIN contacts AS c ON c.id = vpn.vendor_id "
						"AND vendor = True "
						"WHERE (product_id, vpn.deleted) = (%s, False) "
						"ORDER BY c.name FOR UPDATE NOWAIT", 
						(self.product_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			c.close()
			hint = "Hint: somebody else is editing this product's order numbers"
			error = str(e) + hint
			self.show_message (error)
			self.window.destroy()
			return False
		for row in c.fetchall():
			store.append(row)
		c.close()
		
	def window_destroy (self, widget):
		DB.rollback()
	
	def delete_row_clicked (self, button):
		selection = self.get_object('tree-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		c = DB.cursor()
		row_id = model[path][0]
		c.execute("DELETE FROM vendor_product_numbers "
							"WHERE id = %s", (row_id,))
		self.populate_product_order_numbers ()
		c.close()

	def new_row_clicked (self, button):
		c = DB.cursor()
		c.execute("WITH vendor AS "
					"(SELECT id FROM contacts WHERE vendor = True "
						"AND id NOT IN "
						"(SELECT vendor_id FROM vendor_product_numbers "
							"WHERE product_id = %s GROUP BY vendor_id)"
						"ORDER BY name LIMIT 1)"
					"INSERT INTO vendor_product_numbers "
					"(product_id, vendor_id, vendor_sku, vendor_barcode) "
					"VALUES "
					"(%s, (SELECT id FROM vendor), '', '') RETURNING id",
					(self.product_id, self.product_id))
		row_id = c.fetchone()[0]
		self.populate_product_order_numbers ()
		self.select_row (row_id)
		c.close()

	def select_row(self, row_id):
		store = self.get_object('order_number_store')
		selection = self.get_object('tree-selection')
		for row in store:
			if row[0] == row_id:
				selection.select_iter(row.iter)
				break

	def vendor_combo_changed (self, combo, path, tree_iter):
		vendor_store = self.get_object('vendor_store')
		vendor_id = vendor_store[tree_iter][0]
		store = self.get_object('order_number_store')
		row_id = store[path][0]
		c = DB.cursor()
		try:
			c.execute("UPDATE vendor_product_numbers "
						"SET vendor_id = %s WHERE id = %s", 
						(vendor_id, row_id))
		except psycopg2.IntegrityError as e:
			DB.rollback()
			hint = "\nHint: you have an order number for this vendor already"
			self.show_message(str(e) + hint)
		c.close()
		self.populate_product_order_numbers ()
		self.select_row (row_id)

	def buy_qty_edited (self, cellrenderertext, path, text):
		c = DB.cursor()
		store = self.get_object('order_number_store')
		row_id = store[path][0]
		c.execute("UPDATE vendor_product_numbers "
					"SET qty = %s WHERE id = %s", 
					(text, row_id))
		self.populate_product_order_numbers ()
		self.select_row (row_id)
		c.close()

	def qty_price_edited (self, cellrenderertext, path, text):
		c = DB.cursor()
		store = self.get_object('order_number_store')
		row_id = store[path][0]
		c.execute("UPDATE vendor_product_numbers "
					"SET price = %s WHERE id = %s", 
					(text, row_id))
		self.populate_product_order_numbers ()
		self.select_row (row_id)
		c.close()

	def barcode_edited (self, cellrenderertext, path, text):
		c = DB.cursor()
		store = self.get_object('order_number_store')
		row_id = store[path][0]
		c.execute("UPDATE vendor_product_numbers "
					"SET vendor_barcode = %s WHERE id = %s", 
					(text, row_id))
		self.populate_product_order_numbers ()
		self.select_row (row_id)
		c.close()

	def order_number_edited (self, cellrenderertext, path, text):
		c = DB.cursor()
		store = self.get_object('order_number_store')
		row_id = store[path][0]
		c.execute("UPDATE vendor_product_numbers "
					"SET vendor_sku = %s WHERE id = %s", 
					(text, row_id))
		self.populate_product_order_numbers ()
		self.select_row (row_id)
		c.close()

	def save_clicked (self, button):
		DB.commit()
		self.window.destroy()

	def cancel_clicked (self, button):
		self.window.destroy()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




