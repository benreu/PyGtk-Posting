# bank_statements.py
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
from constants import ui_directory, db, broadcaster

UI_FILE = ui_directory + "/reports/bank_statements.ui"

class BankStatementsGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.bank_account_store = self.builder.get_object('bank_account_store')
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE deposits = True")
		for row in self.cursor.fetchall():
			self.bank_account_store.append(row)
		self.statement_store = self.builder.get_object('statement_store')
		self.account_number = None

		window = self.builder.get_object('window1')
		window.show_all()
		
	def grouped_checkbutton_toggled (self, checkbutton):
		if self.account_number != None:
			self.populate_bank_statement_store ()

	def bank_account_combo_changed (self, combobox):
		account_number = combobox.get_active_id()
		if account_number != None:
			self.cursor.execute("CREATE OR REPLACE TEMP VIEW "
							"bank_statement_view AS "
							"WITH account_numbers AS "
								"(SELECT number FROM gl_accounts "
								"WHERE number = %s OR parent_number = %s"
								") "
								"SELECT id, amount, debit_account, "
								"credit_account, check_number, date_inserted, "
								"reconciled, transaction_description, "
								"date_reconciled, TRUE AS debit, FALSE AS credit "
								"FROM gl_entries WHERE debit_account "
								"IN (SELECT * FROM account_numbers) "
								"UNION "
								"SELECT id, amount, debit_account, "
								"credit_account, check_number, date_inserted, "
								"reconciled, transaction_description, "
								"date_reconciled, FALSE AS debit, TRUE AS credit "
								"FROM gl_entries WHERE credit_account "
								"IN (SELECT * FROM account_numbers)"
								, (account_number, account_number))
			self.account_number = account_number
			self.populate_bank_statement_store ()

	def populate_bank_statement_store (self):
		self.statement_store.clear()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.populate_statement_threaded ()
		else:
			self.populate_statement ()

	def populate_statement (self):
		self.cursor.execute("SELECT ge.id, "
							"COALESCE(ge.check_number::text, ''), "
							"ge.date_inserted::text, "
							"format_date(ge.date_inserted), "
							"CASE WHEN contacts.name IS NOT NULL "
								"THEN contacts.name "
								"ELSE transaction_description END, "
							"reconciled, "
							"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
							"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
							"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
							"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END "
							"FROM bank_statement_view AS ge "
							"LEFT JOIN payments_incoming AS pi "
							"ON ge.id = pi.gl_entries_id "
							"LEFT JOIN contacts ON contacts.id = "
							"pi.customer_id "
							"WHERE date_reconciled IS NOT NULL "
							"ORDER BY date_inserted;", 
							(self.account_number, self.account_number))
		for row in self.cursor.fetchall():
			self.statement_store.append(None, row)

	def populate_statement_threaded (self):
		previous_date = None
		self.cursor.execute("SELECT ge.id, "
							"COALESCE(ge.check_number::text, ''), "
							"ge.date_inserted::text, "
							"format_date(ge.date_inserted), "
							"CASE WHEN contacts.name IS NOT NULL "
								"THEN contacts.name "
								"ELSE transaction_description END, "
							"reconciled, "
							"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
							"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
							"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
							"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
							"ge.date_reconciled "
							"FROM bank_statement_view AS ge "
							"LEFT JOIN payments_incoming AS pi "
							"ON ge.id = pi.gl_entries_id "
							"LEFT JOIN contacts ON contacts.id = "
							"pi.customer_id "
							"WHERE date_reconciled IS NOT NULL "
							"ORDER BY date_reconciled, date_inserted;", 
							(self.account_number, self.account_number))
		for row in self.cursor.fetchall():
			if row[8] != previous_date:
				parent = self.statement_store.append(None, [0, 
															'', 
															row[2], 
															row[3], 
															'', 
															False, 
															'', 
															0.00, 
															'', 
															0.00])
				previous_date = row[8]
			self.statement_store.append(parent, [	row[0], 
													row[1], 
													row[2], 
													row[3], 
													row[4], 
													row[5], 
													row[6], 
													row[7],
													row[8],
													row[9]
												])
			




		



		
