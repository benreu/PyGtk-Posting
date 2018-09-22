# data_export.py
#
# Copyright (C) 2016 Reuben Rissler
# 
# data_export is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# data_export is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
import xlrd, xlsxwriter, subprocess
import main

UI_FILE = main.ui_directory + "/admin/data_export.ui"


class DataExportUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db

		window = self.builder.get_object('window1')
		window.show_all()

	def contacts_page_clicked (self, button):
		stack = self.builder.get_object('main_stack')
		stack.set_visible_child_name('export_contacts_page')
		self.populate_contacts ()

	def product_page_clicked (self, button):
		stack = self.builder.get_object('main_stack')
		stack.set_visible_child_name('export_products_page')
		self.populate_products ()

	def populate_contacts (self):
		store = self.builder.get_object('contact_export_store')
		store.clear()
		c = self.db.cursor ()
		c.execute ("SELECT "
							"name, "
							"ext_name, "
							"address, "
							"city, "
							"state, "
							"zip, "
							"fax, "
							"phone, "
							"email, "
							"label, "
							"tax_number, "
							"customer, "
							"vendor, "
							"employee, "
							"service_provider, "
							"custom1, "
							"custom2, "
							"custom3, "
							"custom4, "
							"notes "
					"FROM contacts WHERE deleted = False")
		for row in c.fetchall():
			store.append(row)
		c.close()

	def populate_products (self):
		store = self.builder.get_object('product_export_store')
		store.clear()
		c = self.db.cursor ()
		c.execute ("SELECT "
							"name, "
							"ext_name, "
							"description, "
							"barcode, "
							"cost::float, "
							"weight::float, "
							"tare::float, "
							"sellable, "
							"purchasable, "
							"manufactured, "
							"job, "
							"stock "
					"FROM products WHERE (deleted, expense) = (False, False)")
		for row in c.fetchall():
			store.append(row)
		c.close()

	def export_products_clicked (self, button):
		chooser = self.builder.get_object('export_file_chooser')
		response = chooser.run()
		chooser.hide()
		if response == Gtk.ResponseType.ACCEPT:
			filename = chooser.get_filename()
			if not filename.endswith('.xls'):
				filename = filename + '.xls'
			treeview = self.builder.get_object('product_treeview')
			self.write_xls (filename, treeview, "Products")
		subprocess.Popen(['soffice', filename])

	def export_contacts_clicked (self, button):
		chooser = self.builder.get_object('export_file_chooser')
		response = chooser.run()
		chooser.hide()
		if response == Gtk.ResponseType.ACCEPT:
			filename = chooser.get_filename()
			if not filename.endswith('.xls'):
				filename = filename + '.xls'
			treeview = self.builder.get_object('contact_treeview')
			self.write_xls (filename, treeview, "Contacts")
		subprocess.Popen(['soffice', filename])

	def write_xls(self, file_name, treeview, sheet_name):
		book = xlsxwriter.Workbook(file_name)
		sheet = book.add_worksheet(sheet_name)
		for index, column in enumerate(treeview.get_columns()):
			title = column.get_title()
			sheet.write(0, index, title)
		sheet.freeze_panes (1, True) # frozen headings instead of split panes
		model = treeview.get_model()
		rows = float(len(model))
		progressbar = self.builder.get_object('progressbar1')
		for rowx, row in enumerate(model):
			rowx += 1 # we already have a row
			for colx, cell in enumerate(row):
				sheet.write(rowx, colx, cell)
			progressbar.set_fraction(float(rowx)/rows)
			while Gtk.events_pending():
				Gtk.main_iteration()
		progressbar.set_fraction(1.00)
		book.close()

	def main_page_clicked (self, button):
		stack = self.builder.get_object('main_stack')
		stack.set_visible_child_name('start_page')





