# inventory_adjustment.py
# Copyright (C) 2016 reuben 
# 
# inventory_adjustment.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# inventory_adjustment.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
from datetime import datetime

UI_FILE = "src/inventory/inventory_adjustment.ui"

class InventoryAdjustmentGUI:
	def __init__(self, db, product_id = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
		self.db = db
		self.cursor = self.db.cursor()
		self.product_store = self.builder.get_object('product_store')
		self.location_store = self.builder.get_object('location_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.populate_stores ()
		if product_id != None:
			self.product_id = product_id
			self.builder.get_object('combobox1').set_active_id(str(product_id))
		
		window = self.builder.get_object('window')
		window.show_all()

	def destroy(self, window = None):
		self.builder.get_object('window').destroy()
		return True

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_stores (self):
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, stock) "
							"= (False, True) ORDER BY name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			self.product_store.append([str(product_id), product_name])
		self.cursor.execute("SELECT id, name FROM locations "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			self.location_store.append([str(location_id), location_name])
		self.builder.get_object('combobox2').set_active(0)

	def product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.product_selected (self.product_id)

	def product_completion_match_selected (self, completion, model, iter):
		self.product_id = model[iter][0]
		self.product_selected (self.product_id)

	def product_selected (self, product_id):
		self.cursor.execute("SELECT inventory_enabled FROM products "
							"WHERE id = %s", (product_id,))
		if self.cursor.fetchone()[0] == True:
			self.populate_adjustment_reason_combobox ()
		else:
			combo = self.builder.get_object('comboboxtext3')
			combo.remove_all()
			combo.append("1","Starting inventory")
		inventory = 0
		self.cursor.execute("SELECT SUM(qty) FROM inventory_transactions "
							"WHERE product_id = %s "
							"GROUP BY product_id", (product_id,))
		for row in self.cursor.fetchall():
			inventory = row[0]
		self.builder.get_object('label24').set_text(str(inventory))

	def inventory_history_clicked (self, widget):
		from inventory import inventory_history
		inventory_history.InventoryHistoryGUI(self.db, self.product_id)

	def inventory_adjustment_spinbutton_changed(self, spinbutton):
		adjustment_amount = spinbutton.get_value()
		inventory = 0
		self.cursor.execute("SELECT SUM(qty) FROM inventory_transactions "
							"WHERE product_id = %s", (self.product_id,))
		for row in self.cursor.fetchall():
			inventory = row[0]
		current_inventory = str(inventory + adjustment_amount)
		self.builder.get_object('label23').set_text(current_inventory)
		self.builder.get_object('comboboxtext3').set_sensitive(True)

	def inventory_adjustment_combobox_changed(self, widget):
		if self.product_id != 0:
			self.builder.get_object('button2').set_sensitive(True)
		else:
			self.builder.get_object('button2').set_sensitive(False)

	def apply_inventory_adjustment_clicked (self, widget):
		adjustment_amount = self.builder.get_object('spinbutton12').get_text()
		adjustment_reason = self.builder.get_object('comboboxtext3').get_active_text()
		location_id = self.builder.get_object('combobox2').get_active_id()
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty, reason, date_inserted, "
							"location_id) VALUES (%s, %s, %s, %s, %s)", 
							(self.product_id, adjustment_amount, 
							adjustment_reason, datetime.today(), 
							location_id))
		self.cursor.execute("UPDATE products SET inventory_enabled = True "
							"WHERE id = %s", (self.product_id,))
		self.db.commit()
		self.builder.get_object('spinbutton12').set_value(0)
		self.builder.get_object('comboboxtext3').set_sensitive(False)
		self.builder.get_object('comboboxtext3').set_active(0-1)
		widget.set_sensitive(False)

	def populate_adjustment_reason_combobox(self):
		combo = self.builder.get_object('comboboxtext3')
		combo.remove_all()
		combo.append("1","Broken")
		combo.append("2","Donation")
		combo.append("3","Invoiced and unpaid")
		combo.append("4","Lost and found")
		combo.append("5","Lost")
		combo.append("6","Purchased and unreceived")
		combo.append("7","Stolen")
		combo.append("8","Wrong count")
