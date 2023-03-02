# inventory_compare.py
#
# Copyright (C) 2023 - Reuben Rissler
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, GLib
from decimal import Decimal
from pricing import product_retail_price
from constants import ui_directory, DB

UI_FILE = ui_directory + "/inventory/inventory_compare.ui"

class InventoryCompareGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		#self.product_store = self.get_object('product_store')
		self.populate_stores()
		#product_completion = self.get_object('product_completion')
		#product_completion.set_match_func(self.product_match_func)

		self.window = self.get_object('window')
		self.window.show_all()

	def populate_stores (self):
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

	def inventory_summaries_clicked (self, button):
		from inventory import inventory_summaries
		inventory_summaries.InventorySummariesGUI(self)

	def inventory_summary_changed (self, combobox):
		summary_id = combobox.get_active_id()
		if summary_id == None:
			return
		self.summary_id = summary_id
		self.populate_current_inventory()
		c = DB.cursor()
		# previous summary view
		previous_store = self.get_object("previous_inventory_store")
		previous_store.clear()
		c.execute("SELECT cs.id, cs.name "
					"FROM inventory.count_summaries AS cs "
					"WHERE cs.id = %s-1", (summary_id,))
		for row in c.fetchall():
			previous_id, previous_name = row[0], row[1]
			self.get_object('previous_summary_label').set_label(previous_name)
			c = DB.cursor()
			c.execute("SELECT cr.qty, "
						"p.id, "
						"p.name "
						"FROM inventory.count_rows AS cr "
						"JOIN products AS p ON p.id = cr.product_id "
						"WHERE count_summary_id = %s", (previous_id,))
			for row in c.fetchall():
				previous_store.append(row)
			self.set_widgets_sensitive(True)
			break
		else:
			self.get_object('previous_summary_label').set_label('does not exist')
			self.set_widgets_sensitive(False)

	def populate_current_inventory(self):
		current_store = self.get_object("current_inventory_store")
		current_store.clear()
		c = DB.cursor()
		c.execute("SELECT cr.qty, "
					"p.id, "
					"p.name "
					"FROM inventory.count_rows AS cr "
					"JOIN products AS p ON p.id = cr.product_id "
					"WHERE count_summary_id = %s", (self.summary_id,))
		for row in c.fetchall():
			current_store.append(row)

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def delete_activated (self, menuitem):
		selection = self.get_object('current_inventory_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		c = DB.cursor()
		c.execute("DELETE FROM inventory.count_rows "
					"WHERE (count_summary_id, product_id) = (%s, %s)",
					(self.summary_id, product_id))
		DB.commit()
		self.populate_current_inventory ()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('current_inventory_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		import product_hub
		product_hub.ProductHubGUI(product_id)
		
	def copy_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"VALUES (%s, "
						"%s, "
						"%s, "
						"(SELECT cost FROM products WHERE id = %s)," 
						"(SELECT product_retail_price(%s))"
						") "
					"ON CONFLICT DO NOTHING",
					(self.summary_id, product_id, qty, product_id, product_id))
		DB.commit()
		self.populate_current_inventory()
		
	def update_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"VALUES (%s, "
						"%s, "
						"%s, "
						"(SELECT cost FROM products WHERE id = %s)," 
						"(SELECT product_retail_price(%s))"
						") "
					"ON CONFLICT (count_summary_id, product_id) "
					"DO UPDATE SET qty = %s "
					"WHERE (cr.count_summary_id, cr.product_id) = (%s, %s)",
					(self.summary_id, product_id, qty, product_id, product_id,
					qty, self.summary_id, product_id))
		DB.commit()
		self.populate_current_inventory()
		
	def create_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"VALUES (%s, "
						"%s, "
						"0, "
						"(SELECT cost FROM products WHERE id = %s)," 
						"(SELECT product_retail_price(%s))"
						") "
					"ON CONFLICT DO NOTHING",
					(self.summary_id, product_id, product_id, product_id))
		DB.commit()
		self.populate_current_inventory()

	def set_widgets_sensitive(self, value):
		self.get_object('copy_button').set_sensitive(value)
		self.get_object('update_button').set_sensitive(value)
		self.get_object('create_button').set_sensitive(value)


