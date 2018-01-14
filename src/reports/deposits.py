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
from dateutils import datetime_to_text 

UI_FILE = "src/reports/deposits.ui"

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

	def populate_deposits_store (self):
		self.cursor.execute ("SELECT gl_entries.id, gl_entries.amount, gl_accounts.name, date_inserted FROM gl_entries "
							"JOIN gl_accounts ON gl_accounts.number = gl_entries.debit_account "
							"WHERE gl_entries.id IN "
								"(SELECT gl_entries_deposit_id FROM payments_incoming "
								"GROUP BY gl_entries_deposit_id ) "
							"ORDER BY date_inserted")
		for row in self.cursor.fetchall():
			row_id = row[0]
			amount = row[1]
			account_name = row[2]
			date = row[3]
			date_formatted = datetime_to_text(date)
			parent = self.deposit_store.append(None,[row_id, str(date), 
												date_formatted, float(amount), 
												account_name, ""])
			self.cursor.execute("SELECT p.id, amount, payment_text, "
								"date_inserted, c.name "
								"FROM payments_incoming AS p "
								"JOIN contacts AS c ON c.id = p.customer_id "
								"WHERE gl_entries_deposit_id = %s", (row_id,))
			for row in self.cursor.fetchall():
				payment_id = row[0]
				amount = row[1]
				text = row[2]
				date = row[3]
				customer_name = row[4]
				date_formatted = datetime_to_text(date)
				self.deposit_store.append(parent,[payment_id, str(date), 
												date_formatted, float(amount), 
												text, customer_name])




		



		