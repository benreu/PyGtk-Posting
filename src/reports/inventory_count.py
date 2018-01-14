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
from pricing import product_retail_price

UI_FILE = "src/reports/inventory_count.ui"


class InventoryCountGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.product_count = 0
		self.retail = 0.00
		self.cost = 0.00
		self.inventory_store = self.builder.get_object('inventory_store')

		self.window = self.builder.get_object('window1')
		self.window.show_all()


	def barcode_entry_activated (self, entry):
		barcode = entry.get_text()
		entry.set_text('')
		if barcode == "":
			return
		self.cursor.execute("SELECT id, name, cost FROM products "
							"WHERE barcode = %s", (barcode,))
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			product_cost = float(row[2])
			break
		else:
			return # no product
		self.product_count += 1
		for row in self.inventory_store:
			if row[0] == product_id:
				row[2] += 1
				self.cost += row[4]
				self.retail += row[5]
				break
			continue
		else:
			retail = product_retail_price (self.db, product_id)
			self.retail += retail
			self.cost += product_cost
			self.inventory_store.append([product_id, barcode, 1, product_name,
										product_cost, retail])
		self.builder.get_object('label3').set_label(str(self.product_count))
		self.builder.get_object('label5').set_label('${:,.2f}'.format(self.retail))
		self.builder.get_object('label7').set_label('${:,.2f}'.format(self.cost))






		