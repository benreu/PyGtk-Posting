# inventory_count.py
# Copyright (C) 2021 reuben 
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

from gi.repository import Gtk, GLib
from decimal import Decimal
from pricing import product_retail_price
from constants import ui_directory, DB

UI_FILE = ui_directory + "/inventory/inventory_count.ui"


class InventoryCountGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.product_store = self.get_object('product_store')
		self.populate_stores()
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.window = self.get_object('window1')
		self.window.show_all()

	def populate_stores (self):
		c = DB.cursor()
		self.product_store.clear()
		c.execute("SELECT id::text, name || ' {' || ext_name || '}' "
							"FROM products ORDER BY name, ext_name")
		for row in c.fetchall():
			self.product_store.append(row)
		c = DB.cursor()
		store = self.get_object('inventory_summaries_store')
		store.clear()
		c.execute("SELECT id::text, name "
					"FROM inventory.count_summaries "
					"WHERE active = True "
					"ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		DB.rollback()
	
	def destroy (self, widget):
		pass

	def widget_focus_in_event (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)

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
		self.process_product(product_id)
		DB.rollback()

	def product_match_selected (self, completion, treemodel, treeiter):
		product_id = treemodel[treeiter][0]
		self.get_object('product_combo').set_active_id(product_id)

	def qty_edited (self, cellrenderertext, path, qty):
		store = self.get_object('inventory_rows_store')
		product_id = store[path][1]
		c = DB.cursor()
		c.execute("UPDATE inventory.count_rows SET qty = %s "
					"WHERE (product_id, count_summary_id) = (%s, %s) ",
					(qty, product_id, self.summary_id))
		DB.commit()
		store[path][0] = int(qty)
		self.populate_inventory_count ()

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def delete_activated (self, menuitem):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		c = DB.cursor()
		c.execute("DELETE FROM inventory.count_rows "
					"WHERE (count_summary_id, product_id) = (%s, %s)",
					(self.summary_id, product_id))
		DB.commit()
		self.populate_inventory_count ()

	def product_hub_activated (self, menuitem):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def barcode_entry_activated (self, entry):
		barcode = entry.get_text()
		entry.select_region(0, -1)
		if barcode == "":
			return
		c = DB.cursor()
		c.execute("SELECT id FROM products "
					"WHERE barcode = %s", (barcode,))
		for row in c.fetchall():
			self.process_product(row[0])
			break
		else:
			store = self.get_object('missing_barcode_store')
			for row in store:
				if row[1] == barcode:
					row[0] += 1
					break
			else:
				store.append([1, barcode])
		DB.rollback()

	def inventory_summaries_combo_changed (self, combobox):
		summary_id = combobox.get_active_id()
		if summary_id != None:
			self.summary_id = summary_id
			self.get_object('widget_box').set_sensitive(True)
			self.populate_inventory_count()

	def process_product(self, product_id):
		c = DB.cursor()
		c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"VALUES (%s, "
						"%s, "
						"1, "
						"(SELECT cost FROM products WHERE id = %s)," 
						"(SELECT product_retail_price(%s))"
						") "
					"ON CONFLICT (count_summary_id, product_id) "
					"DO UPDATE SET qty = cr.qty + 1 "
					"WHERE (cr.count_summary_id, cr.product_id) = (%s, %s)",
					(self.summary_id, product_id,  product_id, product_id,
					self.summary_id, product_id))
		DB.commit()
		self.populate_inventory_count ()

	def populate_inventory_count (self):
		store = self.get_object("inventory_rows_store")
		store.clear()
		c = DB.cursor()
		c.execute("SELECT cr.qty, "
					"p.id, "
					"p.name, "
					"cr.cost, "
					"cr.cost::text, "
					"cr.retail, "
					"cr.retail::text "
					"FROM inventory.count_rows AS cr "
					"JOIN products AS p ON p.id = cr.product_id "
					"WHERE count_summary_id = %s", (self.summary_id,))
		for row in c.fetchall():
			store.append(row)
		self.calculate_totals()

	def inventory_summaries_activated (self, button):
		from inventory import inventory_summaries
		inventory_summaries.InventorySummariesGUI(self)

	def calculate_totals(self):
		c = DB.cursor()
		c.execute("SELECT COALESCE(SUM(qty), 0)::text, "
					"COALESCE(SUM(cost * qty), 0.00)::money, "
					"COALESCE(SUM(retail * qty), 0.00)::money "
					"FROM inventory.count_rows "
					"WHERE count_summary_id = %s", (self.summary_id,))
		for row in c.fetchall():
			product_count = row[0]
			cost = row[1]
			retail = row[2]
		self.get_object('label3').set_label(product_count)
		self.get_object('label7').set_label(cost)
		self.get_object('label5').set_label(retail)






		