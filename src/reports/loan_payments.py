# loan_payments.py
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

UI_FILE = main.ui_directory + "/reports/loan_payments.ui"

class LoanPaymentsGUI:
	def __init__(self):

		self.db = main.db
		self.cursor = self.db.cursor()

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.loan_payment_store = self.builder.get_object('loan_payments_store')
		self.loan_store = self.builder.get_object('loan_store')
		self.populate_loans ()

		column = self.builder.get_object ('treeviewcolumn2')
		renderer = self.builder.get_object ('cellrenderertext2')
		column.set_cell_data_func(renderer, self.cell_func, 2)

		column = self.builder.get_object ('treeviewcolumn3')
		renderer = self.builder.get_object ('cellrenderertext3')
		column.set_cell_data_func(renderer, self.cell_func, 3)

		column = self.builder.get_object ('treeviewcolumn4')
		renderer = self.builder.get_object ('cellrenderertext4')
		column.set_cell_data_func(renderer, self.cell_func, 4)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def cell_func (self, column, cellrenderer, model, iter1, index):
		amount = "{:,.2f}".format(model[iter1][index])
		cellrenderer.set_property("text", amount)

	def populate_loans (self):
		self.cursor.execute("SELECT l.id::text, l.description "
							"FROM loans AS l "
							"ORDER BY description")
		for row in self.cursor.fetchall():
			self.loan_store.append(row)

	def loan_combo_changed (self, combo):
		loan_id = combo.get_active_id ()
		if loan_id != None :
			self.loan_id = loan_id
			self.populate_loan_payments()

	def populate_loan_payments (self):
		self.loan_payment_store.clear()
		self.cursor.execute("SELECT "
								"lp.id, "
								"c.name, "
								"total.amount::float, "
								"principal.amount::float, "
								"interest.amount::float, "
								"total.date_inserted::text, "
								"format_date(total.date_inserted) "
							"FROM loan_payments AS lp "
							"JOIN gl_entries AS total "
								"ON total.id = lp.gl_entries_total_id "
							"JOIN gl_entries AS principal "
								"ON principal.id = lp.gl_entries_principal_id "
							"JOIN gl_entries AS interest "
								"ON interest.id = lp.gl_entries_interest_id "
							"JOIN contacts AS c ON c.id = lp.contact_id "
							"WHERE lp.loan_id = %s ORDER BY principal.date_inserted", 
							(self.loan_id,))
		for row in self.cursor.fetchall():
			self.loan_payment_store.append(row)


			

		
