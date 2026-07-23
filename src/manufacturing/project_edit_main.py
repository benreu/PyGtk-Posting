# project_edit_main.py
#
# Copyright (C) 2020 - reuben
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
from db_connection import DB, broadcaster
from constants import ui_directory, MANUFACTURING_PROJECT_LOCK_CLASSID

UI_FILE = ui_directory + "/manufacturing/project_edit_main.ui"


class ProjectEditGUI(Gtk.Builder):
	project_lock_acquired = False
	def __init__(self, parent_class, project_id = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.product_store = self.get_object('product_store')
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.version_store = self.get_object('version_store')
		version_completion = self.get_object('version_completion')
		version_completion.set_match_func(self.version_match_func)
		self.parts_needed_store = self.get_object('parts_needed_store')
		self.part_product_store = self.get_object('part_product_store')
		alt_product_completion = self.get_object('alt_product_completion')
		alt_product_completion.set_match_func(self.alt_product_match_func)
		self.populate_part_product_store()
		self.vendor_choice_store = self.get_object('vendor_choice_store')
		vendor_completion = self.get_object('vendor_completion')
		vendor_completion.set_match_func(self.vendor_match_func)
		self.populate_vendor_choice_store()
		self.parent_class = parent_class
		self.project_id = project_id
		self.populate_stores ()
		self.product_id = None
		self.version_id = None
		self.window = self.get_object('window')
		self.window.show_all()
		if project_id != None:
			self.load_project()
	
	def widget_focus_in_event (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)
	
	def populate_stores(self):
		cursor = DB.cursor()
		self.product_store.clear()
		cursor.execute("SELECT id::text, name FROM products "
							"WHERE (manufactured, deleted) = "
							"(True, False) ORDER BY name")
		for row in cursor.fetchall():
			self.product_store.append(row)
		cursor.close()

	def product_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def product_match_selected(self, completion, model, iter_):
		self.product_id = model[iter_][0]
		self.get_object('product_combo').set_active_id(self.product_id)
		return True

	def product_combo_changed(self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			c = DB.cursor()
			self.product_id = product_id
			self.get_object('version_combo').set_active(-1)
			self.version_store.clear()
			c = DB.cursor()
			c.execute("SELECT id::text, version_name "
						"FROM product_assembly_versions "
						"WHERE product_id = %s AND (active = True OR id = %s)",
						(self.product_id, self.version_id))
			for row in c.fetchall():
				self.version_store.append(row)
			c.close()

	def version_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.version_store[iter_][1].lower():
				return False
		return True

	def version_match_selected(self, completion, model, iter_):
		version_id = model[iter_][0]
		self.get_object('version_combo').set_active_id(version_id)
		return True

	def version_combo_changed (self, combo):
		version_id = combo.get_active_id()
		if version_id != None:
			self.version_id = version_id
			self.generate_project_description ()

	def qty_spinbutton_changed (self, spinbutton):
		if not self.product_id or not self.version_id:
			return
		self.generate_project_description ()

	def generate_project_description (self):
		qty = self.get_object('units_spinbutton').get_value_as_int()
		cursor = DB.cursor()
		cursor.execute("SELECT name FROM products "
							"WHERE id = %s", (self.product_id,))
		for row in cursor.fetchall():
			p_name = row[0]
		manufacturing_name_string = "Manufacturing : %s [%s]" % (p_name, qty)
		self.get_object('description_entry').set_text(manufacturing_name_string)
		cursor.close()
		self.get_object('save_button').set_sensitive(True)

	def load_project (self):
		cursor = DB.cursor()
		cursor.execute("SELECT pg_try_advisory_lock(%s, %s)",
					(MANUFACTURING_PROJECT_LOCK_CLASSID, self.project_id))
		locked = cursor.fetchone()[0]
		if not locked:
			DB.rollback()
			cursor.close()
			error = "Somebody else is editing this project"
			self.show_message (error)
			self.window.destroy()
			return False
		self.project_lock_acquired = True
		cursor.execute("SELECT product_id::text, "
						"qty, "
						"name, "
						"batch_notes, "
						"version_id::text "
						"FROM manufacturing_projects WHERE id = %s",
						(self.project_id, ))
		for row in cursor.fetchall():
			self.version_id = row[4]
			self.get_object('product_combo').set_active_id(row[0])
			self.get_object('units_spinbutton').set_value(row[1])
			self.get_object('description_entry').set_text(row[2])
			self.get_object('batch_notes_buffer').set_text(row[3])
			self.get_object('version_combo').set_active_id(row[4])
		self.get_object('product_combo').set_sensitive(False)
		self.get_object('create_project_button').set_label("Update project")
		cursor.close()
		self.populate_parts_needed_store()

	def destroy (self, window):
		if self.project_lock_acquired:
			cursor = DB.cursor()
			cursor.execute("SELECT pg_advisory_unlock(%s, %s)",
						(MANUFACTURING_PROJECT_LOCK_CLASSID, self.project_id))
			cursor.close()
			self.project_lock_acquired = False
		DB.rollback()
		
	def focus_out_event (self, widget, event):
		self.window.set_urgency_hint(True)
		
	def focus_in_event (self, widget, event):
		self.window.set_urgency_hint(False)

	def insert_project_row (self, product_id, name, qty, notes):
		c = DB.cursor()
		time_clock_id = self.get_time_clock_id (name)
		c.execute("INSERT INTO manufacturing_projects "
					"(product_id, name, qty, time_clock_projects_id, "
					"batch_notes, active, version_id) VALUES "
					"(%s, %s, %s, %s, %s, True, %s) "
					"RETURNING id",
					(product_id, name, qty, time_clock_id,
					notes, self.version_id))
		self.project_id = c.fetchone()[0]
		c.close()

	def update_project_row (self, name, qty, notes):
		c = DB.cursor()
		c.execute("UPDATE manufacturing_projects SET "
					"(name, qty, batch_notes, version_id) = "
					"(%s, %s, %s, %s) WHERE id = %s "
					"RETURNING time_clock_projects_id",
					(name, qty, notes, self.version_id, self.project_id))
		active = self.get_object('time_clock_checkbutton').get_active()
		for row in c.fetchall():
			time_clock_projects_id = row[0]
			c.execute("UPDATE time_clock_projects "
						"SET (name, active, stop_date) = "
						"(%s, %s, CURRENT_DATE) "
						"WHERE id = %s",
						(name, active, time_clock_projects_id))
		c.close()

	def get_project_fields (self):
		product_id = self.get_object('product_combo').get_active_id()
		name = self.get_object('description_entry').get_text()
		qty = self.get_object('units_spinbutton').get_value()
		buf = self.get_object('batch_notes_buffer')
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		notes = buf.get_text(start_iter, end_iter, True)
		return product_id, name, qty, notes

	def create_or_update_project_clicked (self, button):
		product_id, name, qty, notes = self.get_project_fields()
		if self.project_id == None:
			if not self.product_id or not self.version_id:
				self.show_message("Select a product and version first.")
				return
			self.insert_project_row(product_id, name, qty, notes)
			c = DB.cursor()
			c.execute("SELECT pg_try_advisory_lock(%s, %s)",
						(MANUFACTURING_PROJECT_LOCK_CLASSID, self.project_id))
			self.project_lock_acquired = c.fetchone()[0]
			c.close()
			self.get_object('product_combo').set_sensitive(False)
			button.set_label("Update project")
			self.sync_manufacturing_items(self.project_id, self.version_id, qty)
		else:
			self.update_project_row(name, qty, notes)
		DB.commit()
		self.populate_parts_needed_store()
		self.parent_class.populate_projects()

	def save_clicked (self, button):
		product_id, name, qty, notes = self.get_project_fields()
		if self.project_id == None:
			self.insert_project_row(product_id, name, qty, notes)
			self.sync_manufacturing_items(self.project_id, self.version_id, qty)
		else:
			self.update_project_row(name, qty, notes)
		c = DB.cursor()
		if self.project_lock_acquired:
			c.execute("SELECT pg_advisory_unlock(%s, %s)",
						(MANUFACTURING_PROJECT_LOCK_CLASSID, self.project_id))
			self.project_lock_acquired = False
		DB.commit()
		c.close()
		self.window.destroy ()
		self.parent_class.populate_projects()

	def get_time_clock_id (self, project_name):
		if self.get_object('time_clock_checkbutton').get_active() == False:
			return None
		cursor = DB.cursor()
		cursor.execute("INSERT INTO time_clock_projects "
						"(name, start_date, active, permanent) "
						"VALUES (%s, CURRENT_DATE, True, False) "
						"RETURNING id", 
						(project_name, ))
		time_clock_projects_id = cursor.fetchone()[0]
		cursor.close()
		return time_clock_projects_id

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

	def populate_part_product_store (self):
		c = DB.cursor()
		self.part_product_store.clear()
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, stock) = (False, True) "
					"ORDER BY name")
		for row in c.fetchall():
			self.part_product_store.append(row)
		c.close()
		DB.rollback()

	def populate_vendor_choice_store (self):
		c = DB.cursor()
		self.vendor_choice_store.clear()
		c.execute("SELECT id::text, name FROM contacts "
					"WHERE vendor = True ORDER BY name")
		for row in c.fetchall():
			self.vendor_choice_store.append(row)
		c.close()
		DB.rollback()

	def alt_product_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.part_product_store[tree_iter][1].lower():
				return False
		return True

	def vendor_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.vendor_choice_store[tree_iter][1].lower():
				return False
		return True

	def get_on_hand_qty (self, product_id):
		c = DB.cursor()
		c.execute("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
					"FROM inventory_transactions WHERE product_id = %s",
					(product_id,))
		on_hand = c.fetchone()[0]
		c.close()
		DB.rollback()
		return on_hand

	def get_vendor_sku (self, vendor_id, product_id):
		c = DB.cursor()
		c.execute("SELECT vendor_sku FROM vendor_product_numbers "
					"WHERE (vendor_id, product_id) = (%s, %s) "
					"AND deleted = False", (vendor_id, product_id))
		row = c.fetchone()
		c.close()
		DB.rollback()
		return row[0] if row else ''

	def sync_manufacturing_items (self, project_id, version_id, project_qty):
		# Keeps manufacturing_items in step with the product's current BOM
		# (product_assembly_items), which may have been edited after this
		# project was created. Rows are matched on default_product_id (the
		# original BOM component) rather than product_id, so an alternate
		# part or vendor already chosen for a still-needed component is left
		# untouched; only components added to or removed from the BOM change
		# the row set.
		c = DB.cursor()
		params = {'project_id': project_id, 'project_qty': project_qty,
					'version_id': version_id}
		c.execute("INSERT INTO manufacturing_items "
					"(manufacturing_project_id, qty, product_id, "
					"default_product_id, remark, cost, ext_cost, from_bom) "
					"SELECT %(project_id)s, "
					"CEIL(pai.qty * %(project_qty)s)::smallint, "
					"pai.assembly_product_id, "
					"pai.assembly_product_id, "
					"pai.remark, "
					"p.cost, "
					"p.cost * CEIL(pai.qty * %(project_qty)s), "
					"True "
					"FROM product_assembly_items AS pai "
					"JOIN products AS p ON p.id = pai.assembly_product_id "
					"WHERE pai.version_id = %(version_id)s "
					"ON CONFLICT (manufacturing_project_id, default_product_id) "
					"WHERE deleted = False DO UPDATE SET "
					"qty = EXCLUDED.qty, remark = EXCLUDED.remark, "
					"cost = EXCLUDED.cost, ext_cost = EXCLUDED.ext_cost, "
					"from_bom = True",
					params)
		# never touch manually-added rows (from_bom = False) here -- only
		# BOM-derived rows are added/updated/soft-deleted by this sync
		c.execute("UPDATE manufacturing_items SET deleted = True "
					"WHERE manufacturing_project_id = %(project_id)s "
					"AND deleted = False "
					"AND from_bom = True "
					"AND default_product_id NOT IN ("
					"SELECT assembly_product_id FROM product_assembly_items "
					"WHERE version_id = %(version_id)s)",
					params)
		c.close()

	def reset_manufacturing_items_from_bom (self, project_id, version_id, project_qty):
		# used by "Reload from BOM": wipes the whole list (including manually
		# added parts and substitutions) and rebuilds it fresh from the BOM
		c = DB.cursor()
		c.execute("UPDATE manufacturing_items SET deleted = True "
					"WHERE manufacturing_project_id = %s AND deleted = False",
					(project_id,))
		c.close()
		self.sync_manufacturing_items(project_id, version_id, project_qty)

	def populate_parts_needed_store (self):
		self.parts_needed_store.clear()
		c = DB.cursor()
		c.execute("SELECT mi.id, mi.qty, mi.product_id, p.name, "
					"mi.default_product_id, "
					"COALESCE((SELECT SUM(qty_in - qty_out) "
					"FROM inventory_transactions "
					"WHERE product_id = mi.product_id), 0) AS on_hand, "
					"COALESCE(mi.vendor_id, 0), "
					"COALESCE(v.name, 'Select a vendor'), "
					"mi.purchase_order_item_id IS NOT NULL, "
					"COALESCE(vpn.vendor_sku, '') "
					"FROM manufacturing_items AS mi "
					"JOIN products AS p ON p.id = mi.product_id "
					"LEFT JOIN contacts AS v ON v.id = mi.vendor_id "
					"LEFT JOIN vendor_product_numbers AS vpn "
					"ON (vpn.vendor_id, vpn.product_id) = "
					"(mi.vendor_id, mi.product_id) AND vpn.deleted = False "
					"WHERE mi.manufacturing_project_id = %s "
					"AND mi.deleted = False "
					"ORDER BY mi.id", (self.project_id,))
		for row in c.fetchall():
			needed, on_hand = row[1], row[5]
			order_qty = max(needed - on_hand, 0)
			status = "Added" if row[8] else ""
			self.parts_needed_store.append([row[0], row[1], row[2], row[3],
							row[4], on_hand, row[6], row[7],
							order_qty, status, row[9]])
		c.close()
		DB.rollback()

	def alt_product_combo_editing_started (self, combo_renderer, combo, path):
		entry = combo.get_child()
		entry.set_completion(self.get_object('alt_product_completion'))

	def apply_part_selection (self, tree_iter, product_id, product_name):
		product_id = int(product_id)
		item_id = self.parts_needed_store[tree_iter][0]
		vendor_id = self.parts_needed_store[tree_iter][6]
		qty_needed = self.parts_needed_store[tree_iter][1]
		c = DB.cursor()
		if item_id == 0:
			c.execute("SELECT id FROM manufacturing_items WHERE "
						"manufacturing_project_id = %s AND "
						"default_product_id = %s AND deleted = False",
						(self.project_id, product_id))
			existing = c.fetchone()
			if existing:
				self.show_message("%s is already in the parts needed list."
									% product_name)
				c.close()
				DB.rollback()
				self.parts_needed_store.remove(tree_iter)
				return
			c.execute("SELECT cost FROM products WHERE id = %s",
						(product_id,))
			cost = c.fetchone()[0]
			c.execute("INSERT INTO manufacturing_items "
						"(manufacturing_project_id, qty, product_id, "
						"default_product_id, remark, cost, ext_cost, "
						"from_bom) VALUES "
						"(%s, %s, %s, %s, '', %s, %s, False) "
						"RETURNING id",
						(self.project_id, qty_needed, product_id, product_id,
						cost, cost * qty_needed))
			item_id = c.fetchone()[0]
			self.parts_needed_store[tree_iter][0] = item_id
			self.parts_needed_store[tree_iter][4] = product_id
		else:
			c.execute("UPDATE manufacturing_items SET product_id = %s "
						"WHERE id = %s", (product_id, item_id))
		self.parts_needed_store[tree_iter][2] = product_id
		self.parts_needed_store[tree_iter][3] = product_name
		DB.commit()
		c.close()
		on_hand = self.get_on_hand_qty(product_id)
		self.parts_needed_store[tree_iter][5] = on_hand
		self.parts_needed_store[tree_iter][8] = max(
			self.parts_needed_store[tree_iter][1] - on_hand, 0)
		if vendor_id != 0:
			self.parts_needed_store[tree_iter][10] = self.get_vendor_sku(
									vendor_id, product_id)
		else:
			self.parts_needed_store[tree_iter][10] = ''

	def alt_product_combo_changed (self, combo_renderer, path, combo_iter):
		product_id = self.part_product_store[combo_iter][0]
		product_name = self.part_product_store[combo_iter][1]
		tree_iter = self.parts_needed_store.get_iter(path)
		self.apply_part_selection(tree_iter, product_id, product_name)

	def alt_product_match_selected (self, completion, model, combo_iter):
		product_id = model[combo_iter][0]
		product_name = model[combo_iter][1]
		selection = self.get_object('parts_needed_treeview_selection')
		store, paths = selection.get_selected_rows()
		tree_iter = self.parts_needed_store.get_iter(paths[0])
		self.apply_part_selection(tree_iter, product_id, product_name)
		return True

	def vendor_combo_editing_started (self, combo_renderer, combo, path):
		entry = combo.get_child()
		entry.set_completion(self.get_object('vendor_completion'))

	def apply_vendor_selection (self, tree_iter, vendor_id, vendor_name):
		vendor_id = int(vendor_id)
		item_id = self.parts_needed_store[tree_iter][0]
		product_id = self.parts_needed_store[tree_iter][2]
		self.parts_needed_store[tree_iter][6] = vendor_id
		self.parts_needed_store[tree_iter][7] = vendor_name
		c = DB.cursor()
		c.execute("UPDATE manufacturing_items SET vendor_id = %s "
					"WHERE id = %s", (vendor_id, item_id))
		DB.commit()
		c.close()
		self.parts_needed_store[tree_iter][10] = self.get_vendor_sku(
								vendor_id, product_id)

	def vendor_combo_changed (self, combo_renderer, path, combo_iter):
		vendor_id = self.vendor_choice_store[combo_iter][0]
		vendor_name = self.vendor_choice_store[combo_iter][1]
		tree_iter = self.parts_needed_store.get_iter(path)
		self.apply_vendor_selection(tree_iter, vendor_id, vendor_name)

	def vendor_match_selected (self, completion, model, combo_iter):
		vendor_id = model[combo_iter][0]
		vendor_name = model[combo_iter][1]
		selection = self.get_object('parts_needed_treeview_selection')
		store, paths = selection.get_selected_rows()
		tree_iter = self.parts_needed_store.get_iter(paths[0])
		self.apply_vendor_selection(tree_iter, vendor_id, vendor_name)
		return True

	def order_qty_edited (self, widget, path, text):
		try:
			value = int(text)
		except ValueError:
			return
		self.parts_needed_store[path][8] = max(value, 0)

	def order_number_edited (self, widget, path, text):
		tree_iter = self.parts_needed_store.get_iter(path)
		vendor_id = self.parts_needed_store[tree_iter][6]
		product_id = self.parts_needed_store[tree_iter][2]
		if vendor_id == 0:
			self.show_message("Select a vendor for this part first.")
			return
		self.parts_needed_store[tree_iter][10] = text
		c = DB.cursor()
		c.execute("INSERT INTO vendor_product_numbers "
					"(vendor_sku, vendor_id, product_id) "
					"VALUES (%s, %s, %s) "
					"ON CONFLICT (vendor_id, product_id) "
					"DO UPDATE SET vendor_sku = EXCLUDED.vendor_sku",
					(text, vendor_id, product_id))
		DB.commit()
		c.close()

	def parts_needed_treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('parts_needed_menu')
			menu.popup_at_pointer()

	def product_hub_clicked (self, menuitem):
		selection = self.get_object('parts_needed_treeview_selection')
		model, paths = selection.get_selected_rows()
		if not paths:
			return
		import product_hub
		for path in paths:
			product_hub.ProductHubGUI(model[path][2])

	def view_po_clicked (self, menuitem):
		selection = self.get_object('parts_needed_treeview_selection')
		model, paths = selection.get_selected_rows()
		if not paths:
			return
		import purchase_order_window
		c = DB.cursor()
		for path in paths:
			item_id = model[path][0]
			c.execute("SELECT poi.purchase_order_id "
						"FROM manufacturing_items AS mi "
						"JOIN purchase_order_items AS poi "
						"ON poi.id = mi.purchase_order_item_id "
						"WHERE mi.id = %s", (item_id,))
			row = c.fetchone()
			if row is None:
				self.show_message("This part has not been added to a PO yet.")
				continue
			purchase_order_window.PurchaseOrderGUI(row[0])
		c.close()
		DB.rollback()

	def delete_part_clicked (self, menuitem):
		selection = self.get_object('parts_needed_treeview_selection')
		model, paths = selection.get_selected_rows()
		if not paths:
			return
		tree_iters = [model.get_iter(path) for path in paths]
		c = DB.cursor()
		for tree_iter in tree_iters:
			item_id = model[tree_iter][0]
			if item_id != 0:
				c.execute("UPDATE manufacturing_items SET deleted = True "
							"WHERE id = %s", (item_id,))
			model.remove(tree_iter)
		DB.commit()
		c.close()

	def confirm_update_po_item (self, product_name, existing_qty, new_qty):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.QUESTION,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup("%s is already on this vendor's purchase order "
							"(qty %s).\nUpdate the existing line to qty %s "
							"instead of adding a new one?"
							% (product_name, existing_qty, new_qty))
		response = dialog.run()
		dialog.destroy()
		return response == Gtk.ResponseType.YES

	def add_to_po_clicked (self, button):
		selection = self.get_object('parts_needed_treeview_selection')
		model, paths = selection.get_selected_rows()
		if not paths:
			return
		import purchase_order_window
		for path in paths:
			tree_iter = model.get_iter(path)
			item_id = model[tree_iter][0]
			product_id = model[tree_iter][2]
			product_name = model[tree_iter][3]
			vendor_id = model[tree_iter][6]
			order_qty = model[tree_iter][8]
			if vendor_id == 0:
				self.show_message("Select a vendor for this part first.")
				continue
			if order_qty <= 0:
				continue
			po_id = purchase_order_window.find_or_create_open_po(vendor_id)
			existing = purchase_order_window.find_po_item(po_id, product_id)
			if existing:
				po_item_id, existing_qty = existing
				new_qty = existing_qty + order_qty
				if not self.confirm_update_po_item(product_name,
													existing_qty, new_qty):
					continue
				purchase_order_window.update_po_item_qty(po_item_id, new_qty)
			else:
				po_item_id = purchase_order_window.add_manufacturing_item_to_po(
								po_id, product_id, order_qty)
			c = DB.cursor()
			c.execute("UPDATE manufacturing_items "
						"SET purchase_order_item_id = %s WHERE id = %s",
						(po_item_id, item_id))
			DB.commit()
			c.close()
			model[tree_iter][9] = "Added"

	def sync_from_bom_clicked (self, button):
		if self.project_id == None:
			self.show_message("Create the project first.")
			return
		qty = self.get_object('units_spinbutton').get_value()
		self.sync_manufacturing_items(self.project_id, self.version_id, qty)
		DB.commit()
		self.populate_parts_needed_store()

	def reload_from_bom_activated (self, button):
		if self.project_id == None:
			self.show_message("Create the project first.")
			return
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.WARNING,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup("This will discard the entire parts needed list "
							"-- including manually added parts, "
							"substitutions, and vendor selections -- and "
							"rebuild it from scratch using the product's "
							"current bill of materials.\n\n"
							"This cannot be undone. Continue?")
		response = dialog.run()
		dialog.destroy()
		if response != Gtk.ResponseType.YES:
			return
		qty = self.get_object('units_spinbutton').get_value()
		self.reset_manufacturing_items_from_bom(self.project_id,
												self.version_id, qty)
		DB.commit()
		self.populate_parts_needed_store()

	def add_part_clicked (self, button):
		if self.project_id == None:
			self.show_message("Create the project first.")
			return
		treeview = self.get_object('parts_needed_treeview')
		column = treeview.get_column(0)
		row = self.parts_needed_store.append([0, 1, 0, "Select a product", 0,
							0, 0, "Select a vendor", 1, "", ""])
		path = self.parts_needed_store.get_path(row)
		treeview.set_cursor(path, column, True)

	def add_part_barcode_entry_key_released (self, entry, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname != 'Return' and keyname != 'KP_Enter':
			return
		text = entry.get_text().strip()
		if text == "":
			return
		if self.project_id == None:
			self.show_message("Create the project first.")
			return
		c = DB.cursor()
		c.execute("SELECT id, name FROM products WHERE barcode = %s",
					(text,))
		row = c.fetchone()
		if row is None:
			c.execute("SELECT p.id, p.name FROM vendor_product_numbers AS vpn "
						"JOIN products AS p ON p.id = vpn.product_id "
						"WHERE (vpn.vendor_sku = %s OR vpn.vendor_barcode = %s) "
						"AND vpn.deleted = False LIMIT 1", (text, text))
			row = c.fetchone()
		c.close()
		DB.rollback()
		if row is None:
			self.show_message("No product found for '%s'." % text)
			return
		product_id, product_name = row
		entry.select_region(0, -1)
		for existing_row in self.parts_needed_store:
			if existing_row[2] == product_id:
				self.set_needed_qty(existing_row.iter, existing_row[1] + 1)
				return
		tree_row = self.parts_needed_store.append([0, 1, 0,
							"Select a product", 0, 0, 0,
							"Select a vendor", 1, "", ""])
		self.apply_part_selection(tree_row, product_id, product_name)

	def set_needed_qty (self, tree_iter, qty):
		item_id = self.parts_needed_store[tree_iter][0]
		if item_id == 0:
			return
		self.parts_needed_store[tree_iter][1] = qty
		c = DB.cursor()
		c.execute("UPDATE manufacturing_items SET qty = %s, "
					"ext_cost = cost * %s WHERE id = %s",
					(qty, qty, item_id))
		DB.commit()
		c.close()
		on_hand = self.parts_needed_store[tree_iter][5]
		self.parts_needed_store[tree_iter][8] = max(qty - on_hand, 0)

	def needed_qty_edited (self, widget, path, text):
		try:
			qty = int(text)
		except ValueError:
			return
		if qty <= 0:
			return
		tree_iter = self.parts_needed_store.get_iter(path)
		self.set_needed_qty(tree_iter, qty)


