# customer_statement.py
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

from gi.repository import Gtk, Gdk, GLib
import os, sys, subprocess
from datetime import datetime
import customer_payment, statementing
from constants import ui_directory, DB, help_dir
from dateutils import DateTimeCalendar

UI_FILE = ui_directory + "/customer_statement.ui"

class GUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.customer_id = None

		self.customer_store = self.get_object('customer_store')
		self.statement_store = self.get_object('statement_store')
		customer_completion = self.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected-double-click', 
								self.calendar_day_selected)
		self.calendar.set_relative_to(self.get_object('entry1'))
		self.statement_end_date = None
				
		self.window = self.get_object('window1')
		self.window.show_all()
		self.calendar.show()

	def destroy (self, widget):
		self.cursor.close()

	def finish_statement_clicked (self, button):
		dialog = self.get_object('dialog1')
		response = dialog.run()
		if response == Gtk.ResponseType.ACCEPT:
			self.cursor.execute("UPDATE settings "
								"SET statement_finish_date = %s", 
								(self.statement_end_date,))
			DB.commit()
		dialog.hide()

	def help_button_clicked (self, widget):
		subprocess.Popen(["yelp", help_dir + "/statement.page"])

	def payment_window(self, widget):
		customer_payment.GUI(customer_id = self.customer_id )

	def print_statement_clicked(self, button):
		statement = statementing.Setup( self.statement_store, 
										self.customer_id,
										self.customer_unformatted_total,
										self.statement_end_date)
		statement.print_dialog(self.window)
		self.customer_combobox_populate ()
		self.statement_store.clear()
		self.get_object('combobox-entry').set_text("")

	def view_statement_clicked (self, button):
		statement = statementing.Setup( self.statement_store, 
										self.customer_id, 
										self.customer_unformatted_total,
										self.statement_end_date)
		statement.view()

	def customer_combobox_populate(self):
		self.customer_store.clear()
		c = DB.cursor()
		c.execute("WITH table2 AS  "
					"(  "
					"SELECT id, "
					"(SELECT COALESCE(SUM(amount_due), 0.0) "
					"AS invoices_total FROM invoices "
					"WHERE (canceled, posted, customer_id) = "
					"(False, True, c.id)),  "
					"(SELECT COALESCE(SUM(amount_due), 0.0) "
					"AS invoices_total_to_end_date FROM invoices "
					"WHERE (canceled, posted, customer_id) = "
					"(False, True, c.id) AND dated_for <= %s ), "
						"(SELECT amount + amount_owed AS payments_total "
						"FROM "
						"(SELECT COALESCE(SUM(amount), 0.0) AS amount "
						"FROM payments_incoming "
						"WHERE (customer_id, misc_income) = (c.id, False) "
						") pi, "
						"(SELECT COALESCE(SUM(amount_owed), 0.0) "
							"AS amount_owed "
						"FROM credit_memos "
						"WHERE (customer_id, posted) = (c.id, True) "
						") cm "
					"), "
					"(SELECT ending_amount + ending_amount_owed "
					"AS ending_payments_total "
					"FROM "
						"(SELECT COALESCE(SUM(amount), 0.0) AS ending_amount "
						"FROM payments_incoming  "
						"WHERE (customer_id, misc_income) = (c.id, False) "
						"AND date_inserted <= %s "
						") pi_ending, "
						"(SELECT COALESCE(SUM(amount_owed), 0.0) "
							"AS ending_amount_owed "
						"FROM credit_memos "
						"WHERE (customer_id, posted) = "
							"(c.id, True) AND dated_for <= %s "
						") cm_ending "
					"), "
					"name, ext_name FROM contacts AS c "
					"WHERE customer = True "
					") "
					"SELECT "
					"id::text, "
					"name, "
					"ext_name, "
					"'Statement Balance ' || "
						"(invoices_total_to_end_date - "
							"ending_payments_total)::money, "
					"invoices_total_to_end_date - ending_payments_total, "
					"'Account Balance ' || "
						"(invoices_total - payments_total)::money "
					"FROM table2 "
					"WHERE (invoices_total-payments_total) <> 0 "
					"GROUP BY id, name, invoices_total, payments_total, "
						"ext_name, invoices_total_to_end_date, "
						"ending_payments_total "
					"ORDER BY name ",
					(self.statement_end_date, 
					self.statement_end_date, self.statement_end_date))
		for row in c.fetchall():
			self.customer_store.append(row)
		c.close()
		DB.rollback()

	def focus (self, window, event):
		self.refresh()

	def refresh(self):
		if self.statement_end_date == None:
			return
		self.customer_combobox_populate ()
		self.get_object('customer_combobox').set_active_id(self.customer_id)

	def customer_combobox_changed(self, combobox):
		active = combobox.get_active()
		if active == -1:
			return
		self.customer_id = self.customer_store[active][0]
		customer_total = self.customer_store[active][3]
		self.customer_unformatted_total = self.customer_store[active][4]
		account_total = self.customer_store[active][5]
		self.get_object('label2').set_label(customer_total)
		self.get_object('label1').set_label(account_total)
		self.populate_statement_store()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def customer_match_selected(self, completion, model, iter):
		customer_id = model[iter][0]
		self.get_object('customer_combobox').set_active_id(customer_id)

	def populate_statement_store (self):
		self.statement_store.clear()
		c_id = self.customer_id
		self.cursor.execute("SELECT * FROM "
								"(SELECT "
									"id, "
									"'', "
									"'Balance forward', "
									"date_inserted::text AS date, "
									"format_date(date_inserted), "
									"amount, "
									"amount::text "
								"FROM statements " 
								"WHERE id =(SELECT MAX(id) FROM statements "
								"WHERE (customer_id, printed) = (%s, True) )"
								") s "
								"UNION "
								"(SELECT "
									"id, "
									"'Invoice', "
									"id::text, "
									"dated_for::text AS date, "
									"format_date(dated_for), "
									"amount_due, "
									"amount_due::text "
								"FROM invoices "
								"WHERE (canceled, posted, customer_id) = "
								"(False, True, %s) AND dated_for <= %s "
								"AND statement_id IS NULL"
								") "
								"UNION "
								"(SELECT "
									"id, "
									"'Credit Memo', "
									"id::text, "
									"date_created::text AS date, "
									"format_date(date_created), "
									"(-amount_owed), "
									"(-amount_owed)::text "
								"FROM credit_memos "
								"WHERE (posted, customer_id) = (True, %s) "
								"AND dated_for <= %s "
								"AND statement_id IS NULL"
								") "
								"UNION "
								"(SELECT "
									"id, "
									"'Payment', "
									"payment_info(id), "
									"date_inserted::text AS date, "
									"format_date(date_inserted), "
									"amount, "
									"amount::text "
								"FROM payments_incoming "
								"WHERE (customer_id, misc_income) = "
								"(%s, False) AND date_inserted <= %s "
								" AND statement_id IS NULL"
								") "
							"ORDER BY date", 
							(c_id, c_id, self.statement_end_date, c_id,
							self.statement_end_date, c_id, 
							self.statement_end_date))
		for row in self.cursor.fetchall():
			self.statement_store.append(row)
		self.get_object('button3').set_sensitive(True)
		DB.rollback()

	def calendar_day_selected (self, calendar):
		self.statement_end_date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry1').set_text(day_text)
		GLib.idle_add(self.refresh)

	def calendar_icon_release (self, widget, icon, event):
		self.calendar.show()



