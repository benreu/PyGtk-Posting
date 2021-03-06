#
# product_import.py
# Copyright (C) 2016 Reuben Rissler
# 
# product_import is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# product_import is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
import xlrd
from xlrd.biffh import XLRDError
from psycopg2 import IntegrityError
from constants import DB, ui_directory

UI_FILE = ui_directory + "/admin/product_import.ui"


class ProductsImportGUI(Gtk.Builder):
	error = None
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_combos()

	def populate_combos (self):
		revenue_combo = self.get_object('revenue_combo')
		c = DB.cursor()
		c.execute("SELECT number::text, name "
					"FROM gl_accounts "
					"WHERE revenue_account = True ORDER BY name")
		for row in c.fetchall():
			revenue_combo.append(row[0], row[1])
		revenue_combo.set_active(0)
		expense_combo = self.get_object('expense_combo')
		c.execute("SELECT number::text, name "
					"FROM gl_accounts "
					"WHERE expense_account = True ORDER BY name")
		for row in c.fetchall():
			expense_combo.append(row[0], row[1])
		expense_combo.set_active(0)
		tax_rate_combo = self.get_object('tax_rate_combo')
		c.execute("SELECT id::text, name "
					"FROM tax_rates "
					"WHERE (deleted, exemption) = (False, False) ORDER BY name")
		for row in c.fetchall():
			tax_rate_combo.append(row[0], row[1])
		tax_rate_combo.set_active(0)
		c.close()
		DB.rollback()

####### start import to treeview

	def load_xls (self, filename):
		store = self.get_object('product_import_store')
		store.clear()
		try:
			book = xlrd.open_workbook(filename)
		except XLRDError as e:
			self.error = e
			return False
		try:
			sheet = book.sheet_by_name ('Products')
		except XLRDError as e:
			self.error = e
			return False
		for i in range(sheet.nrows):
			if i == 0:
				continue # skip the header
			try:
				xls_row = sheet.row(i)
				name = xls_row[0].value
				ext_name = xls_row[1].value
				description = xls_row[2].value
				barcode = xls_row[3].value
				cost = xls_row[4].value
				weight = xls_row[5].value
				tare = xls_row[6].value
				sellable = xls_row[7].value
				purchasable = xls_row[8].value
				manufactured = xls_row[9].value
				job = xls_row[10].value
				stock = xls_row[11].value
			except Exception as e:
				self.error = str(e) + "\n\nPlease export some data "\
										"from Posting and match that format."\
										"\nHint : You are missing "\
										"one or more columns."
				return False
			try:
				store.append([	str(name), 
								str(ext_name),
								str(description),
								str(barcode),
								float(cost),
								float(weight),
								float(tare),
								bool(sellable),
								bool(purchasable),
								bool(manufactured),
								bool(job),
								bool(stock)   ])
			except Exception as e:
				self.error = str(e) + "\n\nPlease export some data "\
										"from Posting and match that format."\
										"\nHint : You have wrong cell data."
				return False
		return True

####### end import to treeview

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right click menu')
			menu.popup_at_pointer()

	def delete_product_activated (self, menu):
		selection = self.get_object('xls_import_selection')
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		iter_ = model.get_iter(path)
		model.remove(iter_)

	def import_clicked (self, button):
		button.set_sensitive(False)
		checkbutton = self.get_object('barcode_checkbutton')
		if checkbutton.get_active() == True:
			self.import_with_generated_barcodes()
		else:
			self.import_with_barcodes ()

	def import_with_generated_barcodes (self):
		revenue_account = self.get_object('revenue_combo').get_active_id()
		expense_account = self.get_object('expense_combo').get_active_id()
		tax_rate_id = self.get_object('tax_rate_combo').get_active_id()
		progressbar = self.get_object('progressbar1')
		model = self.get_object('product_import_store')
		c = DB.cursor()
		total = len(model)
		for row_count, row in enumerate(model):
			c.execute ("INSERT INTO products ("
												"name, "
												"ext_name, "
												"description, "
												"cost, "
												"weight, "
												"tare, "
												"sellable, "
												"purchasable, "
												"manufactured, "
												"job, "
												"stock,"
												"revenue_account,"
												"default_expense_account,"
												"tax_rate_id, "
												"unit)"
						"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
						"1)",
						(row[0],row[1],row[2],row[4],row[5],row[6],
						row[7],row[8],row[9],row[10],row[11],
						revenue_account, expense_account, tax_rate_id))
			progressbar.set_fraction(float(row_count)/total)
			while Gtk.events_pending():
				Gtk.main_iteration()
		c.close()
		DB.commit()

	def import_with_barcodes (self):
		revenue_account = self.get_object('revenue_combo').get_active_id()
		expense_account = self.get_object('expense_combo').get_active_id()
		tax_rate_id = self.get_object('tax_rate_combo').get_active_id()
		progressbar = self.get_object('progressbar1')
		model = self.get_object('product_import_store')
		c = DB.cursor()
		total = len(model)
		for row_count, row in enumerate(model):
			try:
				c.execute ("INSERT INTO products ("
												"name, "
												"ext_name, "
												"description, "
												"barcode, "
												"cost, "
												"weight, "
												"tare, "
												"sellable, "
												"purchasable, "
												"manufactured, "
												"job, "
												"stock,"
												"revenue_account,"
												"default_expense_account,"
												"tax_rate_id, "
												"unit)"
						"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
						"1)",
						(row[0],row[1],row[2],row[3],row[4],row[5],row[6],
						row[7],row[8],row[9],row[10],row[11],
						revenue_account, expense_account, tax_rate_id))
				progressbar.set_fraction(float(row_count)/total)
				while Gtk.events_pending():
					Gtk.main_iteration()
			except IntegrityError as e:
				print (e)
				self.show_message (str(e))
				c.close()
				DB.rollback()
				return
		c.close()
		DB.commit()

	def show_message (self, error):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (error)
		dialog.run()
		dialog.destroy()
		
	def text_renderer_edited (self, text_renderer, path, new_text):
		treeview = self.get_object('xls_treeview')
		path, column = treeview.get_cursor()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id()
		model[path][col_index] = new_text

	def float_renderer_edited (self, text_renderer, path, new_text):
		treeview = self.get_object('xls_treeview')
		path, column = treeview.get_cursor()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id()
		model[path][col_index] = float(new_text)

	def boolean_renderer_toggled (self, toggle_renderer, path):
		treeview = self.get_object('xls_treeview')
		old_path, column = treeview.get_cursor ()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id ()
		model[path][col_index] = not model[path][col_index]

	def destroy (self, window = None):
		self.window.destroy()

	def barcode_tool_clicked (self, button):
		dialog = self.get_object('barcode_dialog')
		response = dialog.run()
		dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			chars = self.get_object('barcode_entry').get_text()
			model = self.get_object('product_import_store')
			for row in model:
				row[3] = chars + row[3]
	
	def barcode_generator_checkbutton_toggled (self, togglebutton):
		button = self.get_object('prepend_button')
		active = togglebutton.get_active()
		button.set_sensitive(not active)
		
		

