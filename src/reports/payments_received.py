# payments_received.py
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
import dateutils
from decimal import Decimal

UI_FILE = "src/reports/payments_received.ui"



class PaymentsReceivedGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		self.cursor = db.cursor()

		self.payment_store = self.builder.get_object('payments_received_store')
		self.contact_store = self.builder.get_object('contact_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.customer_id = None
		self.populate_stores()
		self.populate_payment_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def focus(self, window, event):
		return
		self.populate_payment_store()

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT customer_id, name FROM payments_incoming "
							"JOIN contacts ON payments_incoming.customer_id "
							"= contacts.id "
							"GROUP BY customer_id, name "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			customer_name = row[1]
			self.contact_store.append([str(customer_id), customer_name])
		store = self.builder.get_object('fiscal_store')
		store.clear()
		self.cursor.execute("SELECT id, name FROM fiscal_years "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			fiscal_id = row[0]
			fiscal_name = row[1]
			store.append([str(fiscal_id), fiscal_name])
		self.builder.get_object('combobox2').set_active(0)

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def view_all_checkbutton_toggled (self, checkbutton):
		self.populate_payment_store ()

	def fiscal_combo_changed (self, combo):
		self.populate_payment_store ()

	def populate_payment_store (self):
		self.payment_store.clear()
		total_amount = Decimal()
		fiscal_id = self.builder.get_object('combobox2').get_active_id()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT pay.id, pay.date_inserted, "
								"contacts.name, pay.amount, payment_info(pay.id) "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"WHERE (pay.date_inserted "
								"BETWEEN (SELECT start_date "
									"FROM fiscal_years WHERE id = %s) "
									"AND "
									"(SELECT end_date "
									"FROM fiscal_years WHERE id = %s)) "
								"ORDER BY date_inserted;", (
								fiscal_id, fiscal_id))
		elif self.customer_id != None:
			self.cursor.execute("SELECT pay.id, pay.date_inserted, "
								"contacts.name, pay.amount, payment_info(pay.id) "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"WHERE contacts.id = %s "
								"AND (pay.date_inserted "
								"BETWEEN (SELECT start_date "
									"FROM fiscal_years WHERE id = %s) "
									"AND "
									"(SELECT end_date "
									"FROM fiscal_years WHERE id = %s)) "
								"ORDER BY date_inserted;", (self.customer_id, 
								fiscal_id, fiscal_id))
		for row in self.cursor.fetchall():
			row_id = row[0]
			date = row[1]
			formatted_date = dateutils.datetime_to_text(date)
			contact = row[2]
			amount = row[3]
			payment_text = row[4]
			total_amount += amount
			self.payment_store.append([row_id, str(date), formatted_date,
															contact,
															str(amount),
															payment_text])
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)


		
		