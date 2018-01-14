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
from db import transactor
from dateutils import DateTimeCalendar

UI_FILE = "src/miscellaneous_revenue.ui"

class MiscellaneousRevenueGUI:
	def __init__ (self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		main.connect("contacts_changed", self.populate_contacts )
		self.builder.get_object('treeview1').set_model(main.revenue_acc)
		self.contact_store = self.builder.get_object('contact_store')
		contact_completion = self.builder.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		self.contact_id = None
		self.calendar = DateTimeCalendar(self.db)
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
		GLib.idle_add(self.highlight, spinbutton)

	def highlight (self, spinbutton):
		spinbutton.select_region(0, -1)

	def contacts_clicked (self, button):
		import contacts
		contacts.GUI(self.main)

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
		self.cursor.execute("SELECT id, name, c_o FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			contact_co = row[2]
			self.contact_store.append([str(contact_id), contact_name, contact_co])

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
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows ()
		if path != []:
			treeiter = model.get_iter(path)
			if model.iter_has_child(treeiter) == True:
				button.set_label('Parent account selected')
				return # parent account selected
		else:
			button.set_label('No account selected')
			return # no account selected
		check_text = self.builder.get_object('entry1').get_text()
		check_active = self.builder.get_object('radiobutton1').get_active()
		if check_active == True and check_text == '':
			button.set_label('No check number')
			return # no check number
		if self.builder.get_object('spinbutton1').get_value() == 0.00:
			button.set_label('No amount entered')
			return
		button.set_sensitive(True)
		button.set_label('Post Income')
	
	def amount_spinbutton_changed (self, spinbutton):
		self.check_if_all_entries_valid ()

	def revenue_account_treeview_activated (self, treeview, path, column):
		self.check_if_all_entries_valid ()

	def post_income_clicked (self, button):
		comments = self.builder.get_object('entry5').get_text()
		amount = self.builder.get_object('spinbutton1').get_value()
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		revenue_account = model[path][0]
		#transactor.post_miscellaneous_income (self.db, self.date, amount, account_number)
		if self.payment_type_id == 0:
			payment_text = self.check_entry.get_text()
			self.cursor.execute("INSERT INTO payments_incoming (check_payment, cash_payment, credit_card_payment, payment_text , check_deposited, customer_id, amount, date_inserted, comments, closed, misc_income) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, True) RETURNING id", (True, False, False, payment_text, False, self.contact_id, amount, self.date, comments, False))
			payment_id = self.cursor.fetchone()[0]
			transactor.post_misc_check_payment(self.db, self.date, amount, payment_id, revenue_account)	
		elif self.payment_type_id == 1:
			payment_text = self.credit_entry.get_text()
			self.cursor.execute("INSERT INTO payments_incoming (check_payment, cash_payment, credit_card_payment, payment_text , check_deposited, customer_id, amount, date_inserted, comments, closed, misc_income) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, True) RETURNING id", (False, False, True, payment_text, False, self.contact_id, amount, self.date, comments, False))
			payment_id = self.cursor.fetchone()[0]
			transactor.post_misc_credit_card_payment(self.db, self.date, amount, payment_id, revenue_account)	
		elif self.payment_type_id == 2:
			payment_text = self.cash_entry.get_text()
			self.cursor.execute("INSERT INTO payments_incoming (check_payment, cash_payment, credit_card_payment, payment_text , check_deposited, customer_id, amount, date_inserted, comments, closed, misc_income) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, True) RETURNING id", (False, True, False, payment_text, False, self.contact_id, amount, self.date, comments, False))
			payment_id = self.cursor.fetchone()[0]
			transactor.post_misc_cash_payment(self.db, self.date, amount, payment_id, revenue_account)
		self.db.commit()
		self.cursor.close()
		self.window.destroy()

	def date_entry_icon_release (self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()

	def day_selected (self, calendar):
		self.date = calendar.get_date()
		date_text = calendar.get_text()
		self.builder.get_object('entry4').set_text(date_text)
		self.check_if_all_entries_valid ()
		
		