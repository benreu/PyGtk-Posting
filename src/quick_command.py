# quick_command.py
#
# Copyright (C) 2019 - house
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

import gi
from gi.repository import Gtk
import main

UI_FILE = main.ui_directory + "/quick_command.ui"

class QuickCommandGUI(Gtk.Builder):
	def __init__(self, menu):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.quick_command_store = self.get_object('quick_command_store')
		self.connect_signals(self)
		self.populate_menu_shortcuts(menu)

	def show_all (self):
		window = self.get_object('quick_command_window')
		window.show_all()

	def populate_menu_shortcuts (self, menu):
		for child in menu.get_children():
			self.populate_child_menu_shortcuts(child)

	def populate_child_menu_shortcuts (self, parent):
		if parent.get_sensitive() and parent.get_submenu() != None:
			for child in parent.get_submenu():
				if type(child) == gi.overrides.Gtk.MenuItem:
					submenus = child.get_submenu()
					if submenus:
						self.populate_child_menu_shortcuts(child)
					else:
						label = child.get_label()
						self.quick_command_store.append([label, child.activate])
				elif type(child) == gi.repository.Gtk.ImageMenuItem:
					label = child.get_label()
					self.quick_command_store.append([label, child.activate])




