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
from constants import ui_directory

UI_FILE = ui_directory + "/keybindings.ui"

parent = None

no_mod = Gdk.ModifierType(0)
def populate_shortcuts (main):
	global shortcuts
	shortcuts = (
	["Main window (global)", 0, no_mod, 'present-main-window', main.present, True],
	["Product location", 0, no_mod, 'product-location', main.product_location, False],
	["Quick command", 0, no_mod, 'quick-command', main.quick_command_activate, False],
	["Invoice window", 0, no_mod, 'invoice-window', main.new_invoice, False],
	["Purchase order window", 0, no_mod, 'purchase-order-window', main.new_purchase_order, False],
	["Time clock", 0, no_mod, 'time-clock', main.time_clock, False])

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
		self.accel_group = Gtk.AccelGroup()
		for index, row in enumerate(self.store):
			string = self.settings.get_string(row[3]).split()
			if len(string) == 2:
				hotkey, global_hotkey = string
			else : # not a valid hotkey, just default to nothing
				hotkey, global_hotkey = ('', False)
			key, mod = Gtk.accelerator_parse(hotkey)
			row[1] = key
			row[2] = mod
			closure = row[4]
			if hotkey == '':
				continue # don't bind disabled hotkeys
			if global_hotkey == 'True':
				k.bind(hotkey, closure)
				row[5] = True
			else:
				self.accel_group.connect(key, mod, 0, self.accel_callback)
		parent.window.add_accel_group(self.accel_group)

	def global_toggled (self, cellrenderertoggle, path):
		if path == '0' and self.store[path][5] == True :
			return # main window is always global, or set to global if it isn't
		global_hotkey = not self.store[path][5]
		self.store[path][5] = global_hotkey
		self.save_hotkey_preference (path)

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
		if key == 32:
			self.show_message ('Space is not allowed for a keybinding!')
			return
		self.store[path][1] = key
		self.store[path][2] = mods
		self.save_hotkey_preference (path)

	def save_hotkey_preference (self, path):
		key = self.store[path][1]
		mods = self.store[path][2] 
		setting_name = self.store[path][3]
		global_hotkey = self.store[path][5]
		accelerator = Gtk.accelerator_name(key, mods)
		setting = accelerator + ' ' + str(global_hotkey)
		self.settings.set_string(setting_name, setting)

	def show_message (self, message):
		window = self.get_object('window')
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()


		