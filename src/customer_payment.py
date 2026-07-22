# customer_payment.py
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
from decimal import Decimal
from datetime import date, timedelta
import subprocess
from dateutils import DateTimeCalendar
from db import transactor
from db_connection import DB
from constants import ui_directory, help_dir
from accounts import expense_tree
from payment_entry_panel import PaymentMethodEntry

UI_FILE = ui_directory + "/customer_payment.ui"

class GUI:
	def __init__(self, customer_id = None):

		self.customer_id = customer_id
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		cursor = DB.cursor()
		cursor.execute ("SELECT enforce_exact_payment FROM settings")
		self.exact_payment = cursor.fetchone()[0]
		cursor.execute("SELECT accrual_based FROM settings")
		self.accrual = cursor.fetchone()[0]

		self.expense_trees = expense_tree

		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		self.invoice_store = self.builder.get_object ('unpaid_invoice_store')
		self.customer_store = self.builder.get_object ('customer_store')
		self.cash_account_store = self.builder.get_object ('cash_account_store')
		cursor.execute("SELECT number::text, name FROM gl_accounts "
								"WHERE (is_parent, cash_account) = "
								"(False, True)")
		for row in cursor.fetchall():
			self.cash_account_store.append(row)
		cursor.close()
		self.populate_contacts ()

		self.payment_method = PaymentMethodEntry()
		self.payment_method.connect('changed', self.payment_method_changed)
		self.builder.get_object('check_credit_cash_placeholder').pack_start(self.payment_method.box, True, True, 0)

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today ()
		self.date = self.calendar.get_date()
		self.builder.get_object ('combobox1').set_active_id(str(customer_id))

		self.window = self.builder.get_object('window1')
		self.window.show_all()

		self.check_amount_totals_validity ()

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def help_button_clicked (self, button):
		subprocess.Popen (["yelp", help_dir + "/customer_payment.page"])

	def populate_contacts (self):
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE customer = True ORDER BY name")
		for row in cursor.fetchall():
			self.customer_store.append(row)
		cursor.close()
		DB.rollback()

	def view_invoice_clicked (self, widget):
		invoice_combo = self.builder.get_object('comboboxtext1')
		invoice_id = invoice_combo.get_active_id()
		cursor = DB.cursor()
		cursor.execute("SELECT * FROM invoices WHERE id = %s",
														(invoice_id,))
		for cell in cursor.fetchall():
			file_name = cell[1] + ".pdf"
			file_data = cell[14]
			f = open("/tmp/" + file_name,'wb')
			f.write(file_data)
			subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
			f.close()
		cursor.close()
		DB.rollback()

	def apply_payment_method_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('amount_spinbutton').set_sensitive(active)

	def calculate_discount (self, discount, total):
		discount_percent = (float(discount) / 100.00)
		discount_amount = total * discount_percent
		discounted_amount = total - discount_amount
		discounted_amount = round(discounted_amount, 2)
		return discounted_amount

	def calculate_invoice_discount (self, invoice_id):
		cursor = DB.cursor()
		cursor.execute("SELECT cash_only, discount_percent, pay_in_days, "
							"pay_by_day_of_month, pay_in_days_active, "
							"pay_by_day_of_month_active FROM contacts "
							"JOIN terms_and_discounts "
							"ON contacts.terms_and_discounts_id = "
							"terms_and_discounts.id WHERE contacts.id = %s",
							(self.customer_id,))
		for row in cursor.fetchall():
			cash_only = row[0]
			discount = row[1]
			pay_in_days = row[2]
			pay_by_day_of_month = row[3]
			pay_in_days_active = row[4]
			pay_by_day_of_month_active = row[5]
		cursor.execute("SELECT tax, total, date_created FROM invoices "
							"WHERE id = %s", (invoice_id,))
		if cash_only == True:
			for row in cursor.fetchall():
				tax = row[0]
				self.builder.get_object('label4').set_label("Not applicable")
				self.builder.get_object('label9').set_label("Not applicable")
		elif pay_in_days_active == True:
			for row in cursor.fetchall():
				invoice_id = row[0]
				total = float(row[1])
				date_created = row[2]
				date_difference = self.date - date_created
				discount_due_date = date_created + timedelta(pay_in_days)
				cursor.execute("SELECT format_date(%s)", (discount_due_date,))
				due_date_text = cursor.fetchone()[0]
				self.builder.get_object('label9').set_label(due_date_text)
				discounted_amount = self.calculate_discount (discount, total)
				self.builder.get_object('label4').set_label(str(discounted_amount))
		elif pay_by_day_of_month_active == True:
			for row in cursor.fetchall():
				invoice_id = row[0]
				total = float(row[1])
				date_created = row[2]
				discount_date = date_created.replace(day=pay_by_day_of_month)
				cursor.execute("SELECT format_date(%s)", (discount_date,))
				due_date_text = cursor.fetchone()[0]
				self.builder.get_object('label9').set_label(due_date_text)
				discounted_amount = self.calculate_discount (discount, total)
				self.builder.get_object('label4').set_label(str(discounted_amount))
		else:
			raise Exception("the terms_and_discounts table has invalid entries")
		cursor.close()
		DB.rollback()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_combo_changed(self, widget):
		self.check_amount_totals_validity ()
		customer_id = widget.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			self.select_customer()

	def customer_match_selected(self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.select_customer ()

	def select_customer (self):
		cursor = DB.cursor()
		cursor.execute("SELECT address, city, state, phone From contacts "
							"WHERE id = %s", (self.customer_id,))
		for row in cursor.fetchall():
			self.builder.get_object('label11').set_label(row[0])
			self.builder.get_object('label18').set_label(row[1])
			self.builder.get_object('label17').set_label(row[2])
			self.builder.get_object('label12').set_label(row[3])
		cursor.close()
		self.populate_invoices()
		DB.rollback()

	def populate_invoices (self):
		self.update_invoice_amounts_due ()
		self.invoice_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"i.id, "
								"i.name, "
								"date_created::text, "
								"format_date(date_created), "
								"total, "
								"amount_due, "
								"COALESCE(finance_charge, False) "
							"FROM invoices AS i "
							"WHERE (canceled, paid, posted) = "
							"(False, False, True) "
							"AND customer_id = %s ORDER BY i.date_created",
							(self.customer_id,))
		for row in cursor.fetchall():
			total_formatted = '{:,.2f}'.format(row[4])
			amount_due_formatted = '{:,.2f}'.format(row[5])
			self.invoice_store.append((row[0], row[1], row[2], row[3],
										row[4], total_formatted,
										row[5], amount_due_formatted,
										row[6]))
		cursor.close()
		self.builder.get_object('amount_spinbutton').set_value(0)

	def invoice_selection_changed (self, selection):
		total = Decimal()
		model, path = selection.get_selected_rows ()
		for row in path:
			total += model[row][6]
		if len(path) == 1:
			amount_due = model[path][6]
			self.builder.get_object('amount_spinbutton').set_value(amount_due)
			if not model[path][8]:
				invoice_id = model[path][0]
				self.calculate_invoice_discount (invoice_id)
			else:
				self.builder.get_object('label9').set_label('N/A')
				self.builder.get_object('label4').set_label('N/A')
		else:
			self.builder.get_object('label9').set_label('Select a single invoice')
			self.builder.get_object('label4').set_label('Select a single invoice')
			self.builder.get_object('amount_spinbutton').set_value(total)
		self.builder.get_object('label22').set_label('{:,.2f}'.format(total, 2))
		self.builder.get_object('fifo_payment_checkbutton').set_active(False)
		if len(path) == 0:
			self.builder.get_object('fifo_payment_checkbutton').set_active(True)

	def invoice_treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()

	def amount_due_edited (self, renderer, path, amount):
		if self.invoice_store[path][8]:
			return
		invoice_id = self.invoice_store[path][0]
		if amount == '' or Decimal(amount) > self.invoice_store[path][4]:
			amount = self.invoice_store[path][4]
		cursor = DB.cursor()
		cursor.execute("UPDATE invoices SET amount_due = %s "
							"WHERE id = %s", (amount, invoice_id))
		cursor.close()
		DB.commit()
		self.builder.get_object('amount_spinbutton').set_value(float(amount))
		self.invoice_store[path][6] = Decimal(amount).quantize(Decimal('.01'))
		self.invoice_store[path][7] = '{:,.2f}'.format(self.invoice_store[path][6])

	def amount_due_editing_started (self, renderer, spinbutton, path):
		if self.invoice_store[path][8]:
			upper_limit = self.invoice_store[path][6]
		else:
			upper_limit = self.invoice_store[path][4]
		spinbutton.set_numeric(True)
		self.builder.get_object('amount_due_adjustment').set_upper(upper_limit)
		spinbutton.set_value(self.invoice_store[path][6])

	def apply_discount_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if model[path][8]:
			return
		amount = model[path][6]
		self.builder.get_object('spinbutton3').set_value(amount)
		dialog = self.builder.get_object('invoice_discount_dialog')
		result = dialog.run()
		dialog.hide()
		invoice_id = model[path][0]
		discounted_amount = self.builder.get_object('spinbutton3').get_value()
		if result == Gtk.ResponseType.ACCEPT:
			cursor = DB.cursor()
			cursor.execute("UPDATE invoices SET amount_due = %s "
								"WHERE id = %s", (discounted_amount, invoice_id))
			cursor.close()
			DB.commit()
			self.builder.get_object('amount_spinbutton').set_value(discounted_amount)
			model[path][6] = Decimal(discounted_amount).quantize(Decimal('.01'))
			model[path][7] = '{:,.2f}'.format(model[path][6])
			#self.populate_invoices ()

	def payment_method_changed (self, payment_method):
		self.check_amount_totals_validity ()

	def post_payment_clicked (self, widget):
		total = self.builder.get_object('amount_spinbutton').get_text()
		total = Decimal(total)
		if total == Decimal('0.00'):
			dialog = self.builder.get_object('zero_payment_dialog')
			response = dialog.run()
			dialog.hide()
			if response != Gtk.ResponseType.OK:
				return
		comments = 	self.builder.get_object('entry2').get_text()
		payment_text = self.payment_method.get_payment_text()
		self.payment = transactor.CustomerInvoicePayment(self.date, total)
		cursor = DB.cursor()
		if self.payment_method.payment_type_id == 0:
			cursor.execute("INSERT INTO payments_incoming "
								"(check_payment, cash_payment, "
								"credit_card_payment, payment_text , "
								"check_deposited, customer_id, amount, "
								"date_inserted, comments) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id",
								(True, False, False, payment_text, False,
								self.customer_id, total, self.date,
								comments))
			self.payment_id = cursor.fetchone()[0]
			self.payment.bank_check (self.payment_id)
		elif self.payment_method.payment_type_id == 1:
			cursor.execute("INSERT INTO payments_incoming "
								"(check_payment, cash_payment, "
								"credit_card_payment, payment_text , "
								"check_deposited, customer_id, amount, "
								"date_inserted, comments) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id", (False, False, True,
								payment_text, False, self.customer_id,
								total, self.date, comments))
			self.payment_id = cursor.fetchone()[0]
			account_number = self.payment_method.get_credit_card_account_number()
			self.payment.credit_card (self.payment_id, account_number)
		elif self.payment_method.payment_type_id == 2:
			cursor.execute("INSERT INTO payments_incoming "
								"(check_payment, cash_payment, "
								"credit_card_payment, payment_text , "
								"check_deposited, customer_id, amount, "
								"date_inserted, comments) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id", (False, True, False,
								payment_text, False, self.customer_id,
								total, self.date, comments))
			self.payment_id = cursor.fetchone()[0]
			self.payment.cash (self.payment_id)
		cursor.close()
		if self.builder.get_object('fifo_payment_checkbutton').get_active():
			self.pay_invoices_fifo()
		else:
			self.pay_selected_invoices()
		DB.commit()
		self.window.destroy ()
		
	def pay_invoices_fifo (self):
		c = DB.cursor()
		c_id = self.customer_id
		c.execute("(SELECT id, total - amount_due AS discount, amount_due, "
					"COALESCE(finance_charge, False) AS is_fc FROM "
					"(SELECT id, total, amount_due, finance_charge, "
					"SUM(amount_due) OVER (ORDER BY dated_for, id) invoice_totals "
					"FROM invoices WHERE (paid, posted, canceled, customer_id) "
					"= (False, True, False, %s)"
					") i "
					"WHERE invoice_totals <= "
						"(SELECT payment_total - invoice_total FROM "
							"(SELECT COALESCE(SUM(amount_due), 0.0) "
							"AS invoice_total FROM invoices "
							"WHERE (paid, canceled, customer_id) = "
								"(True, False, %s)"
							") it, "
							"(SELECT amount + amount_owed AS payment_total FROM "
									"(SELECT COALESCE(SUM(amount), 0.0) "
										"AS amount "
									"FROM payments_incoming "
									"WHERE (customer_id, misc_income) = "
										"(%s, False)"
									") pi, "
									"(SELECT COALESCE(SUM(amount_owed), 0.0) "
										"AS amount_owed "
									"FROM credit_memos "
										"WHERE (customer_id, posted) = "
											"(%s, True)"
									") cm "
							") pt "
						")"
					"ORDER BY id);", (c_id, c_id, c_id, c_id))
		for row in c.fetchall():
			invoice_id = row[0]
			discount = row[1]
			amount = row[2]
			is_fc = row[3]
			if discount != Decimal('0.00'):
				self.payment.customer_discount (discount)
			if not is_fc and self.accrual == False:
				transactor.post_invoice_accounts (self.date, invoice_id, amount)
			c.execute("UPDATE invoices "
						"SET (paid, payments_incoming_id, date_paid) "
						"= (True, %s, %s) "
						"WHERE id = %s",
						(self.payment_id, self.date, invoice_id))
		c.close()
		
	def pay_selected_invoices (self):
		c = DB.cursor()
		selection = self.builder.get_object('treeview-selection1')
		model, paths = selection.get_selected_rows()
		discount = Decimal('0.00')
		for row in paths:
			is_fc = model[row][8]
			invoice_id = model[row][0]
			amount = model[row][6]
			if not is_fc and self.accrual == False:
				transactor.post_invoice_accounts (self.date, invoice_id, amount)
			c.execute("UPDATE invoices "
						"SET (paid, payments_incoming_id, date_paid) = "
						"(True, %s, %s) WHERE id = %s "
						"RETURNING total - amount_due AS discount",
						(self.payment_id, self.date, invoice_id))
			discount += c.fetchone()[0]
		if discount != Decimal('0.00'):
			self.payment.customer_discount (discount)
		c.close()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)
		self.populate_invoices ()

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def account_combo_changed (self, combo):
		self.check_amount_totals_validity ()

	def payment_amount_value_changed (self, spinbutton):
		self.check_amount_totals_validity ()

	def update_invoice_amounts_due (self):
		if self.customer_id == None :
			return
		cursor = DB.cursor()
		cursor.execute("SELECT cash_only, discount_percent, pay_in_days, "
							"pay_by_day_of_month, pay_in_days_active, "
							"pay_by_day_of_month_active FROM contacts "
							"JOIN terms_and_discounts "
							"ON contacts.terms_and_discounts_id = "
							"terms_and_discounts.id WHERE contacts.id = %s",
							(self.customer_id,))
		for row in cursor.fetchall():
			cash_only = row[0]
			discount = row[1]
			pay_in_days = row[2]
			pay_by_day_of_month = row[3]
			pay_in_days_active = row[4]
			pay_by_day_of_month_active = row[5]
		cursor.execute("SELECT id, total, date_created FROM invoices "
								"WHERE (customer_id, paid, posted) "
								"= (%s, False, True) "
								"AND (finance_charge = False OR finance_charge IS NULL)",
								(self.customer_id,))
		if cash_only == True:
			for row in cursor.fetchall():
				invoice_id = row[0]
				total = row[1]
				cursor.execute("UPDATE invoices SET amount_due = %s "
									"WHERE id = %s", (total, invoice_id))
		elif pay_in_days_active == True:
			for row in cursor.fetchall():
				invoice_id = row[0]
				total = float(row[1])
				date_created = row[2]
				date_difference = self.date - date_created
				if date_difference <= timedelta(pay_in_days):
					discounted_amount = self.calculate_discount(discount, total)
					cursor.execute("UPDATE invoices SET amount_due = %s "
							"WHERE id = %s", (discounted_amount, invoice_id))
				else:
					cursor.execute("UPDATE invoices SET amount_due = %s "
									"WHERE id = %s", (total, invoice_id))
		elif pay_by_day_of_month_active == True:
			for row in cursor.fetchall():
				invoice_id = row[0]
				total = float(row[1])
				date_created = row[2]
				discount_date = date_created.replace(day=pay_by_day_of_month)
				if self.date <= discount_date:
					discounted_amount = self.calculate_discount(discount, total)
					cursor.execute("UPDATE invoices SET amount_due = %s "
							"WHERE id = %s", (discounted_amount, invoice_id))
				else:
					cursor.execute("UPDATE invoices SET amount_due = %s "
									"WHERE id = %s", (total, invoice_id))
		else:
			raise Exception("your terms_and_discounts table has invalid entries")
		cursor.close()
		DB.commit()
		
	def discount_cash_back_amount_changed (self, spinbutton):
		self.check_amount_totals_validity ()
		amount  = spinbutton.get_value()
		combobox = self.builder.get_object('combobox2')
		if amount == 0.00:
			return
		elif amount < 0.00:
			combobox.set_model(self.expense_trees)
		elif amount > 0.00:
			combobox.set_model(self.cash_account_store)

	def check_amount_totals_validity (self):
		button = self.builder.get_object('button1')
		button.set_sensitive (False)
		if self.date == None:
			button.set_label("No date selected")
			return
		if self.customer_id == None:
			button.set_label("No contact selected")
			return
		if self.payment_method.check_number_missing():
			button.set_label('No check number')
			return # no check number
		if self.payment_method.credit_card_account_missing():
			button.set_label('No deposit account selected')
			return # no credit card deposit account selected
		if self.exact_payment:
			self.check_amount_totals_absolute ()
		else:
			self.check_amount_totals_flexible ()

	def check_amount_totals_flexible (self):
		button = self.builder.get_object('button1')
		button.set_sensitive (False)
		label = self.builder.get_object('label20')
		label.set_visible (True)
		payment = self.builder.get_object('amount_spinbutton').get_value()
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		invoice_amount_due_totals = Decimal()
		for row in path:
			invoice_amount_due_totals += model[row][6]
		self.builder.get_object('label23').set_label ('{:,.2f}'.format(payment))
		if float(invoice_amount_due_totals) == payment :
			label.set_visible (False) #hide the off balance alert
		button.set_sensitive (True)
		button.set_label('Post payment')

	def check_amount_totals_absolute (self):
		button = self.builder.get_object('button1')
		button.set_sensitive (False)
		payment = self.builder.get_object('amount_spinbutton').get_value()
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if len(path) == 0:
			button.set_label ('No invoices selected')
			return
		invoice_amount_due_totals = Decimal()
		for row in path:
			invoice_amount_due_totals += model[row][6]
		self.builder.get_object('label23').set_label ('{:,.2f}'.format(payment))
		if float(invoice_amount_due_totals) != payment :
			button.set_label ("Totals do not match")
			return
		button.set_label ('Post payment')
		button.set_sensitive (True)

		
