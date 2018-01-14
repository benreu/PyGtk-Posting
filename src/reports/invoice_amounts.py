# invoice_amounts.py
#
# Copyright (C) 2017 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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

UI_FILE = "src/reports/invoice_amounts.ui"


class InvoiceAmountsGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		self.cursor = db.cursor()

		self.invoice_store = self.builder.get_object('invoice_amounts_store')
		self.contact_store = self.builder.get_object('contact_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.customer_id = None
		self.populate_payment_store ()
		self.populate_customer_store ()
		
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

	def populate_customer_store (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT customer_id, contacts.name FROM invoices "
							"JOIN contacts ON invoices.customer_id "
							"= contacts.id "
							"GROUP BY customer_id, contacts.name "
							"ORDER BY contacts.name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			customer_name = row[1]
			self.contact_store.append([str(customer_id), customer_name])

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def view_all_checkbutton_toggled (self, checkbutton):
		self.populate_payment_store ()

	def populate_payment_store (self):
		self.invoice_store.clear()
		total_amount = 0.00
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT i.id, i.name, i.total, "
								"i.date_created, contacts.name "
								"FROM invoices AS i "
								"INNER JOIN contacts "
								"ON i.customer_id = contacts.id "
								"WHERE (posted, canceled) = (True, False) "
								"ORDER BY date_created;")
		elif self.customer_id != None:
			self.cursor.execute("SELECT i.id, i.name, i.total, "
								"i.date_created, contacts.name "
								"FROM invoices AS i "
								"INNER JOIN contacts "
								"ON i.customer_id = contacts.id "
								"WHERE (posted, canceled, contacts.id) = "
								"(True, False, %s) "
								"ORDER BY date_created;", 
								(self.customer_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			invoice_name = row[1]
			invoice_amount = row[2]
			date_created = row[3]
			contact_name = row[4]
			formatted_date = dateutils.datetime_to_text(date_created)
			total_amount += float(invoice_amount)
			self.invoice_store.append([row_id, str(date_created), 
										formatted_date, contact_name,
										str(invoice_amount)])
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)


		
		