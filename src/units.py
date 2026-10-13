# units.py
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

UI_FILE = ui_directory + "/units.ui"

#the id column is a string, because the reassign combo takes it as its
#id_column and GtkComboBox only reads a string there. A row that has not been
#inserted yet carries this instead of an id.
UNSAVED = '0'

class UnitsGUI:
	def __init__(self, parent_callback = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		#whoever opened this window gets told once it is closed, so a combo
		#that was filled from the units table can be filled again
		self.parent_callback = parent_callback

		self.unit_store = self.builder.get_object('unit_store')
		self.populate_unit_store ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		if self.parent_callback != None:
			self.parent_callback ()

	def populate_unit_store (self):
		self.unit_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, standard "
							"FROM units "
							"WHERE deleted = False ORDER BY name")
		for row in cursor.fetchall():
			self.unit_store.append(row)
		cursor.close()
		DB.rollback()

	def new_clicked (self, button):
		iter_ = self.unit_store.append([UNSAVED, 'New unit', False])
		self.builder.get_object('treeview-selection1').select_iter(iter_)

	def unit_combo_changed (self, combo):
		self.builder.get_object('button2').set_sensitive(True)

	def name_edited (self, text_renderer, path, text):
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][1] = text
		self.save (iter_)

	def save (self, iter_):
		row_id = self.unit_store[iter_][0]
		name = self.unit_store[iter_][1]
		cursor = DB.cursor()
		try:
			if row_id == UNSAVED:
				cursor.execute("INSERT INTO units (name) VALUES (%s) "
									"RETURNING id::text", (name,))
				self.unit_store[iter_][0] = cursor.fetchone()[0]
			else:
				cursor.execute("UPDATE units "
									"SET (name, date_edited) = (%s, CURRENT_DATE) "
									"WHERE id = %s",
									(name, row_id))
		except Exception as e:
			#units.name is UNIQUE, which the lookup tables this window is
			#modelled on are not, so a repeated name aborts the transaction.
			#Reloading is what puts the row back to the name actually stored,
			#rather than leaving one on screen that was never written.
			DB.rollback()
			cursor.close()
			self.show_message ("That unit could not be saved, which probably "
								"means another unit already has that name.",
								str(e))
			self.populate_unit_store ()
			return
		cursor.close()
		DB.commit()

	def default_toggled (self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		if self.unit_store[selected_path][0] == UNSAVED:
			#there is no row yet to carry the flag, and the other units must
			#not be cleared on behalf of one that does not exist: every product
			#INSERT path resolves its unit through this flag
			self.show_message ("Give this unit a name before making it the "
								"standard one.")
			return
		cursor = DB.cursor()
		for row in self.unit_store:
			if row.path == selected_path:
				row[2] = True
				cursor.execute("UPDATE units SET standard = True "
									"WHERE id = %s", (row[0],))
			else:
				row[2] = False
				cursor.execute("UPDATE units SET standard = False "
									"WHERE id = %s", (row[0],))
		cursor.close()
		DB.commit()

	def delete_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		current_unit_id = model[path][0]
		if current_unit_id == UNSAVED:
			self.unit_store.remove(self.unit_store.get_iter(path[0]))
			return
		if model[path][2] == True:
			#new products take their unit from the standard flag, so it has to
			#stay on a unit that is still there to be named
			self.show_message ("That is the standard unit. Make a different "
								"unit standard before deleting this one.")
			return
		cursor = DB.cursor()
		try:
			#products.unit is ON DELETE RESTRICT, so this asks the database
			#whether anything is using the unit and throws the answer away. A
			#unit that is in use can only ever be retired, never removed, since
			#the products overview still joins units to show its name.
			cursor.execute("DELETE FROM units WHERE id = %s",
								(current_unit_id,))
			DB.rollback()
			cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
								(current_unit_id,))
		except Exception as e:
			DB.rollback()
			self.builder.get_object('label3').set_label(str(e))
			self.populate_reassign_store (current_unit_id)
			dialog = self.builder.get_object('dialog1')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				unit_id = self.builder.get_object('combobox1').get_active_id()
				if unit_id != None:
					cursor.execute("UPDATE products SET unit = %s "
										"WHERE unit = %s",
										(unit_id, current_unit_id))
					cursor.execute("UPDATE units SET deleted = True "
										"WHERE id = %s", (current_unit_id,))
		cursor.close()
		DB.commit()
		self.builder.get_object('button2').set_sensitive(False)
		self.populate_unit_store ()

	def populate_reassign_store (self, current_unit_id):
		'''the dialog gets its own store rather than sharing the treeview's,
		because the unit being retired cannot stand in for itself and a row
		that has not been inserted yet has no id to move the products onto'''
		store = self.builder.get_object('reassign_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name FROM units "
							"WHERE deleted = False AND id != %s "
							"ORDER BY name", (current_unit_id,))
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

	def show_message (self, message, secondary = None):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		if secondary != None:
			dialog.format_secondary_text (secondary)
		dialog.run()
		dialog.destroy()
