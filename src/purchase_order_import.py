# purchase_order_import.py
#
#
# Copyright (C) 2025 reuben
#
# purchase_order_import is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# purchase_order_import is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
import psycopg2, csv
from constants import ui_directory, DB

UI_FILE = ui_directory + "/purchase_order_import.ui"

class PurchaseOrderImportGUI(Gtk.Builder):
	def __init__(self, po_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.po_id = po_id
		self.get_object('reload_button').set_label("Reload PO " + po_id)
		self.treeview = self.get_object('treeview')
		self.populate_purchase_order_items_store()
		c = DB.cursor()
		c.execute("SELECT vendor_id FROM purchase_orders WHERE id = %s", (po_id, ))
		self.vendor_id = c.fetchone()[0]
		c.close()
		self.window = self.get_object('window')
		self.window.show_all()

	def reload_button_clicked (self, button):
		self.populate_purchase_order_items_store()

	def populate_purchase_order_items_store (self):
		store = self.get_object('purchase_order_items_store')
		store.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"ROW_NUMBER () OVER ( "
							"ORDER BY "
							"poi.sort, poi.id ),"
						"qty::text, "
						"p.id, "
						"p.name, "
						"remark, "
						"price::text, "
						"ext_price::text, "
						"CASE WHEN expense = TRUE THEN 0.00 ELSE price END, "
						"order_number, "
						"poi.id, "
						"poi.expense_account "
					"FROM purchase_order_items AS poi "
					"JOIN products AS p ON p.id = poi.product_id "
					"WHERE purchase_order_id = (%s) "
					"ORDER BY poi.sort, poi.id",
					(self.po_id, ))
		for row in c.fetchall() :
			store.append(row)
		c.close()
		DB.rollback()

	def import_file_selected (self, filechooserbutton):
		for column in self.treeview.get_columns():
			self.treeview.remove_column(column)
		self.filename = filechooserbutton.get_filename()
		if self.filename.endswith(".csv") == True:
			self.load_csv()
		elif self.filename.endswith(".xls") == True:
			self.load_xls()

	def load_csv(self):
		with open(self.filename) as csv_file:
			csv_read = csv.reader(csv_file, delimiter=',')
			headers = next(csv_read)  # First row is header
			n_columns = len(headers)
			self.liststore = Gtk.ListStore(*([str] * n_columns))
			column_store = self.get_object("file_column_store")
			column_store.clear()
			for i, title in enumerate(headers):
				column_store.append([str(i), title])
				renderer = Gtk.CellRendererText(editable = True)
				column = Gtk.TreeViewColumn(title, renderer, text=i)
				column.set_resizable(True)
				self.treeview.append_column(column)
			for row in csv_read:
				self.liststore.append(row)
			self.treeview.set_model(self.liststore)
		self.check_import_validity()

	def load_xls(self):
		import xlrd
		book = xlrd.open_workbook(self.filename)
		sheet = book.sheet_by_index(0)
		n_columns = sheet.ncols
		self.liststore = Gtk.ListStore(*([str] * n_columns))
		column_store = self.get_object("file_column_store")
		column_store.clear()
		for col_idx in range(sheet.ncols):
			title = sheet.cell_value(0, col_idx)
			column_store.append([str(col_idx), title])
			renderer = Gtk.CellRendererText(editable = True)
			column = Gtk.TreeViewColumn(title, renderer, text=col_idx)
			column.set_resizable(True)
			self.treeview.append_column(column)
		for row_idx in range(sheet.nrows):
			if row_idx == 0: #header
				continue
			row = tuple(sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols))
			self.liststore.append(row)
		self.treeview.set_model(self.liststore)
		self.check_import_validity()

	def combo_changed(self, combo):
		self.check_import_validity()

	def check_import_validity(self):
		button = self.get_object('import_to_po_button')
		button.set_sensitive(False)
		if self.get_object('qty_combo').get_active_id() == None:
			return
		if self.get_object('order_number_combo').get_active_id() == None:
			return
		if self.get_object('price_combo').get_active_id() == None:
			return
		button.set_sensitive(True)

	def import_to_po_clicked (self, button):
		qty_column = int(self.get_object('qty_combo').get_active_id())
		order_number_column = int(self.get_object('order_number_combo').get_active_id())
		price_column = int(self.get_object('price_combo').get_active_id())
		po_store = self.get_object('purchase_order_items_store')
		cursor = DB.cursor()
		for index, model_row in enumerate(self.liststore):
			qty = model_row[qty_column]
			if qty == '': # blank line?
				continue
			order_number = model_row[order_number_column]
			price = model_row[price_column]
			cursor.execute("SELECT product_id, p.name, p.default_expense_account "
							"FROM vendor_product_numbers AS vpn "
							"JOIN products AS p ON p.id = vpn.product_id "
							"WHERE vendor_id = %s AND vendor_sku = %s LIMIT 1",
							(self.vendor_id, order_number))
			for row in cursor.fetchall():
				po_store[index][2] = row[0] # product id
				po_store[index][3] = row[1] # product name
				po_store[index][10] = row[2] # default expense account
				po_store[index][8] = order_number
			po_store[index][1] = qty
			po_store[index][5] = price
		self.check_import_validity()
		self.get_object('save_po_items_button').set_sensitive(True)

	def save_purchase_order_items_clicked (self, button):
		c = DB.cursor()
		for row in self.get_object('purchase_order_items_store'):
			qty = row[1]
			product_id = row[2]
			price = str(row[5]).replace('$', '')
			order_number = row[8]
			expense_account = row[10]
			row_id = row[9]
			c.execute("UPDATE purchase_order_items "
						"SET (qty, product_id, price, order_number, expense_account) = "
						"(%s, %s, %s, %s, %s) WHERE id = %s",
						(qty, product_id, price, order_number, expense_account, row_id))
		DB.commit()
		c.close()


