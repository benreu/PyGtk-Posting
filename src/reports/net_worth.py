# net_worth.py
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
import main
from decimal import Decimal

UI_FILE = main.ui_directory + "/reports/net_worth.ui"

class NetWorthGUI(Gtk.Builder):
	def __init__(self, db):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.account_treestore = self.get_object("net_worth_store")
		self.db = db
		self.cursor = self.db.cursor()
		self.populate_net_worth ()

		self.window = self.get_object("window")
		self.window.show_all()

	def populate_net_worth (self):
		# Assets first
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE type = 1 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
																name, 
																'0.00'])
			assets = Decimal()
			for i in self.get_child_accounts(is_parent, number, tree_parent):
				assets += i[1]
			self.account_treestore.set_value(tree_parent, 2, str(assets))
		# Liabilities next
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE type = 5 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
																name, 
																'0.00'])
			liabilities = Decimal()
			for i in self.get_child_accounts(is_parent, number, tree_parent):
				liabilities += i[1]
			self.account_treestore.set_value(tree_parent, 2, str(liabilities))
		# and Equities
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE type = 2 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
																name, 
																'0.00'])
			equities = Decimal()
			for i in self.get_child_accounts(is_parent, number, tree_parent):
				equities += i[1]
			self.account_treestore.set_value(tree_parent, 2, str(equities))
		net_worth = assets - liabilities + equities
		self.get_object("income_amount_label").set_label(str(net_worth))

	def get_child_accounts (self, is_parent, parent_account, parent_tree):
		c = self.db.cursor()
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
							"WHERE debit_account = %s ) d, "
						"(SELECT COALESCE(SUM(amount),0.00) AS credits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"WHERE credit_account = %s ) c" , 
					(parent_account, parent_account))
			for row in c.fetchall():
				account_amount = abs(row[0])
				yield parent_account, account_amount
		c.close()



		