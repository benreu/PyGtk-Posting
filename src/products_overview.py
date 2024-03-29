# products_overview.py
# Copyright (C) 2016 reuben
# 
# products_overview.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# products_overview.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, GLib
import subprocess
from constants import broadcaster, DB, ui_directory
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/products_overview.ui"

class ProductsOverviewGUI (Gtk.Builder):
	product_id = 0
	filter_list = ''
	def __init__(self, product_id = None):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		if product_id != None:
			self.product_id = product_id
		self.exists = True
		self.treeview = self.get_object('treeview2')
		self.product_store = self.get_object('product_store')
		self.product_name_store = Gtk.ListStore(str) # for product suggestions
		self.populate_product_names ()
		self.filtered_product_store = self.get_object('filtered_product_store')
		self.filtered_product_store.set_visible_func(self.filter_func)
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		mask = Gdk.ModifierType.BUTTON1_MASK 
		self.treeview.drag_source_set(mask, [dnd], Gdk.DragAction.COPY)
		self.treeview.connect('drag_data_get', self.on_drag_data_get)
		self.treeview.drag_source_set_target_list([dnd])
		self.populate_product_store()
		self.handler_ids = list()
		for connection in (("products_changed", self.show_refresh_button),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		self.window = self.get_object('window')
		self.set_window_layout_from_settings ()
		self.window.show_all()
		GLib.idle_add(self.window.set_position, Gtk.WindowPosition.NONE)

	def show_refresh_button (self, broadcast):
		self.get_object('refresh_button').set_visible(True)

	def product_treeview_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		product_id = model[path][0]
		self.edit_product (product_id)

	def set_window_layout_from_settings(self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT size FROM product_overview "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT size FROM product_overview "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT widget_id, size FROM product_overview WHERE "
					"widget_id NOT IN ('window_height', 'window_width')")
		for row in c.fetchall():
			width = row[1]
			column = self.get_object(row[0])
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()

	def save_window_layout_activated (self, button):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO product_overview (widget_id, size) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO product_overview (widget_id, size) "
					"VALUES ('window_height', ?)", (height,))
		for column in ['name_column', 
						'ext_name_column', 
						'description_column', 
						'barcode_column', 
						'unit_column', 
						'weight_column', 
						'tare_column', 
						'manufacturer_sku_column', 
						'expense_account_column', 
						'inventory_account_column', 
						'revenue_account_column', 
						'sellable_column', 
						'purchasable_column', 
						'manufactured_column', 
						'job_column', 
						'stocked_column', 
						'price_column']:
			try:
				width = self.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO product_overview (widget_id, size) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.window = None

	def report_hub_activated (self, menuitem):
		treeview = self.get_object('treeview2')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def print_label_activated (self, menuitem):
		import product_print_label
		product_print_label.ProductPrintLabelGUI(self.product_id)

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][0]
		string = '1 ' + str(product_id) 
		data.set_text(string, -1)

	def help_button_activated (self, menuitem):
		subprocess.Popen(["yelp", help_dir + "/products.page"])

	def filter_func(self, model, tree_iter, r):
		for text in self.filter_list:
			if text not in model[tree_iter][1].lower():
				return False
		return True

	def search_changed(self, search_entry):
		filter_text = search_entry.get_text().lower()
		self.filter_list = filter_text.split(" ")
		self.filtered_product_store.refilter()

	def populate_product_names (self):
		c = DB.cursor()
		c.execute("SELECT name FROM products "
					"WHERE deleted = False "
					"ORDER BY name")
		for row in c.fetchall():
			self.product_name_store.append(row)
		c.close()

	def product_type_radiobutton_toggled (self, radiobutton):
		if radiobutton.get_active() == True:
			self.populate_product_store()

	def refresh_clicked (self, button):
		self.populate_product_store()
		self.populate_product_names()
		button.set_visible(False)

	def populate_product_store (self, widget = None):
		progressbar = self.get_object('progressbar')
		c = DB.cursor()
		model = self.treeview.get_model()
		self.treeview.set_model(None)
		spinner = self.get_object('spinner')
		spinner.show()
		spinner.start()
		self.product_store.clear()
		if self.get_object('radiobutton1').get_active() == True:
			where = "WHERE (deleted, sellable) = (False, True) " 
		elif self.get_object('radiobutton2').get_active() == True:
			where = "WHERE (deleted, purchasable) = (False, True) "
		elif self.get_object('radiobutton3').get_active() == True:
			where = "WHERE (deleted, manufactured) = (False, True) "
		elif self.get_object('radiobutton4').get_active() == True:
			where = "WHERE (deleted, job) = (False, True) "
		elif self.get_object('radiobutton5').get_active() == True:
			where = "WHERE (deleted, stock) = (False, False) "
		elif self.get_object('radiobutton7').get_active() == True:
			where = "WHERE deleted = True "
		else:
			where = "WHERE deleted = False "
		c.execute("SELECT 	p.id, "
							"p.name, "
							"p.ext_name, "
							"p.description, "
							"p.barcode, "
							"u.name, "
							"p.weight::text, "
							"p.tare::text, "
							"p.manufacturer_sku, "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = default_expense_account), ''), "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = p.inventory_account), ''), "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = p.revenue_account), ''), "
							"p.sellable, "
							"p.purchasable, "
							"p.manufactured, "
							"p.job, "
							"p.stock, "
							"COALESCE(pmp.price, 0.00), "
							"COALESCE(pmp.price::text, 'N/A') "
							"FROM products AS p "
							"JOIN units AS u ON u.id = p.unit "
							"LEFT JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id AND pmp.markup_id = "
							"(SELECT id FROM customer_markup_percent WHERE standard = True) "
							"%s OR p.id = %s ORDER BY p.name, p.ext_name"
							% (where, self.product_id))
		p_tuple = c.fetchall()
		rows = len(p_tuple)
		for row_count, row in enumerate(p_tuple):
			progressbar.set_fraction((row_count + 1) / rows)
			self.product_store.append(row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		self.treeview.set_model(model)
		self.treeview.set_search_column(1)
		self.select_product()
		spinner.hide()
		spinner.stop()
		c.close()
		DB.rollback()

	def append_product(self):
		c = DB.cursor()
		c.execute("SELECT 	p.id, "
							"p.name, "
							"p.ext_name, "
							"p.description, "
							"p.barcode, "
							"u.name, "
							"p.weight::text, "
							"p.tare::text, "
							"p.manufacturer_sku, "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = default_expense_account), ''), "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = p.inventory_account), ''), "
							"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = p.revenue_account), ''), "
							"p.sellable, "
							"p.purchasable, "
							"p.manufactured, "
							"p.job, "
							"p.stock, "
							"COALESCE(pmp.price, 0.00), "
							"COALESCE(pmp.price::text, 'N/A') "
							"FROM products AS p "
							"JOIN units AS u ON u.id = p.unit "
							"LEFT JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id AND pmp.markup_id = "
							"(SELECT id FROM customer_markup_percent WHERE standard = True) "
							"WHERE p.id = %s ", (self.product_id,))
		for row in c.fetchall():
			self.product_store.append(row)
		c.close()

	def select_product (self):
		for row in self.treeview.get_model(): 
			if row[0] == self.product_id: 
				treeview_selection = self.get_object('treeview-selection')
				treeview_selection.select_path(row.path)
				self.treeview.scroll_to_cell(row.path, None, True, 0.5)
				break
			
	def window_key_press_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if event.get_state() & Gdk.ModifierType.CONTROL_MASK: #Control held down
			if keyname == "q":
				window.destroy()

	def product_hub_clicked (self, menuitem):
		model, path = self.get_object('treeview-selection').get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def product_treeview_selection_changed (self, tree_selection):
		model, path = tree_selection.get_selected_rows()
		if path == []:
			return
		self.product_id = model[path][0]

	def order_numbers_clicked (self, widget):
		model, path = self.get_object('treeview-selection').get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_edit_order_numbers
		peon = product_edit_order_numbers.ProductsEditOrderNumbersGUI()
		peon.product_id = product_id
		peon.populate_product_order_numbers ()
		peon.window.set_transient_for(self.window)

	def product_location_clicked (self, widget):
		model, path = self.get_object('treeview-selection').get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_edit_location
		pel = product_edit_location.ProductEditLocationGUI(product_id)
		pel.window.set_transient_for(self.window)

	def edit_clicked (self, widget):
		model, path = self.get_object('treeview-selection').get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		self.edit_product (product_id)

	def edit_product (self, product_id):
		import product_edit_main
		pe = product_edit_main.ProductEditMainGUI()
		pe.get_object('product_completion').set_model(self.product_name_store)
		pe.select_product(product_id)
		pe.window.set_transient_for(self.window)

	def new_clicked (self, button):
		import product_edit_main
		pe = product_edit_main.ProductEditMainGUI(self)
		pe.get_object('product_completion').set_model(self.product_name_store)
		pe.new_product()
		pe.window.set_transient_for(self.window)

	def product_treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()


