# accounts_overview.py
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
from constants import DB, ui_directory

UI_FILE = ui_directory + "/accounts_overview.ui"

class AccountsOverviewGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
		self.populate_account_combos()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_account_combos (self):
		c = DB.cursor()
		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'post_invoice'")
		account = c.fetchone()[0]
		self.builder.get_object('button5').set_label(account)

		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'cash_payment'")
		account = c.fetchone()[0]
		self.builder.get_object('button6').set_label(account)
		
		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'check_payment'")
		account = c.fetchone()[0]
		self.builder.get_object('button7').set_label(account)

		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'credit_card_payment'")
		account = c.fetchone()[0]
		self.builder.get_object('button8').set_label(account)
		
		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'post_purchase_order'")
		account = c.fetchone()[0]
		self.builder.get_object('button10').set_label(account)

		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'sales_tax_canceled'")
		account = c.fetchone()[0]
		self.builder.get_object('button16').set_label(account)

		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'credit_card_penalty'")
		#account = c.fetchone()[0]
		#self.builder.get_object('button17').set_label(account)

		c.execute("SELECT name FROM gl_account_flow "
							"JOIN gl_accounts "
							"ON gl_accounts.number = gl_account_flow.account "
							"WHERE function = 'customer_discount'")
		account = c.fetchone()[0]
		self.builder.get_object('button1').set_label(account)
		c.close()
		DB.rollback()

