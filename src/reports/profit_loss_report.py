# profit_loss_report.py
#
# Copyright (C) 2019 - reuben rissler
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
from constants import ui_directory, DB
from decimal import Decimal

UI_FILE = ui_directory + "/reports/profit_loss_report.ui"

class ProfitLossReportGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.populate_fiscals ()

		self.account_treestore = self.get_object("profit_loss_store")
		self.window = self.get_object("window")
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_fiscals (self):
		fiscal_store = self.get_object('fiscal_store')
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"ORDER BY name ")
		for account in self.cursor.fetchall():
			fiscal_store.append(account)
		DB.rollback()

	def fiscal_year_combo_changed (self, combobox):
		fiscal_id = combobox.get_active_id()
		if fiscal_id == None:
			return
		self.fiscal = fiscal_id
		self.account_treestore.clear()
		# Revenues first
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE type = 4 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
																name, 
																'0.00'])
			revenue = Decimal()
			for i in self.get_child_accounts(is_parent, number, tree_parent):
				revenue += i[1]
			self.account_treestore.set_value(tree_parent, 2, str(revenue))
		# Expenses next
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE type = 3 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
																name, 
																'0.00'])
			expenses = Decimal()
			for i in self.get_child_accounts(is_parent, number, tree_parent):
				expenses += i[1]
			self.account_treestore.set_value(tree_parent, 2, str(expenses))
		income = revenue - expenses
		self.get_object("income_amount_label").set_label(str(income))
		DB.rollback()

	def get_child_accounts (self, is_parent, parent_account, parent_tree):
		c = DB.cursor()
		if is_parent == True:
			c.execute("SELECT is_parent, number::text, name, 0.00::text "
						"FROM gl_accounts "
						"WHERE parent_number = %s ORDER BY number", 
						(parent_account,))
			for row in c.fetchall():
				account_amount = Decimal()
				is_parent = row[0]
				account_number = row[1]
				account_name = row[2]
				tree_parent = self.account_treestore.append(parent_tree,[
																account_number,
																account_name,
																'0.00'])
				for i in self.get_child_accounts (is_parent, account_number, 
															tree_parent):
					account_amount += i[1]
				self.account_treestore.set_value(tree_parent, 2, str(account_amount))
				yield account_number, account_amount
		else:
			c.execute("SELECT SUM(debits - credits) AS total FROM "
						"(SELECT COALESCE(SUM(amount),0.00) AS debits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE debit_account = %s AND fy.id = %s ) d, "
						"(SELECT COALESCE(SUM(amount),0.00) AS credits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE credit_account = %s AND fy.id = %s ) c" , 
					(parent_account, self.fiscal, parent_account, self.fiscal))
			for row in c.fetchall():
				account_amount = abs(row[0])
				yield parent_account, account_amount
		c.close()

	def report_hub_clicked (self, button):
		treeview = self.get_object('profit_loss_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)
		
	def expand_all_clicked (self, button):
		self.get_object('profit_loss_treeview').expand_all()

	def collapse_all_clicked (self, button):
		self.get_object('profit_loss_treeview').collapse_all()



		