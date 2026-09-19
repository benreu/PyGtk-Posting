# contact_edit_shipping_address.py
#
# Copyright (C) 2026 - reuben
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
from db_connection import DB
from constants import ui_directory

UI_FILE = ui_directory + "/contact_edit_shipping_address.ui"

class ContactEditShippingAddressGUI:
	def __init__(self, overview_class, shipping_address_id = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.overview_class = overview_class
		self.shipping_address_id = shipping_address_id
		self.contact_id = None
		self.window = self.builder.get_object('window')
		self.window.set_transient_for(overview_class.window)
		self.populate_carrier_combo ()
		self.window.show_all()
		if shipping_address_id != None:
			self.populate_shipping_address ()

	def destroy (self, widget):
		pass

	def populate_carrier_combo (self):
		combo = self.builder.get_object('combobox1')
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name FROM shipping_carriers "
							"WHERE deleted = False ORDER BY name")
		for row in cursor.fetchall():
			combo.append(row[0], row[1])
		cursor.close()
		DB.rollback()

	def populate_shipping_address (self):
		c = DB.cursor()
		c.execute("SELECT "
					"description, "
					"address, "
					"city, "
					"state, "
					"zip, "
					"shipping_carrier_id::text, "
					"standard, "
					"contact_id "
				"FROM contact_shipping_addresses WHERE id = %s",
				(self.shipping_address_id,))
		for row in c.fetchall():
			self.builder.get_object('entry1').set_text(row[0])
			self.builder.get_object('entry2').set_text(row[1])
			self.builder.get_object('entry4').set_text(row[2])
			self.builder.get_object('entry5').set_text(row[3])
			self.builder.get_object('entry3').set_text(row[4])
			if row[5] != None:
				self.builder.get_object('combobox1').set_active_id(row[5])
			self.builder.get_object('checkbutton1').set_active(row[6])
			self.contact_id = row[7]
		c.close()
		DB.rollback()

	def cancel_clicked (self, button):
		self.window.destroy()

	def save_clicked (self, button):
		c = DB.cursor()
		description = self.builder.get_object('entry1').get_text()
		address = self.builder.get_object('entry2').get_text()
		zip_code = self.builder.get_object('entry3').get_text()
		city = self.builder.get_object('entry4').get_text()
		state = self.builder.get_object('entry5').get_text()
		carrier_id = self.builder.get_object('combobox1').get_active_id()
		standard = self.builder.get_object('checkbutton1').get_active()
		if self.shipping_address_id != None:
			c.execute("UPDATE contact_shipping_addresses SET "
						"(description, address, city, state, zip, "
						"shipping_carrier_id, standard, date_edited) = "
						"(%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE) "
						"WHERE id = %s ",
						(description, address, city, state, zip_code,
						carrier_id, standard, self.shipping_address_id))
			contact_id = self.contact_id
		else:
			c.execute("INSERT INTO contact_shipping_addresses "
						"(description, address, city, state, zip, "
						"shipping_carrier_id, standard, contact_id) "
						"VALUES "
						"(%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
						(description, address, city, state, zip_code,
						carrier_id, standard, self.contact_id))
			self.shipping_address_id = c.fetchone()[0]
			contact_id = self.contact_id
		if standard:
			c.execute("UPDATE contact_shipping_addresses SET standard = False "
						"WHERE contact_id = %s AND id != %s",
						(contact_id, self.shipping_address_id))
		DB.commit()
		c.close()
		self.window.destroy()
		self.overview_class.populate_contact_shipping_addresses ()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
