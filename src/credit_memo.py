# credit_memo.py
#
# Copyright (C) 2018 - reuben
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
from dateutils import datetime_to_text

UI_FILE = "src/credit_memo.ui"

class CreditMemoGUI:
	def __init__(self, main):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('credit_products_store')
		self.credit_items_store = self.builder.get_object('credit_items_store')
		self.db = main.db
		self.cursor = self.db.cursor()
		self.handler_c_id = main.connect ("contacts_changed", self.populate_customer_store )
		self.populate_customer_store ()
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		window = self.builder.get_object('window1')
		window.show_all()
		
	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!
	
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name "
							"FROM contacts WHERE (deleted, customer) = "
							"(False, True) ORDER BY name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			name = row[1]
			ext_name = row[2]
			self.customer_store.append([customer_id, name, ext_name])

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id ()
		if customer_id != None:
			self.select_customer (customer_id)

	def customer_match_selected (self, completion, model, _iter):
		customer_id = model[_iter][0]
		self.select_customer (customer_id)

	def select_customer(self, customer_id):
		self.customer_id = customer_id
		self.populate_product_store ()

	def populate_product_store(self, m=None, i=None):
		self.product_store.clear()
		c = self.db.cursor()
		c.execute("SELECT ili.id::text, p.name, ext_name, i.id::text, i.dated_for "
					"FROM products AS p "
					"JOIN invoice_line_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE customer_id = %s "
					"ORDER BY p.name", (self.customer_id,))
		for row in c.fetchall():
			_id_ = row[0]
			name = "%s {%s}" % (row[1], row[2])
			invoice = row[3]
			date = datetime_to_text (row[4])
			self.product_store.append([_id_, name, invoice, date])
		c.close()

	def product_combo_changed (self, combo):
		invoice_item_id = combo.get_active_id()
		if invoice_item_id != None:
			self.invoice_item_selected(invoice_item_id)

	def product_match_selected (self, completion, model, _iter):
		invoice_item_id = model[_iter_][0]
		self.invoice_item_selected(invoice_item_id)

	def invoice_item_selected (self, invoice_item_id):
		for row in self.credit_items_store:
			if row[5] == int(invoice_item_id):
				self.builder.get_object('treeview-selection1').select_path(row.path)
				return
		c = self.db.cursor()
		c.execute("SELECT product_id, p.name, ili.price, i.id, i.dated_for "
					"FROM products AS p "
					"JOIN invoice_line_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE ili.id = %s ", (invoice_item_id,))
		for row in c.fetchall():
			product_id = row[0]
			product_name = row[1]
			price = row[2]
			invoice = row[3]
			date = row[4]
			date_formatted = datetime_to_text (date)
			self.credit_items_store.append([0, 1.0, product_id, product_name, 
											price, int(invoice_item_id), 
											invoice, str(date), date_formatted])
		c.close()











		


		