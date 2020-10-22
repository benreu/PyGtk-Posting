# about_window.py
#
# Copyright (C) 2020 - Reuben Rissler
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

from gi.repository import Gtk

from constants import ui_directory

UI_FILE = ui_directory + "/about_window.ui"

class AboutWindowGUI (Gtk.Builder):
	def __init__(self, main_window):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		about_window = self.get_object('aboutdialog1')
		about_window.set_transient_for(main_window)
		about_window.add_credit_section("Special thanks", ["Eli Sauder"])
		about_window.add_credit_section("Suggestions/advice from (in no particular order)", 
													["Marvin Stauffer", 
													"Melvin Stauffer", 
													"Roy Horst", 
													"Daniel Witmer", 
													"Alvin Witmer",
													"Jonathan Groff"])
		about_window.run()
		about_window.destroy()