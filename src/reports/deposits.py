# deposits.py
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
import main

UI_FILE = main.ui_directory + "/reports/deposits.ui"

class DepositsGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()

		self.deposit_store = self.builder.get_object('deposit_store')
		self.populate_deposits_store ()

		window = self.builder.get_object('window1')
		window.show_all()

		price_column = self.builder.get_object ('treeviewcolumn2')
		price_renderer = self.builder.get_object ('cellrenderertext2')
		price_column.set_cell_data_func(price_renderer, self.amount_cell_func)

	def amount_cell_func(self, view_column, cellrenderer, model, iter1, column):
		amount = '{:,.2f}'.format(model.get_value(iter1, 3))
		cellrenderer.set_property("text" , amount)

	def populate_deposits_store (self):
		self.cursor.execute ("SELECT "
								"gl_entries.id, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"gl_entries.amount, "
								"'', "
								"gl_accounts.name "
							"FROM gl_entries "
							"JOIN gl_accounts ON gl_accounts.number = gl_entries.debit_account "
							"WHERE gl_entries.id IN "
								"(SELECT gl_entries_deposit_id FROM payments_incoming "
								"GROUP BY gl_entries_deposit_id ) "
							"ORDER BY date_inserted")
		for row in self.cursor.fetchall():
			row_id = row[0]
			parent = self.deposit_store.append(None,row)
			self.cursor.execute("SELECT "
									"p.id, "
									"date_inserted::text, "
									"format_date(date_inserted), "
									"amount, "
									"payment_text, "
									"c.name "
								"FROM payments_incoming AS p "
								"JOIN contacts AS c ON c.id = p.customer_id "
								"WHERE gl_entries_deposit_id = %s", (row_id,))
			for row in self.cursor.fetchall():
				self.deposit_store.append(parent, row)




		



		
