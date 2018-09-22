# kit_products.py
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

from gi.repository import Gtk, GdkPixbuf, Gdk, GLib
import os, sys
import main

UI_FILE = main.ui_directory + "/kit_products.ui"


class KitProductsGUI:
	def __init__(self, parent):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
	
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.assembly_treeview = self.builder.get_object('treeview2')
		self.assembly_treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		#self.assembly_treeview.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
		self.assembly_treeview.connect("drag-data-received", self.on_drag_data_received)		
		self.assembly_treeview.drag_dest_set_target_list([enforce_target])
		#self.assembly_treeview.drag_dest_set_target_list(None)
		#self.assembly_treeview.drag_dest_add_text_targets()
		
		self.db = parent.db
		self.cursor = self.db.cursor()
		
		self.product_store = self.builder.get_object('product_store')
		self.assembly_store = self.builder.get_object('assembly_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_string)
		self.manufactured_product_store = self.builder.get_object('manufactured_product_store')

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
			#self.assembly_store.append([None,1, product, remark, price,1,1,""])

	def product_match_selected(self, completion, model, iter_):
		product_id = self.product_store[iter_][0]
		product_name = self.product_store[iter_][1]
		model, path = self.builder.get_object('treeview-selection2').get_selected_rows()
		self.assembly_store[path][2] = int(product_id)
		self.assembly_store[path][3] = product_name
		self.cursor.execute("SELECT cost FROM products WHERE id = %s", ( product_id, ))
		cost = self.cursor.fetchone()[0]
		self.assembly_store[path][5] = cost
		line = self.assembly_store[path]
		self.save_assembly_product_line (line)
		self.calculate_row_total (line)
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
		self.manufactured_product_store.clear()
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, purchasable, stock) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			self.product_store.append([str(product_id), product_name])
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, kit) = (False, True) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			_id_ = row[0]
			name = row[1]
			self.manufactured_product_store.append([str(_id_), name])

	def products_clicked (self, button):
		import products
		products.ProductsGUI(self.db)	

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		#qty = '{:,.1f}'.format(model.get_value(iter1, 2))
		#cellrenderer.set_property("text" , qty)
		pass

	def qty_edited(self, widget, path, text):		
		self.assembly_store[path][1] = int(text) # update all values related to the price and quantity
		line = self.assembly_store[path]
		self.save_assembly_product_line (line)
		self.calculate_row_total (line)
		self.calculate_totals ()
		
	def qty_edit_canceled(self, cellrenderer):
		qty = int(self.qty_renderer_value)
		self.assembly_store[self.path][self.cell_renderer_position] = qty
		line = self.assembly_store[self.path]
		self.calculate_row_total (line)
		self.calculate_totals ()

	def qty_edit_start(self, cell_renderer,editable, r):
		self.cell_renderer_position = 1
		self.qty_renderer_value = editable.get_chars(0, -1)
		editable.connect("changed", self.set_sticky_qty)# hook up a signal to remember the text even if we don't 
		#save it still saves the text to the last edited cell
		store, self.path = self.builder.get_object("treeview-selection2").get_selected_rows ()

	def set_sticky_qty(self, widget):
		self.qty_renderer_value = widget.get_chars(0, -1)
		
	def remark_edit_canceled(self, cellrenderer): 
		self.assembly_store[self.path][self.cell_renderer_position] = self.edited_renderer_text
		line = self.assembly_store[self.path]
		self.save_assembly_product_line (line)

	def remark_edit_start(self,cell_renderer,editable, r):
		self.cell_renderer_position = 4
		self.edited_renderer_text = editable.get_chars(0, -1) #always update the current text, in case we 
		#cancel editing in a new cell and we have old values from not saving the previous cell: tough isn't it?
		editable.connect("changed", self.set_sticky_text)# hook up a signal to remember the text even if we don't 
		#save it still saves the text to the last edited cell			
		store, self.path = self.builder.get_object("treeview-selection2").get_selected_rows ()

	def remark_edited (self, widget, path, text):
		self.assembly_store[path][4] = text
		line = self.assembly_store[path]
		self.save_assembly_product_line (line)

	def set_sticky_text(self, widget):
		self.edited_renderer_text = widget.get_chars(0, -1)

	def product_combo_changed (self, combo_renderer, path, iter_):
		product_id = self.product_store[iter_][0]
		text = self.product_store[iter_][1]
		self.assembly_store[path][2] = int(product_id)
		self.assembly_store[path][3] = text
		line = self.assembly_store[path]
		self.save_assembly_product_line (line)

	def save_assembly_product_line(self, line):
		if line[3] == "Select a product":
			return # no product yet
		line_id = line[0]
		qty = line[1]
		product_id = line[2]
		remark = line[4]
		self.cursor.execute("SELECT cost FROM products WHERE id = %s", ( product_id, ))
		for row in self.cursor.fetchall():
			cost = row[0]
			line[5] = cost
			line[6] = float(cost) * qty
		if line_id == 0:
			self.cursor.execute("INSERT INTO product_assembly_items (manufactured_product_id, qty, assembly_product_id, remark) VALUES (%s, %s, %s, %s) RETURNING id", (self.manufactured_product_id, qty, product_id, remark))
			line[0] = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE product_assembly_items SET (qty, assembly_product_id, remark) = (%s, %s, %s) WHERE id = %s", ( qty, product_id, remark, line_id))
		self.db.commit()
		self.calculate_totals ()
		
	def remark_edited(self, widget, path, text): 
		self.assembly_store[path][4] = text
		line = self.assembly_store[path]
		self.save_assembly_product_line (line)

	def calculate_totals(self, widget = None):
		self.total = 0
		for item in self.assembly_store:
			self.total = self.total + item[6]
		total = '${:,.2f}'.format(self.total)
		line_items = len(self.assembly_store)
		self.builder.get_object('label4').set_label(str(line_items))
		self.builder.get_object('label5').set_label(total)

	def calculate_row_total(self, line):
		cost = float(line[5])
		qty = float(line[1])
		ext_price = cost * qty
		line[6] = round(ext_price, 2)

	def delete_entry(self, widget):
		row, path = self.builder.get_object("treeview-selection2").get_selected_rows ()
		tree_iter = row.get_iter(path)
		line_id = self.assembly_store.get_value(tree_iter, 0)
		self.assembly_store.remove(tree_iter)
		self.cursor.execute("DELETE FROM product_assembly_items WHERE id = %s", (line_id,))
		self.db.commit()

	def add_product(self, widget):
		products.ProductsGUI(self.db, manufactured = True)

	def manufactured_row_activate(self, treeview, path, treeviewcolumn):
		self.manufactured_product_id = self.manufactured_product_store[path][0]
		product_name = self.manufactured_product_store[path][1]
		self.builder.get_object('label6').set_label("'%s'" % product_name)
		self.assembly_store.clear()
		self.cursor.execute("SELECT pai.id, qty, assembly_product_id, name, "
							"cost, remark "
							"FROM product_assembly_items AS pai "
							"JOIN products ON products.id = "
							"pai.assembly_product_id "
							"WHERE manufactured_product_id = %s",
							(self.manufactured_product_id,))
		for row in self.cursor.fetchall():
			line_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			cost = row[4]
			remark = row[5]
			ext_cost = cost * qty
			self.assembly_store.append([line_id, int(qty), product_id, product_name, remark, cost, ext_cost])
		self.calculate_totals ()

	def add_entry(self, widget):
		self.assembly_store.append([0, 1, 0, "Select a product", "", 0.00, 0.00])



		
