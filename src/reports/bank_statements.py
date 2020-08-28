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
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/reports/bank_statements.ui"

class BankStatementsGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.date_filter = ''
		self.bank_account_store = self.builder.get_object('bank_account_store')
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE deposits = True")
		for row in self.cursor.fetchall():
			self.bank_account_store.append(row)
		self.reconcile_date_store = self.builder.get_object('reconcile_date_store')
		self.cursor.execute("WITH bank_accounts AS "
							"(SELECT number FROM gl_accounts "
							"WHERE deposits = True) "
							"SELECT date_reconciled::text AS date_sort, "
							"format_date(date_reconciled) AS date_format "
							"FROM gl_entries AS ge "
							"WHERE ge.debit_account IN "
							"(SELECT number FROM bank_accounts) "
							"OR ge.credit_account IN "
							"(SELECT number FROM bank_accounts) "
							"UNION "
							"SELECT '0' AS date_sort, 'All'  AS date_format "
							"GROUP BY date_sort "
							"ORDER BY date_sort")
		for row in self.cursor.fetchall():
			self.reconcile_date_store.append(row)
		DB.rollback()
		self.statement_store = self.builder.get_object('statement_store')
		self.account_number = None

		window = self.builder.get_object('window1')
		window.show_all()
		
	def destroy (self, widget):
		self.cursor.close()

	def collapse_all_activated (self, menuitem):
		self.builder.get_object('treeview1').collapse_all()

	def expand_all_activated (self, menuitem):
		self.builder.get_object('treeview1').expand_all()

	def report_hub_activated (self, button):
		treeview = self.builder.get_object('treeview1')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def reconcile_date_match_selected (self, completion, model, treeiter):
		date_filter = model[treeiter][0]
		if date_filter == '0':
			self.date_filter = ""
		else:
			self.date_filter = "AND date_reconciled = '%s'" % date_filter
		text = model[treeiter][1]
		self.builder.get_object('reconcile_date_combo_entry').set_text(text)
		self.populate_bank_statement_store()
		return True # do not update the combobox entry text by default

	def reconcile_date_combo_changed (self, combobox):
		treeiter = combobox.get_active_iter()
		if treeiter == None:
			return
		model = combobox.get_model()
		date_filter = model[treeiter][0]
		if date_filter == '0':
			self.date_filter = ""
		else:
			self.date_filter = "AND date_reconciled = '%s'" % date_filter
		self.populate_bank_statement_store()

	def radiobutton_toggled (self, radiobutton):
		# only load one time (filter by the radiobutton being active)
		if radiobutton.get_active() and self.account_number:
			self.populate_bank_statement_store()

	def bank_account_combo_changed (self, combobox):
		account_number = combobox.get_active_id()
		if account_number == None:
			return
		c = DB.cursor()
		c.execute("CREATE OR REPLACE TEMP VIEW "
					"bank_statement_report_view AS "
					"WITH account_numbers AS "
						"(SELECT number FROM gl_accounts "
						"WHERE number = %s OR parent_number = %s"
						") "
						"SELECT id, amount, debit_account, "
						"credit_account, check_number, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, TRUE AS debit, FALSE AS credit, "
						"gl_transaction_id "
						"FROM gl_entries WHERE debit_account "
						"IN (SELECT * FROM account_numbers) "
						"UNION "
						"SELECT id, amount, debit_account, "
						"credit_account, check_number, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, FALSE AS debit, TRUE AS credit, "
						"gl_transaction_id "
						"FROM gl_entries WHERE credit_account "
						"IN (SELECT * FROM account_numbers)"
						, (account_number, account_number))
		c.close()
		DB.commit()
		self.account_number = account_number
		self.populate_bank_statement_store ()

	def populate_bank_statement_store (self):
		if not self.account_number:
			return
		treeview = self.builder.get_object('treeview1')
		treeview.set_model(None)
		self.statement_store.clear()
		if self.builder.get_object('radiobutton_single').get_active():
			self.populate_statement ()
		elif self.builder.get_object('radiobutton_grouped').get_active():
			self.populate_statement_grouped ()
		elif self.builder.get_object('radiobutton_linked').get_active():
			self.populate_statement_linked ()
		DB.rollback()
		treeview.set_model(self.statement_store)

	def populate_statement (self):
		c = DB.cursor()
		c.execute("SELECT ge.id, "
					"COALESCE(ge.check_number::text, ''), "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN contacts.name IS NOT NULL "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"ge.gl_transaction_id "
					"FROM bank_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					"WHERE date_reconciled IS NOT NULL %s "
					"ORDER BY date_inserted" % 
					(self.date_filter,))
		for row in c.fetchall():
			self.statement_store.append(None, row)
		c.close()

	def populate_statement_grouped (self):
		previous_date = None
		c = DB.cursor()
		c.execute("SELECT ge.id, "
					"COALESCE(ge.check_number::text, ''), "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN contacts.name IS NOT NULL "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"ge.gl_transaction_id "
					"FROM bank_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					"WHERE date_reconciled IS NOT NULL %s "
					"ORDER BY date_reconciled, date_inserted" %
					(self.date_filter,))
		for row in c.fetchall():
			current_date = row[6]
			if current_date != previous_date:
				parent = self.statement_store.append(None, [0, 
															'', 
															row[2], 
															row[3], 
															'', 
															False, 
															'',
															'',
															'', 
															0.00, 
															'', 
															0.00,
															0])
				previous_date = current_date
			self.statement_store.append(parent, row)
		c.close()

	def populate_statement_linked (self):
		c = DB.cursor()
		c.execute("SELECT ge.id, "
					"COALESCE(ge.check_number::text, ''), "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN contacts.name IS NOT NULL "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"ge.gl_transaction_id "
					"FROM bank_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					"WHERE date_reconciled IS NOT NULL %s "
					"ORDER BY date_inserted" %
					(self.date_filter,))
		for row in c.fetchall():
			parent = self.statement_store.append(None, row)
			entry_id = row[0]
			tx_id = row[12]
			c.execute("SELECT ge.id, "
						"COALESCE(ge.check_number::text, ''), "
						"ge.date_inserted::text, "
						"format_date(ge.date_inserted), "
						"ga.name, "
						"reconciled, "
						"ge.date_reconciled::text, "
						"format_date(ge.date_reconciled), "
						"CASE WHEN ge.credit_account IS NOT NULL "
							"THEN ge.amount::text ELSE '' END, "
						"CASE WHEN ge.credit_account IS NOT NULL "
							"THEN ge.amount ELSE 0.00 END, "
						"CASE WHEN ge.debit_account IS NOT NULL "
							"THEN ge.amount::text ELSE '' END, "
						"CASE WHEN ge.debit_account IS NOT NULL "
							"THEN ge.amount ELSE 0.00 END, "
						"ge.gl_transaction_id "
						"FROM gl_entries AS ge "
						"JOIN gl_accounts AS ga "
							"ON ga.number = ge.credit_account "
							"OR ga.number = ge.debit_account "
						"WHERE ge.id != %s AND ge.gl_transaction_id = %s "
						"UNION "
						# handle POs with special treatment
						"SELECT 0, "
						"'', "
						"'', "
						"'', "
						"ga.name, "
						"False, "
						"'', "
						"'', "
						"'', "
						"0.00, "
						"SUM(ge.amount)::text, "
						"SUM(ge.amount), "
						"0 "
						"FROM purchase_orders AS po "
						"JOIN purchase_order_line_items AS poli "
							"ON poli.purchase_order_id = po.id "
						"JOIN gl_entries AS ge "
							"ON ge.id = poli.gl_entries_id "
						"JOIN gl_accounts AS ga "
							"ON ga.number = ge.debit_account "
						"WHERE po.gl_transaction_payment_id = %s "
						"GROUP BY ga.name "
						"ORDER BY date_inserted",
						(entry_id, tx_id, tx_id))
			for row in c.fetchall():
				self.statement_store.append(parent, row)
		c.close()





