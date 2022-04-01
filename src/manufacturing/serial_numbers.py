# serial_numbers.py
#
# Copyright (C) 2020 - reuben
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
import subprocess
import barcode_generator
from constants import ui_directory, template_dir, DB

UI_FILE = ui_directory + "/manufacturing/serial_numbers.ui"

class Item (object):
	pass

class SerialNumbersGUI(Gtk.Builder):
	def __init__(self, parent, manufacturing_id, serials_required):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.parent = parent
		self.manufacturing_id = manufacturing_id
		self.serials_required = serials_required
		self.cursor = DB.cursor()
		self.window = self.get_object('window')
		self.window.show_all()
		self.populate_serial_numbers()

	def window_destroy (self, widget):
		self.parent.populate_projects()
		self.cursor.execute("SELECT pg_advisory_unlock(%s) "
							"FROM serial_numbers",
							(self.manufacturing_id,))
		DB.commit()
		self.cursor.close()

	def populate_serial_numbers (self):
		store = self.get_object('serial_number_store')
		store.clear()
		self.cursor.execute("SELECT id, serial_number "
							"FROM serial_numbers "
							"WHERE manufacturing_id = %s ",
							(self.manufacturing_id,))
		for row in self.cursor.fetchall():
			store.append(row)
		self.cursor.execute("SELECT p.id, p.serial_number, "
							"pg_try_advisory_lock(mp.id) "
							"FROM products AS p "
							"JOIN manufacturing_projects AS mp "
							"ON mp.product_id = p.id "
							"WHERE mp.id = %s",
							(self.manufacturing_id,))
		for row in self.cursor.fetchall():
			self.product_id = row[0]
			serial_start = row[1]
			if row[2] == False:
				DB.rollback()
				error = "Somebody else is working on serial numbers"
				self.show_message (error)
				self.window.destroy()
				return
		self.get_object('serial_number_adjustment').set_lower(serial_start)
		self.get_object('serial_number_spinbutton').set_value(serial_start)
		self.serials_generated = len(store)
		if self.serials_required == self.serials_generated:
			self.get_object('generate_box').set_sensitive(False)
		else:
			self.get_object('generate_box').set_sensitive(True)
		end = serial_start + (self.serials_required - self.serials_generated)
		self.get_object('serial_end_label').set_label(str(end))

	def reprint_serial_number_clicked (self, button):
		barcode = self.get_object('reprint_spinbutton').get_value_as_int()
		self.print_serial_number(barcode, 1)

	def generate_serial_numbers_clicked (self, button):
		spinbutton = self.get_object('serial_number_spinbutton')
		serial_start = spinbutton.get_value_as_int()
		label_qty = self.get_object('label_qty_spinbutton').get_value_as_int()
		cursor = DB.cursor()
		for i in range(self.serials_required):
			barcode = serial_start + i
			while Gtk.events_pending():
				Gtk.main_iteration()
			self.print_serial_number(barcode, label_qty)
			cursor.execute("INSERT INTO serial_numbers "
							"(product_id, date_inserted, serial_number, "
							"manufacturing_id) "
							"VALUES (%s, CURRENT_DATE, %s, %s)", 
							(self.product_id, barcode, self.manufacturing_id))
		serial = self.serials_required + serial_start
		cursor.execute("UPDATE products SET serial_number = %s "
							"WHERE id = %s", (serial, self.product_id))
		DB.commit()
		cursor.close()
		self.populate_serial_numbers()

	def print_serial_number (self, barcode, label_qty):
		label = Item()
		label.code128 = barcode_generator.makeCode128(str(barcode))
		label.barcode = barcode
		from py3o.template import Template
		label_file = "/tmp/manufacturing_serial_label.odt"
		t = Template(template_dir+"/manufacturing_serial_template.odt", 
															label_file )
		data = dict(label = label)
		t.render(data) 
		for i in range(label_qty):
			subprocess.call(["soffice", "--headless", "-p", label_file])

	def start_serial_number_value_changed (self, spinbutton):
		serial_number = spinbutton.get_value_as_int()
		qty = self.get_object('spinbutton1').get_value_as_int()
		self.get_object('label10').set_label(str(qty + serial_number))

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()





