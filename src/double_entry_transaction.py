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

from gi.repository import Gtk
from dateutils import DateTimeCalendar
from decimal import Decimal
from db.transactor import DoubleEntryTransaction
from constants import DB, ui_directory 

UI_FILE = ui_directory + "/double_entry_transaction.ui"
TWO_PLACES = Decimal('0.01')

class DoubleEntryTransactionGUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		self.account_store = self.get_object('account_store')
		self.populate_stores()
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_stores (self):
		self.account_store.clear()
		self.cursor.execute("SELECT number, name, ' / '||name FROM gl_accounts "
							"WHERE parent_number IS NULL "
							"ORDER BY number")
		for row in self.cursor.fetchall():
			iter_ = self.account_store.append(None, row)
			self.get_child_accounts (row[0], row[2], iter_)
		DB.rollback()

	def get_child_accounts (self, account_number, account_path, parent):
		self.cursor.execute("SELECT number, name, ' / '||name FROM gl_accounts "
							"WHERE parent_number = %s ORDER BY name", 
							(account_number,))
		for row in self.cursor.fetchall():
			path = account_path + row[2]
			iter_ = self.account_store.append(parent, [row[0], row[1], path])
			self.get_child_accounts (row[0], path, iter_)

	def check_if_all_requirements_valid (self):
		post_button = self.get_object('button2')
		post_button.set_sensitive(False)
		description = self.get_object('entry2').get_text()
		if self.date == None:
			post_button.set_label ('No date selected')
			return # no date selected
		if description == '':
			post_button.set_label ('No description')
			return # no description
		store = self.get_object('debit_store')
		debit_amount = Decimal()
		for row in store:
			if Decimal(row[0]) == Decimal(0):
				post_button.set_label ('0.00 debit amount')
				return # zero amount
			if row[1] == 0:
				post_button.set_label ('Debit account not selected')
				return # account not selected
			debit_amount += Decimal(row[0])
		store = self.get_object('credit_store')
		credit_amount = Decimal()
		for row in store:
			if Decimal(row[0]) == Decimal(0):
				post_button.set_label ('0.00 credit amount')
				return # zero amount
			if row[1] == 0:
				post_button.set_label ('Credit account not selected')
				return # account not selected
			credit_amount += Decimal(row[0])
		if debit_amount != credit_amount:
			post_button.set_label ('Credit and debit do not match')
			return # credit and debit amount do not match
		if debit_amount == Decimal(0):
			post_button.set_label ('No rows added')
			return # credit and debit amount do not match
		post_button.set_sensitive (True)
		post_button.set_label ('Post transaction')

	def add_debit_row_clicked (self, button):
		store = self.get_object('debit_store')
		iter_ = store.append(['0.00', 0, 'Select account', 'No account'])
		self.get_object('treeview-selection2').select_iter(iter_)
		self.check_if_all_requirements_valid ()

	def delete_debit_row_clicked (self, button):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		model.remove(model.get_iter(path))
		self.check_if_all_requirements_valid ()

	def debit_combo_changed (self, cellrenderercombo, path, treeiter):
		account_number = self.account_store[treeiter][0]
		account_name = self.account_store[treeiter][1]
		account_path = self.account_store[treeiter][2]
		account_string = str(account_number)
		if account_string.startswith('1'):
			operand = ' +'
		elif account_string.startswith('2'):
			operand = ' +'
		elif account_string.startswith('3'):
			operand = ' +'
		elif account_string.startswith('4'):
			operand = ' -'
		elif account_string.startswith('5'):
			operand = ' -'
		store = self.get_object('debit_store')
		store[path][1] = account_number
		store[path][2] = account_name + operand
		store[path][3] = account_path
		self.check_if_all_requirements_valid ()

	def debit_amount_edited (self, cellrenderertext, path, text):
		store = self.get_object('debit_store')
		store[path][0] = str(Decimal(text).quantize(TWO_PLACES))
		amount = Decimal()
		for row in store:
			amount += Decimal(row[0])
		self.get_object('debit_total_label').set_label('${:,.2f}'.format(amount))
		self.check_if_all_requirements_valid ()

	def debit_amount_editing_started (self, cellrenderer, spinbutton, path):
		spinbutton.set_numeric(True)

	def credit_amount_editing_started (self, cellrenderer, spinbutton, path):
		spinbutton.set_numeric(True)

	def add_credit_row_clicked (self, button):
		store = self.get_object('credit_store')
		iter_ = store.append(['0.00', 0, 'Select account', 'No account'])
		self.get_object('treeview-selection3').select_iter(iter_)
		self.check_if_all_requirements_valid ()

	def delete_credit_row_clicked (self, button):
		selection = self.get_object('treeview-selection3')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		model.remove(model.get_iter(path))
		self.check_if_all_requirements_valid ()

	def credit_combo_changed (self, cellrenderercombo, path, treeiter):
		account_number = self.account_store[treeiter][0]
		account_name = self.account_store[treeiter][1]
		account_path = self.account_store[treeiter][2]
		account_string = str(account_number)
		if account_string.startswith('1'):
			operand = ' -'
		elif account_string.startswith('2'):
			operand = ' -'
		elif account_string.startswith('3'):
			operand = ' -'
		elif account_string.startswith('4'):
			operand = ' +'
		elif account_string.startswith('5'):
			operand = ' +'
		store = self.get_object('credit_store')
		store[path][1] = account_number
		store[path][2] = account_name + operand
		store[path][3] = account_path
		self.check_if_all_requirements_valid ()

	def credit_amount_edited (self, cellrenderertext, path, text):
		store = self.get_object('credit_store')
		store[path][0] = str(Decimal(text).quantize(TWO_PLACES))
		amount = Decimal()
		for row in store:
			amount += Decimal(row[0])
		self.get_object('credit_total_label').set_label('${:,.2f}'.format(amount))
		self.check_if_all_requirements_valid ()

	def description_changed (self, entry):
		self.check_if_all_requirements_valid ()

	def post_transaction_clicked (self, button):
		description = self.get_object('entry2').get_text()
		det = DoubleEntryTransaction (self.date, description)
		#### debit
		debit_store = self.get_object('debit_store')
		for row in debit_store:
			amount = row[0]
			account_number = row[1]
			det.post_debit_entry(amount, account_number)
		#### credit
		credit_store = self.get_object('credit_store')
		for row in credit_store:
			amount = row[0]
			account_number = row[1]
			det.post_credit_entry(amount, account_number)
		DB.commit()
		self.window.destroy()

	def refresh_accounts_clicked (self, button):
		self.populate_stores ()
		self.check_if_all_requirements_valid ()

	def calendar_day_selected(self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry1').set_text(day_text)
		self.check_if_all_requirements_valid ()

	def calendar_entry_icon_released(self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()





