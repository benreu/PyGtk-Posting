# product_search.py
#
# Copyright (C) 2016 reuben
# 
# product_search is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# product_search is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.



from gi.repository import Gtk, Gdk
from pricing import product_retail_price

UI_FILE = "src/product_search.ui"


class ProductSearchGUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db  = main.db
		self.cursor = self.db.cursor()

		self.product_name = ''
		self.ext_name = ''
		self.barcode = ''
		self.vendor = ''
		self.order_number = ''
		self.vendor_barcode = ''

		self.treeview = self.builder.get_object('treeview1')
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)	
		self.treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		self.treeview.connect('drag_data_get', self.on_drag_data_get)
		self.treeview.drag_source_set_target_list([dnd])
		
		self.product_store = self.builder.get_object('product_store')
		self.product_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
		self.filtered_product_store = self.builder.get_object('filtered_product_store')
		self.filtered_product_store.set_visible_func(self.filter_func)
		self.populate_product_treeview_store()
		self.handler_id = main.connect("products_changed", self.populate_product_treeview_store )

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.main.disconnect(self.handler_id)
		self.cursor.close()
		
	def on_drag_data_get (self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][0]
		string = "%s %s" % ('1', product_id)
		data.set_text(string, -1)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		id_ = model[path][0]
		import product_hub
		product_hub.ProductHubGUI(self.main, id_)

	def treeview_row_activated (self, treeview, path, column):
		if self.builder.get_object('checkbutton1').get_active() == False:
			return

	def any_search_changed (self, entry):
		'''This signal is hooked up to all search entries'''
		self.product_name = self.builder.get_object('searchentry1').get_text().lower()
		self.ext_name = self.builder.get_object('searchentry2').get_text().lower()
		self.barcode = self.builder.get_object('searchentry3').get_text().lower()
		self.vendor = self.builder.get_object('searchentry4').get_text().lower()
		self.order_number = self.builder.get_object('searchentry5').get_text().lower()
		self.vendor_barcode = self.builder.get_object('searchentry6').get_text().lower()
		self.filtered_product_store.refilter()

	def filter_func (self, model, tree_iter, r):
		for i in self.product_name.split():
			if i in model[tree_iter][1].lower():
				continue
			else:
				return False
		for i in self.ext_name.split():
			if i in model[tree_iter][2].lower():
				continue
			else:
				return False
		for i in self.barcode.split():
			if i in model[tree_iter][3].lower():
				continue
			else:
				return False
		for i in self.vendor.split():
			if i in model[tree_iter][4].lower():
				continue
			else:
				return False
		for i in self.order_number.split():
			if i in model[tree_iter][5].lower():
				continue
			else:
				return False
		for i in self.vendor_barcode.split():
			if i in model[tree_iter][6].lower():
				continue
			else:
				return False
		return True

	def populate_product_treeview_store (self, m = None):
		self.product_store.clear()
		self.cursor.execute ("SELECT p.id, p.name, p.ext_name, p.barcode, "
							"p.deleted, p.stock, p.sellable, p.purchasable, "
							"p.manufactured, "
							"c.name, vp.vendor_sku, vp.vendor_barcode "
							"FROM products AS p "
							"LEFT JOIN vendor_product_numbers AS vp "
							"ON vp.product_id = p.id "
							"LEFT JOIN contacts AS c ON vp.vendor_id = c.id")
		for row in self.cursor.fetchall():
			product_id = row[0]
			name = row[1]
			ext_name = row[2]
			barcode = row[3]
			deleted = row[4]
			stock = row[5]
			sellable = row[6]
			purchasable = row[7]
			manufactured = row[8]
			vendor = row[9]
			order_number = row[10]
			vendor_barcode = row[11]
			if vendor == None:
				vendor = ''
			if order_number == None:
				order_number = ''
			if vendor_barcode == None:
				vendor_barcode = ''
			self.product_store.append([product_id, name, ext_name, 
											barcode, vendor, order_number, 
											vendor_barcode, deleted, stock, 
											sellable, purchasable, 
											manufactured])

	def set_all_column_indicators_false(self):
		for column in self.treeview.get_columns():
			column.set_sort_indicator(False )

	def product_name_column_clicked(self, treeview_column ):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (1, Gtk.SortType.ASCENDING )

	def ext_name_column_clicked(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (2, Gtk.SortType.ASCENDING )

	def barcode_column_clicked(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (3, Gtk.SortType.ASCENDING )

	def vendor_column_clicked(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (4, Gtk.SortType.ASCENDING )

	def order_number_column_clicked(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (5, Gtk.SortType.ASCENDING )

	def vendor_barcode_column_clicked(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (6, Gtk.SortType.ASCENDING )

	def stock_column_clicked(self, treeview_column):	
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (8, Gtk.SortType.ASCENDING )

	def sellable_column_clicked(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (9, Gtk.SortType.ASCENDING)

	def purchasable_column_clicked(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (10, Gtk.SortType.ASCENDING)

	def manufactured_column_clicked(self, treeview_column):
		self.set_all_column_indicators_false()
		treeview_column.set_sort_indicator(True )
		self.product_store.set_sort_column_id (11, Gtk.SortType.ASCENDING)
		