# traceback_handler.py
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

from gi.repository import Gtk, GLib
import main, sys, logging, traceback

UI_FILE = main.ui_directory + "/traceback_handler.ui"

class Log :
	def __init__(self, log_file):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.logger = logging.getLogger("PyGtk Posting")
		c_handler = logging.StreamHandler()
		c_handler.setLevel(logging.WARNING)
		c_format = logging.Formatter('%(message)s')
		self.logger.addHandler(c_handler)
		if log_file != None:
			f_handler = logging.FileHandler(log_file)
			f_handler.setLevel(logging.DEBUG)
			f_format = logging.Formatter('%(message)s')
			self.logger.addHandler(f_handler)
		sys.excepthook = self.exception_handler

	def exception_handler (self, type_, value, tb):
		"Catch uncaught exceptions and show them with Glib's idle_add since"
		"we cannot access widgets directly without Gtk knowing what is going on"
		GLib.idle_add(self.show_traceback, type_, value, tb)
	
	def show_traceback (self, type_, value, tb):
		buf = self.builder.get_object('traceback_buffer')
		for text in traceback.format_exception(type_, value, tb):
			buf.insert(buf.get_end_iter(), text)
			self.logger.error(text.strip("\n"))
		window = self.builder.get_object('traceback_window')
		window.show_all()
		window.present()

	def clear_and_close_clicked (self, window):
		"the window object is passed from the button clicked event"
		self.builder.get_object('traceback_buffer').set_text('')
		window.hide()

	def close_clicked (self, window):
		"the window object is passed from the button clicked event"
		window.hide()

	def window_delete_event (self, window, event):
		window.hide()
		return True

		