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
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/product_search.ui"

class ProductSearchGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

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
		self.filtered_product_store = self.builder.get_object('filtered_product_store')
		self.filtered_product_store.set_visible_func(self.filter_func)
		self.handler_ids = list()
		for connection in (("products_changed", self.show_refresh_button),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_product_treeview_store()

	def show_refresh_button (self, broadcast):
		self.builder.get_object('refresh_button').set_visible(True)

	def destroy (self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()
		
	def on_drag_data_get (self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][0]
		string = "%s %s" % ('1', product_id)
		data.set_text(string, -1)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		id_ = model[path][0]
		import product_hub
		product_hub.ProductHubGUI(id_)

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
			if i not in model[tree_iter][1].lower():
				return False
		for i in self.ext_name.split():
			if i not in model[tree_iter][2].lower():
				return False
		for i in self.barcode.split():
			if i not in model[tree_iter][3].lower():
				return False
		for i in self.vendor.split():
			if i not in model[tree_iter][4].lower():
				return False
		for i in self.order_number.split():
			if i not in model[tree_iter][5].lower():
				return False
		for i in self.vendor_barcode.split():
			if i not in model[tree_iter][6].lower():
				return False
		return True

	def refresh_clicked (self, button):
		self.populate_product_treeview_store()
		button.set_visible(False)

	def populate_product_treeview_store (self):
		progressbar = self.builder.get_object('progressbar')
		treeview = self.builder.get_object('treeview1')
		store = self.builder.get_object('product_store')
		treeview.set_model(None)
		store.clear()
		c = DB.cursor()
		c.execute ("SELECT p.id, "
							"p.name, "
							"p.ext_name, "
							"p.barcode, "
							"COALESCE(c.name, ''), "
							"COALESCE(vpn.vendor_sku, ''), "
							"COALESCE(vpn.vendor_barcode, ''), "
							"p.deleted, "
							"p.stock, "
							"p.sellable, "
							"p.purchasable, "
							"p.manufactured "
							"FROM products AS p "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON vpn.product_id = p.id "
							"LEFT JOIN contacts AS c ON vpn.vendor_id = c.id")
		p_tuple = c.fetchall()
		rows = len(p_tuple)
		for row_count, row in enumerate(p_tuple):
			progressbar.set_fraction((row_count + 1) / rows)
			store.append(row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		treeview.set_model(self.builder.get_object('sorted_product_store'))
		DB.rollback()

