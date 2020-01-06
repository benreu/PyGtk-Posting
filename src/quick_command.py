# quick_command.py
#
# Copyright (C) 2019 - Reuben
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
from gi.repository import Gtk, Gdk, GObject
from constants import ui_directory

UI_FILE = ui_directory + "/quick_command.ui"

class QuickCommand(Gtk.Builder):
	command_text = ''
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.store = self.get_object('quick_command_store')
		self.connect_signals(self)
		self.filtered_store = self.get_object('quick_command_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.sorted_store = self.get_object('quick_command_sort')
		self.sorted_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

	def show_all (self):
		window = self.get_object('quick_command_window')
		window.show_all()
		window.present()
		self.get_object('search_entry').grab_focus()

	def treeview_row_activated (self, treeview, treepath, treeviewcolumn):
		self.get_object('quick_command_window').hide()
		item = self.sorted_store[treepath][2]
		item.activate()
		
	def filter_text_changed (self, entry):
		self.command_text = entry.get_text().lower()
		self.filtered_store.refilter()

	def filter_func(self, model, tree_iter, r):
		if self.command_text not in model[tree_iter][0].lower():
			return False
		return True

	def delete (self, window, event):
		window.hide()
		return True

	def window_keypress_event (self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'Escape':
			window.hide()


