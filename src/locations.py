# locations.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GdkPixbuf, Gdk
import os, sys
import main

UI_FILE = main.ui_directory + "/locations.ui"

class LocationsGUI:
	def __init__(self, db):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.location_store = self.builder.get_object('location_store')
		self.location_treeview_populate ()
		
		window = self.builder.get_object('window1')
		
		window.show_all()

	def location_treeview_populate (self):
		self.location_store.clear()
		self.cursor.execute("SELECT id, name FROM locations ORDER BY 2")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			self.location_store.append([location_id, location_name])

	def location_treeview_activated(self, treeview, path, treeviewcolumn):
		self.location_id = self.location_store[path][0]
		self.cursor.execute("SELECT name FROM locations WHERE id = %s", (self.location_id,))
		for row in self.cursor.fetchall():
			location_name = row[0]
		self.builder.get_object('entry1').set_text(location_name)

	def new_clicked(self, button):
		self.location_id = 0
		self.builder.get_object('entry1').set_text('New location')

	def save_clicked(self, button):
		location_name = self.builder.get_object('entry1').get_text()
		if self.location_id == 0:
			self.cursor.execute("INSERT INTO locations (name) VALUES (%s)", (location_name,))
		else:
			self.cursor.execute("UPDATE locations SET name = %s WHERE id = %s", (location_name, self.location_id))
		self.db.commit()
		self.location_treeview_populate ()

	def delete_clicked (self, button):
		model, path = self.builder.get_object('treeview-selection2').get_selected_rows()
		if path != []:
			location_id = model[path][0]
			self.cursor.execute("UPDATE locations SET deleted = True WHERE id = %s", (location_id,))
			self.db.commit()
			self.location_treeview_populate ()
			



		
