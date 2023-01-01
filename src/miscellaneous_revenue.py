# miscellaneous_revenue.py
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

from gi.repository import Gtk, GLib
from decimal import Decimal
from db.transactor import MiscRevenueTransaction
from dateutils import DateTimeCalendar
from constants import ui_directory, DB, broadcaster
from accounts import revenue_account, revenue_list

UI_FILE = ui_directory + "//miscellaneous_revenue.ui"

class MiscellaneousRevenueGUI:
	def __init__ (self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_contacts ), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.builder.get_object('revenue_combo_renderer').set_property('model',revenue_account)
		self.builder.get_object('account_completion').set_model(revenue_list)
		self.contact_store = self.builder.get_object('contact_store')
		contact_completion = self.builder.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		self.contact_id = None
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.day_selected)
		self.date = None
		self.populate_contacts ()
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		self.check_entry = self.builder.get_object('entry1')
		self.credit_entry = self.builder.get_object('entry2')
		self.cash_entry = self.builder.get_object('entry3')
		self.payment_type_id = 0

	def focus_in_event (self, window, event):
		return

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def destroy (self, widget):
		for connection_id in self.handler_ids:
			broadcaster.disconnect(connection_id)
		self.cursor.close()

	def contacts_clicked (self, button):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()

	def contact_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False # no match
		return True # it's a hit!

	def contact_match_selected(self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.check_if_all_entries_valid ()

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
		self.check_if_all_entries_valid ()

	def populate_contacts (self, m=None, i=None):
		self.contact_store.clear ()
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name, ext_name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		DB.rollback()

	def check_btn_toggled(self, widget):
		self.check_entry.set_sensitive(True)
		self.credit_entry.set_sensitive(False)
		self.cash_entry.set_sensitive(False)
		self.payment_type_id = 0
		self.check_if_all_entries_valid()

	def credit_btn_toggled(self, widget):
		self.check_entry.set_sensitive(False)
		self.credit_entry.set_sensitive(True)
		self.cash_entry.set_sensitive(False)
		self.payment_type_id = 1

	def cash_btn_toggled(self, widget):
		self.check_entry.set_sensitive(False)
		self.credit_entry.set_sensitive(False)
		self.cash_entry.set_sensitive(True)
		self.payment_type_id = 2

	def check_number_changed (self, entry):
		self.check_if_all_entries_valid ()

	def check_if_all_entries_valid (self):
		button = self.builder.get_object('button2')
		button.set_sensitive(False)
		if self.contact_id == None:
			button.set_label('No contact selected')
			return
		if self.date == None:
			button.set_label('No date selected')
			return
		total = Decimal('0.00')
		model = self.builder.get_object('revenue_store')
		for row in model:
			total += Decimal(row[3])
			if row[0] == 0:
				button.set_label('No account selected')
				return # no account selected
			if Decimal(row[3]) == Decimal('0.00'):
				button.set_label('Row amount is 0.00')
				return # row amount is 0.00
		if total == Decimal('0.00'):
			button.set_label('No revenue rows added')
			return # row amount is 0.00
		check_text = self.builder.get_object('entry1').get_text()
		check_active = self.builder.get_object('radiobutton1').get_active()
		if check_active == True and check_text == '':
			button.set_label('No check number')
			return # no check number
		value = self.builder.get_object('spinbutton1').get_text()
		if Decimal(value) != total:
			button.set_label('Amount does not match total')
			return
		button.set_sensitive(True)
		button.set_label('Post Revenue')
	
	def amount_spinbutton_changed (self, spinbutton):
		self.check_if_all_entries_valid ()

	def revenue_account_treeview_activated (self, treeview, path, column):
		self.check_if_all_entries_valid ()

	def treeview_button_release_event (self, widget, event):
		if event.button != 3:
			return
		menu = self.builder.get_object('menu1')
		menu.popup_at_pointer()

	def balance_this_row_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		amount = Decimal()
		for row in model:
			if row.path != path[0]:
				amount += Decimal(row[3])
		total = self.builder.get_object('spinbutton1').get_text()
		model[path][3] = str(Decimal(total) - amount)
		self.check_if_all_entries_valid()

	def post_revenue_clicked (self, button):
		comments = self.builder.get_object('entry5').get_text()
		total = self.builder.get_object('spinbutton1').get_text()
		cursor = DB.cursor()
		transaction = MiscRevenueTransaction(self.date)
		if self.payment_type_id == 0:
			payment_text = self.check_entry.get_text()
			cursor.execute("INSERT INTO payments_incoming "
							"(check_payment, payment_text, "
							"customer_id, amount, "
							"date_inserted, comments, misc_income) "
							"VALUES (True, %s, %s, %s, %s, %s, True) "
							"RETURNING id", 
							(payment_text, self.contact_id, 
							total, self.date, comments))
			payment_id = cursor.fetchone()[0]
			transaction.post_misc_check_payment(total, payment_id)
		elif self.payment_type_id == 1:
			payment_text = self.credit_entry.get_text()
			cursor.execute("INSERT INTO payments_incoming "
							"(credit_card_payment, payment_text, "
							"customer_id, amount, date_inserted, "
							"comments, misc_income) "
							"VALUES (True, %s, %s, %s, %s, %s, True) "
							"RETURNING id", 
							(payment_text, self.contact_id, 
							total, self.date, comments))
			payment_id = cursor.fetchone()[0]
			transaction.post_misc_credit_card_payment(total, payment_id)
		elif self.payment_type_id == 2:
			payment_text = self.cash_entry.get_text()
			cursor.execute("INSERT INTO payments_incoming "
							"(cash_payment, payment_text, "
							"customer_id, amount, date_inserted, "
							"comments, misc_income) "
							"VALUES (True, %s, %s, %s, %s, %s, True) "
							"RETURNING id", 
							(payment_text, self.contact_id, 
							total, self.date, comments))
			payment_id = cursor.fetchone()[0]
			transaction.post_misc_cash_payment(total, payment_id)
		model = self.builder.get_object('revenue_store')
		for row in model:
			revenue_account = row[0]
			amount = row[3]
			transaction.post_credit_entry(revenue_account, amount)
		DB.commit()
		cursor.close()
		self.window.destroy()

	def date_entry_icon_release (self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()

	def day_selected (self, calendar):
		self.date = calendar.get_date()
		date_text = calendar.get_text()
		self.builder.get_object('entry4').set_text(date_text)
		self.check_if_all_entries_valid ()

	def revenue_account_combo_changed (self, cellrenderercombo, path, treeiter):
		account_number = revenue_account[treeiter][0]
		account_name = revenue_account[treeiter][1]
		account_path = revenue_account[treeiter][2]
		model = self.builder.get_object('revenue_store')
		model[path][0] = account_number
		model[path][1] = account_name
		model[path][2] = account_path
		self.check_if_all_entries_valid()
	
	def account_match_selected (self, entrycompletion, model, treeiter):
		selection = self.builder.get_object('treeview-selection2')
		treeview_model, path = selection.get_selected_rows()
		if path == []:
			return
		account_number = model[treeiter][0]
		account_name = model[treeiter][1]
		account_path = model[treeiter][2]
		treeview_model[path][0] = account_number
		treeview_model[path][1] = account_name
		treeview_model[path][2] = account_path
		self.check_if_all_entries_valid()

	def revenue_account_editing_started (self, cellrenderer, editable, path):
		entry = editable.get_child()
		entry.set_completion(self.builder.get_object('account_completion'))

	def revenue_amount_edited (self, cellrenderertext, path, text):
		model = self.builder.get_object('revenue_store')
		model[path][3] = '{:.2f}'.format(float(text))
		self.check_if_all_entries_valid()

	def revenue_amount_editing_started (self, cellrenderer, editable, path):
		editable.set_numeric(True)
	
	def equalize_clicked (self, button):
		model = self.builder.get_object('revenue_store')
		lines = model.iter_n_children()
		if lines == 0:
			return
		revenue_amount = self.builder.get_object('spinbutton1').get_text()
		split_amount = Decimal(revenue_amount) / lines
		split_amount = Decimal(split_amount).quantize(Decimal('0.01'))
		for row in model:
			row[3] = str(split_amount)
		self.check_if_all_entries_valid ()

	def delete_row_clicked (self, button):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path != []:
			model.remove(model.get_iter(path))
		self.check_if_all_entries_valid()

	def add_row_clicked (self, button):
		treeview = self.builder.get_object('treeview1')
		model = treeview.get_model()
		if len(model) == 0:
			amount = self.builder.get_object('spinbutton1').get_text()
		else:
			amount = '0.00'
		iter_ = model.append([0, '', '', amount])
		path = model.get_path(iter_)
		column = treeview.get_column(0)
		treeview.set_cursor(path, column, True)
		self.check_if_all_entries_valid()


