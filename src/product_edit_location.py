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
import psycopg2
from constants import DB, ui_directory

UI_FILE = ui_directory + "/product_edit_location.ui"

class ProductEditLocationGUI (Gtk.Builder):
	def __init__(self, product_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.window = self.get_object('window')
		self.window.show_all()
		store = self.get_object('location_store')
		c = DB.cursor()
		c.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in c.fetchall():
			store.append(row)
		c.close()
		DB.rollback()
		self.product_id = product_id
		self.get_object('location_combo').set_active(0)
	
	def window_destroy (self, widget):
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
		DB.commit()
		c.close()
		self.window.destroy()
		
	def location_combo_changed (self, combobox):
		location_id = combobox.get_active_id()
		c = DB.cursor()
		try:
			c.execute("SELECT aisle, rack, cart, shelf, cabinet, drawer, bin "
						"FROM product_location "
						"WHERE (product_id, location_id) = (%s, %s) "
						"FOR UPDATE NOWAIT", 
						(self.product_id, location_id))
		except psycopg2.OperationalError as e:
			DB.rollback()
			c.close()
			error = str(e) + "Hint: somebody else is editing this product location"
			self.show_message (error)
			self.window.destroy()
			return False
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





