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
import main

UI_FILE = main.ui_directory + "/keybindings.ui"

class KeybinderInit:
	def __init__ (self, main):
		#print (main, k)
		k = Keybinder
		k.init()
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.store = self.builder.get_object('keybindings_store')
		self.store.append([Gdk.ModifierType.SHIFT_MASK, 85, "New Invoice"])
		self.store.append([Gdk.ModifierType.CONTROL_MASK, 76, "Time Clock"])
		for row in [	
						("F7", main.new_invoice), 
						("F8", main.time_clock),
						("F9", main.present)     ]:
			k.bind(row[0], row[1])
		#self.builder.get_object('keybinding_dialog').show_all()
	
	def accel_edited(self, cellrendereraccel, path, key, mods, hwcode):
		accelerator = Gtk.accelerator_name(key, mods)
		self.store[path][0] = mods
		self.store[path][1] = key
		print (mods)
		#for i in dir(mods):
		#	print (i)
		#print (mods, key)


		