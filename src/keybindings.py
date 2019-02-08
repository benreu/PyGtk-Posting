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

parent = None

no_mod = Gdk.ModifierType(0)
def populate_shortcuts (main):
	global shortcuts
	shortcuts = (
	["Main window (global)", 0, no_mod, 'present-main-window', main],
	["Product location", 0, no_mod, 'product-location', main.product_location],
	["Invoice window", 0, no_mod, 'invoice-window', main.new_invoice],
	["Purchase order window", 0, no_mod, 'purchase-order-window', main.new_purchase_order],
	["Time clock", 0, no_mod, 'time-clock', main.time_clock])

class KeybinderInit (Gtk.Builder):
	def __init__ (self, main):
		k = Keybinder
		k.init()
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.settings = Gio.Settings.new("pygtk-posting.keybinding")
		self.store = self.get_object('keybindings_store')
		for row in shortcuts:
			self.store.append(row)
		shortcut = self.settings.get_string('present-main-window')
		key, mod = Gtk.accelerator_parse(shortcut)
		self.store[0][1] = key
		self.store[0][2] = mod
		k.bind(shortcut, main.present)
		self.accel_group = Gtk.AccelGroup()
		for index, row in enumerate(self.store):
			if index == 0:
				continue
			shortcut = self.settings.get_string(row[3])
			key, mod = Gtk.accelerator_parse(shortcut)
			row[1] = key
			row[2] = mod
			self.accel_group.connect(key, mod, 0, self.accel_callback)
		parent.window.add_accel_group(self.accel_group)

	def accel_callback(self, accel_group, window, key, mod):
		for row in self.store:
			if row[1] == key and row[2] == mod:
				closure = row[4]
				closure()

	def show_window (self):
		window = self.get_object('window')
		window.show_all()
		window.present()

	def window_delete_event (self, window, event):
		window.hide()
		return True
	
	def accel_edited(self, cellrendereraccel, path, key, mods, hwcode):
		self.store[path][1] = key
		self.store[path][2] = mods
		print (key)
		#return
		setting_name = self.store[path][3]
		accelerator = Gtk.accelerator_name(key, mods)
		self.settings.set_string(setting_name, accelerator)


		