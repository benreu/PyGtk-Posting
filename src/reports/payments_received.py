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
import main

UI_FILE = main.ui_directory + "/reports/payments_received.ui"



class PaymentsReceivedGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = main.db
		self.cursor = self.db.cursor()

		self.treeview = self.builder.get_object('treeview1')
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
		self.cursor.execute("SELECT customer_id::text, name "
							"FROM payments_incoming "
							"JOIN contacts ON payments_incoming.customer_id "
							"= contacts.id "
							"GROUP BY customer_id, name "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		store = self.builder.get_object('fiscal_store')
		store.clear()
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		self.builder.get_object('combobox2').set_active(0)

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.builder.get_object('checkbutton2').set_active(False)
		self.customer_id = customer_id
		self.populate_payment_store ()

	def view_all_checkbutton_toggled (self, checkbutton):
		self.populate_payment_store ()

	def fiscal_combo_changed (self, combo):
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def populate_payment_store (self):
		if self.builder.get_object('checkbutton2').get_active() == True:
			self.populate_payments_all_customers ()
		else:
			self.populate_payment_by_customer ()

	def populate_payments_all_customers (self):
		self.payment_store.clear()
		total_amount = Decimal()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_info(pay.id) "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"ORDER BY date_inserted;")
		else:
			fiscal_id = self.builder.get_object('combobox2').get_active_id()
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_info(pay.id) "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"WHERE (pay.date_inserted "
								"BETWEEN (SELECT start_date "
									"FROM fiscal_years WHERE id = %s) "
									"AND "
									"(SELECT end_date "
									"FROM fiscal_years WHERE id = %s)) "
								"ORDER BY date_inserted;", 
								(fiscal_id, fiscal_id))
		for row in self.cursor.fetchall():
			total_amount += row[4]
			self.payment_store.append(row)
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)

	def populate_payment_by_customer (self):
		if self.customer_id == None:
			return
		self.payment_store.clear()
		total_amount = Decimal()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_info(pay.id) "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"WHERE contacts.id = %s "
								"ORDER BY date_inserted;", (self.customer_id,))
		else:
			fiscal_id = self.builder.get_object('combobox2').get_active_id()
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_info(pay.id) "
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
			total_amount += row[4]
			self.payment_store.append(row)
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)

	def report_hub_activated (self, menuitem):
		from reports import report_hub
		report_hub.ReportHubGUI(self.treeview)



