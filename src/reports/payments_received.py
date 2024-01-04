# payments_received.py
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
import dateutils, psycopg2
from decimal import Decimal
from constants import ui_directory, DB, broadcaster
import admin_utils

UI_FILE = ui_directory + "/reports/payments_received.ui"

class PaymentsReceivedGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.treeview = self.builder.get_object('treeview1')
		self.payment_store = self.builder.get_object('payments_received_store')
		self.contact_store = self.builder.get_object('contact_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.customer_id = None
		self.populate_stores()
		self.populate_payment_store ()
		self.handler_ids = list()
		for connection in (("admin_changed", self.admin_changed), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def edit_mode_checkbutton_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)

	def admin_changed (self, broadcast_object, value):
		self.builder.get_object('edit_mode_checkbutton').set_active(False)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def focus(self, window, event):
		return
		self.populate_payment_store()

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT customer_id::text, name "
							"FROM payments_incoming "
							"JOIN contacts ON payments_incoming.customer_id "
							"= contacts.id "
							"GROUP BY customer_id, name "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		store = self.builder.get_object('fiscal_store')
		store.clear()
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		self.builder.get_object('combobox2').set_active(0)
		DB.rollback()

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.builder.get_object('checkbutton2').set_active(False)
		self.customer_id = customer_id
		self.populate_payment_store ()

	def view_all_checkbutton_toggled (self, checkbutton):
		self.populate_payment_store ()

	def fiscal_combo_changed (self, combo):
		self.builder.get_object('checkbutton1').set_active(False)
		self.populate_payment_store ()

	def populate_payment_store (self):
		if self.builder.get_object('checkbutton2').get_active() == True:
			self.populate_payments_all_customers ()
		else:
			self.populate_payment_by_customer ()

	def populate_payments_all_customers (self):
		self.payment_store.clear()
		total_amount = Decimal()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_type(pay.id), "
								"payment_text, "
								"CASE WHEN pay.misc_income THEN 'Misc' "
									"ELSE 'Invoice' END, "
								"pay.deposit, "
								"fy.active "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"JOIN fiscal_years AS fy ON pay.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
								"ORDER BY date_inserted;")
		else:
			fiscal_id = self.builder.get_object('combobox2').get_active_id()
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_type(pay.id), "
								"payment_text, "
								"CASE WHEN pay.misc_income THEN 'Misc' "
									"ELSE 'Invoice' END, "
								"pay.deposit, "
								"fy.active "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"JOIN fiscal_years AS fy ON pay.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
								"WHERE (pay.date_inserted "
								"BETWEEN (SELECT start_date "
									"FROM fiscal_years WHERE id = %s) "
									"AND "
									"(SELECT end_date "
									"FROM fiscal_years WHERE id = %s)) "
								"ORDER BY date_inserted;", 
								(fiscal_id, fiscal_id))
		for row in self.cursor.fetchall():
			total_amount += row[4]
			self.payment_store.append(row)
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)
		DB.rollback()

	def populate_payment_by_customer (self):
		if self.customer_id == None:
			return
		self.payment_store.clear()
		total_amount = Decimal()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_type(pay.id), "
								"payment_text, "
								"CASE WHEN pay.misc_income THEN 'Misc' "
									"ELSE 'Invoice' END, "
								"pay.deposit, "
								"fy.active "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"JOIN fiscal_years AS fy ON pay.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
								"WHERE contacts.id = %s "
								"ORDER BY date_inserted;", (self.customer_id,))
		else:
			fiscal_id = self.builder.get_object('combobox2').get_active_id()
			self.cursor.execute("SELECT "
								"pay.id, "
								"pay.date_inserted::text, "
								"format_date(pay.date_inserted), "
								"contacts.name, "
								"pay.amount, "
								"pay.amount::text, "
								"payment_type(pay.id), "
								"payment_text, "
								"CASE WHEN pay.misc_income THEN 'Misc' "
									"ELSE 'Invoice' END, "
								"pay.deposit, "
								"fy.active "
								"FROM payments_incoming AS pay "
								"INNER JOIN contacts "
								"ON pay.customer_id = contacts.id "
								"JOIN fiscal_years AS fy ON pay.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
								"WHERE contacts.id = %s "
								"AND fy.id = %s "
								"ORDER BY date_inserted;", 
								(self.customer_id, fiscal_id))
		for row in self.cursor.fetchall():
			total_amount += row[4]
			self.payment_store.append(row)
		amount_received = '${:,.2f}'.format(total_amount)
		self.builder.get_object('label2').set_label(amount_received)
		DB.rollback()

	def date_edited (self, cellrenderertext, path, date):
		if date == self.payment_store[path][2]:
			return
		if self.payment_store[path][10] == False:
			self.show_error_dialog("Fiscal year is already closed!")
			return
		row_id = self.payment_store[path][0]
		try:
			self.cursor.execute("UPDATE payments_incoming "
								"SET date_inserted = %s "
								"WHERE id = %s;"
								"SELECT date_inserted::text, "
								"format_date(date_inserted) "
								"FROM payments_incoming WHERE id = %s", 
								(date, row_id, row_id))
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_error_dialog(str(e))
			return
		for row in self.cursor.fetchall():
			date = row[0]
			date_formatted = row[1]
			self.payment_store[path][2] = date_formatted
			self.payment_store[path][1] = date
		DB.commit()
	
	def amount_edited (self, cellrenderertext, path, amount):
		if amount == self.payment_store[path][5]:
			return
		if self.payment_store[path][9] == True:
			self.show_error_dialog("Payment is already deposited!")
			return
		if self.payment_store[path][10] == False:
			self.show_error_dialog("Fiscal year is already closed!")
			return
		row_id = self.payment_store[path][0]
		self.cursor.execute("UPDATE gl_entries "
							"SET amount = %s WHERE id = "
								"(UPDATE payments_incoming "
								"SET amount = %s "
								"WHERE id = %s "
								"RETURNING gl_entries_id);"
							"SELECT amount, "
							"amount::text "
							"FROM payments_incoming WHERE id = %s", 
							(amount, amount, row_id, row_id,))
		for row in self.cursor.fetchall():
			amount = row[0]
			amount_formatted = row[1]
			self.payment_store[path][5] = amount_formatted
			self.payment_store[path][4] = amount
		DB.commit()
	
	def payment_type_changed (self, cellrenderercombo, path, treeiter):
		model = self.builder.get_object('payment_types_store')
		payment_column_id = model[treeiter][0]
		payment_type = model[treeiter][1]
		if payment_type == self.payment_store[path][6]:
			return
		if self.payment_store[path][9] == True:
			self.show_error_dialog("Payment is already deposited!")
			return
		if self.payment_store[path][10] == False:
			self.show_error_dialog("Fiscal year is already closed!")
			return
		row_id = self.payment_store[path][0]
		c = DB.cursor()
		c.execute("UPDATE payments_incoming "
					"SET (cash_payment, check_payment, credit_card_payment) "
					"= (False, False, False) WHERE id = %s; "
					"UPDATE payments_incoming SET %s = True WHERE id = %s" %
					(row_id, payment_column_id, row_id))
		DB.commit()
		self.payment_store[path][6] = payment_type

	def description_edited (self, cellrenderertext, path, description):
		if description == self.payment_store[path][7]:
			return
		if self.payment_store[path][9] == True:
			self.show_error_dialog("Payment is already deposited!")
			return
		if self.payment_store[path][10] == False:
			self.show_error_dialog("Fiscal year is already closed!")
			return
		row_id = self.payment_store[path][0]
		self.cursor.execute("UPDATE payments_incoming "
								"SET payment_text = %s "
								"WHERE id = %s", (description, row_id))
		DB.commit()
		self.payment_store[path][7] = description

	def report_hub_activated (self, menuitem):
		from reports import report_hub
		report_hub.ReportHubGUI(self.treeview)

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (error)
		dialog.run()
		dialog.destroy()

