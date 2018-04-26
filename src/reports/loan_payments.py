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

UI_FILE = "src/reports/loan_payments.ui"

class LoanPaymentsGUI:
	def __init__(self, db):

		self.db = db
		self.cursor = db.cursor()

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.loan_payment_store = self.builder.get_object('loan_payments_store')
		self.contact_store = self.builder.get_object('contacts_store')
		self.populate_contacts ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_contacts (self):
		self.cursor.execute("SELECT contacts.id, name "
							"FROM gl_entries "
							"JOIN contacts "
							"ON gl_entries.contact_id "
							"= contacts.id WHERE loan_payment = True "
							"GROUP BY contacts.id, name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			self.contact_store.append ([str(contact_id), contact_name])

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id ()
		if contact_id != None :
			self.contact_id = contact_id
			self.populate_loan_payments()

	def populate_loan_payments (self):
		self.loan_payment_store.clear()
		self.cursor.execute("SELECT "
								"contact_id, "
								"name, "
								"date_inserted::text, "
								"format_date(date_inserted) "
							"FROM gl_entries AS acl "
							"JOIN contacts ON contacts.id = acl.contact_id "
							"WHERE contact_id = %s "
							"GROUP BY contact_id, name, date_inserted", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			date = row[2]
			formatted_date = row[3]
			parent = self.loan_payment_store.append(None, [0, contact_name, '', '', '', date, formatted_date])
			self.cursor.execute("SELECT name, amount, debit_account, "
								"credit_account, date_inserted::text "
								"FROM gl_entries "
								"JOIN contacts "
								"ON gl_entries.contact_id = "
								"contacts.id WHERE (contact_id, date_inserted) "
								"= (%s, %s)", 
								(contact_id, date))
			for row in self.cursor.fetchall():
				self.loan_payment_store.append(parent, [0, '', '', '', '', date, formatted_date])


			

		