# double_entry_transaction.py
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

from gi.repository import Gtk, Gdk, GLib, GObject
from dateutils import DateTimeCalendar
from db.transactor import double_entry_transaction

UI_FILE = "src/double_entry_transaction.ui"


class DoubleEntryTransactionGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		self.contact_id = 0
		self.account_store = self.builder.get_object('account_store')
		self.populate_stores()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_stores (self):
		self.account_store.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE (type = 5 OR type = 1) "
							"AND parent_number IS NULL "
							"ORDER BY number")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			tree_parent = self.account_store.append(None,[account_number, 
																account_name])
			self.get_child_accounts (self.account_store, account_number, tree_parent)

	def get_child_accounts (self, store, parent_number, tree_parent):
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE parent_number = %s", (parent_number,))
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			parent = store.append(tree_parent,[account_number, account_name])
			self.get_child_accounts (store, account_number, parent)

	def check_if_all_requirements_valid (self):
		post_button = self.builder.get_object('button2')
		post_button.set_sensitive(False)
		description = self.builder.get_object('entry2').get_text()
		if self.date == 'None':
			post_button.set_label ('No date selected')
			return # no description
		if description == '':
			post_button.set_label ('No description')
			return # no description
		amount = self.builder.get_object('spinbutton1').get_value()
		if amount == 0.00:
			post_button.set_label ('Amount is $0.00')
			return # no account selected
		credit_selection = self.builder.get_object('treeview-selection3')
		model, path = credit_selection.get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				post_button.set_label('Credit parent account selected')
				return # parent account selected
		else:
			post_button.set_label ('No credit account selected')
			return # no account selected
		debit_selection = self.builder.get_object('treeview-selection2')
		model, path = debit_selection.get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				post_button.set_label('Debit parent account selected')
				return # parent account selected
		else:
			post_button.set_label ('No debit account selected')
			return # no account selected
		post_button.set_sensitive (True)
		post_button.set_label ('Post transaction')

	def debit_row_activate (self, treeview, path, treeviewcolumn):
		self.check_if_all_requirements_valid ()
		account_number = self.account_store[path][0]
		account_name = self.account_store[path][1]
		if str(account_number)[0:1] == '1':
			treeviewcolumn.set_title('%s+'% account_name)
		else:
			treeviewcolumn.set_title('%s-'% account_name)

	def credit_row_activate (self, treeview, path, treeviewcolumn):
		self.check_if_all_requirements_valid ()
		account_number = self.account_store[path][0]
		account_name = self.account_store[path][1]
		if str(account_number)[0:1] == '1':
			treeviewcolumn.set_title('%s-'% account_name)
		else:
			treeviewcolumn.set_title('%s+'% account_name)

	def description_changed (self, entry):
		self.check_if_all_requirements_valid ()

	def amount_value_changed (self, entry):
		self.check_if_all_requirements_valid ()

	def post_transaction_clicked (self, button):
		description = self.builder.get_object('entry2').get_text()
		amount = self.builder.get_object('spinbutton1').get_value()
		#### debit
		debit_selection = self.builder.get_object('treeview-selection2')
		model, path = debit_selection.get_selected_rows()
		debit_account = model[path][0]
		#### credit
		credit_selection = self.builder.get_object('treeview-selection3')
		model, path = credit_selection.get_selected_rows()
		credit_account = model[path][0]
		double_entry_transaction (self.db, self.date, debit_account,
									credit_account, amount, description)
		self.db.commit()
		self.window.destroy()

	def refresh_accounts_clicked (self, button):
		self.populate_stores ()
		self.check_if_all_requirements_valid ()
		debit_title = 'Debit    |    Assets+  Liabilities-'
		self.builder.get_object('treeviewcolumn1').set_title (debit_title)
		credit_title = 'Credit    |    Assets-  Liabilities+'
		self.builder.get_object('treeviewcolumn2').set_title (credit_title)

	def calendar_day_selected(self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)
		self.check_if_all_requirements_valid ()

	def calendar_entry_icon_released(self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()




		