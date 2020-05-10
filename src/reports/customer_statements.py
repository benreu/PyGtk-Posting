# customer_statements.py
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


from gi.repository import Gtk, GdkPixbuf, Gdk
import subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/customer_statements.ui"

class StatementsGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.customer_id = None
		self.customer_store = self.builder.get_object('customer_store')
		self.statement_store = self.builder.get_object('statement_store')
		self.populate_customer_store ()
		self.populate_statement_store ()
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_customer_store (self):
		self.customer_store.clear()
		c = DB.cursor()
		c.execute("SELECT customer_id::text, contacts.name, contacts.ext_name "
					"FROM statements JOIN contacts "
					"ON contacts.id = statements.customer_id "
					"GROUP BY contacts.name, customer_id, contacts.ext_name "
					"ORDER BY contacts.name ")
		for row in c.fetchall():
			self.customer_store.append(row)
		c.close()
		DB.rollback()

	def customer_match_selected (self, completion, model, iter):
		customer_id = model[iter][0]
		self.builder.get_object('combobox1').set_active_id(customer_id)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def treeview_row_activated (self, treeview, path, treeviewcolumn):
		statement_id = self.statement_store[path][0]
		self.view_statement (statement_id)

	def view_statement (self, statement_id):
		self.cursor.execute("SELECT name, pdf FROM statements "
							"WHERE id = %s", (statement_id,))
		for row in self.cursor.fetchall():
			file_name = row[0]
			if file_name == None:
				return
			statement_file = "/tmp/%s.pdf" % file_name
			file_data = row[1]
			with open(statement_file,'wb') as f:
				f.write(file_data)
			subprocess.call(["xdg-open", statement_file])

	def view_all_toggled (self, togglebutton):
		self.populate_statement_store ()

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.builder.get_object('checkbutton1').set_active(False)
		self.customer_id = customer_id
		self.populate_statement_store ()

	def populate_statement_store (self):
		self.statement_store.clear()
		self.builder.get_object('statement_items_store').clear()
		c = DB.cursor()
		if self.builder.get_object('checkbutton1').get_active() == True:
			c.execute("SELECT s.id, date_inserted::text, "
						"format_date(date_inserted), contacts.id, "
						"contacts.name, s.name, amount, amount::text, printed "
						"FROM statements AS s "
						"JOIN contacts "
						"ON contacts.id = s.customer_id "
						"ORDER BY date_inserted, s.id")
		else:
			if self.customer_id == None:
				return # no customer selected
			c.execute("SELECT s.id, date_inserted::text, "
						"format_date(date_inserted), contacts.id, "
						"contacts.name, s.name, amount, amount::text, printed "
						"FROM statements AS s "
						"JOIN contacts "
						"ON contacts.id = s.customer_id "
						"WHERE customer_id = %s "
						"ORDER BY date_inserted, s.id", 
						(self.customer_id, ))
		for row in c.fetchall():
			self.statement_store.append(row)
		DB.rollback()
		c.close()

	def statement_cursor_changed (self, treeview):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		customer_id = model[path][3]
		store = self.builder.get_object('statement_items_store')
		store.clear()
		c = DB.cursor()
		c.execute("SELECT * FROM "
					"(SELECT "
						"pi.id, "
						"payment_info(pi.id), "
						"payment_text, "
						"date_inserted::text AS date, "
						"format_date(date_inserted), "
						"amount, "
						"amount::text, "
						"False "
					"FROM payments_incoming AS pi "
					"WHERE statement_id = %s) p "
					"UNION "
					"(SELECT "
						"i.id, "
						"'Invoice', "
						"id::text, "
						"date_created::text AS date, "
						"format_date(date_created), "
						"amount_due, "
						"amount_due::text, "
						"(date_printed IS NOT NULL) "
					"FROM invoices AS i "
					"WHERE statement_id = %s) "
					"UNION "
					"(SELECT "
						"id, "
						"'Credit Memo', "
						"id::text, "
						"date_created::text AS date, "
						"format_date(date_created), "
						"(-amount_owed), "
						"(-amount_owed)::text, "
						"(date_printed IS NOT NULL) "
					"FROM credit_memos "
					"WHERE statement_id = %s) "
					"UNION "
					"(SELECT "
						"id, "
						"'Statement', "
						"'Balance forward', "
						"date_inserted::text AS date, "
						"format_date(date_inserted), "
						"amount, "
						"amount::text, "
						"printed "
					"FROM statements " 
					"WHERE id ="
						"(SELECT MAX(id) FROM statements "
						"WHERE id < %s AND customer_id = %s)"
					") "
					"ORDER BY date", 
					(row_id, row_id, row_id, row_id, customer_id))
		for row in c.fetchall():
			store.append(row)
		DB.rollback()
		c.close()



