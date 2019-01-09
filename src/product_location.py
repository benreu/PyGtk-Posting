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
import main

UI_FILE = main.ui_directory + "/product_location.ui"

class ProductLocationGUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
			
		self.builder.connect_signals(self)
		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.aisle_text = ""
		self.product_text = ""
		self.rack_text = ""
		self.cart_text = ""
		self.shelf_text = ""
		self.cabinet_text = ""
		self.drawer_text = ""
		self.bin_text = ""
		self.ascending = False
	
		self.product_location_store = self.builder.get_object('location_treeview_store')
		self.product_location_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
		self.location_store = self.builder.get_object('location_store')
		
		self.filtered_location_store = self.builder.get_object('filtered_location_store')
		self.filtered_location_store.set_visible_func(self.filter_func)

		self.treeview = self.builder.get_object('treeview1')
		
		self.populate_product_location_treeview()
		self.populate_location_combo()
		self.handler_id = main.connect("products_changed", self.populate_product_location_treeview)
		
		window = self.builder.get_object('window1')
		window.show_all()
		
	def destroy (self, window):	
		self.main.disconnect(self.handler_id)
		self.cursor.close()

	def clear_all_search_clicked(self, widget):
		self.builder.get_object('searchentry1').set_text("")
		self.builder.get_object('entry1').set_text("")
		self.builder.get_object('entry2').set_text("")
		self.builder.get_object('entry3').set_text("")
		self.builder.get_object('entry4').set_text("")
		self.builder.get_object('entry5').set_text("")
		self.builder.get_object('entry6').set_text("")
		self.builder.get_object('entry7').set_text("")

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][9]
		import product_hub 
		product_hub.ProductHubGUI(self.main, product_id)

	def set_all_column_indicators_false(self):
		for column in self.treeview.get_columns():
			column.set_sort_indicator(False )

	def product_column_sort(self, treeview_column ):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (1, Gtk.SortType.ASCENDING )

	def aisle_column_sort(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (2, Gtk.SortType.ASCENDING )

	def rack_column_sort(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (3, Gtk.SortType.ASCENDING )

	def cart_column_sort(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (4, Gtk.SortType.ASCENDING )

	def shelf_column_sort(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (5, Gtk.SortType.ASCENDING )

	def cabinet_column_sort(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (6, Gtk.SortType.ASCENDING )

	def drawer_column_sort(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (7, Gtk.SortType.ASCENDING )

	def bin_column_sort(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_location_store.set_sort_column_id (8, Gtk.SortType.ASCENDING )
		
	def search_changed(self, widget):
		self.product_text = self.builder.get_object('searchentry1').get_text().lower()
		self.aisle_text = self.builder.get_object('entry1').get_text().lower()
		self.rack_text = self.builder.get_object('entry2').get_text().lower()
		self.cart_text = self.builder.get_object('entry3').get_text().lower()
		self.shelf_text = self.builder.get_object('entry4').get_text().lower()
		self.cabinet_text = self.builder.get_object('entry5').get_text().lower()
		self.drawer_text = self.builder.get_object('entry6').get_text().lower()
		self.bin_text = self.builder.get_object('entry7').get_text().lower()
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
		tree_selection = self.builder.get_object('treeview-selection1')
		model, path = tree_selection.get_selected_rows()
		self.populate_product_location_treeview ()
		self.populate_location_combo()
		if path == []:
			return		
		#if self.builder.get_object('checkbutton1').get_active() == True:
		self.builder.get_object('treeview1').scroll_to_cell(path)
		tree_selection.select_path(path)

	def populate_product_location_treeview (self, i = None):
		location_id = self.builder.get_object('combobox1').get_active_id()
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
							"WHERE (locator_visible, location_id) = (True, %s)", 
							(location_id,))
		for row in self.cursor.fetchall():
			self.product_location_store.append(row)

	def populate_location_combo(self):
		location_combo = self.builder.get_object('combobox1')
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

	def row_activate(self, treeview, path, treeviewcolumn):
		treeiter = self.product_location_store.get_iter(path)
		product_id = self.product_location_store.get_value(treeiter, 9)
		import products
		products.ProductsGUI(self.db, product_id, product_location_tab = True)

	def product_treeview_button_release (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()




		
