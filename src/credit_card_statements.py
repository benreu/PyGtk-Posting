# credit_card_statements.py
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

from gi.repository import Gtk, GLib
import psycopg2
from db import transactor
from dateutils import DateTimeCalendar
from constants import ui_directory, DB

UI_FILE = ui_directory + "/credit_card_statements.ui"

class CreditCardStatementGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.transactions_store = self.builder.get_object('transactions_store')
		self.income_expense_accounts_store = self.builder.get_object(
									'income_expense_accounts_store')
		self.fees_rewards_store = self.builder.get_object(
									'fees_rewards_description_store')

		self.credit_card_account = None
		self.date = None
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)

		self.populate_accounts_combo ()
				
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def focus (self, window, event):
		pass

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def populate_accounts_combo(self):
		credit_card_store = self.builder.get_object('credit_card_store')
		credit_card_store.clear()
		self.cursor.execute("SELECT number, name, "
							"(SELECT COALESCE(SUM(amount), 0.00) FROM gl_entries "
							"WHERE credit_account = gla.number) "
							"- "
							"(SELECT COALESCE(SUM(amount), 0.00) FROM gl_entries "
							"WHERE debit_account = gla.number) "
							"FROM gl_accounts AS gla "
							"WHERE credit_card_account = True")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			amount = row[2]
			credit_card_store.append([str(number), name, str(amount)])
		###################################################
		checking_account_combo = self.builder.get_object('comboboxtext4')
		active_account = checking_account_combo.get_active_id()
		checking_account_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE bank_account = True")
		for i in self.cursor.fetchall():
			number = i[0]
			name = i[1]
			checking_account_combo.append(str(number), name)
		checking_account_combo.set_active_id (active_account)
		####################################################
		self.fees_rewards_store.clear()
		self.cursor.execute("SELECT DISTINCT transaction_description "
							"FROM gl_entries "
							"WHERE fees_rewards = True")
		for row in self.cursor.fetchall():
			description = row[0]
			self.fees_rewards_store.append([description])
		####################################################
		self.income_expense_accounts_store.clear()
		self.cursor.execute("SELECT number, name, type FROM gl_accounts "
							"WHERE (type = 3 OR type = 4) "
							"AND parent_number IS NULL ORDER BY name")
		for row in self.cursor.fetchall():
			account_number = str(row[0])
			account_name = row[1]
			account_type = row[2]
			p = self.income_expense_accounts_store.append(None, 
														[account_number, 
														account_name, 
														account_type])
			self.get_child_accounts(account_number, p)

	def get_child_accounts (self, number, parent):
		self.cursor.execute("SELECT number, name, type FROM gl_accounts WHERE "
							"parent_number = %s", (number,))
		for row in self.cursor.fetchall():
			account_number = str(row[0])
			account_name = row[1]
			account_type = row[2]
			p = self.income_expense_accounts_store.append(parent,
															[account_number, 
															account_name,
															account_type])
			self.get_child_accounts (account_number, p)

	def reconcile_clicked (self, widget):
		self.cursor.execute("SELECT 1 FROM gl_entries "
							"WHERE date_reconciled = %s "
							"AND (credit_account = %s OR debit_account = %s)",
							(self.date, self.credit_card_account, 
							self.credit_card_account))
		if self.cursor.fetchone():
			self.show_error_dialog("A reconcile already exists for this "
									"credit card on this date.\n"
									"Please choose a different date.")
			return
		self.cursor.execute("UPDATE gl_entries "
							"SET date_reconciled = %s "
							"WHERE date_reconciled IS NULL "
							"AND reconciled = True "
							"AND (credit_account = %s OR debit_account = %s) ", 
							(self.date, self.credit_card_account, 
							self.credit_card_account))
		DB.commit()
		self.populate_statement_treeview ()
		self.date = None
		self.builder.get_object('entry4').set_text('')
		self.builder.get_object('button5').set_label("Reconcile - no date selected")
		self.builder.get_object('button5').set_sensitive(False)

	def description_edited (self, renderer, path, text):
		row_id = self.transactions_store[path][0]
		self.cursor.execute("UPDATE gl_entries SET transaction_description = %s "
							"WHERE id = %s", (text, row_id))
		DB.commit()
		self.transactions_store[path][3] = text

	def date_renderer_edited (self, renderer, path, text):
		row_id = self.transactions_store[path][0]
		try:
			self.cursor.execute("UPDATE gl_entries SET date_inserted = %s "
							"WHERE id = %s RETURNING format_date(date_inserted)", 
							(text, row_id))
			#Postgres has a powerful date resolver, let it figure out the date
			date_formatted = self.cursor.fetchone()[0]
		except psycopg2.DataError as e:
			DB.rollback()
			print (e)
			self.builder.get_object('label10').set_label(str(e))
			dialog = self.builder.get_object('date_error_dialog')
			dialog.run()
			dialog.hide()
			return
		DB.commit()
		self.transactions_store[path][1] = text
		self.transactions_store[path][2] = date_formatted

	def date_renderer_editing_started (self, renderer, entry, path):
		date = self.transactions_store[path][1]
		entry.set_text(date)

	def credit_card_statement_history_clicked (self, button):
		from reports import credit_card_statement_history
		credit_card_statement_history.CreditCardHistoryGUI()

	def refresh_clicked (self, button):
		if self.credit_card_account:
			self.populate_statement_treeview()

	def populate_statement_treeview (self):
		self.transactions_store.clear()
		self.cursor.execute("SELECT "
								"id, "
								"transaction_description, "
								"amount::numeric, "
								"amount::text, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"reconciled, "
								"debit_account, "
								"credit_account "
							"FROM gl_entries "
							"WHERE (debit_account = %s OR credit_account = %s) "
							"AND date_reconciled IS NULL ORDER BY date_inserted", 
							(self.credit_card_account,
							self.credit_card_account))
		for row in self.cursor.fetchall():
			row_id = row[0]
			description = row[1]
			amount = row[2]
			amount_formatted = row[3]
			date = row[4]
			date_formatted = row[5]
			reconciled = row[6]
			if str(row[7]) == self.credit_card_account:
				self.transactions_store.append([row_id, str(date), date_formatted, 
											description, amount, amount_formatted, 
											0.0, '', reconciled])
			else:
				self.transactions_store.append([row_id, str(date), date_formatted, 
											description, 0.0, '',
											amount, amount_formatted, reconciled])
		
	def all_reconciled_off_activated (self, menuitem):
		for row in self.transactions_store:
			row[8] = False
		
	def all_reconciled_on_activated (self, menuitem):
		for row in self.transactions_store:
			row[8] = True

	def reconcile_toggled (self, toggle_renderer, path):
		active = not toggle_renderer.get_active()
		row_id = self.transactions_store[path][0]
		self.transactions_store[path][8] = active
		if self.builder.get_object('save_reconciled_checkmenuitem').get_active():
			self.cursor.execute("UPDATE gl_entries "
							"SET reconciled = %s WHERE id = %s", 
							(active, row_id))
			DB.commit()

	def save_reconciled_toggled (self, checkmenuitem):
		self.check_widget_validity()

	def check_widget_validity (self):
		button = self.builder.get_object('button5')
		button.set_sensitive(False)
		if not self.credit_card_account:
			button.set_label("No card selected")
			return
		if self.date == None:
			button.set_label("No reconcile date")
			return
		self.builder.get_object('combobox1').set_sensitive(True)
		self.builder.get_object('spinbutton2').set_sensitive(True)
		if not self.builder.get_object('save_reconciled_checkmenuitem').get_active():
			button.set_label("Reconcile disabled")
			return
		button.set_label("Reconcile")
		button.set_sensitive(True)

	def credit_combo_changed (self, combo):
		account = combo.get_active_id()
		if account == None:
			return
		store = combo.get_model()
		iter_ = combo.get_active_iter()
		balance = store[iter_][2]
		self.credit_card_account = account
		self.populate_statement_treeview ()
		self.builder.get_object('label9').set_label(str(balance))
		self.check_widget_validity()

	def fees_rewards_description_changed(self, entry):
		if entry.get_text() == '':
			self.builder.get_object('spinbutton1').set_sensitive(False)
		else:
			self.builder.get_object('spinbutton1').set_sensitive(True)

	def fees_rewards_amount_value_changed (self, spinbutton):
		self.builder.get_object('combobox2').set_sensitive(True)
		self.penalty_amount = spinbutton.get_value()

	def fees_rewards_account_combo_changed (self, combo):
		account = combo.get_active_id()
		if account == None:
			return
		path = combo.get_active()
		self.fees_rewards_type = self.income_expense_accounts_store[path][2]
		self.fees_rewards_account = account
		self.builder.get_object('button1').set_sensitive(True)
		
	def save_fee_reward_clicked (self, button):
		description = self.builder.get_object('combobox-entry').get_text()
		if self.fees_rewards_type == 3:
			transactor.credit_card_fee_reward(self.date, 
										self.credit_card_account, 
										self.fees_rewards_account,
										float(self.penalty_amount), description)
		else:
			transactor.credit_card_fee_reward(self.date, 
										self.fees_rewards_account,
										self.credit_card_account, 
										float(self.penalty_amount), description)
		self.populate_statement_treeview ()
		self.builder.get_object('combobox2').set_active(-1)
		self.builder.get_object('combobox2').set_sensitive(False)
		self.builder.get_object('combobox1').set_active(-1)
		self.builder.get_object('combobox-entry').set_text('')
		button.set_sensitive(False)
		DB.commit()
		
	def payment_amount_value_changed (self, spinbutton):
		self.builder.get_object('comboboxtext4').set_sensitive(True)
		self.payment_amount = spinbutton.get_value()

	def bank_account_combo_changed (self, combo):
		contact_name = self.builder.get_object('combobox-entry2').get_text()
		self.builder.get_object('entry3').set_text(contact_name + ' ')
		self.builder.get_object('entry3').set_sensitive(True)
		self.bank_account = combo.get_active_id()

	def transaction_number_changed(self, widget):
		self.builder.get_object('button2').set_sensitive(True)

	def save_payment(self, widget):
		transaction_number = self.builder.get_object('entry3').get_text()
		transactor.bank_to_credit_card_transfer(self.bank_account, 
											self.credit_card_account, 
											self.payment_amount, 
											self.date, 
											transaction_number)
		self.populate_statement_treeview ()
		self.builder.get_object('entry3').set_sensitive(False)
		self.builder.get_object('entry3').set_text("")
		self.builder.get_object('button2').set_sensitive(False)
		self.builder.get_object('comboboxtext4').set_sensitive(False)
		DB.commit()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry4').set_text(day_text)
		self.check_widget_validity()

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (error)
		dialog.run()
		dialog.destroy()



