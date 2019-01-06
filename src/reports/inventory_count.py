#
# inventory_count.py
# Copyright (C) 2016 reuben 
# 
# inventory_count is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# inventory_count is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.



from gi.repository import Gtk
from decimal import Decimal
from pricing import product_retail_price

UI_FILE = "src/reports/inventory_count.ui"


class InventoryCountGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.inventory_store = self.builder.get_object('inventory_store')
		self.product_store = self.builder.get_object('product_store')
		self.cursor.execute("SELECT id::text, name || ' {' || ext_name || '}' "
							"FROM products ORDER BY name, ext_name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.window = self.builder.get_object('window1')
		self.window.show_all()
	
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id == None:
			return
		self.cursor.execute("SELECT name, cost, barcode FROM products "
							"WHERE id = %s", (product_id,))
		for row in self.cursor.fetchall():
			self.process_product(int(product_id), row[0], row[1], row[2])
			self.calculate_totals ()

	def product_match_selected (self, completion, treemodel, treeiter):
		product_id = treemodel[treeiter][0]
		self.builder.get_object('product_combo').set_active_id(product_id)

	def qty_edited (self, cellrenderertext, path, qty):
		self.inventory_store[path][2] = int(qty)
		self.calculate_totals()

	def barcode_entry_activated (self, entry):
		barcode = entry.get_text()
		entry.select_region(0, -1)
		if barcode == "":
			return
		self.cursor.execute("SELECT id, name, cost FROM products "
							"WHERE barcode = %s", (barcode,))
		for row in self.cursor.fetchall():
			self.process_product(row[0], row[1], row[2], barcode)
			self.calculate_totals ()

	def process_product(self, product_id, product_name, product_cost, barcode, qty = 0):
		for row in self.inventory_store:
			if row[0] == product_id:
				if qty != 0:
					row[2] = qty 
				else:
					row[2] += 1
				break
			continue
		else:
			retail = product_retail_price (self.db, product_id)
			self.inventory_store.append([product_id, barcode, 1, product_name,
										product_cost, retail])

	def calculate_totals(self):
		product_count = 0
		cost = Decimal()
		retail = Decimal()
		for row in self.inventory_store:
			product_count += 1
			cost += Decimal(row[4] * row[2])
			retail += Decimal(row[5] * row[2])
		self.builder.get_object('label3').set_label(str(product_count))
		self.builder.get_object('label5').set_label('${:,.2f}'.format(retail))
		self.builder.get_object('label7').set_label('${:,.2f}'.format(cost))






		