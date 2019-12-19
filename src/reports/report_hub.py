# report_hub.py
#
# Copyright (C) 2019 - Reuben Rissler
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

from gi.repository import Gtk
from constants import ui_directory

UI_FILE = ui_directory + "/reports/report_hub.ui"

class ReportHubGUI (Gtk.Builder):
	border_width = 25
	def __init__(self, treeview):

		Gtk.Builder.__init__ (self)
		self.add_from_file (UI_FILE)
		self.connect_signals(self)
		if treeview.get_allocated_width() > 742:
			self.get_object("error_label").set_no_show_all(False)
		self.window = self.get_object("window")
		self.window.show_all()
		self.treeview = treeview
		self.calculate_pdf_layout()

	def pdf_export_clicked (self, button):
		border_width = self.get_object('border_spinbutton').get_value_as_int()
		font_desc = self.get_object('font_chooser').get_font()
		from reports import export_to_pdf
		etp = export_to_pdf.ExportToPdfGUI(self.treeview)
		etp.border_width = border_width
		etp.font_desc = font_desc
		etp.generate_pdf()
		self.window.destroy()

	def border_spinbutton_changed (self, spinbutton):
		self.border_width = spinbutton.get_value_as_int()
		self.calculate_pdf_layout ()

	def calculate_pdf_layout(self):
		pdf_width = self.treeview.get_allocated_width() + self.border_width
		if pdf_width > 792:
			self.get_object("error_label").set_visible(True)
			self.get_object("layout_label").set_label("Landscape")
		elif pdf_width > 612: # greater than 8.5 inches
			self.get_object("error_label").set_visible(False)
			self.get_object("layout_label").set_label("Landscape")
		else: # less than 8.5 inches
			self.get_object("error_label").set_visible(False)
			self.get_object("layout_label").set_label("Portrait")

	def xls_export_clicked (self, button):
		from reports import export_to_xls
		export_to_xls.ExportToXlsGUI(self.window, self.treeview)
		self.window.destroy()

	def cancel_clicked (self, button):
		self.window.destroy()



