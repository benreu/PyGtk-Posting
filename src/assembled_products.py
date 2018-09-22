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
import main

UI_FILE = main.ui_directory + "/assembled_products.ui"


class AssembledProductsGUI:
	def __init__(self, main):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
	
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.assembly_treeview = self.builder.get_object('treeview2')
		self.assembly_treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		self.assembly_treeview.connect("drag-data-received", self.on_drag_data_received)
		self.assembly_treeview.drag_dest_set_target_list([enforce_target])

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.assembly_treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		self.assembly_treeview.connect('drag_data_get', self.on_drag_data_get)
		self.assembly_treeview.drag_source_set_target_list([dnd])

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		
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
		self.cursor.execute("SELECT product, remark, cost FROM %s WHERE id = %s" % (table, _id_))
		for row in self.cursor.fetchall():
			product = row[0]
			remark = row[1]
			price = row[2]
	
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
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def products_button_release_event (self, treeview, event):
		if event.button == 3:
			selection = self.builder.get_object('treeview-selection2')
			model, path = selection.get_selected()
			if path == []:
				return
			self.product_hub_id = model[path][2]
			menu = self.builder.get_object('assembled_popup_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			
	def product_hub_activated (self, menuitem):
		import product_hub
		product_hub.ProductHubGUI(self.main, self.product_hub_id)

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

	def destroy(self, window):
		self.cursor.close()
		return True

	def focus (self, widget, event):
		self.populate_stores ()

	def populate_stores(self):
		self.product_store.clear()
		self.assembled_product_store.clear()
		self.cursor.execute("SELECT id::text, name FROM products "
							"WHERE (deleted, purchasable, stock) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		self.cursor.execute("SELECT id::text, name FROM products "
							"WHERE (deleted, manufactured) = (False, True) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.assembled_product_store.append(row)

	def products_clicked (self, button):
		import products
		products.ProductsGUI(self.main)

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
		if self.assembly_store[tree_iter][3] == "Select a product":
			return # no product yet
		line_id = self.assembly_store[tree_iter][0]
		qty = self.assembly_store[tree_iter][1]
		product_id = self.assembly_store[tree_iter][2]
		remark = self.assembly_store[tree_iter][4]
		self.cursor.execute("SELECT cost FROM products WHERE id = %s", ( product_id, ))
		for row in self.cursor.fetchall():
			cost = row[0]
			self.assembly_store[tree_iter][5] = cost
			self.assembly_store[tree_iter][6] = float(cost) * qty
		if line_id == 0:
			self.cursor.execute("INSERT INTO product_assembly_items "
									"(manufactured_product_id, "
									"qty, "
									"assembly_product_id, "
									"remark) "
								"VALUES (%s, %s, %s, %s) RETURNING id", 
									(self.manufactured_product_id, 
									qty, 
									product_id, 
									remark))
			self.assembly_store[tree_iter][0] = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE product_assembly_items SET "
									"(qty, "
									"assembly_product_id, "
									"remark) "
								"= (%s, %s, %s) WHERE id = %s", 
									(qty, 
									product_id, 
									remark, 
									line_id))
		self.db.commit()
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
		row, path = self.builder.get_object("treeview-selection2").get_selected_rows ()
		tree_iter = row.get_iter(path)
		line_id = self.assembly_store.get_value(tree_iter, 0)
		self.assembly_store.remove(tree_iter)
		self.cursor.execute("DELETE FROM product_assembly_items "
							"WHERE id = %s", (line_id,))
		self.db.commit()

	def add_product(self, widget):
		products.ProductsGUI(self.db, manufactured = True)

	def manufactured_row_activate(self, treeview, path, treeviewcolumn):
		self.manufactured_product_id = self.assembled_product_store[path][0]
		product_name = self.assembled_product_store[path][1]
		self.builder.get_object('label6').set_label("'%s'" % product_name)
		self.assembly_store.clear()
		self.cursor.execute("SELECT pai.id, qty, assembly_product_id, name, "
							"remark, cost, cost*qty "
							"FROM product_assembly_items AS pai "
							"JOIN products ON products.id = "
							"pai.assembly_product_id "
							"WHERE manufactured_product_id = %s",
							(self.manufactured_product_id,))
		for row in self.cursor.fetchall():
			self.assembly_store.append(row)
		self.populating = True
		self.cursor.execute ("SELECT assembly_notes "
								"FROM products WHERE id = %s", 
								(self.manufactured_product_id,))
		for row in self.cursor.fetchall():
			self.builder.get_object('notes_buffer').set_text(row[0])
		self.calculate_totals ()
		self.populating = False

	def notes_buffer_changed (self, textbuffer):
		if self.populating == True:
			return
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		notes = textbuffer.get_text(start, end, True)
		self.cursor.execute("UPDATE products SET assembly_notes = %s "
							"WHERE id = %s", 
							(notes,  self.manufactured_product_id))
		self.db.commit()
		
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

		
