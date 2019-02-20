# export_to_xls.py
#
# Copyright (C) 2019 - reuben
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
import xlsxwriter, subprocess
import main

UI_FILE = main.ui_directory + "/reports/export_to_xls.ui"

class ExportToXlsGUI (Gtk.Builder):
	def __init__(self, parent_window, treeview):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.treeview = treeview

		file_dialog = self.get_object("file_dialog")
		file_dialog.set_transient_for(parent_window)
		response = file_dialog.run()
		if response == Gtk.ResponseType.ACCEPT:
			self.filename = file_dialog.get_filename()
			if not self.filename.endswith('.xls'):
				self.filename = self.filename + '.xls'
			self.save_to_xls ()
		file_dialog.hide()

	def save_to_xls (self):
		book = xlsxwriter.Workbook(self.filename)
		sheet = book.add_worksheet("Report")
		index = 0
		columns = list()
		for column in self.treeview.get_columns():
			if column.get_visible():
				title = column.get_title()
				sheet.write(0, index, title)
				cell_area = column.get_area()
				renderer = cell_area.get_cells()[0]
				columns.append(cell_area.attribute_get_column(renderer, "text"))
				index += 1
		sheet.freeze_panes (1, True) # frozen headings instead of split panes
		progressbar = self.get_object('progressbar')
		model = self.treeview.get_model()
		rows = float(len(model))
		# we need some fancy stuff to get only visible columns in the model
		for rowx, row in enumerate(model):
			rowx += 1 # we already have a row
			for colx, column in enumerate (columns):
				sheet.write(rowx, colx, row[column])
			progressbar.set_fraction(float(rowx)/rows)
			while Gtk.events_pending():
				Gtk.main_iteration()
		progressbar.set_fraction(1.00)
		book.close()
		subprocess.Popen(['soffice', self.filename])



