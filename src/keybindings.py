# keybindings.py
#
# Copyright (C) 2018 - reuben
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
gi.require_version('Keybinder', '3.0')
from gi.repository import Gtk, Gdk, Keybinder, Gio
import main

UI_FILE = main.ui_directory + "/keybindings.ui"

shortcuts = (
	["Product location", Gdk.ModifierType(0), 65475, 'product-location'],
	["New invoice", Gdk.ModifierType(0), 65476, 'new-invoice'],
	["Time clock", Gdk.ModifierType(0), 65477, 'time-clock'],
	["Main window", Gdk.ModifierType(0), 65478, 'present'])

class KeybinderInit (Gtk.Builder):
	def __init__ (self, main):
		k = Keybinder
		k.init()
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.settings = Gio.Settings.new("pygtk-posting.keybinding.global")
		self.store = self.get_object('keybindings_store')
		for row in shortcuts:
			self.store.append(row)
		shortcut = self.settings.get_string('present')
		key, mod = Gtk.accelerator_parse(shortcut)
		self.store[3][1] = mod
		self.store[3][2] = key
		for row in [	
						("F7", main.new_invoice), 
						("F8", main.time_clock),
						("F6", main.product_location_window)    ]:
			k.bind(row[0], row[1])

	def show_window (self):
		window = self.get_object('window')
		window.show_all()
		window.present()

	def window_delete_event (self, window, event):
		window.hide()
		return True
	
	def accel_edited(self, cellrendereraccel, path, key, mods, hwcode):
		self.store[path][1] = mods
		self.store[path][2] = key
		setting_name = self.store[path][3]
		accelerator = Gtk.accelerator_name(key, mods)
		self.settings.set_string(setting_name, accelerator)


		