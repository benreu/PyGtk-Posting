# simple_example.py
#
# Copyright (C) 2016 - reuben
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/modules/simple_example.ui"

class GUI:
	def __init__(self, menuitem):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.populate_combo ()
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_combo (self):
		combo = self.builder.get_object('comboboxtext1')
		combo.remove_all()
		self.cursor.execute("SELECT id::text, name FROM contacts "
							"WHERE deleted = False "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			combo.append(contact_id, contact_name)
		DB.rollback()

	def button1_clicked (self, button):
		buffer_ = self.builder.get_object('textbuffer1')
		buffer_.set_text("you clicked button1")

	def button2_clicked (self, button):
		buffer_ = self.builder.get_object('textbuffer1')
		buffer_.set_text("you clicked button2")

	def checkbutton_toggled (self, togglebutton):
		buffer_ = self.builder.get_object('textbuffer1')
		buffer_.set_text("you set the togglebutton to %s" %	
													togglebutton.get_active())

	def combobox_changed (self, combo):
		buffer_ = self.builder.get_object('textbuffer1')
		buffer_.set_text("you set the combo to %s, id %s" %	
													(combo.get_active_text(),
													combo.get_active_id() )
													)

	def textentry_changed (self, entry):
		buffer_ = self.builder.get_object('textbuffer1')
		buffer_.set_text("you changed the text to %s" %	
													entry.get_text())


		
