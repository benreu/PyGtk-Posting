# product_edit_location.py
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
from db_connection import DB
from constants import ui_directory, PRODUCT_LOCATION_LOCK_CLASSID

UI_FILE = ui_directory + "/product_edit_location.ui"

class ProductEditLocationGUI (Gtk.Builder):
	product_lock_acquired = False
	def __init__(self, product_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.window = self.get_object('window')
		self.window.show_all()
		self.product_id = product_id
		c = DB.cursor()
		c.execute("SELECT pg_try_advisory_lock(%s, %s)",
					(PRODUCT_LOCATION_LOCK_CLASSID, product_id))
		locked = c.fetchone()[0]
		if not locked:
			c.close()
			DB.rollback()
			error = "Somebody else is editing this product's locations"
			self.show_message (error)
			self.window.destroy()
			return
		self.product_lock_acquired = True
		store = self.get_object('location_store')
		c.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		c.execute("SELECT name FROM products WHERE id = %s",
					(self.product_id,))
		name = c.fetchone()[0]
		self.window.set_title("'" + name + "' location")
		c.close()
		DB.rollback()
		self.get_object('location_combo').set_active(0)

	def window_destroy (self, widget):
		if self.product_lock_acquired:
			c = DB.cursor()
			c.execute("SELECT pg_advisory_unlock(%s, %s)",
						(PRODUCT_LOCATION_LOCK_CLASSID, self.product_id))
			c.close()
			self.product_lock_acquired = False
		DB.rollback()

	def cancel_clicked (self, button):
		self.window.destroy()

	def save_clicked (self, button):
		aisle = self.get_object('entry5').get_text()
		rack = self.get_object('entry6').get_text()
		cart = self.get_object('entry7').get_text()
		shelf = self.get_object('entry8').get_text()
		cabinet = self.get_object('entry9').get_text()
		drawer = self.get_object('entry10').get_text()
		_bin_ = self.get_object('entry11').get_text()
		location_id = self.get_object('location_combo').get_active_id()
		c = DB.cursor()
		c.execute("INSERT INTO product_location "
					"(product_id, location_id, aisle, rack, cart, "
					"shelf, cabinet, drawer, bin) "
					"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
					"ON CONFLICT (product_id, location_id) "
					"DO UPDATE SET "
					"(aisle, rack, cart, shelf, cabinet, drawer, bin) = "
					"(%s, %s, %s, %s, %s, %s, %s) "
					"WHERE "
						"(product_location.product_id, "
						"product_location.location_id) = (%s, %s)", 
					(self.product_id, location_id, aisle, rack, 
					cart, shelf, cabinet, drawer, _bin_, 
					aisle, rack, cart, shelf, cabinet, drawer, _bin_, 
					self.product_id, location_id))
		if self.product_lock_acquired:
			c.execute("SELECT pg_advisory_unlock(%s, %s)",
						(PRODUCT_LOCATION_LOCK_CLASSID, self.product_id))
			self.product_lock_acquired = False
		DB.commit()
		c.close()
		self.window.destroy()
		
	def location_combo_changed (self, combobox):
		location_id = combobox.get_active_id()
		c = DB.cursor()
		c.execute("SELECT aisle, rack, cart, shelf, cabinet, drawer, bin "
					"FROM product_location "
					"WHERE (product_id, location_id) = (%s, %s)",
					(self.product_id, location_id))
		for row in c.fetchall():
			self.get_object('entry5').set_text(row[0])
			self.get_object('entry6').set_text(row[1])
			self.get_object('entry7').set_text(row[2])
			self.get_object('entry8').set_text(row[3])
			self.get_object('entry9').set_text(row[4])
			self.get_object('entry10').set_text(row[5])
			self.get_object('entry11').set_text(row[6])
		c.close()
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()





