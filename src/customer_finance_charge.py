# customer_finance_charge.py
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
import subprocess
from datetime import datetime
import constants

UI_FILE = constants.ui_directory + "/customer_finance_charge.ui"

class CustomerFinanceChargeGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()

		self.customer_id = None

		self.customer_store = self.builder.get_object('customer_store')
		self.finance_charge_store = self.builder.get_object('finance_charge_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.customer_combobox_populate ()
				
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def help_button_clicked (self, widget):
		subprocess.Popen(["yelp", constants.help_dir + "/finance_charge.page"])

	def payment_window(self, widget):
		import customer_payment
		customer_payment.GUI(customer_id = self.customer_id )

	def print_statement_clicked(self, button):
		statement = statementing.Setup(self.db, self.finance_charge_store, 
										self.customer_id, datetime.today(), 
										self.customer_total)
		statement.print_dialog(self.window)
		self.customer_combobox_populate ()
		self.finance_charge_store.clear()
		self.builder.get_object('combobox-entry').set_text("")

	def view_statement_clicked (self, button):
		statement = statementing.Setup(self.db, self.finance_charge_store, 
										self.customer_id, datetime.today(), 
										self.customer_total)
		statement.view()

	def customer_combobox_populate(self):
		self.customer_store.clear()
		c = self.db.cursor()
		c.execute("WITH table2 AS "
					"( "
					"SELECT id, "
						"(SELECT COALESCE(SUM(amount_due), 0.0) " 
						"AS invoices_total FROM invoices  "
						"WHERE (canceled, posted, customer_id) = "
						"(False, True, c.id)),  "
						"(SELECT amount + amount_owed AS payments_total FROM "
							"(SELECT COALESCE(SUM(amount), 0.0) AS amount "
							"FROM payments_incoming "
							"WHERE (customer_id, misc_income) = (c.id, False)"
							") pi, "
							"(SELECT COALESCE(SUM(amount_owed), 0.0) "
								" AS amount_owed "
							"FROM credit_memos WHERE (customer_id, posted) "
								"= (c.id, True)"
							") cm "
						"), "
					"name, ext_name FROM contacts AS c "
					"WHERE customer = True ORDER by name"
					") "
					"SELECT  "
						"id::text, "
						"name, "
						"ext_name, "
						"(invoices_total - payments_total)::money "
							"AS balance_due, "
						"((invoices_total - payments_total) * "
							"(SELECT finance_rate FROM settings))::money "
								"AS finance_fee "
					"FROM table2 "
					"WHERE (invoices_total-payments_total) > 0  "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.customer_store.append(row)
		c.close()

	def focus (self, window, event):
		self.customer_combobox_populate ()
		if self.customer_id != None:
			self.populate_finance_charge_store()

	def customer_combobox_changed(self, combo): #updates the customer
		active = self.builder.get_object('combobox1').get_active()
		if active == -1:
			return
		self.customer_id = self.customer_store[active][0]
		self.customer_total = self.customer_store[active][3]
		self.builder.get_object('label2').set_label (str(self.customer_total))
		self.populate_finance_charge_store()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def customer_match_selected(self, completion, model, iter):
		customer_id = model[iter][0]
		self.builder.get_object('combobox1').set_active_id (customer_id)

	def populate_finance_charge_store (self):
		self.finance_charge_store.clear()
		c_id = self.customer_id
		self.cursor.execute("SELECT "
								"id::text, "
								"name, "
								"dated_for::text AS date, "
								"format_date(dated_for), "
								"amount_due, "
								"amount_due::text "
							"FROM invoices "
							"WHERE (canceled, posted, customer_id) = "
							"(False, True, %s) "
							"AND paid = False "
							"ORDER BY date", 
							(c_id, ))
		for row in self.cursor.fetchall():
			self.finance_charge_store.append(row)
		self.builder.get_object('button3').set_sensitive(True)


		

