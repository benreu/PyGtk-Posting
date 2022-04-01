# resource_categories.py
#
# Copyright (C) 2017 - reuben
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

UI_FILE = ui_directory + "/resources/resource_categories.ui"

class ResourceCategoriesGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.category_store = self.get_object('category_store')
		self.populate_category_store()
		self.create_new_tag ()
		
		self.window = self.get_object('window1')
		self.window.show_all() 

	def destroy (self, widget):
		self.cursor.close()

	def populate_category_store (self):
		self.category_store.clear()
		self.cursor.execute("SELECT id, tag, red, green, blue, alpha, finished "
							"FROM resource_tags "
							"ORDER BY tag")
		for row in self.cursor.fetchall():
			tag_id = row[0]
			tag_name = row[1]
			red = row[2]
			green = row[3]
			blue = row[4]
			alpha = row[5]
			finished = row[6]
			rgba = Gdk.RGBA(red, green, blue, alpha)
			self.category_store.append([tag_id, tag_name, rgba, finished])
		DB.rollback()

	def save_tag_clicked (self, button):
		tag_name = self.get_object('entry2').get_text()
		rgba = self.get_object('colorbutton1').get_rgba()
		red = rgba.red
		green = rgba.green
		blue = rgba.blue
		alpha = rgba.alpha
		if self.tag_id == 0:
			self.cursor.execute ("INSERT INTO resource_tags "
								"(tag, red, green, blue, alpha, finished) VALUES "
								"(%s, %s, %s, %s, %s, False) RETURNING id", 
								(tag_name, red, green, blue, alpha))
			self.tag_id = self.cursor.fetchone()[0]
		else:
			self.cursor.execute ("UPDATE resource_tags SET "
								"(tag, red, green, blue, alpha) = "
								"(%s, %s, %s, %s, %s) WHERE id = %s", 
								(tag_name, red, green, blue, alpha, 
								self.tag_id))
		DB.commit()
		self.populate_category_store ()

	def new_tag_clicked (self, button):
		self.create_new_tag()

	def create_new_tag(self):
		rgba = Gdk.RGBA(0, 0, 0, 1)
		self.tag_id = 0 
		self.get_object('entry2').set_text('New tag')
		self.get_object('entry2').select_region(0, -1)
		self.get_object('colorbutton1').set_rgba(rgba)

	def row_activated (self, treeview, path, treeviewcolumn):
		self.tag_id = self.category_store[path][0]
		self.cursor.execute("SELECT tag, red, green, blue, alpha "
							"FROM resource_tags "
							"WHERE id = %s", (self.tag_id,))
		for row in self.cursor.fetchall():
			tag_name = row[0]
			red = row[1]
			green = row[2]
			blue = row[3]
			alpha = row[4]
			rgba = Gdk.RGBA(red, green, blue, alpha)
			self.get_object('entry2').set_text(tag_name)
			self.get_object('colorbutton1').set_rgba(rgba)
		DB.rollback()

	def finished_toggled (self, toggle_renderer, path):
		active = not toggle_renderer.get_active()
		self.category_store[path][3] = active
		row_id = self.category_store[path][0]
		self.cursor.execute("UPDATE resource_tags "
									"SET finished = %s "
									"WHERE id = %s",(active, row_id))
		DB.commit()





