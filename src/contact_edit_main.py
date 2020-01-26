# contact_edit_main.py
#
# Copyright (C) 2019 - Reuben
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
import psycopg2
from constants import ui_directory, DB

UI_FILE = ui_directory + "/contact_edit_main.ui"

class ContactEditMainGUI(Gtk.Builder):
	def __init__(self, contact_id = None, overview_class = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_combos()
		self.populate_zip_codes ()
		self.contact_id = contact_id
		if contact_id != None:
			self.load_contact()
		self.overview_class = overview_class
		
	def destroy(self, window):
		self.cursor.close()

	def populate_zip_codes (self):
		zip_code_store = self.get_object("zip_code_store")
		zip_code_store.clear()
		self.cursor.execute("SELECT zip, city, state FROM contacts "
							"WHERE deleted = False "
							"GROUP BY zip, city, state "
							"ORDER BY zip, city")
		for row in self.cursor.fetchall():
			zip_code_store.append(row)

	def zip_code_match_selected (self, completion, store, _iter):
		city = store[_iter][1]
		state = store[_iter][2]
		self.get_object("entry5").set_text(city)
		self.get_object("entry6").set_text(state)

	def zip_activated (self, entry):
		zip_code = entry.get_text()
		self.cursor.execute("SELECT city, state FROM contacts "
							"WHERE (deleted, zip) = (False, %s) "
							"GROUP BY city, state LIMIT 1", (zip_code,))
		for row in self.cursor.fetchall():
			city = row[0]
			state = row[1]
			self.get_object("entry5").set_text(city)
			self.get_object("entry6").set_text(state)

	def populate_combos (self):
		store = self.get_object('terms_store')
		self.cursor.execute("SELECT id::text, name FROM terms_and_discounts "
								"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		self.cursor.execute("SELECT id::text FROM terms_and_discounts "
							"WHERE standard = True")
		for row in self.cursor.fetchall():
			self.get_object('combobox1').set_active_id(row[0])
		store = self.get_object('markup_store')
		self.cursor.execute("SELECT id::text, name FROM customer_markup_percent "
								"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		self.cursor.execute("SELECT id::text FROM customer_markup_percent "
							"WHERE standard = True")
		for row in self.cursor.fetchall():
			self.get_object('combobox2').set_active_id(row[0])
		DB.rollback()

	def load_contact (self):
		try:
			self.cursor.execute("SELECT "
									"name, "
									"ext_name, "
									"address, "
									"zip, "
									"city, "
									"state, "
									"phone, "
									"fax, "
									"email, "
									"checks_payable_to, "
									"label, "
									"tax_number, "
									"custom1, "
									"custom2, "
									"custom3, "
									"custom4, "
									"notes, "
									"customer, "
									"vendor, "
									"employee, "
									"service_provider, "
									"terms_and_discounts_id::text, "
									"markup_percent_id::text "
								"FROM contacts WHERE id = %s FOR UPDATE NOWAIT", 
								(self.contact_id, ))
		except psycopg2.OperationalError as e:
			DB.rollback()
			error = str(e) + "Hint: somebody else is editing this contact"
			self.show_message (error)
			self.window.destroy()
			return
		for row in self.cursor.fetchall():
			self.get_object('entry1').set_text(row[0])
			self.get_object('entry2').set_text(row[1])
			self.get_object('entry3').set_text(row[2])
			self.get_object('entry4').set_text(row[3])
			self.get_object('entry5').set_text(row[4])
			self.get_object('entry6').set_text(row[5])
			self.get_object('entry7').set_text(row[6])
			self.get_object('entry8').set_text(row[7])
			self.get_object('entry9').set_text(row[8])
			self.get_object('entry10').set_text(row[9])
			self.get_object('entry11').set_text(row[10])
			self.get_object('entry12').set_text(row[11])
			self.get_object('entry13').set_text(row[12])
			self.get_object('entry14').set_text(row[13])
			self.get_object('entry15').set_text(row[14])
			self.get_object('entry16').set_text(row[15])
			self.get_object('notes_buffer').set_text(row[16])
			self.get_object('checkbutton1').set_active(row[17])
			self.get_object('checkbutton2').set_active(row[18])
			self.get_object('checkbutton3').set_active(row[19])
			self.get_object('checkbutton4').set_active(row[20])
			self.get_object('combobox1').set_active_id(row[21])
			self.get_object('combobox2').set_active_id(row[22])
		
	def cancel_clicked (self, button):
		self.window.destroy()

	def save_clicked (self, button):
		name = self.get_object('entry1').get_text()
		ext_name = self.get_object('entry2').get_text()
		address = self.get_object('entry3').get_text()
		zip_code = self.get_object('entry4').get_text()
		city = self.get_object('entry5').get_text()
		state = self.get_object('entry6').get_text()
		phone = self.get_object('entry7').get_text()
		fax = self.get_object('entry8').get_text()
		email = self.get_object('entry9').get_text()
		checks_payable_to = self.get_object('entry10').get_text()
		misc = self.get_object('entry11').get_text()
		tax_number = self.get_object('entry12').get_text()
		custom1 = self.get_object('entry13').get_text()
		custom2 = self.get_object('entry14').get_text()
		custom3 = self.get_object('entry15').get_text()
		custom4 = self.get_object('entry16').get_text()
		buf = self.get_object('notes_buffer')
		start = buf.get_start_iter ()
		end = buf.get_end_iter ()
		notes = buf.get_text(start, end, True)
		customer = self.get_object('checkbutton1').get_active()
		vendor = self.get_object('checkbutton2').get_active()
		employee = self.get_object('checkbutton3').get_active()
		service_provider = self.get_object('checkbutton4').get_active()
		term_id = self.get_object('combobox1').get_active_id()
		markup_id = self.get_object('combobox2').get_active_id()
		if self.contact_id != None:   
			#if the serial number is not None we update the info
			self.cursor.execute("UPDATE contacts SET "
								"(name, ext_name, address, city, state, zip, "
								"phone, fax, email, label, tax_number, vendor, "
								"customer, employee, custom1, "
								"custom2, custom3, custom4, notes, "
								"terms_and_discounts_id, service_provider, "
								"checks_payable_to, markup_percent_id) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s, %s, %s ,%s, %s, %s, %s, "
								"%s, %s) "
								"WHERE id = %s ", 
								(name, ext_name, address, city, 
								state, zip_code, phone, fax, email, misc, 
								tax_number, vendor, customer, employee, 
								custom1, custom2, custom3, custom4, notes, 
								term_id, service_provider, checks_payable_to,
								markup_id, self.contact_id))
		else:
			self.cursor.execute("INSERT INTO contacts " 
								"(name, ext_name, address, city, state, zip, "
								"phone, fax, email, label, tax_number, vendor, "
								"customer, employee, custom1, "
								"custom2, custom3, custom4, notes, deleted, "
								"terms_and_discounts_id, service_provider, "
								"checks_payable_to, markup_percent_id) "
								"VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s ,%s, %s, %s, %s, %s, False, "
								"%s, %s, %s, %s) RETURNING id ", 
								(name, ext_name, address, city, state, zip_code, 
								phone, fax, email, misc, tax_number, vendor, 
								customer, employee, custom1, custom2, 
								custom3, custom4, notes, term_id, 
								service_provider, checks_payable_to, 
								markup_id))
			contact_id = self.cursor.fetchone()[0]
			self.overview_class.append_contact(contact_id)
			self.overview_class.select_contact(contact_id)
		DB.commit()
		self.window.destroy()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




