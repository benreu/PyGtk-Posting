# contact_edit_individual.py
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
import psycopg2
from constants import ui_directory, DB

UI_FILE = ui_directory + "/contact_edit_individual.ui"

class ContactEditIndividualGUI (Gtk.Builder):
	def __init__(self, overview_class, individual_id = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.overview_class = overview_class
		self.individual_id = individual_id
		self.contact_id = None
		if individual_id != None:
			self.populate_individual ()
		self.window = self.get_object('window')
		self.window.show_all()

	def populate_individual (self):
		c = DB.cursor()
		try:
			c.execute("SELECT "
						"name, "
						"ext_name, "
						"address, "
						"city, "
						"state, "
						"zip, "
						"phone, "
						"fax, "
						"email, "
						"notes "
					"FROM contact_individuals WHERE id = %s "
					"FOR UPDATE NOWAIT", 
					(self.individual_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			error = str(e) + "Hint: somebody else is editing this individual"
			self.show_message (error)
			self.window.destroy()
			return
		for row in c.fetchall():
			self.get_object('entry1').set_text(row[0])
			self.get_object('entry2').set_text(row[1])
			self.get_object('entry3').set_text(row[2])
			self.get_object('entry4').set_text(row[3])
			self.get_object('entry5').set_text(row[4])
			self.get_object('entry6').set_text(row[5])
			self.get_object('entry7').set_text(row[6])
			self.get_object('entry8').set_text(row[7])
			self.get_object('entry9').set_text(row[8])
			self.get_object('notes_buffer').set_text(row[9])
		c.close()
		
	def cancel_clicked (self, button):
		self.window.destroy()

	def save_clicked (self, button):
		c = DB.cursor()
		name = self.get_object('entry1').get_text()
		ext_name = self.get_object('entry2').get_text()
		address = self.get_object('entry3').get_text()
		zip_code = self.get_object('entry4').get_text()
		city = self.get_object('entry5').get_text()
		state = self.get_object('entry6').get_text()
		phone = self.get_object('entry7').get_text()
		fax = self.get_object('entry8').get_text()
		email = self.get_object('entry9').get_text()
		buf = self.get_object('notes_buffer')
		start = buf.get_start_iter ()
		end = buf.get_end_iter ()
		notes = buf.get_text(start, end, True)
		if self.individual_id != None:   
			#if the id is not None we update the info
			c.execute("UPDATE contact_individuals SET "
						"(name, ext_name, address, city, state, zip, "
						"phone, fax, email, notes) = "
						"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
						"WHERE id = %s ", 
						(name, ext_name, address, city, 
						state, zip_code, phone, fax, email, 
						notes, self.individual_id))
		else:
			c.execute("INSERT INTO contact_individuals " 
						"(name, ext_name, address, city, state, zip, "
						"phone, fax, email, notes, contact_id) "
						"VALUES "
						"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
						(name, ext_name, address, city, state, 
						zip_code, phone, fax, email, notes, self.contact_id))
		DB.commit()
		c.close()
		self.window.destroy()
		self.overview_class.populate_contact_individuals ()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




