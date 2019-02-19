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

class DepositsGUI(Gtk.Builder):
	def __init__(self, db):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()

		self.deposit_store = self.get_object('deposit_store')
		self.treeview = self.get_object('treeview1')
		self.populate_deposits_store ()

		window = self.get_object('window1')
		window.show_all()

	def populate_deposits_store (self):
		self.cursor.execute ("SELECT "
								"gl_entries.id, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"gl_entries.amount::float, "
								"gl_entries.amount::text, "
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
									"amount::float, "
									"amount::text, "
									"payment_text, "
									"c.name "
								"FROM payments_incoming AS p "
								"JOIN contacts AS c ON c.id = p.customer_id "
								"WHERE gl_entries_deposit_id = %s", (row_id,))
			for row in self.cursor.fetchall():
				self.deposit_store.append(parent, row)

	def export_to_pdf_activated (self, menuitem):
		from reports import export_to_pdf
		export_to_pdf.ExportToPdfGUI(self.treeview)
		
	def collapse_all_activated (self, menuitem):
		self.treeview.collapse_all()

	def expand_all_activated (self, menuitem):
		self.treeview.expand_all()





