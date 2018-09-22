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
import main

UI_FILE = main.ui_directory + "/admin/data_import.ui"


class DataImportUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def import_contacts_file_set (self, filechooser):
		from admin import contact_import
		filename = filechooser.get_filename()
		if filename.endswith('.xls') :
			c = contact_import.ContactsImportGUI(self.db)
			if not c.load_xls(filename):
				c.destroy()
				self.show_message (c.error)
		else:
			self.show_message ("File type not recognized")

	def import_products_file_set (self, filechooser):
		from admin import product_import
		filename = filechooser.get_filename()
		if filename.endswith('.xls') :
			p = product_import.ProductsImportGUI(self.db)
			if not p.load_xls(filename):
				p.destroy()
				self.show_message (p.error)
		else:
			self.show_message ("File type not recognized")

	def show_message (self, error):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									error)
		dialog.run()
		dialog.destroy()

	def destroy (self, window = None):
		pass

