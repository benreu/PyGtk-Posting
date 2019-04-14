# resource_management.py
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
import main

UI_FILE = main.ui_directory + "/resource_management_tags.ui"

class ResourceManagementTagsGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = main.db
		self.cursor = self.db.cursor()
		
		self.tag_edit_store = self.builder.get_object('tag_edit_store')
		self.populate_edit_tag_store()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all() 

	def populate_edit_tag_store (self):
		self.tag_edit_store.clear()
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
			self.tag_edit_store.append([tag_id, tag_name, rgba, finished])

	def save_tag_clicked (self, button):
		tag_name = self.builder.get_object('entry2').get_text()
		rgba = self.builder.get_object('colorbutton1').get_rgba()
		red = rgba.red
		green = rgba.green
		blue = rgba.blue
		alpha = rgba.alpha
		if self.tag_id == 0:
			self.cursor.execute ("INSERT INTO resource_tags "
								"(tag, red, green, blue, alpha, finished) VALUES "
								"(%s, %s, %s, %s, %s, False)", 
								(tag_name, red, green, blue, alpha))
		else:
			self.cursor.execute ("UPDATE resource_tags SET "
								"(tag, red, green, blue, alpha) = "
								"(%s, %s, %s, %s, %s) WHERE id = %s", 
								(tag_name, red, green, blue, alpha, 
								self.tag_id))
		self.db.commit()
		self.populate_edit_tag_store ()

	def new_tag_clicked (self, button):
		rgba = Gdk.RGBA(0, 0, 0, 1)
		self.tag_id = 0 
		self.builder.get_object('entry2').set_text('New tag')
		self.builder.get_object('colorbutton1').set_rgba(rgba)

	def row_activated (self, treeview, path, treeviewcolumn):
		self.tag_id = self.tag_edit_store[path][0]
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
			self.builder.get_object('entry2').set_text(tag_name)
			self.builder.get_object('colorbutton1').set_rgba(rgba)

	def finished_toggled (self, toggle_renderer, path):
		active = not toggle_renderer.get_active()
		self.tag_edit_store[path][3] = active
		row_id = self.tag_edit_store[path][0]
		self.cursor.execute("UPDATE resource_tags "
									"SET finished = %s "
									"WHERE id = %s",(active, row_id))
		self.db.commit()
		return
		selected_path = Gtk.TreePath(path)
		for row in self.tag_edit_store:
			#print row[2]
			if row.path == selected_path:
				row[3] = True
				self.cursor.execute("UPDATE resource_tags "
									"SET finished = True "
									"WHERE id = (%s)",[row[0]])
			else:
				row[3] = False
				self.cursor.execute("UPDATE resource_tags "
									"SET finished = False "
									"WHERE id = %s",[row[0]])



		


		
