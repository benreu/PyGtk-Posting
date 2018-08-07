#
# data_import.py
# Copyright (C) 2016 Reuben Rissler
# 
# data_import is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# data_import is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
import xlrd
from xlrd.biffh import XLRDError

UI_FILE = "src/admin/data_import.ui"


class DataImportUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def import_contacts_file_set (self, filechooser):
		self.filename = filechooser.get_filename()
		if self.filename.endswith('.xls') :
			if self.load_xls() :
				stack = self.builder.get_object('main_stack')
				stack.set_visible_child_name('import_contacts_xls')
		else:
			self.show_message ("File type not recognized")

####### start import to treeview

	def load_xls (self):
		store = self.builder.get_object('xls_import_store')
		store.clear()
		book = xlrd.open_workbook(self.filename)
		try:
			sheet = book.sheet_by_name ('Contacts')
		except XLRDError as e:
			print (e)
			self.show_message (e)
			return False
		for i in range(sheet.nrows):
			if i == 0:
				continue # skip the header
			try:
				xls_row = sheet.row(i)
				name = xls_row[0].value
				ext_name = xls_row[1].value
				address = xls_row[2].value
				city = xls_row[3].value
				state = xls_row[4].value
				zip = xls_row[5].value
				fax = xls_row[6].value
				phone = xls_row[7].value
				email = xls_row[8].value
				misc = xls_row[9].value
				tax_number = xls_row[10].value
				customer = xls_row[11].value
				vendor = xls_row[12].value
				employee = xls_row[13].value
				service_provider = xls_row[14].value
				custom1 = xls_row[15].value
				custom2 = xls_row[16].value
				custom3 = xls_row[17].value
				custom4 = xls_row[18].value
				notes = xls_row[19].value
			except Exception as e:
				print (e)
				self.show_message (str(e) + '\n\nPlease export some data '
										'from Posting and match that format.'
										'\nHint : You are missing '
										'one or more columns')
				return False
			try:
				store.append([	name, 
								ext_name,
								address,
								city,
								state,
								zip,
								fax,
								phone,
								email,
								misc,
								tax_number,
								customer,
								vendor,
								employee,
								service_provider,
								custom1,
								custom2,
								custom3,
								custom4,
								notes    ])
			except Exception as e:
				print (e)
				self.show_message (str(e) + '\n\nPlease export some data '
										'from Posting and match that format.'
										'\nHint : You have wrong cell data-types')
				return False
		return True

####### end import to treeview

	def import_clicked (self, button):
		model = self.builder.get_object('xls_import_store')
		c = self.db.cursor()
		for row in model:
			c.execute ("INSERT INTO contacts VALUES ()")
		c.close()

	def show_message (self, error):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									error)
		dialog.run()
		dialog.destroy()

	def main_page_clicked (self, button):
		stack = self.builder.get_object('main_stack')
		stack.set_visible_child_name('main_page')
		
	def text_renderer_edited (self, text_renderer, path, new_text):
		treeview = self.builder.get_object('xls_treeview')
		path, column = treeview.get_cursor()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id()
		model[path][col_index] = new_text

	def boolean_renderer_toggled (self, toggle_renderer, path):
		treeview = self.builder.get_object('xls_treeview')
		old_path, column = treeview.get_cursor ()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id ()
		model[path][col_index] = not model[path][col_index]

	def destroy (self, window):
		pass

