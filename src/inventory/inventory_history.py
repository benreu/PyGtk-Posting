# inventory_history.py
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
import constants

UI_FILE = constants.ui_directory + "/inventory/inventory_history.ui"

class InventoryHistoryGUI:
	def __init__(self, product_id = None):

		self.previous_keyname = None
		self.ascending = False
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()
		
		self.product_id = product_id

		self.inventory_transaction_store = self.builder.get_object('inventory_transaction_store')
		self.product_store = self.builder.get_object('product_store')
		self.location_store = self.builder.get_object('location_store')
		self.populate_location_store()
		self.populate_product_store ()
		
		self.filter_list = ""
		#self.populate_history_treeview ()
		self.builder.get_object('product_completion').set_match_func(self.product_match_string)

		if product_id != None:
			self.builder.get_object('combobox2').set_active_id(str(product_id))
			self.populate_history_treeview ()

		window = self.builder.get_object('window1')
		window.show_all()

	def populate_location_store (self):
		location_combo = self.builder.get_object('combobox1')
		active_location = location_combo.get_active()
		self.location_store.clear()
		self.cursor.execute("SELECT id, name FROM locations ORDER BY 1")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			self.location_store.append([str(location_id), location_name])
		if active_location < 0:
			location_combo.set_active(0)
		else:
			location_combo.set_active(active_location)

	def populate_product_store (self):
		self.product_store.clear()
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, stock) = (False, True) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			self.product_store.append([str(product_id), product_name])

	def product_match_selected(self, completion, model, iter_):
		self.product_id = model[iter_][0]
		product_name = model[iter_][1]
		self.builder.get_object('comboboxtext-entry').set_text(product_name)
		self.populate_history_treeview ()

	def product_match_string(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def date_format(self, column, cellrenderer, model, iter1, data):
		date = model.get_value(iter1, 1)
		if date == '': # no valid date
			return
		day_entry = date[8:10]
		month_numeric = int(date[5:7])
		month_entry = Month()[month_numeric - 1] #turn the integer to a text month
		year_entry = date[0:4]
		date = month_entry + " " + str(day_entry) + " " + str(year_entry)#format the string so we can read it easily
		cellrenderer.set_property("text" , date)

	def focus(self, window, event):
		self.populate_history_treeview ()

	def product_combobox_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.builder.get_object('checkbutton1').set_active(False)
			self.populate_history_treeview ()

	def view_all_toggled(self, toggle_button):
		self.populate_history_treeview ()

	def location_changed(self, combo):
		self.populate_history_treeview ()

	def populate_history_treeview (self):
		all_history = self.builder.get_object('checkbutton1').get_active()
		location_id = self.builder.get_object('combobox1').get_active_id()
		self.inventory_transaction_store.clear()
		if self.product_id != None and all_history == False:	
			self.cursor.execute("SELECT "
									"i_t.id, "
									"format_date(date_inserted), "
									"(qty_in - qty_out), "
									"products.name, "
									"locations.name "
								"FROM inventory_transactions AS i_t "
								"JOIN locations "
								"ON locations.id = i_t.location_id "
								"JOIN products "
								"ON products.id = i_t.product_id "
								"WHERE (product_id, location_id) = "
								"(%s, %s) ORDER BY locations.name", 
								(self.product_id, location_id))
		else:
			self.cursor.execute("SELECT "
									"i_t.id, "
									"format_date(date_inserted), "
									"(qty_in - qty_out), "
									"products.name, "
									"locations.name "
								"FROM inventory_transactions AS i_t "
								"JOIN locations "
								"ON locations.id = i_t.location_id "
								"JOIN products "
								"ON products.id = i_t.product_id "
								"WHERE location_id = %s "
								"ORDER BY locations.name",
								(location_id, ))
		for row in self.cursor.fetchall():
			self.inventory_transaction_store.append(row)



				

		
