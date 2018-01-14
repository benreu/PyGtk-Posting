# statements.py
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
from dateutils import datetime_to_text

UI_FILE = "src/reports/statements.ui"

class StatementsGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()

		self.customer_id = None
		self.customer_store = self.builder.get_object('customer_store')
		self.statement_store = self.builder.get_object('statement_store')
		self.populate_customer_store ()
		self.populate_statement_store ()
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		price_column = self.builder.get_object ('treeviewcolumn4')
		price_renderer = self.builder.get_object ('cellrenderertext4')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_customer_store (self):
		self.customer_store.clear()
		self.cursor.execute("SELECT customer_id, contacts.name, contacts.c_o "
							"FROM statements JOIN contacts "
							"ON contacts.id = statements.customer_id "
							"GROUP BY contacts.name, customer_id, contacts.c_o "
							"ORDER BY contacts.name ")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			customer_name = row[1]
			ext_name = row[2]
			self.customer_store.append([str(customer_id), customer_name, ext_name])

	def price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 5)
		cellrenderer.set_property("text" , str(price))

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

	def view_statement_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			statement_id = model[path][0]
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
			f = open(statement_file,'wb')
			f.write(file_data)
			subprocess.call("xdg-open %s" % statement_file, shell = True)
			f.close()

	def view_all_toggled (self, togglebutton):
		self.populate_statement_store ()

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.builder.get_object('checkbutton1').set_active(False)
		self.customer_id = customer_id
		self.populate_statement_store ()

	def treeview_parent_togglebutton_toggled (self, togglebutton):
		self.populate_statement_store()

	def populate_statement_store (self):
		self.statement_store.clear()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT s.id, date_inserted, contacts.name, "
								"contacts.id, s.name, amount, printed "
								"FROM statements AS s "
								"JOIN contacts "
								"ON contacts.id = s.customer_id ")
		else:
			if self.customer_id == None:
				return # no customer selected
			self.cursor.execute("SELECT s.id, date_inserted, contacts.name, "
								"contacts.id, s.name, amount, printed "
								"FROM statements AS s "
								"JOIN contacts "
								"ON contacts.id = s.customer_id "
								"WHERE customer_id = %s", (self.customer_id, ))
		for row in self.cursor.fetchall():
			row_id = row[0]
			date = row[1]
			customer_name = row[2]
			customer_id = row[3]
			statement_name = row[4]
			amount = row[5]
			printed = row[6]
			date_formatted = datetime_to_text (date)
			parent = self.statement_store.append(None, [row_id, date_formatted,  
										str(date),customer_name, statement_name, 
										amount, printed])
			if self.builder.get_object('checkbutton2').get_active() == False:
				parent = None
			self.cursor.execute("SELECT * FROM (SELECT pi.id, date_inserted, "
								"c.name, payment_info(pi.id), "
								"amount, False FROM payments_incoming AS pi "
								"JOIN contacts AS c ON c.id = pi.customer_id "
								"WHERE (customer_id, statement_id) = (%s, %s)) p "
								"UNION "
								"(SELECT i.id, date_created, c.name, i.name, "
								"amount_due, (date_printed IS NOT NULL) "
								"FROM invoices AS i "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE (customer_id, statement_id) = (%s, %s) ) "
								"ORDER BY 2", 
								(customer_id, row_id, customer_id, row_id))
			for row in self.cursor.fetchall():
				row_id = row[0]
				date = row[1]
				customer_name = row[2]
				description = row[3]
				amount = row[4]
				printed = row[5]
				date_formatted = datetime_to_text (date)
				self.statement_store.append(parent, [row_id, date_formatted,  
										str(date),customer_name, description, 
										amount, printed])



		
