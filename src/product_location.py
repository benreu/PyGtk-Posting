# product_location.py
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
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/product_location.ui"

class ProductLocationGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.aisle_text = ""
		self.product_text = ""
		self.rack_text = ""
		self.cart_text = ""
		self.shelf_text = ""
		self.cabinet_text = ""
		self.drawer_text = ""
		self.bin_text = ""
		self.ascending = False
	
		self.product_location_store = self.get_object('location_treeview_store')
		self.location_store = self.get_object('location_store')
		
		self.filtered_location_store = self.get_object(
											'filtered_location_treeview_store')
		self.filtered_location_store.set_visible_func(self.filter_func)

		self.treeview = self.get_object('treeview1')
		
		self.populate_location_combo()
		self.populate_product_location_treeview()
		self.handler_ids = list()
		for connection in (("products_changed", self.show_refresh_button),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def delete_event (self, window, event):
		self.get_object('searchentry1').set_text('')
		window.hide()
		return True

	def present (self):
		self.populate_product_location_treeview()
		self.window.present()

	def show_refresh_button (self, callback):
		self.get_object('refresh_button').set_visible(True)

	def refresh_clicked (self, button):
		button.set_visible(False)
		tree_selection = self.get_object('treeview-selection1')
		model, path = tree_selection.get_selected_rows()
		self.populate_product_location_treeview ()
		if path == []:
			return
		self.get_object('treeview1').scroll_to_cell(path)
		tree_selection.select_path(path)

	def clear_all_search_clicked(self, widget):
		self.get_object('searchentry1').set_text("")
		self.get_object('entry1').set_text("")
		self.get_object('entry2').set_text("")
		self.get_object('entry3').set_text("")
		self.get_object('entry4').set_text("")
		self.get_object('entry5').set_text("")
		self.get_object('entry6').set_text("")
		self.get_object('entry7').set_text("")

	def product_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][9]
		import product_hub 
		product_hub.ProductHubGUI(product_id)
		
	def search_changed(self, widget):
		self.product_text = self.get_object('searchentry1').get_text().lower()
		self.aisle_text = self.get_object('entry1').get_text().lower()
		self.rack_text = self.get_object('entry2').get_text().lower()
		self.cart_text = self.get_object('entry3').get_text().lower()
		self.shelf_text = self.get_object('entry4').get_text().lower()
		self.cabinet_text = self.get_object('entry5').get_text().lower()
		self.drawer_text = self.get_object('entry6').get_text().lower()
		self.bin_text = self.get_object('entry7').get_text().lower()
		self.filtered_location_store.refilter()

	def filter_func(self, model, tree_iter, r):
		if self.product_text in model[tree_iter][1].lower():
			if self.aisle_text in model[tree_iter][2].lower():
				if self.rack_text in model[tree_iter][3].lower():
					if self.cart_text in model[tree_iter][4].lower():
						if self.shelf_text in model[tree_iter][5].lower():
							if self.cabinet_text in model[tree_iter][6].lower():
								if self.drawer_text in model[tree_iter][7].lower():
									if self.bin_text in model[tree_iter][8].lower():
										return True
		return False

	def focus(self, widget, event):
		self.populate_location_combo()

	def populate_product_location_treeview (self):
		location_id = self.get_object('combobox1').get_active_id()
		self.product_location_store.clear()
		self.cursor.execute ("SELECT "
								"pl.id, "
								"p.name, "
								"aisle, "
								"rack, "
								"cart, "
								"shelf, "
								"cabinet, "
								"drawer, "
								"bin, "
								"product_id "
							"FROM product_location AS pl "
							"JOIN products AS p ON p.id = pl.product_id "
							"WHERE location_id = %s "
							"ORDER BY p.name", 
							(location_id,))
		for row in self.cursor.fetchall():
			self.product_location_store.append(row)
		DB.rollback()

	def populate_location_combo(self):
		location_combo = self.get_object('combobox1')
		active_id = location_combo.get_active_id()
		self.location_store.clear()
		self.cursor.execute ("SELECT id, name FROM locations")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			self.location_store.append([str(location_id), location_name])
		if active_id == None:
			location_combo.set_active(0)
		else:
			location_combo.set_active_id(active_id)
		DB.rollback()

	def row_activate(self, treeview, path, treeviewcolumn):
		treeiter = self.product_location_store.get_iter(path)
		product_id = self.product_location_store.get_value(treeiter, 9)
		import products_overview
		po = products_overview.ProductsOverviewGUI(product_id)

	def product_treeview_button_release (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()





