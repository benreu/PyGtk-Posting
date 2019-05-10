# deposits.py
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
from dateutils import DateTimeCalendar
from db import transactor
import constants

UI_FILE = constants.ui_directory + "/deposits.ui"


class GUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()

		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect('day-selected', self.day_selected)
		self.date = None
		
		self.deposit_store = self.builder.get_object('checks_to_deposit')
		self.cash_account_store = self.builder.get_object('cash_account_store')
		self.populate_account_stores ()

		amount_column = self.builder.get_object ('treeviewcolumn2')
		amount_renderer = self.builder.get_object ('cellrenderertext2')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def focus (self, window, event):
		self.populate_deposit_store ()

	def amount_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = '{:,.2f}'.format(model.get_value(iter1, 2))
		cellrenderer.set_property("text" , qty)

	def date_entry_icon_released (self, entry, icon, event):
		self.date_calendar.set_relative_to (entry)
		self.date_calendar.show()

	def day_selected (self, calendar):
		self.date = calendar.get_date ()
		day_text = calendar.get_text ()
		self.builder.get_object('entry3').set_text(day_text)
		self.check_if_all_entries_valid ()

	def populate_deposit_store(self):
		self.cursor.execute("SELECT p_i.id, amount, payment_text, customer_id,"
							"name, date_inserted, format_date(date_inserted) "
							"FROM payments_incoming AS p_i "
							"JOIN contacts ON p_i.customer_id = contacts.id "
							"WHERE (check_payment, check_deposited) = "
							"(True, False)")
		tupl = self.cursor.fetchall()
		if len(tupl) != len(self.deposit_store): # something changed; repopulate
			self.deposit_store.clear()
			for check_transaction in tupl:
				transaction_id = check_transaction[0]
				ck_amount = check_transaction[1]
				ck_number = check_transaction[2]
				contact_id = check_transaction[3]
				ck_name = check_transaction[4]
				date = check_transaction[5]
				date_formatted = check_transaction[6]
				self.deposit_store.append([transaction_id, ck_number, 
											float(ck_amount), ck_name, str(date), 
											date_formatted, True])
											
			self.calculate_deposit_total()

	def populate_account_stores (self):
		bank_combo = self.builder.get_object('comboboxtext1')
		bank_id = bank_combo.get_active_id()
		bank_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE deposits = True")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			bank_combo.append(str(account_number), account_name)
		bank_combo.set_active_id(bank_id)
		self.cash_account_store.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE cash_account = True")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.cash_account_store.append([str(account_number), account_name])
		
	def deposit_check_togglebutton_toggled (self, togglebutton, path):
		self.deposit_store[path][6] = not togglebutton.get_active()
		self.calculate_deposit_total ()

	def calculate_deposit_total (self):
		total_money = 0.00
		total_checks = 0
		for row in self.deposit_store:
			if row[6] is True:
				total_money += float(row[2])
				total_checks += 1
		self.builder.get_object('label6').set_label('${:,.2f}'.format(total_money))
		self.builder.get_object('label7').set_label(str(total_checks))
		total_money += self.builder.get_object('spinbutton1').get_value()
		self.builder.get_object('label3').set_label('${:,.2f}'.format(total_money))

	def checking_account_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		button = self.builder.get_object('button1')
		button.set_sensitive(False)
		cash_account = self.builder.get_object('combobox1').get_active()
		cash_amount = self.builder.get_object('spinbutton1').get_value()
		if self.date == None:
			button.set_label('No date selected')
			return
		if cash_amount == 0.00 and cash_account > -1:
			button.set_label('Cash amount is 0.00')
			return
		elif cash_amount > 0.00 and cash_account == -1:
			button.set_label('Cash account not selected')
			return
		if self.builder.get_object('comboboxtext1').get_active() == -1:
			button.set_label('Bank account not selected')
			return
		button.set_label('Process Deposit')
		button.set_sensitive (True)

	def cash_amount_value_changed (self, spinbutton):
		if spinbutton.get_value() == 0.00:
			self.builder.get_object('combobox1').set_active(-1)
		self.check_if_all_entries_valid ()
		self.calculate_deposit_total ()

	def cash_account_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def process_deposit(self, widget):
		d = transactor.Deposit(self.db, self.date)
		total_amount = 0.00
		checking_account = self.builder.get_object('comboboxtext1').get_active_id()
		for row in self.deposit_store:
			if row[6] is True:
				total_amount += float(row[2])
		if total_amount != 0.00:
			d.check (total_amount)
		cash_amount = self.builder.get_object('spinbutton1').get_value()
		if cash_amount != 0.00:
			total_amount += cash_amount
			cash_account = self.builder.get_object('combobox1').get_active_id ()
			d.cash (cash_amount, cash_account)
		deposit_id = d.bank (total_amount, checking_account)
		for row in self.deposit_store:
			if row[6] is True:
				row_id = row[0]
				self.cursor.execute("UPDATE payments_incoming "
									"SET (check_deposited, "
										"gl_entries_deposit_id) = (True, %s) "
									"WHERE id = %s", (deposit_id, row_id))
		self.db.commit()
		self.cursor.close()
		self.window.destroy()

		
		
