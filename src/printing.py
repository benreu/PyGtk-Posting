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

class PrintDialog:
	def __init__(self, file_to_print):
		file_uri = GLib.filename_to_uri(file_to_print)
		self.operation = Gtk.PrintOperation()

		self.operation.connect('begin-print', self.begin_print, None)
		self.operation.connect('draw-page', self.draw_page, None)

		self.doc = Poppler.Document.new_from_file(file_uri)

	def begin_print(self, operation, print_ctx, print_data):
		operation.set_n_pages(self.doc.get_n_pages())

	def draw_page(self, operation, print_ctx, page_num, print_data):
		cr = print_ctx.get_cairo_context()
		page = self.doc.get_page(page_num)
		page.render(cr)

	def run_print_dialog(self, parent):
		"parent dialog to attach the dialog to"
		result = self.operation.run(Gtk.PrintOperationAction.PRINT_DIALOG,
									parent)
		if result == Gtk.PrintOperationResult.ERROR:
			message = self.operation.get_error()
			dialog = Gtk.MessageDialog(parent,
										0,
										Gtk.MessageType.ERROR,
										Gtk.ButtonsType.CLOSE,
										message)
			dialog.run()
			dialog.destroy()
		return result

	def print_direct(self, parent):
		"parent dialog to attach the dialog to"
		result = self.operation.run(Gtk.PrintOperationAction.PRINT,
									parent)
		if result == Gtk.PrintOperationResult.ERROR:
			message = self.operation.get_error()
			dialog = Gtk.MessageDialog(parent,
										0,
										Gtk.MessageType.ERROR,
										Gtk.ButtonsType.CLOSE,
										message)
			dialog.run()
			dialog.destroy()
		return result






		