# assembled_products.py
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

from gi.repository import Gtk, Gdk, GLib
import os, sys
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/assembled_products.ui"


class AssembledProductsGUI:
	timeout_id = None
	def __init__(self):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.handler_ids = list()
		for connection in (("shutdown", self.main_shutdown),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.assembly_treeview = self.builder.get_object('treeview2')
		self.assembly_treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		self.assembly_treeview.connect("drag-data-received", self.on_drag_data_received)
		self.assembly_treeview.drag_dest_set_target_list([enforce_target])

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.assembly_treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		self.assembly_treeview.connect('drag_data_get', self.on_drag_data_get)
		self.assembly_treeview.drag_source_set_target_list([dnd])
		self.product_store = self.builder.get_object('product_store')
		self.assembly_store = self.builder.get_object('assembly_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_string)
		self.assembled_product_store = self.builder.get_object('assembled_product_store')

		self.populate_stores ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
		return
		_list_ = data.get_text().split(' ')
		if len(_list_) != 2:
			return
		table, _id_ = _list_[0], _list_[1]
		c = DB.cursor()
		c.execute("SELECT product, remark, cost FROM %s WHERE id = %s" % (table, _id_))
		for row in c.fetchall():
			product = row[0]
			remark = row[1]
			price = row[2]
		c.close()
		DB.rollback()
	
	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][2]
		qty = model[path][1]
		string = str(qty) + ' ' + str(product_id) 
		data.set_text(string, -1)

	def assembled_products_button_release_event (self, treeview, event):
		if event.button == 3:
			selection = self.builder.get_object('treeview-selection1')
			model, path = selection.get_selected()
			if path == []:
				return
			self.product_hub_id = model[path][0]
			menu = self.builder.get_object('assembled_popup_menu')
			menu.popup_at_pointer()

	def products_button_release_event (self, treeview, event):
		if event.button == 3:
			selection = self.builder.get_object('treeview-selection2')
			model, path = selection.get_selected()
			if path == []:
				return
			self.product_hub_id = model[path][2]
			menu = self.builder.get_object('assembled_popup_menu')
			menu.popup_at_pointer()
		
	def export_csv_activated (self, menuitem):
		self.populate_vendor_store () 
		import csv 
		dialog = self.builder.get_object ('csv_file_dialog')
		uri = os.path.expanduser('~')
		dialog.set_current_folder_uri("file://" + uri)
		dialog.set_current_name("assembly_list.csv")
		response = dialog.run()
		dialog.hide()
		if response != Gtk.ResponseType.ACCEPT:
			return
		selected_file = dialog.get_filename()
		vendor_id = self.builder.get_object('vendor_combo').get_active_id()
		c = DB.cursor()
		with open(selected_file, 'w') as csvfile:
			exportfile = csv.writer(	csvfile, 
										delimiter=',',
										quotechar='|', 
										quoting=csv.QUOTE_MINIMAL)
			c.execute(	"SELECT "
							"pai.qty, "
							"products.name, "
							"COALESCE(vpn.vendor_sku, 'No order number'), "
							"products.manufacturer_sku, "
							"pai.remark, "
							"products.cost "
						"FROM product_assembly_items AS pai "
						"JOIN products ON pai.assembly_product_id = products.id "
						"LEFT JOIN vendor_product_numbers AS vpn "
							"ON vpn.product_id = pai.assembly_product_id "
							"AND vendor_id = %s "
						"WHERE (manufactured_product_id) = (%s) "
						"ORDER BY pai.id", 
						(vendor_id, self.manufactured_product_id))
			for row in c.fetchall():
				exportfile.writerow(row)
		c.close()
		DB.rollback()
	
	def product_hub_activated (self, menuitem):
		import product_hub
		product_hub.ProductHubGUI(self.product_hub_id)

	def product_match_selected(self, completion, model, combo_iter):
		product_id = self.product_store[combo_iter][0]
		product_name = self.product_store[combo_iter][1]
		model, path = self.builder.get_object('treeview-selection2').get_selected_rows()
		tree_iter = self.assembly_store.get_iter(path)
		self.assembly_store[tree_iter][2] = int(product_id)
		self.assembly_store[tree_iter][3] = product_name
		self.save_assembly_product_line (tree_iter)
		self.calculate_row_total (tree_iter)
		self.calculate_totals()

	def product_combo_editing_started (self, combo_renderer, combo, path):
		entry = combo.get_child()
		completion = self.builder.get_object('product_completion')
		entry.set_completion(completion)

	def product_match_string(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_vendor_store (self):
		c = DB.cursor()
		active = self.builder.get_object('vendor_combo').get_active()
		store = self.builder.get_object('vendor_store')
		store.clear()
		store.append(['0', 'No vendor'])
		c.execute("SELECT id::text, name FROM contacts "
					"WHERE vendor = True "
					"ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		if active < 0:
			self.builder.get_object('vendor_combo').set_active(0)
		c.close()
		DB.rollback()

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def focus (self, widget, event):
		self.populate_stores ()

	def populate_stores(self):
		c = DB.cursor()
		self.product_store.clear()
		self.assembled_product_store.clear()
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, purchasable, stock) = "
					"(False, True, True) ORDER BY name")
		for row in c.fetchall():
			self.product_store.append(row)
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, manufactured) = (False, True) "
					"ORDER BY name")
		for row in c.fetchall():
			self.assembled_product_store.append(row)
		c.close()
		DB.rollback()

	def products_activated (self, button):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def qty_edited(self, widget, path, text):
		self.assembly_store[path][1] = int(text) # update all values related to the price and quantity
		iter = self.assembly_store.get_iter(path)
		self.save_assembly_product_line (iter)
		self.calculate_row_total (iter)
		self.calculate_totals ()

	def remark_edited (self, widget, path, text):
		self.assembly_store[path][4] = text
		iter = self.assembly_store.get_iter(path)
		self.save_assembly_product_line (iter)

	def product_combo_changed (self, combo_renderer, path, combo_iter):
		product_id = self.product_store[combo_iter][0]
		text = self.product_store[combo_iter][1]
		tree_iter = self.assembly_store.get_iter(path)
		self.assembly_store[tree_iter][2] = int(product_id)
		self.assembly_store[tree_iter][3] = text
		self.save_assembly_product_line (tree_iter)

	def save_assembly_product_line(self, tree_iter):
		c = DB.cursor()
		if self.assembly_store[tree_iter][3] == "Select a product":
			return # no product yet
		line_id = self.assembly_store[tree_iter][0]
		qty = self.assembly_store[tree_iter][1]
		product_id = self.assembly_store[tree_iter][2]
		remark = self.assembly_store[tree_iter][4]
		c.execute("SELECT cost FROM products WHERE id = %s", ( product_id, ))
		for row in c.fetchall():
			cost = row[0]
			self.assembly_store[tree_iter][5] = cost
			self.assembly_store[tree_iter][6] = float(cost) * qty
		if line_id == 0:
			c.execute("INSERT INTO product_assembly_items "
									"(manufactured_product_id, "
									"qty, "
									"assembly_product_id, "
									"remark) "
								"VALUES (%s, %s, %s, %s) RETURNING id", 
									(self.manufactured_product_id, 
									qty, 
									product_id, 
									remark))
			self.assembly_store[tree_iter][0] = c.fetchone()[0]
		else:
			c.execute("UPDATE product_assembly_items SET "
									"(qty, "
									"assembly_product_id, "
									"remark) "
								"= (%s, %s, %s) WHERE id = %s", 
									(qty, 
									product_id, 
									remark, 
									line_id))
		DB.commit()
		c.close()
		self.calculate_totals ()

	def calculate_totals(self, widget = None):
		self.total = 0
		for item in self.assembly_store:
			self.total = self.total + item[6]
		total = '${:,.2f}'.format(self.total)
		line_items = len(self.assembly_store)
		self.builder.get_object('label4').set_label(str(line_items))
		self.builder.get_object('label5').set_label(total)

	def calculate_row_total(self, tree_iter):
		cost = float(self.assembly_store[tree_iter][5])
		qty = float(self.assembly_store[tree_iter][1])
		ext_price = cost * qty
		self.assembly_store[tree_iter][6] = round(ext_price, 2)

	def delete_entry(self):
		c = DB.cursor()
		row, path = self.builder.get_object("treeview-selection2").get_selected_rows ()
		tree_iter = row.get_iter(path)
		line_id = self.assembly_store.get_value(tree_iter, 0)
		self.assembly_store.remove(tree_iter)
		c.execute("DELETE FROM product_assembly_items "
					"WHERE id = %s", (line_id,))
		DB.commit()
		c.close()

	def add_product(self, widget):
		import products_overview
		po = products_overview.ProductsOverviewGUI()
		po.get_object('radiobutton3').set_active(True)

	def manufactured_row_activate(self, treeview, path, treeviewcolumn):
		c = DB.cursor()
		self.manufactured_product_id = self.assembled_product_store[path][0]
		product_name = self.assembled_product_store[path][1]
		self.builder.get_object('label6').set_label("'%s'" % product_name)
		self.assembly_store.clear()
		c.execute("SELECT pai.id, qty, assembly_product_id, name, "
					"remark, cost, cost*qty "
					"FROM product_assembly_items AS pai "
					"JOIN products ON products.id = "
					"pai.assembly_product_id "
					"WHERE manufactured_product_id = %s",
					(self.manufactured_product_id,))
		for row in c.fetchall():
			self.assembly_store.append(row)
		self.populating = True
		c.execute ("SELECT assembly_notes "
					"FROM products WHERE id = %s", 
					(self.manufactured_product_id,))
		for row in c.fetchall():
			self.builder.get_object('notes_buffer').set_text(row[0])
		c.close()
		DB.rollback()
		self.calculate_totals ()
		self.populating = False

	def main_shutdown (self, main):
		if self.timeout_id:
			self.save_notes()

	def notes_buffer_changed (self, textbuffer):
		if self.populating == True:
			return
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		self.notes = textbuffer.get_text(start, end, True)
		if self.timeout_id:
			GLib.source_remove(self.timeout_id)
		self.timeout_id = GLib.timeout_add_seconds(10, self.save_notes)

	def save_notes (self ):
		c = DB.cursor()
		if self.timeout_id:
			GLib.source_remove(self.timeout_id)
		c.execute("UPDATE products SET assembly_notes = %s "
					"WHERE id = %s", 
					(self.notes, self.manufactured_product_id))
		DB.commit()
		c.close()
		self.timeout_id = None
		
	def delete_item_clicked (self, button):
		self.delete_entry()

	def new_item_clicked (self, button):
		self.add_entry()

	def add_entry(self):
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(0)
		row = self.assembly_store.append([0, 1, 0, "Select a product", "", 0.00, 0.00])
		path = self.assembly_store.get_path(row)
		treeview.set_cursor(path, c, True)

	def treeview_key_release_event (self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)

	def window_key_release_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'F1':
			pass # create help file 
		elif keyname == 'F2':
			self.add_entry ()
		elif keyname == 'F3':
			self.delete_entry()

		
