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
from gi.repository import Gtk, Gdk, Keybinder
from constants import ui_directory
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/keybindings.ui"


class KeybinderInit (Gtk.Builder):
	def __init__ (self, main):
		self.k = Keybinder
		self.k.init()
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.store = self.get_object('keybindings_store')
		self.sqlite_conn = get_apsw_connection() 

	def add_menu_keybinding (self, menu_path, menu_item):
		cursor = self.sqlite_conn.cursor()
		cursor.execute("SELECT keybinding FROM keybindings "
						"WHERE widget_id = ?", (menu_path,))
		for row in cursor.fetchall():
			keybinding = row[0]
			key, modifier = Gtk.accelerator_parse(keybinding)
			self.k.bind(keybinding, self.callback, menu_item)
			break
		else:
			key, modifier = Gtk.accelerator_parse('')
		self.store.append([menu_path, key, modifier, menu_item])

	def callback (self, keybinder, menu_item):
		menu_item.activate()

	def accel_callback(self, accel_group, window, key, mod):
		for row in self.store:
			if row[1] == key and row[2] == mod:
				closure = row[4]
				closure()
				break

	def show_window (self):
		window = self.get_object('window')
		window.show_all()
		window.present()

	def window_delete_event (self, window, event):
		window.hide()
		return True
	
	def accel_cleared (self, cellrendereraccel, path):
		sqlite_conn = get_apsw_connection() 
		cursor = sqlite_conn.cursor()
		key, modifier = Gtk.accelerator_parse('')
		menu_path = self.store[path][0]
		self.store[path][1] = key
		self.store[path][2] = modifier
		cursor.execute ("DELETE FROM keybindings "
						"WHERE widget_id = ?", (menu_path,))
		sqlite_conn.close()

	def accel_edited(self, cellrendereraccel, path, key, modifiers, hwcode):
		if key not in range(65470, 65482) and modifiers == Gdk.ModifierType(0):
			self.show_message ('Please use a modifier key!')
			return
		self.store[path][1] = key
		self.store[path][2] = modifiers
		self.save_hotkey_preference (path)

	def save_hotkey_preference (self, path):
		sqlite_conn = get_apsw_connection() 
		cursor = sqlite_conn.cursor()
		menu_path = self.store[path][0]
		key = self.store[path][1]
		modifiers = self.store[path][2] 
		accelerator = Gtk.accelerator_name(key, modifiers)
		cursor.execute("REPLACE INTO keybindings (keybinding, widget_id) "
						"VALUES (?, ?) ", (accelerator, menu_path))
		sqlite_conn.close()

	def show_message (self, message):
		window = self.get_object('window')
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()


		