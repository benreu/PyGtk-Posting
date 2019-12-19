# expense_products.py
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

from gi.repository import Gtk, GObject
from constants import DB, ui_directory

UI_FILE = ui_directory + "/expense_products.ui"

class GUI(Gtk.Builder):
	__gsignals__ = { 
	'expense-products-changed': (GObject.SignalFlags.RUN_FIRST, 
								GObject.TYPE_NONE, ())
														}
	"""the expense-products-changed signal is used to send a message to the 
		parent window that an expense product has been changed"""
	def __init__(self):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.expense_products_store = self.get_object('expense_products_store')
		self.expense_account_store = self.get_object('expense_account_store')
		self.populate_expense_products_store()
		self.populate_expense_account_store ()
		self.window = self.get_object('window')
		self.window.show_all()

	def populate_expense_account_store (self):
		c = DB.cursor()
		self.expense_account_store.clear()
		c.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE expense_account = True")
		for row in c.fetchall():
			self.expense_account_store.append(row)
		DB.rollback()
		c.close()

	def populate_expense_products_store (self):
		self.expense_products_store.clear()
		c = DB.cursor()
		c.execute("SELECT p.id, p.name, cost, "
							"default_expense_account, a.name "
							"FROM products AS p LEFT JOIN gl_accounts "
							"AS a ON a.number = p.default_expense_account "
							"WHERE (deleted, expense) = (False, True)")
		for row in c.fetchall():
			self.expense_products_store.append(row)
		DB.rollback()
		c.close()

	def product_expense_account_combo_changed (self, combo, path, iter_):
		expense_account = self.expense_account_store[iter_][0]
		expense_account_name = self.expense_account_store[iter_][1]
		self.expense_products_store[path][3] = int(expense_account)
		self.expense_products_store[path][4] = expense_account_name
		self.save_expense_product (path)

	def product_expense_name_renderer_edited (self, entry, path, text):
		self.expense_products_store[path][1] = text
		self.save_expense_product (path)

	def product_expense_spin_value_edited (self, spin, path, value):
		self.expense_products_store[path][2] = float(value)
		self.save_expense_product (path)

	def save_expense_product (self, path):
		c = DB.cursor()
		product_id = self.expense_products_store[path][0]
		product_name = self.expense_products_store[path][1]
		product_cost = self.expense_products_store[path][2]
		expense_account = self.expense_products_store[path][3]
		if expense_account == 0:
			expense_account = None
		c.execute("UPDATE products SET "
					"(name, cost, default_expense_account) = "
					"(%s, %s, %s) WHERE id = %s", 
					(product_name, product_cost, 
					expense_account, product_id))
		DB.commit()
		c.close()
		self.emit('expense-products-changed')

	def new_expense_product_clicked (self, button):
		c = DB.cursor()
		c.execute("INSERT INTO products "
								"(name, "
								"unit, "
								"cost, "
								"expense, "
								"tax_rate_id, "
								"revenue_account, "
								"default_expense_account) "
							"VALUES "
								"('New expense product', "
								"1, "
								"0.00, "
								"True, "
								"(SELECT id FROM tax_rates "
									"WHERE standard = True "
									"), "
								"(SELECT number FROM gl_accounts "
									"WHERE revenue_account = True LIMIT 1 "
									"), "
								"(SELECT number FROM gl_accounts "
									"WHERE expense_account = True LIMIT 1 "
									"))")
		DB.commit()
		c.close()
		self.emit('expense-products-changed')

	def delete_expense_product_clicked (self, button):
		c = DB.cursor()
		model, path = self.get_object("treeview-selection2").get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		try:
			c.execute("DELETE FROM products WHERE id = %s ", 
								(product_id,))
		except psycopg2.IntegrityError as e:
			print (e)
			DB.rollback()
			c.execute("UPDATE products SET deleted = TRUE "
								"WHERE id = %s ", (product_id,))
		DB.commit()
		c.close()
		self.populate_expense_products_store ()
		self.emit('expense-products-changed')




