# view_log.py
#
# Copyright (C) 2016 - reuben
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

from gi.repository import Gtk, GObject
import log_utils

UI_FILE = "src/view_log.ui"

parent = None
builder = None

#for some odd reason, self (instance) variables get lost
#therefore we use file variables

class ViewLogGUI:
	def __init__(self, p):

		global parent
		global builder
		parent = p
		builder = Gtk.Builder()
		builder.add_from_file(UI_FILE)
		builder.connect_signals(self)
		
		self.window = builder.get_object('window1')
		self.window.show_all()


	def focus (self, window, event):
		l = parent.log_file
		if l == None:
			log_exception = ("Log file '%s' was not found. \n"
								"Hint: are you starting PyGtk Posting "
								"with the run.sh?" % l)
			builder.get_object("textbuffer1").set_text(log_exception)
			return
		f = open (l, 'r')
		log_text = f.read()
		builder.get_object("textbuffer1").set_text(log_text)










		
