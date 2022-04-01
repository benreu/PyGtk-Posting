# resource_types.py
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


from gi.repository import Gtk, GLib, Gdk
from datetime import datetime, date
from constants import ui_directory, DB

UI_FILE = ui_directory + "/resources/resource_types.ui"

class ResourceTypesGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.type_edit_store = self.get_object('type_edit_store')
		self.populate_edit_type_store()
		self.create_new_type ()
		
		self.window = self.get_object('window1')
		self.window.show_all() 

	def destroy (self, widget):
		self.cursor.close()

	def populate_edit_type_store (self):
		self.type_edit_store.clear()
		self.cursor.execute("SELECT id, name "
							"FROM resource_types "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.type_edit_store.append(row)
		DB.rollback()

	def save_type_clicked (self, button):
		type_name = self.get_object('entry2').get_text()
		if self.type_id == 0:
			self.cursor.execute ("INSERT INTO resource_types "
								"(name) VALUES (%s) RETURNING id", 
								(type_name,))
			self.type_id = self.cursor.fetchone()[0]
		else:
			self.cursor.execute ("UPDATE resource_types SET "
								"name = %s WHERE id = %s", 
								(type_name, self.type_id))
		DB.commit()
		self.populate_edit_type_store ()

	def new_type_clicked (self, button):
		self.create_new_type()

	def create_new_type(self):
		self.type_id = 0 
		self.get_object('entry2').set_text('New type')
		self.get_object('entry2').select_region(0, -1)

	def row_activated (self, treeview, path, treeviewcolumn):
		self.type_id = self.type_edit_store[path][0]
		self.cursor.execute("SELECT name "
							"FROM resource_types "
							"WHERE id = %s", (self.type_id,))
		for row in self.cursor.fetchall():
			type_name = row[0]
			self.get_object('entry2').set_text(type_name)
		DB.rollback()


