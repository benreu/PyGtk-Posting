# add_files.py
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

UI_FILE = "src/modules/simple_example.ui"

class GUI:
	def __init__(self, menuitem, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		
		self.db = db
		self.cursor = db.cursor()
		self.populate_combo ()
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_combo (self):
		combo = self.builder.get_object('comboboxtext1')
		combo.remove_all()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE deleted = False "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			combo.append(str(contact_id), contact_name)

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


		
