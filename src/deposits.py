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
from decimal import Decimal
from dateutils import DateTimeCalendar
from db import transactor
from constants import ui_directory, DB

UI_FILE = ui_directory + "/deposits.ui"


class GUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect('day-selected', self.day_selected)
		self.date = None
		
		self.deposit_store = self.builder.get_object('checks_to_deposit_store')
		self.cash_account_store = self.builder.get_object('cash_account_store')
		self.populate_account_stores ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.check_if_all_entries_valid()

	def destroy (self, widget):
		self.cursor.close()

	def focus (self, window, event):
		self.populate_deposit_store ()

	def date_entry_icon_released (self, entry, icon, event):
		self.date_calendar.set_relative_to (entry)
		self.date_calendar.show()

	def day_selected (self, calendar):
		self.date = calendar.get_date ()
		day_text = calendar.get_text ()
		self.builder.get_object('entry3').set_text(day_text)
		self.check_if_all_entries_valid ()

	def populate_deposit_store(self):
		self.cursor.execute("SELECT p_i.id, payment_text, "
							"amount, amount::text, customer_id, c.name, "
							"date_inserted::text, format_date(date_inserted), deposit "
							"FROM payments_incoming AS p_i "
							"JOIN contacts AS c ON p_i.customer_id = c.id "
							"WHERE (check_payment, check_deposited) = "
							"(True, False)")
		tupl = self.cursor.fetchall()
		if len(tupl) != len(self.deposit_store): # something changed; repopulate
			self.deposit_store.clear()
			for row in tupl:
				self.deposit_store.append(row)
			self.calculate_deposit_total()
		DB.rollback()

	def populate_account_stores (self):
		bank_combo = self.builder.get_object('comboboxtext1')
		bank_id = bank_combo.get_active_id()
		bank_combo.remove_all()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE deposits = True")
		for row in self.cursor.fetchall():
			bank_combo.append(row[0], row[1])
		bank_combo.set_active_id(bank_id)
		self.cash_account_store.clear()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE cash_account = True")
		for row in self.cursor.fetchall():
			self.cash_account_store.append(row)
		DB.rollback()
		
	def deposit_check_togglebutton_toggled (self, togglebutton, path):
		active = not togglebutton.get_active()
		self.deposit_store[path][8] = active
		row_id = self.deposit_store[path][0]
		self.cursor.execute("UPDATE payments_incoming SET deposit = %s "
							"WHERE id = %s", (active, row_id))
		DB.commit()
		self.calculate_deposit_total ()

	def calculate_deposit_total (self):
		amount = Decimal()
		total_checks = 0
		for row in self.deposit_store:
			if row[8] is True:
				amount += Decimal(row[3])
				total_checks += 1
		self.builder.get_object('label6').set_label('${:,.2f}'.format(amount))
		self.builder.get_object('label7').set_label(str(total_checks))
		amount += Decimal(self.builder.get_object('spinbutton1').get_text())
		self.builder.get_object('label3').set_label('${:,.2f}'.format(amount))

	def checking_account_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		label = self.builder.get_object('info_label')
		label.set_visible(True)
		self.builder.get_object('box3').set_visible(False)
		cash_account = self.builder.get_object('combobox1').get_active()
		cash_amount = self.builder.get_object('spinbutton1').get_value()
		if self.date == None:
			label.set_label('No date selected')
			return
		if cash_amount == 0.00 and cash_account > -1:
			label.set_label('Cash amount is 0.00')
			return
		elif cash_amount > 0.00 and cash_account == -1:
			label.set_label('Cash account not selected')
			return
		if self.builder.get_object('comboboxtext1').get_active() == -1:
			label.set_label('Bank account not selected')
			return
		label.set_visible(False)
		self.builder.get_object('box3').set_visible (True)
		self.builder.get_object('box3').set_sensitive (True)

	def cash_amount_value_changed (self, spinbutton):
		if spinbutton.get_value() == 0.00:
			self.builder.get_object('combobox1').set_active(-1)
		self.check_if_all_entries_valid ()
		self.calculate_deposit_total ()

	def cash_account_combo_changed (self, combo):
		self.check_if_all_entries_valid ()

	def get_deposit_total (self):
		amount = Decimal()
		for row in self.deposit_store:
			if row[8] is True:
				amount += Decimal(row[3])
		return amount

	def process_deposit(self):
		d = transactor.Deposit(self.date)
		checking_account = self.builder.get_object('comboboxtext1').get_active_id()
		amount = self.get_deposit_total()
		if amount != 0.00:
			d.check (amount)
		cash_amount = self.builder.get_object('spinbutton1').get_value()
		if cash_amount != 0.00:
			amount += cash_amount
			cash_account = self.builder.get_object('combobox1').get_active_id ()
			d.cash (cash_amount, cash_account)
		deposit_id = d.bank (amount, checking_account)
		for row in self.deposit_store:
			if row[8] is True:
				row_id = row[0]
				self.cursor.execute("UPDATE payments_incoming "
									"SET (check_deposited, "
										"gl_entries_deposit_id) = (True, %s) "
									"WHERE id = %s", (deposit_id, row_id))
		DB.commit()

	def process_deposit_close_window_clicked (self, button):
		self.builder.get_object('box3').set_sensitive(False)
		self.process_deposit()
		self.window.destroy()

	def process_deposit_new_clicked (self, button):
		self.builder.get_object('box3').set_sensitive(False)
		self.process_deposit()
		self.populate_deposit_store()



