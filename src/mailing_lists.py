# mailing_lists.py
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



from gi.repository import Gtk
import main

UI_FILE = main.ui_directory + "/mailing_lists.ui"


class MailingListsGUI:
	
	def __init__(self, main):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = main.db
		self.cursor = self.db.cursor()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_mailing_store ()

	def populate_mailing_store (self):
		model = self.builder.get_object('liststore1')
		model.clear()
		self.cursor.execute("SELECT id, name, active FROM mailing_lists")
		for row in self.cursor.fetchall():
			row_id = row[0]
			name = row[1]
			active = row[2]
			model.append([row_id, name, active])

	def name_edited (self, renderer, path, text):
		model = self.builder.get_object('liststore1')
		row_id = model[path][0]
		self.cursor.execute("UPDATE mailing_lists SET name = %s WHERE id = %s",
							(text, row_id))
		self.db.commit()
		model[path][1] = text

	def add_clicked (self, button):
		model = self.builder.get_object('liststore1')
		self.cursor.execute("INSERT INTO mailing_lists "
							"(name, active, date_inserted) "
							"VALUES ('New mailing list', True, now()) "
							"RETURNING id")
		row_id = self.cursor.fetchone()[0]
		self.populate_mailing_store ()
		for row in model:
			if row[0] == row_id:
				self.builder.get_object('treeview-selection1').select_path(row.path)
		self.db.commit()

	def deactivate_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("UPDATE mailing_lists SET "
							"active = False WHERE id = %s",
							(row_id,))
		self.db.commit()
		self.populate_mailing_store ()



		
