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
from db_connection import DB, broadcaster
from constants import ui_directory, PRODUCT_LOCK_CLASSID
import user_manual
import calculator
from pricing import MarkupPriceGrid

UI_FILE = ui_directory + "/manufacturing/assembled_products.ui"


class AssembledProductsGUI:
	timeout_id = None
	manufactured_product_id = None
	version_id = None
	total = 0.00
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
		self.assembled_product_store = self.builder.get_object('assembled_product_store')
		self.version_store = self.builder.get_object('version_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		version_completion = self.builder.get_object('version_completion')
		version_completion.set_match_func(self.version_match_func)
		assembled_completion = self.builder.get_object('assembled_product_completion')
		assembled_completion.set_match_func(self.assembled_product_match_func)
		for column_id, store_column in (('treeviewcolumn5', 5),
										('treeviewcolumn6', 6),
										('retail_column', 7),
										('ext_retail_column', 8)):
			column = self.builder.get_object(column_id)
			column.set_cell_data_func(column.get_cells()[0],
										self.money_cell_func, store_column)
		self.update_cost_spin = self.builder.get_object('update_cost_spin')
		self.markup_prices = MarkupPriceGrid(
									self.builder.get_object('markup_price_grid'),
									self.update_cost_spin)

		self.populate_stores ()

		self.window = self.builder.get_object('window1')
		user_manual.bind_f1(self.window, "assembled_products")
		user_manual.bind_f1(self.builder.get_object('duplicate_product_window'),
							"assembled_products")
		user_manual.bind_f1(self.builder.get_object('cost_update_dialog'),
							"assembled_products")
		self.window.show_all()

	def money_cell_func (self, column, renderer, model, tree_iter, store_column):
		renderer.set_property('text',
							'{:,.2f}'.format(model[tree_iter][store_column]))

	def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
		list_ = data.get_text().split(' ')
		if len(list_) != 2:
			raise Exception("invalid drag data received")
			return
		qty, product_id = list_[0], list_[1]
		self.window.present()
		c = DB.cursor()
		c.execute("SELECT name, cost FROM products WHERE id = %s", 
																(product_id,))
		for row in c.fetchall():
			name = row[0]
			price = row[1]
			#save_assembly_product_line fills in the extension and retail
			iter_ = self.assembly_store.append([0, int(qty), int(product_id),
												name, "", price, 0.00,
												0.00, 0.00])
			self.save_assembly_product_line(iter_)
			path = self.assembly_store.get_path(iter_)
			column = self.assembly_treeview.get_column(0)
			self.assembly_treeview.set_cursor(path, column, True)
		c.close()
		DB.rollback()
	
	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][2]
		qty = model[path][1]
		string = str(qty) + ' ' + str(product_id) 
		data.set_text(string, -1)

	def assembled_products_button_release_event (self, treeview, event): #FIXME
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
							"p.name, "
							"COALESCE(vpn.vendor_sku, 'No order number'), "
							"p.manufacturer_sku, "
							"pai.remark, "
							"p.cost "
						"FROM product_assembly_items AS pai "
						"JOIN product_assembly_versions AS pav "
							"ON pai.version_id = pav.id "
						"JOIN products AS p ON pai.assembly_product_id = p.id "
						"LEFT JOIN vendor_product_numbers AS vpn "
							"ON vpn.product_id = pai.assembly_product_id "
							"AND vendor_id = %s "
						"WHERE pav.id = %s "
						"ORDER BY pai.id", 
						(vendor_id, self.version_id))
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
		self.set_assembly_product (tree_iter, product_id, product_name)

	def product_combo_editing_started (self, combo_renderer, combo, path):
		entry = combo.get_child()
		completion = self.builder.get_object('product_completion')
		entry.set_completion(completion)

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def version_clicked (self, button):
		from manufacturing import assembly_versions
		assembly_versions.AssembledVersionsGUI (self.manufactured_product_id)

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
		self.save_notes()

	def focus (self, widget, event):
		self.populate_stores ()
		self.show_assembled_product_prices () # may have been changed elsewhere

	def populate_stores(self):
		c = DB.cursor()
		self.product_store.clear()
		self.assembled_product_store.clear()
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, stock) = "
					"(False, True) ORDER BY name")
		for row in c.fetchall():
			self.product_store.append(row)
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, manufactured) = (False, True) "
					"ORDER BY name")
		for row in c.fetchall():
			self.assembled_product_store.append(row)
		c.close()
		DB.rollback()

	def help_clicked (self, menuitem):
		user_manual.show("assembled_products", self.window)

	def products_activated (self, button):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def qty_edited(self, widget, path, text):
		try:
			qty = calculator.whole(text) # a sum like 2x12 is its result
		except ValueError:
			return
		self.assembly_store[path][1] = qty # update all values related to the price and quantity
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
		product_name = self.product_store[combo_iter][1]
		tree_iter = self.assembly_store.get_iter(path)
		self.set_assembly_product (tree_iter, product_id, product_name)

	def set_assembly_product (self, tree_iter, product_id, product_name):
		product_id = int(product_id)
		if self.check_for_duplicate_product (product_id, tree_iter):
			self.duplicate_product_id = product_id
			self.duplicate_product_name = product_name
			self.duplicate_product_new_iter = tree_iter
			return
		self.assembly_store[tree_iter][2] = product_id
		self.assembly_store[tree_iter][3] = product_name
		self.save_assembly_product_line (tree_iter)
		self.calculate_row_total (tree_iter)
		self.calculate_totals()

	def check_for_duplicate_product (self, product_id, tree_iter):
		path = self.assembly_store.get_path(tree_iter)
		for row in self.assembly_store:
			if row.path == path:
				continue # continue with the rest of the liststore
			if product_id == row[2]: # the liststore has duplicates
				self.builder.get_object('duplicate_product_label').set_label(
							"This part (" + row[3] + ") is already on this BOM.\n"
							"Do you want to update the quantity to ")
				qty_spinbutton = self.builder.get_object('duplicate_qty_spinbutton')
				qty_spinbutton.set_value(int(row[1]))
				self.duplicate_product_primary_row = row
				window = self.builder.get_object('duplicate_product_window')
				window.show_all()
				return True
		return False

	def cancel_product_cell_editing (self):
		# neither cancel nor update-qty touch the row that's still being
		# edited in the treeview, so the combo cell is left in editing mode
		# unless we cancel it explicitly (add-again exits editing as a side
		# effect of writing into that same row)
		area = self.builder.get_object('treeviewcolumn3').get_area()
		area.stop_editing(True)

	def duplicate_product_cancel_clicked (self, button):
		self.cancel_product_cell_editing ()
		self.builder.get_object('duplicate_product_window').hide()

	def duplicate_product_update_qty_clicked (self, button):
		qty_spinbutton = self.builder.get_object('duplicate_qty_spinbutton')
		qty = qty_spinbutton.get_value_as_int()
		self.duplicate_product_primary_row[1] = qty
		primary_iter = self.assembly_store.get_iter(self.duplicate_product_primary_row.path)
		self.calculate_row_total (primary_iter)
		self.save_assembly_product_line (primary_iter)
		self.calculate_totals()
		self.cancel_product_cell_editing ()
		self.builder.get_object('duplicate_product_window').hide()

	def duplicate_product_add_again_clicked (self, button):
		tree_iter = self.duplicate_product_new_iter
		self.assembly_store[tree_iter][2] = self.duplicate_product_id
		self.assembly_store[tree_iter][3] = self.duplicate_product_name
		self.save_assembly_product_line (tree_iter)
		self.calculate_row_total (tree_iter)
		self.calculate_totals()
		self.builder.get_object('duplicate_product_window').hide()

	def save_assembly_product_line(self, tree_iter):
		c = DB.cursor()
		if self.assembly_store[tree_iter][3] == "Select a product":
			return # no product yet
		line_id = self.assembly_store[tree_iter][0]
		qty = self.assembly_store[tree_iter][1]
		product_id = self.assembly_store[tree_iter][2]
		remark = self.assembly_store[tree_iter][4]
		c.execute("SELECT cost, COALESCE(product_retail_price(id), 0.00) "
					"FROM products WHERE id = %s", ( product_id, ))
		for cost, retail in c.fetchall():
			self.assembly_store[tree_iter][5] = cost
			self.assembly_store[tree_iter][6] = float(cost) * qty
			self.assembly_store[tree_iter][7] = retail
			self.assembly_store[tree_iter][8] = float(retail) * qty
		if line_id == 0:
			c.execute("INSERT INTO product_assembly_items "
									"(manufactured_product_id, "
									"qty, "
									"assembly_product_id, "
									"remark, "
									"version_id) "
								"VALUES (%s, %s, %s, %s, %s) RETURNING id", 
									(self.manufactured_product_id, 
									qty, 
									product_id, 
									remark,
									self.version_id))
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
		retail_total = 0
		for item in self.assembly_store:
			self.total = self.total + item[6]
			retail_total += item[8]
		total = '${:,.2f}'.format(self.total)
		line_items = len(self.assembly_store)
		self.builder.get_object('label4').set_label(str(line_items))
		self.builder.get_object('label5').set_label(total)
		self.builder.get_object('parts_retail_label').set_label(
										'${:,.2f}'.format(retail_total))

	def calculate_row_total(self, tree_iter):
		cost = float(self.assembly_store[tree_iter][5])
		qty = float(self.assembly_store[tree_iter][1])
		ext_price = cost * qty
		self.assembly_store[tree_iter][6] = round(ext_price, 2)
		retail = float(self.assembly_store[tree_iter][7])
		self.assembly_store[tree_iter][8] = round(retail * qty, 2)

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

############## assembled product selection

	def assembled_product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id == None:
			return
		self.save_notes()
		self.manufactured_product_id = product_id
		self.populate_versions ()

	def assembled_product_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.assembled_product_store[tree_iter][1].lower():
				return False
		return True

	def assembled_completion_match_selected (self, completion, model, t_iter):
		self.save_notes()
		self.manufactured_product_id = model[t_iter][0]
		self.populate_versions ()

############## version selection

	def populate_versions (self):
		self.save_notes()
		self.builder.get_object('version_combobox').set_active(-1)
		self.assembly_store.clear()
		self.calculate_totals ()
		#the parts list it would price is gone until a version is chosen
		self.builder.get_object('update_prices_button').set_sensitive(False)
		self.version_store.clear()
		c = DB.cursor()
		c.execute("SELECT id::text, version_name "
					"FROM product_assembly_versions "
					"WHERE product_id = %s AND active = True "
					"ORDER BY version_name, date_created",
					(self.manufactured_product_id,))
		for row in c.fetchall():
			self.version_store.append(row)
		c.close()
		self.builder.get_object('version_button').set_sensitive(True)
		self.show_assembled_product_prices ()

	def show_assembled_product_prices (self):
		'''the assembled product's own saved cost and retail price, beside what
		its parts add up to'''
		if self.manufactured_product_id is None:
			return
		c = DB.cursor()
		c.execute("SELECT cost, product_retail_price(id) "
					"FROM products WHERE id = %s",
					(self.manufactured_product_id,))
		for cost, retail in c.fetchall():
			self.builder.get_object('product_cost_label').set_label(
											'${:,.2f}'.format(cost))
			if retail is None: # no standard markup level to price it at
				retail = 'N/A'
			else:
				retail = '${:,.2f}'.format(retail)
			self.builder.get_object('product_retail_label').set_label(retail)
		c.close()
		DB.rollback()

	def update_prices_clicked (self, button):
		'''Set the assembled product's cost from this version's parts, and its
		price at every markup level. The cost starts at the parts total, priced
		at the parts' costs now, and can be changed to cover labor. Each level
		keeps the markup % its saved price makes on the old cost, so the prices
		move with the cost, the same as a purchase order's cost update.'''
		c = DB.cursor()
		c.execute("SELECT p.id, p.name, p.cost, pav.version_name, "
						"(SELECT COALESCE(SUM(part.cost * pai.qty), 0.00) "
						"FROM product_assembly_items AS pai "
						"JOIN products AS part "
							"ON part.id = pai.assembly_product_id "
						"WHERE pai.version_id = pav.id) "
					"FROM product_assembly_versions AS pav "
					"JOIN products AS p ON p.id = pav.product_id "
					"WHERE pav.id = %s", (self.version_id,))
		product_id, name, cost, version_name, parts_total = c.fetchone()
		#the same lock the product edit window holds while a product is open,
		#so another workstation's edit window does not save over this
		c.execute("SELECT pg_try_advisory_lock(%s, %s)",
					(PRODUCT_LOCK_CLASSID, product_id))
		if c.fetchone()[0] == False:
			c.close()
			DB.rollback()
			self.show_message("Somebody else is editing %s, so its cost and "
								"prices cannot be changed now." % name)
			return
		DB.rollback() # a session lock, it outlives the transaction
		try:
			self.builder.get_object('update_product_label').set_label(
							"Current cost of {} is ${:,.2f}".format(name, cost))
			self.builder.get_object('update_parts_total_label').set_label(
							"Parts total for {} is ${:,.2f}".format(
												version_name, parts_total))
			#the saved prices are read against the cost they were set on, and
			#moving to the new cost then carries each level's markup % along
			self.update_cost_spin.set_value(float(cost))
			self.markup_prices.load(product_id)
			self.update_cost_spin.set_value(float(parts_total))
			dialog = self.builder.get_object('cost_update_dialog')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				self.update_cost_spin.update() # a value still being typed
				c.execute("UPDATE products SET cost = %s WHERE id = %s",
							(self.update_cost_spin.get_value(), product_id))
				self.markup_prices.save(c, product_id)
				DB.commit()
		finally:
			DB.rollback()
			c.execute("SELECT pg_advisory_unlock(%s, %s)",
						(PRODUCT_LOCK_CLASSID, product_id))
			c.close()
			DB.rollback()
		self.show_assembled_product_prices()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (GLib.markup_escape_text(message))
		dialog.run()
		dialog.destroy()

	def version_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.version_store[tree_iter][1].lower():
				return False
		return True

	def version_combo_changed (self, combobox):
		version_id = combobox.get_active_id()
		if version_id != None:
			self.version_id = version_id
			self.populate_product_assembly_store()

	def version_completion_match_selected (self, completion, model, t_iter):
		self.version_id = model[t_iter][0]
		self.populate_product_assembly_store()

############## assembly store

	def populate_product_assembly_store (self):
		c = DB.cursor()
		self.assembly_store.clear()
		c.execute("SELECT pai.id, qty, assembly_product_id, name, "
					"remark, cost, cost*qty, retail, retail*qty "
					"FROM product_assembly_items AS pai "
					"JOIN products ON products.id = "
					"pai.assembly_product_id "
					"CROSS JOIN LATERAL (SELECT COALESCE("
						"product_retail_price(products.id), 0.00) AS retail"
					") AS r "
					"WHERE version_id = %s",
					(self.version_id,))
		for row in c.fetchall():
			self.assembly_store.append(row)
		self.builder.get_object('update_prices_button').set_sensitive(True)
		self.populating = True
		c.execute ("SELECT assembly_notes "
					"FROM product_assembly_versions WHERE id = %s", 
					(self.version_id,))
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
		if not self.timeout_id:
			return
		GLib.source_remove(self.timeout_id)
		c = DB.cursor()
		c.execute("UPDATE product_assembly_versions SET assembly_notes = %s "
					"WHERE id = %s", 
					(self.notes, self.version_id))
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
		row = self.assembly_store.append([0, 1, 0, "Select a product", "",
											0.00, 0.00, 0.00, 0.00])
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
		if keyname == 'F2':
			self.add_entry ()
		elif keyname == 'F3':
			self.delete_entry()

		
