# product_transactions.py
#
# Copyright (C) 2017 - reuben
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
import main, product_hub

UI_FILE = main.ui_directory + "/reports/product_transactions.ui"



class ProductTransactionsGUI:
	def __init__(self, main_class, product_id = None):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main_class = main_class
		self.db = main_class.db
		self.cursor = self.db.cursor()

		self.product_store = self.builder.get_object('product_store')
		self.customer_transaction_store = self.builder.get_object('customer_transaction_store')
		self.vendor_transaction_store = self.builder.get_object('vendor_transaction_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.exists = True
		self.populate_product_store ()
		if product_id != None:
			self.product_id = product_id
			self.select_product()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.exists = False

	def product_hub_clicked (self, button):
		product_hub.ProductHubGUI(self.main_class, self.product_id)

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_product_store (self):
		self.cursor.execute("SELECT id, name FROM products "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			self.product_store.append([str(product_id), product_name])

	def product_match_selected(self, completion, model, iter_):
		self.product_id = self.product_store[iter_][0]
		self.select_product ()

	def product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.select_product ()

	def select_product (self):
		self.builder.get_object('combobox1').set_active_id(str(self.product_id))
		self.customer_transaction_store.clear()
		qty_total = 0
		self.cursor.execute("SELECT i.id, "
								"qty, "
								"i.date_created::text, "
								"format_date(i.date_created), "
								"c.name, "
								"i.name, "
								"price, "
								"remark "
							"FROM invoice_items AS ili "
							"JOIN invoices AS i "
							"ON i.id = ili.invoice_id "
							"JOIN contacts AS c "
							"ON c.id = i.customer_id "
							"JOIN products AS p "
							"ON p.id = ili.product_id "
							"WHERE (product_id, i.canceled, ili.canceled) = "
							"(%s, False, False) "
							"ORDER BY i.id", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			qty_total += row[1]
			self.customer_transaction_store.append(row)
		self.builder.get_object('label3').set_label(str(qty_total))
		self.vendor_transaction_store.clear()
		qty_total = 0
		self.cursor.execute("SELECT "
								"po.id, "
								"qty, "
								"po.date_created::text, "
								"format_date(po.date_created), "
								"c.name, "
								"po.name, "
								"price, "
								"order_number, "
								"remark "
							"FROM purchase_order_line_items AS pli "
							"JOIN purchase_orders AS po "
							"ON po.id = pli.purchase_order_id "
							"JOIN contacts AS c "
							"ON c.id = po.vendor_id "
							"JOIN products AS p "
							"ON p.id = pli.product_id "
							"WHERE (product_id, po.canceled, pli.canceled) = "
							"(%s, False, False) "
							"ORDER BY po.id", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			qty_total += row[1]
			self.vendor_transaction_store.append(row)
		self.builder.get_object('label5').set_label(str(qty_total))






		
