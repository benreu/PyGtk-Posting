# customer_history.py
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


from gi.repository import Gtk
from decimal import Decimal
import subprocess
import dateutils

UI_FILE = "src/reports/product_history.ui"

class ProductHistoryGUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.invoice_history = None

		self.product_store = self.builder.get_object('product_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM products "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			id_ = row[0]
			name = row[1]
			ext_name = row[2]
			self.product_store.append([id_ , name, ext_name])
			
		amount_column = self.builder.get_object ('treeviewcolumn4')
		amount_renderer = self.builder.get_object ('cellrenderertext4')
		amount_column.set_cell_data_func(amount_renderer, self.qty_cell_func, 5)
			
		amount_column = self.builder.get_object ('treeviewcolumn5')
		amount_renderer = self.builder.get_object ('cellrenderertext5')
		amount_column.set_cell_data_func(amount_renderer, self.price_cell_func, 6)

		amount_column = self.builder.get_object ('treeviewcolumn8')
		amount_renderer = self.builder.get_object ('cellrenderertext9')
		amount_column.set_cell_data_func(amount_renderer, self.price_cell_func, 5)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def close_transaction_window (self, window, event):
		self.cursor.close()

	def qty_cell_func(self, view_column, cellrenderer, model, iter1, column):
		price = '{:,.1f}'.format(model.get_value(iter1, column))
		cellrenderer.set_property("text" , price)

	def price_cell_func(self, view_column, cellrenderer, model, iter1, column):
		price = '{:,.2f}'.format(model.get_value(iter1, column))
		cellrenderer.set_property("text" , price)
		
	def invoice_row_activated (self, treeview, treepath, treeviewcolumn):
		model = treeview.get_model()
		file_id = model[treepath][0]
		self.cursor.execute("SELECT name, pdf_data FROM invoices WHERE id = %s", 
																	(file_id ,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/" + row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.call(["xdg-open", file_name])
			f.close()

	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('invoice_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def invoice_history_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][0]
		contact_id = model[path][8]
		if not self.invoice_history or self.invoice_history.exists == False:
			from reports import invoice_history as ih
			self.invoice_history = ih.InvoiceHistoryGUI(self.main)
		combo = self.invoice_history.builder.get_object('combobox1')
		combo.set_active_id(contact_id)
		store = self.invoice_history.builder.get_object('invoice_store')
		selection = self.invoice_history.builder.get_object('treeview-selection1')
		selection.unselect_all()
		for row in store:
			if row[0] == invoice_id:
				selection.select_iter(row.iter)
				break
		self.invoice_history.present()

	def product_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter][1].lower():
				return False# no match
		return True# it's a hit!
		
	def product_changed(self, combo):
		product_id = combo.get_active_id ()
		if product_id == None:
			return
		self.product_id = product_id
		self.populate_product_stores ()

	def product_match_selected (self, completion, model, iter):
		self.product_id = model[iter][0]
		self.populate_product_stores ()

	def populate_product_stores (self):
		self.populate_product_invoices()
		self.populate_purchase_orders ()
		self.populate_warranty_store ()

	def populate_warranty_store (self):
		warranty_store = self.builder.get_object('warranty_store')
		warranty_store.clear()
		count = 0
		self.cursor.execute("SELECT snh.id, p.name, sn.serial_number, "
							"snh.date_inserted, snh.description, c.name "
							"FROM serial_number_history AS snh "
							"JOIN serial_numbers AS sn "
							"ON sn.id = snh.serial_number_id "
							"JOIN products AS p ON p.id = sn.product_id "
							"JOIN contacts AS c ON c.id = snh.contact_id "
							"WHERE sn.product_id = %s ORDER by date_inserted", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			row_id = row[0]
			product_name = row[1]
			serial_number = row[2]
			date = row[3]
			description = row[4]
			c_name = row[5]
			date_formatted = dateutils.datetime_to_text (date)
			warranty_store.append([row_id, product_name, serial_number, 
									str(date), date_formatted, description, 
									c_name])
		if count == 0:
			self.builder.get_object('label8').set_label('Warranty')
		else:
			label = "<span weight='bold'>Warranty (%s)</span>" % count
			self.builder.get_object('label8').set_markup(label)

	def populate_purchase_orders (self):
		po_store = self.builder.get_object('po_store')
		po_store.clear()
		count = 0
		self.cursor.execute("SELECT po.id, contacts.name, date_created, qty, price "
							"FROM purchase_orders AS po "
							"JOIN purchase_order_line_items AS poli "
							"ON poli.purchase_order_id = po.id "
							"JOIN contacts ON contacts.id = po.vendor_id "
							"WHERE product_id = %s", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			po_id = row[0]
			vendor_name = row[1]
			dated_for = row[2]
			qty = row[3]
			price = row[4]
			date_formatted = dateutils.datetime_to_text(dated_for)
			po_store.append([po_id, str(dated_for), 
									date_formatted, vendor_name, qty, price])
		if count == 0:
			self.builder.get_object('label4').set_label('Purchase Orders')
		else:
			label = "<span weight='bold'>Purchase Orders (%s)</span>" % count
			self.builder.get_object('label4').set_markup(label)

	def populate_product_invoices (self):
		invoice_store = self.builder.get_object('invoice_store')
		invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT i.id, dated_for, i.name, c.id::text, c.name, "
							"comments, qty, price "
							"FROM invoices AS i "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"JOIN invoice_items AS ii ON ii.invoice_id = i.id "
							"WHERE (product_id, i.canceled) = "
							"(%s, False) ORDER BY dated_for", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			id_ = row[0]
			date = row[1]
			date_formatted = dateutils.datetime_to_text(date)
			i_name = row[2]
			c_id = row[3]
			c_name = row[4]
			remark = "Comments: " + row[5]
			qty = row[6]
			price = row[7]
			invoice_store.append([id_, str(date), date_formatted, i_name, 
									remark, qty, price, c_id, c_name])
		if count == 0:
			self.builder.get_object('label2').set_label('Invoices')
		else:
			label = "<span weight='bold'>Invoices (%s)</span>" % count
			self.builder.get_object('label2').set_markup(label)





			