# loans.py
#
# Copyright (C) 2018 - reuben
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
from dateutils import DateTimeCalendar
from db import transactor
import constants

UI_FILE = constants.ui_directory + "/loans.ui"

class LoanGUI :
	def __init__(self):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()
		
		self.loan_store = self.builder.get_object('loan_store')

		self.contact_store = self.builder.get_object('contact_store')
		self.populate_contacts()
		self.populate_accounts ()
		self.populate_loans ()

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.day_selected)
		self.calendar.set_today()
		entry = self.builder.get_object('entry1')
		self.calendar.set_relative_to (entry)
		
		contact_completion = self.builder.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		
		amount_column = self.builder.get_object ('treeviewcolumn4')
		amount_renderer = self.builder.get_object ('cellrenderertext5')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def window_destroy (self, window):
		self.cursor.close()

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(self.highlight, entry)

	def highlight (self, entry):
		entry.select_region(0, -1)

	def amount_cell_func (self, column, cellrenderer, model, iter1, data):
		amount = "{:,.2f}".format(model[iter1][5])
		cellrenderer.set_property("text", amount)

	def populate_contacts (self):
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)

	def populate_accounts (self):
		accounts_store = self.builder.get_object('liability_account_store')
		accounts_store.clear()
		self.cursor.execute("SELECT number::text, name "
						"FROM gl_accounts WHERE type = 5 "
						"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			parent = accounts_store.append(None,row)
			number = row[0]
			self.populate_child_accounts(number, parent, accounts_store)

	def populate_child_accounts (self, number, parent, accounts_store):
		self.cursor.execute("SELECT number::text, name FROM gl_accounts WHERE "
							"parent_number = %s", (number,))
		for row in self.cursor.fetchall():
			p = accounts_store.append(parent,row)
			number = row[0]
			self.populate_child_accounts (number, p, accounts_store)

	def populate_loans (self):
		self.loan_store.clear()
		self.cursor.execute("SELECT "
								"l.id, "
								"c.name, "
								"l.date_received::text, "
								"format_date(l.date_received), "
								"l.description, "
								"l.amount, "
								"l.period_amount, "
								"l.period||'(s)' "
							"FROM loans AS l "
							"JOIN contacts AS c ON c.id = l.contact_id "
							"WHERE finished = False")
		for row in self.cursor.fetchall():
			self.loan_store.append(row)

	def description_edited (self, cellrenderertext, path, text):
		row_id = self.loan_store[path][0]
		self.cursor.execute("UPDATE loans SET description = %s WHERE id = %s",
							(text, row_id))
		self.db.commit()
		self.loan_store[path][4] = text

	def contact_combo_changed (self, combobox):
		contact_id = combobox.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
			self.contact_selected ()
			
	def contact_match_selected (self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.contact_selected()

	def contact_selected (self):
		self.builder.get_object('entry2').set_sensitive(True)

	def contact_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def day_selected (self, calendar):
		text = calendar.get_text()
		self.builder.get_object('entry1').set_text(text)
		self.date = calendar.get_date()

	def date_entry_icon_release (self, entry, iconposition, event):
		self.calendar.show()
			
	def description_entry_changed (self, entry):
		self.description = entry.get_text()
		self.builder.get_object('spinbutton1').set_sensitive(True)
		
	def amount_value_changed (self, spinbutton):
		self.amount = spinbutton.get_text()
		self.builder.get_object('comboboxtext1').set_sensitive(True)

	def payment_period_combo_changed (self, combobox):
		self.payment_period = combobox.get_active_id()
		self.builder.get_object('combobox2').set_sensitive(True)

	def liability_combo_changed (self, combobox):
		account = combobox.get_active_id ()
		if account != None:
			self.account = account
			self.builder.get_object('button1').set_sensitive(True)

	def save_clicked (self, button):
		gl_entries_id = transactor.create_loan(self.db, self.date, 
												self.amount, self.account)
		period_amount = self.builder.get_object('period_amount_spin').get_text()
		self.cursor.execute("INSERT INTO loans "
								"(description, "
								"contact_id, "
								"date_received, "
								"amount, "
								"period, "
								"period_amount, "
								"last_payment_date, "
								"gl_entries_id) "
							"VALUES (%s, %s, %s, %s, %s, %s, now(), %s) ",
							(self.description,
							self.contact_id,
							self.date,
							self.amount,
							self.payment_period,
							period_amount, 
							gl_entries_id))
		self.db.commit()
		self.populate_loans ()
		button.set_sensitive(False)
		self.window.destroy()

	
		
		
