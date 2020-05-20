# project_edit_main.py
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
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/manufacturing/project_edit_main.ui"


class ProjectEditGUI(Gtk.Builder):
	def __init__(self, parent_class, project_id = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.product_store = self.get_object('product_store')
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.parent_class = parent_class
		self.project_id = project_id
		self.populate_stores ()
		self.product_id = None
		self.window = self.get_object('window')
		self.window.show_all()
		if project_id != None:
			self.load_project()
		
	def populate_stores(self):
		cursor = DB.cursor()
		self.product_store.clear()
		cursor.execute("SELECT id::text, name FROM products "
							"WHERE (manufactured, deleted) = "
							"(True, False) ORDER BY name")
		for row in cursor.fetchall():
			self.product_store.append(row)
		cursor.close()

	def product_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def product_match_selected(self, completion, model, iter_):
		self.product_id = model[iter_][0]
		self.get_object('product_combo').set_active_id(self.product_id)
		return True

	def product_combo_changed(self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.get_object('save_button').set_sensitive(True)
			self.generate_project_description ()

	def qty_spinbutton_changed (self, spinbutton):
		if not self.product_id:
			return
		self.generate_project_description ()

	def generate_project_description (self):
		qty = self.get_object('units_spinbutton').get_value_as_int()
		cursor = DB.cursor()
		cursor.execute("SELECT name FROM products "
							"WHERE id = %s", (self.product_id,))
		for row in cursor.fetchall():
			p_name = row[0]
		manufacturing_name_string = "Manufacturing : %s [%s]" % (p_name, qty)
		self.get_object('description_entry').set_text(manufacturing_name_string)
		cursor.close()

	def load_project (self):
		cursor = DB.cursor()
		try:
			cursor.execute("SELECT product_id::text, qty, name, batch_notes "
							"FROM manufacturing_projects WHERE id = %s "
							"FOR UPDATE NOWAIT",
							(self.project_id, ))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Hint: somebody else is editing this project"
			self.show_message (error)
			self.window.destroy()
			return False
		for row in cursor.fetchall():
			self.get_object('product_combo').set_active_id(row[0])
			self.get_object('units_spinbutton').set_value(row[1])
			self.get_object('description_entry').set_text(row[2])
			self.get_object('batch_notes_buffer').set_text(row[3])
		self.get_object('product_combo').set_sensitive(False)
		cursor.close()

	def cancel_clicked (self, button):
		self.window.destroy()

	def destroy (self, window):
		DB.rollback()
		
	def focus_out_event (self, widget, event):
		self.window.set_urgency_hint(True)
		
	def focus_in_event (self, widget, event):
		self.window.set_urgency_hint(False)

	def save_clicked (self, button):
		cursor = DB.cursor()
		product_id = self.get_object('product_combo').get_active_id()
		name = self.get_object('description_entry').get_text()
		qty = self.get_object('units_spinbutton').get_value()
		buf = self.get_object('batch_notes_buffer')
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		notes = buf.get_text(start_iter, end_iter, True)
		if self.project_id == None:
			time_clock_id = self.get_time_clock_id (name)
			cursor.execute("INSERT INTO manufacturing_projects "
							"(product_id, name, qty, time_clock_projects_id, "
							"batch_notes, active) VALUES "
							"(%s, %s, %s, %s, %s, True)", 
							(product_id, name, qty, time_clock_id, notes))
		else:
			cursor.execute("UPDATE manufacturing_projects SET "
							"(name, qty, batch_notes) = "
							"(%s, %s, %s) WHERE id = %s "
							"RETURNING time_clock_projects_id", 
							(name, qty, notes, self.project_id))
			active = self.get_object('time_clock_checkbutton').get_active()
			for row in cursor.fetchall():
				time_clock_projects_id = row[0]
				cursor.execute("UPDATE time_clock_projects "
								"SET (active, stop_date) = "
								"(%s, CURRENT_DATE) "
								"WHERE id = %s",
								(active, time_clock_projects_id))
		DB.commit()
		cursor.close()
		self.window.destroy ()
		self.parent_class.populate_projects()

	def get_time_clock_id (self, project_name):
		if self.get_object('time_clock_checkbutton').get_active() == False:
			return None
		cursor = DB.cursor()
		cursor.execute("INSERT INTO time_clock_projects "
						"(name, start_date, active, permanent) "
						"VALUES (%s, CURRENT_DATE, True, False) "
						"RETURNING id", 
						(project_name, ))
		time_clock_projects_id = cursor.fetchone()[0]
		cursor.close()
		return time_clock_projects_id

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()


