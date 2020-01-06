# customer_markup_percent.py
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/customer_markup_percent.ui"

class CustomerMarkupPercentGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.customer_markup_store = self.builder.get_object('customer_markup_store')
		self.populate_markup_store ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_markup_store (self):
		self.customer_markup_store.clear()
		self.cursor.execute("SELECT id::text, name, markup_percent, standard "
							"FROM customer_markup_percent "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_markup_store.append(row)
		DB.rollback()

	def new_clicked (self, button):
		iter_ = self.customer_markup_store.append([0, 'New markup', 35, False])
		self.builder.get_object('treeview-selection1').select_iter(iter_)

	def markup_combo_changed(self, combo):
		self.builder.get_object('button2').set_sensitive(True)

	def delete_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		current_markup_id = model[path][0]
		try:
			self.cursor.execute("DELETE FROM customer_markup_percent "
								"WHERE id = %s", (current_markup_id,))
			DB.rollback()
			self.cursor.execute("UPDATE customer_markup_percent "
								"SET deleted = True WHERE id = %s", 
								(current_markup_id,))
		except Exception as e:
			DB.rollback()
			self.builder.get_object('label3').set_label(str(e))
			dialog = self.builder.get_object('dialog1')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				markup_id = self.builder.get_object('combobox1').get_active_id()
				self.cursor.execute("UPDATE contacts "
									"SET markup_percent_id = %s "
									"WHERE markup_percent_id = %s", 
									(markup_id, current_markup_id))
				self.cursor.execute("UPDATE customer_markup_percent "
									"SET deleted = True WHERE id = %s", 
									(current_markup_id,))
		DB.commit()
		self.builder.get_object('button2').set_sensitive(False)
		self.populate_markup_store ()

	def name_edited (self, text_renderer, path, text):
		iter_ = self.customer_markup_store.get_iter(path)
		self.customer_markup_store[path][1] = text
		self.save (iter_)

	def markup_edited (self, spin_renderer, path, markup):
		iter_ = self.customer_markup_store.get_iter(path)
		self.customer_markup_store[path][2] = int(markup)
		self.save (iter_)

	def default_toggled (self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		for row in self.customer_markup_store:
			if row.path == selected_path:
				row[3] = True
				self.cursor.execute("UPDATE customer_markup_percent "
									"SET standard = True "
									"WHERE id = (%s)",[row[0]])
			else:
				row[3] = False
				self.cursor.execute("UPDATE customer_markup_percent "
									"SET standard = False "
									"WHERE id = %s",[row[0]])
		DB.commit()

	def save (self, iter_):
		row_id = self.customer_markup_store[iter_][0]
		name = self.customer_markup_store[iter_][1]
		markup = self.customer_markup_store[iter_][2]
		if row_id == 0:
			self.cursor.execute("INSERT INTO customer_markup_percent "
								"(name, markup_percent) VALUES (%s, %s) "
								"RETURNING id", 
								(name, markup))
			row_id = self.cursor.fetchone()[0]
			self.customer_markup_store[iter_][0] = row_id
		else:
			self.cursor.execute("UPDATE customer_markup_percent "
								"SET (name, markup_percent) = (%s, %s) "
								"WHERE id = %s", 
								(name, markup, row_id))
		DB.commit()
		


		
