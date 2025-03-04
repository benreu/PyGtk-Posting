# assembly_versions.py
#
# Copyright (C) 2021 - Reuben
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
from constants import DB, ui_directory

UI_FILE = ui_directory + "/manufacturing/assembly_versions.ui"


class AssembledVersionsGUI (Gtk.Builder):
	def __init__(self, product_id = None):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.version_store = self.get_object('version_store')
		self.assembled_product_store = self.get_object('assembled_product_store')
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.populate_assembled_products ()
		if product_id != None:
			self.get_object('product_combo').set_active_id(product_id)
		self.window = self.get_object('window')
		self.window.show_all()

	def product_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.assembled_product_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def product_match_selected (self, entrycompletion, treemodel, treeiter):
		product_id = treemodel[treeiter][0]
		self.get_object('product_combo').set_active_id(product_id)
		return True

	def populate_assembled_products (self):
		c = DB.cursor()
		self.assembled_product_store.clear()
		c.execute("SELECT id::text, name FROM products "
					"WHERE (deleted, manufactured) = (False, True) "
					"ORDER BY name")
		for row in c.fetchall():
			self.assembled_product_store.append(row)
		c.close()

	def assembly_product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id == None:
			return
		self.get_object('create_version_button').set_sensitive(True)
		self.product_id = product_id
		self.populate_versions ()

	def populate_versions (self):
		c = DB.cursor()
		self.version_store.clear()
		c.execute("SELECT "
						"id::text, "
						"version_name, "
						"date_created::text, "
						"format_date(date_created), "
						"active "
					"FROM product_assembly_versions "
					"WHERE product_id = %s ORDER BY version_name, date_created",
					(self.product_id,))
		for row in c.fetchall():
			self.version_store.append(row)
		c.close()

	def create_version_clicked (self, button):
		name = self.get_object('version_name_entry').get_text()
		c = DB.cursor()
		c.execute("INSERT INTO product_assembly_versions "
					"(product_id, version_name) VALUES (%s, %s) "
					"RETURNING id",
					(self.product_id, name))
		if self.get_object('existing_items_checkbutton').get_active() :
			new_version_id = c.fetchone()[0]
			combo = self.get_object('existing_version_combo')
			old_version_id = combo.get_active_id()
			c.execute("UPDATE product_assembly_versions SET assembly_notes = "
					"(SELECT assembly_notes FROM product_assembly_versions "
						"WHERE id = %s)"
					"WHERE id = %s; "
					"INSERT INTO product_assembly_items "
					"(qty, assembly_product_id, version_id)"
					"SELECT qty, assembly_product_id, %s "
					"FROM product_assembly_items WHERE version_id = %s",
					(old_version_id, new_version_id,
					new_version_id, old_version_id))
		DB.commit()
		c.close()
		self.populate_versions()

	def use_version_items_combo_changed (self, combobox):
		if combobox.get_active_id != None:
			self.get_object('existing_items_checkbutton').set_active(True)

	def version_name_edited (self, cellrenderertext, path, text):
		row_id = self.version_store[path][0]
		c = DB.cursor()
		c.execute("UPDATE product_assembly_versions SET "
					"version_name = %s WHERE id = %s",
					(text, row_id))
		DB.commit()
		c.close()
		self.version_store[path][1] = text

	def active_toggled (self, cellrenderertoggle, path):
		row_id = self.version_store[path][0]
		c = DB.cursor()
		c.execute("UPDATE product_assembly_versions SET "
					"active = NOT active WHERE id = %s RETURNING active",
					(row_id,))
		self.version_store[path][4] = c.fetchone()[0]
		DB.commit()
		c.close()


