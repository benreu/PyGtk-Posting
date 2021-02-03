# contact_files.py
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
import psycopg2, subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/contact_edit_files.ui"

class ContactEditFilesGUI(Gtk.Builder):
	def __init__(self, contact_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.contact_id = contact_id
		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_file_store()

	def destroy (self, widget):
		self.cursor.close()
		DB.rollback()

	def populate_file_store (self):
		store = self.get_object('files_store')
		store.clear()
		c = DB.cursor()
		try:
			c.execute("SELECT "
							"id, "
							"name, "
							"(octet_length(file_data)/1000)::text || ' Kb', "
							"date_inserted::text, "
							"format_date(date_inserted) "
						"FROM files "
						"WHERE contact_id = %s ORDER BY name "
						"FOR UPDATE NOWAIT", 
						(self.contact_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			error = str(e) + "Hint: somebody else is editing these files"
			self.show_message (error)
			self.window.destroy()
			return
		for row in c.fetchall():
			store.append(row)
		c.close()

	def view_file_clicked (self, button):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		file_id = model[path][0]
		self.cursor.execute("SELECT file_data, name FROM files "
							"WHERE id = %s", (file_id,))
		for row in self.cursor.fetchall():
			pdf_data = row[0]
			pdf_path = "/tmp/%s" % row[1]
			with open(pdf_path,'wb') as f:
				f.write(pdf_data)
			subprocess.Popen(["xdg-open", pdf_path])

	def delete_file_clicked (self, button):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		dialog = Gtk.Dialog(title = "")
		dialog.set_transient_for(self.window)
		dialog.add_button("Go back", Gtk.ResponseType.REJECT)
		box = dialog.get_content_area()
		from constants import is_admin
		if is_admin == False:
			label = Gtk.Label(label = "You are not admin !")
		else:
			file_name = model[path][1]
			dialog.add_button("Delete file", Gtk.ResponseType.ACCEPT)
			label = Gtk.Label(label = "Are you sure you want to delete \n'%s' ?"
														%file_name)
		box.add(label)
		box.show_all()
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			file_id = model[path][0]
			self.cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
			DB.commit ()
			self.populate_file_store ()
		dialog.hide()

	def add_file_clicked (self, widget):
		dialog = Gtk.FileChooserDialog(title = "Choose a file",
										action = Gtk.FileChooserAction.OPEN)
		dialog.set_transient_for(self.window)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			path = dialog.get_filename()
			with open(path,'rb') as f:
				data = f.read()
			split_filename = path.split("/")
			name = split_filename[-1]
			self.cursor.execute("INSERT INTO files "
								"(file_data, contact_id, name) "
								"VALUES (%s, %s, %s)", 
								(data, self.contact_id, name))
			DB.commit()
			self.populate_file_store()

	def close_clicked (self, button):
		self.window.destroy()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



