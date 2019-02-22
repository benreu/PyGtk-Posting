# printing.py
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

import gi
gi.require_version('Poppler', '0.18')
from gi.repository import Gtk, GLib, Poppler
import main, os

class Setup (Gtk.PrintOperation):
	settings_file = None
	def __init__(self, parent = None, file_to_print = None, settings_file = None):

		Gtk.PrintOperation.__init__(self)
		self.set_embed_page_setup(True)
		self.connect('create-custom-widget', self.create_custom_widget, None)
		
		if settings_file:
			self.settings_file = (os.path.join
									(main.preferences_path,
									'%s_print_settings' % settings_file))
			try:
				settings = Gtk.PrintSettings.new_from_file(self.settings_file)
			except Exception as e:
				print ("Error when loading print settings file: ", str(e))
				settings = Gtk.PrintSettings()
			self.set_print_settings(settings)
		if file_to_print:
			self.set_file_to_print (file_to_print)
		if parent:
			self.parent = parent

	def set_parent (self, parent):
		self.parent = parent

	def set_file_to_print (self, file_to_print):
		file_uri = GLib.filename_to_uri(file_to_print)
		try:
			self.doc = Poppler.Document.new_from_file(file_uri)
		except Exception as e:
			self.show_error_message ('no file found at %s'% file_uri)

	def create_custom_widget (self, operation, args):
		self.set_custom_tab_label('PyGtk Posting')
		box = Gtk.Box (orientation = Gtk.Orientation.VERTICAL)
		box.set_halign (Gtk.Align.CENTER)
		button = Gtk.Button(label = "Cancel printing")
		button.set_tooltip_text("This button really doesn't do anything, it is here for reference")
		button.connect('clicked', self.button_cancel)
		box.pack_start(button, False, False, 50)
		box.show_all()
		return box

	def button_cancel (self, button = None):
		self.cancel()

	def set_bytes_to_print (self, bytes):
		self.doc = Poppler.Document.new_from_stream(bytes, -1, None, None)

	def do_begin_print(self, operation):
		self.set_n_pages(self.doc.get_n_pages())

	def do_draw_page(self, print_ctx, page_num):
		cr = print_ctx.get_cairo_context()
		page = self.doc.get_page(page_num)
		page.render(cr)

	def print_dialog (self, parent = None):
		"parent dialog to attach the dialog to"
		if parent:
			self.parent = parent
		result = self.run(Gtk.PrintOperationAction.PRINT_DIALOG,
									self.parent)
		if result == Gtk.PrintOperationResult.ERROR:
			message = self.get_error()
			self.show_error_message(message, parent)
		elif result == Gtk.PrintOperationResult.APPLY:
			settings = self.get_print_settings()
			try:
				if self.settings_file:
					settings.to_file(self.settings_file)
			except Exception as e:
				message = str(e)
				self.show_error_message(message, parent)
		return result

	def print_directly (self, parent):
		"parent dialog to attach the dialog to"
		if parent:
			self.parent = parent
		result = self.run(Gtk.PrintOperationAction.PRINT,
									self.parent)
		if result == Gtk.PrintOperationResult.ERROR:
			message = self.get_error()
			self.show_error_message(message)
		return result

	def show_error_message (self, message):
		dialog = Gtk.MessageDialog(self.parent,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()






		