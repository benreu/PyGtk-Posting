# inventory_summaries.py
# Copyright (C) 2021 reuben 
# 
# inventory_summaries is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# inventory_summaries is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
from decimal import Decimal
from pricing import product_retail_price
from db_connection import DB
from constants import ui_directory

UI_FILE = ui_directory + "/inventory/inventory_summaries.ui"


class InventorySummariesGUI(Gtk.Builder):
	def __init__(self, inventory_count = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.parent = inventory_count
		self.id = 0
		self.active = True
		self.populate_stores()
		self.window = self.get_object('window1')
		self.window.show_all()
		self.check_info_validity()
	
	def destroy (self, widget):
		if self.parent:
			self.parent.populate_stores()

	def populate_stores (self):
		c = DB.cursor()
		store = self.get_object('fiscal_store')
		store.clear()
		c.execute("SELECT id::text, name "
					"FROM fiscal_years WHERE active = True ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		combo = self.get_object('location_combo')
		selected = combo.get_active_id() # clearing the store unsets the combo
		store = self.get_object('location_store')
		store.clear()
		c.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		if selected != None:
			combo.set_active_id(selected)
		elif len(store) > 0:
			# a shop with one location can then never pick the wrong one, and this
			# combo decides the whole variance a close corrects
			combo.set_active(0)
		store = self.get_object('inventory_summaries_store')
		store.clear()
		# a summary from before location_id existed can still be NULL, and
		# ListStore.append refuses None for the gint column, so it would stop the
		# whole window populating. 0 matches no location, which leaves the combo
		# unset and the save button reading 'No location'
		c.execute("SELECT "
					"cs.id, "
					"cs.name, "
					"fy.id, "
					"fy.name, "
					"cs.active, "
					"COALESCE(cs.location_id, 0), "
					"COALESCE(l.name, '') "
					"FROM inventory.count_summaries AS cs "
					"JOIN fiscal_years AS fy ON fy.id = cs.fiscal_id "
					"LEFT JOIN locations AS l ON l.id = cs.location_id "
					"ORDER BY cs.name")
		for row in c.fetchall():
			store.append(row)
		DB.rollback()

	def treeview_row_activated (self, treeview, path, treeviewcolumn):
		store = treeview.get_model()
		self.id = store[path][0]
		name = store[path][1]
		fiscal_id = str(store[path][2])
		self.active = store[path][4]
		location_id = str(store[path][5])
		self.get_object('name_entry').set_text(name)
		self.get_object('fiscal_year_combo').set_active_id(fiscal_id)
		combo = self.get_object('location_combo')
		# set_active_id leaves the combo alone when nothing matches, so a count
		# from before location_id existed would quietly keep whatever was showing
		# and be given that location by the next save
		combo.set_active(-1)
		combo.set_active_id(location_id)
		self.check_info_validity()

	def name_entry_changed (self, editable):
		self.check_info_validity()

	def fiscal_year_changed (self, combobox):
		self.check_info_validity()

	def location_changed (self, combobox):
		self.check_info_validity()

	def check_info_validity (self):
		name = self.get_object('name_entry').get_text()
		fiscal_year = self.get_object('fiscal_year_combo').get_active_id()
		location = self.get_object('location_combo').get_active_id()
		button = self.get_object('save_button')
		button.set_sensitive(False)
		if name == '':
			button.set_label('No name')
			return
		if fiscal_year == None :
			button.set_label('No fiscal year')
			return
		if location == None:
			button.set_label('No location')
			return
		if self.active == False:
			# a closed count was corrected against the location it named, so moving
			# it afterwards would leave the stock rows pointing somewhere else
			button.set_label('Count closed')
			return
		button.set_sensitive(True)
		button.set_label('Save')

	def save_clicked (self, button):
		name = self.get_object('name_entry').get_text()
		fiscal_year = self.get_object('fiscal_year_combo').get_active_id()
		location = self.get_object('location_combo').get_active_id()
		c = DB.cursor()
		if self.id != 0:
			c.execute("UPDATE inventory.count_summaries SET "
						"(name, fiscal_id, location_id) = (%s, %s, %s) "
						"WHERE id = %s AND active",
						(name, fiscal_year, location, self.id))
		else:
			c.execute("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, location_id) VALUES (%s, %s, %s) "
						"RETURNING id",
						(name, fiscal_year, location))
			self.id = c.fetchone()[0]
		DB.commit()
		self.populate_stores()

	def new_clicked (self, button):
		self.id = 0
		self.active = True
		self.get_object('name_entry').set_text('New name')
		self.check_info_validity()





		