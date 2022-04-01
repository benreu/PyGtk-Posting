#
# time_clock_tool.py
# Copyright (C) 2016 reuben 
# 
# time_clock_tool is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# time_clock_tool is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk
from datetime import datetime, date, timedelta
from constants import DB, ui_directory

UI_FILE = ui_directory + "/admin/time_clock_tool.ui"


class TimeClockToolGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.employee_project_store = self.get_object('employee_project_store')
		self.time_clock_entries_store = self.get_object('time_clock_entries_store')
		self.project_store = self.get_object('project_store')
		self.employee_store = self.get_object('employee_store')
		self.populate_stores()

		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_stores (self):
		self.cursor.execute("SELECT id::text, name FROM contacts "
							"WHERE (employee, deleted) = "
							"(True, False) ORDER BY name")
		for row in self.cursor.fetchall():
			self.employee_store.append(row)
		self.cursor.execute("SELECT project_id::text, time_clock_projects.name "
							"FROM time_clock_entries "
							"JOIN time_clock_projects "
							"ON time_clock_projects.id = "
							"time_clock_entries.project_id "
							"WHERE (employee_paid) = (False) "
							"GROUP BY project_id, time_clock_projects.name "
							"ORDER BY time_clock_projects.name")
		for row in self.cursor.fetchall():
			self.project_store.append(row)
		DB.rollback()

	def view_all_employees_toggled (self, checkbutton):
		self.populate_employee_project_store ()

	def view_all_projects_toggled (self, checkbutton):
		self.populate_employee_project_store ()

	def project_combo_changed (self, combo):
		self.populate_employee_project_store ()

	def employee_combo_changed (self, combo):
		self.populate_employee_project_store ()
		
	def populate_employee_project_store (self):
		self.time_clock_entries_store.clear()
		self.employee_project_store.clear()
		employee = self.get_object('combobox1').get_active_id()
		project = self.get_object('combobox2').get_active_id()
		all_employee = self.get_object('checkbutton1').get_active()
		all_project = self.get_object('checkbutton2').get_active()
		c = DB.cursor()
		if all_employee == True and all_project == True:
			c.execute("SELECT " 
						"employee_id, "
						"contacts.name, "
						"project_id, "
						"time_clock_projects.name, "
						"make_interval(secs => SUM(adjusted_seconds))::text "
						"FROM time_clock_entries "
						"JOIN contacts "
						"ON time_clock_entries.employee_id = "
						"contacts.id "
						"JOIN time_clock_projects "
						"ON time_clock_entries.project_id = "
						"time_clock_projects.id "
						"GROUP BY employee_id, contacts.name, "
						"project_id, time_clock_projects.name")
		elif all_employee == True and project != 0:
			c.execute("SELECT " 
						"employee_id, "
						"contacts.name, "
						"project_id, "
						"time_clock_projects.name, "
						"make_interval(secs => SUM(adjusted_seconds))::text "
						"FROM time_clock_entries "
						"JOIN contacts "
						"ON time_clock_entries.employee_id = "
						"contacts.id "
						"JOIN time_clock_projects "
						"ON time_clock_entries.project_id = "
						"time_clock_projects.id "
						"WHERE time_clock_projects.id = %s "
						"GROUP BY employee_id, contacts.name, "
						"project_id, time_clock_projects.name", 
						(project,))
		elif all_project == True and employee != 0:
			c.execute("SELECT " 
						"employee_id, "
						"contacts.name, "
						"project_id, "
						"time_clock_projects.name, "
						"make_interval(secs => SUM(adjusted_seconds))::text "
						"FROM time_clock_entries "
						"JOIN contacts "
						"ON time_clock_entries.employee_id = "
						"contacts.id "
						"JOIN time_clock_projects "
						"ON time_clock_entries.project_id = "
						"time_clock_projects.id "
						"WHERE contacts.id = %s "
						"GROUP BY employee_id, contacts.name, "
						"project_id, time_clock_projects.name", 
						(employee,))
		elif employee != 0 and project != 0:
			c.execute("SELECT " 
						"employee_id, "
						"contacts.name, "
						"project_id, "
						"time_clock_projects.name, "
						"make_interval(secs => SUM(adjusted_seconds))::text "
						"FROM time_clock_entries "
						"JOIN contacts "
						"ON time_clock_entries.employee_id = "
						"contacts.id "
						"JOIN time_clock_projects "
						"ON time_clock_entries.project_id = "
						"time_clock_projects.id "
						"WHERE (contacts.id, time_clock_projects.id) "
						"= (%s, %s) "
						"GROUP BY employee_id, contacts.name, "
						"project_id, time_clock_projects.name", 
						(employee, project))
		else:
			return
		for row in c.fetchall():
			self.employee_project_store.append(row)
		self.get_object('button5').set_sensitive(False)
		DB.rollback()
		c.close()
		
	def populate_time_clock_entries_store (self):
		self.time_clock_entries_store.clear()
		self.cursor.execute("SELECT "
								"id, "
								"format_timestamp(start_time), "
								"format_timestamp(stop_time), "
								"actual_seconds::text, "
								"adjusted_seconds::text "
							"FROM time_clock_entries "
							"WHERE (employee_id, project_id) "
							"= (%s, %s) ORDER BY start_time", 
							(self.employee_id, self.project_id))
		for row in self.cursor.fetchall():
			self.time_clock_entries_store.append(row)
		DB.rollback()

	def employee_project_row_activated (self, treeview, path, treeviewcolumn):
		self.employee_id = self.employee_project_store[path][0]
		self.project_id = self.employee_project_store[path][2]
		self.populate_time_clock_entries_store ()

	def time_clock_entries_row_activated (self, treeview, path, treeviewcolumn):
		self.get_object('button5').set_sensitive(True)

	def time_clock_entries_button_release_event (self, treeview, event):
		if event.button == 3:
			self.show_edit_dialog ()

	def edit_entry_clicked (self, button):
		self.show_edit_dialog()

	def show_edit_dialog (self):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.active_entry = None
		self.get_object('combobox3').set_active_id(
														str(self.employee_id))
		entry_id = self.time_clock_entries_store[path][0]
		self.cursor.execute("SELECT start_time, stop_time "
							"FROM time_clock_entries WHERE id = %s", 
							(entry_id,))
		for row in self.cursor.fetchall():
			self.start_time = row[0]
			self.original_start_time = self.start_time
			self.stop_time = row[1]
			self.original_stop_time = self.stop_time
			self.convert_start_seconds(self.original_start_time)
			self.convert_stop_seconds(self.original_stop_time)
			self.get_object('spinbutton2').set_value(0)
			self.get_object('spinbutton3').set_value(0)
		dialog = self.get_object('dialog1')
		response = dialog.run()

		dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			employee_id = self.get_object('combobox3').get_active_id()
			self.cursor.execute("UPDATE time_clock_entries "
								"SET (employee_id, start_time, stop_time) = "
								"(%s, %s, %s) WHERE id = %s", (employee_id, 
								self.start_time, self.stop_time, entry_id))
		elif response == -2: # Duplicate the entry button ....emmission changed 
			#because the original was the same as the x button in the corner
			employee_id = self.get_object('combobox3').get_active_id()
			self.cursor.execute("INSERT INTO time_clock_entries "
								"(employee_id, start_time, stop_time, "
								"project_id, state, invoiced, employee_paid) "
								"VALUES (%s, %s, %s, %s, 'complete', False, "
								"False) RETURNING id", 
								(employee_id, self.start_time,
								self.stop_time, self.project_id))
			id = self.cursor.fetchone()[0] #following is needed for triggers
			self.cursor.execute("UPDATE time_clock_entries SET stop_time = %s "
								"WHERE id = %s", (self.stop_time, id)) 
		elif response == -5: #Delete the entry
			self.cursor.execute("DELETE FROM time_clock_entries "
								"WHERE id = %s", (entry_id,))
		DB.commit()
		self.populate_employee_project_store ()

	def start_time_spinbutton_changed (self, spinbutton):
		if self.active_entry == None:
			spinbutton.set_value (0)
			return
		offset = spinbutton.get_value_as_int()
		self.start_time = self.original_start_time + (offset * self.time_object)
		self.convert_start_seconds (self.start_time) 

	def convert_start_seconds (self, start_time):
		day = datetime.strftime(start_time, "%a %b %d %Y")
		hour = datetime.strftime(start_time, "%I")
		minute = datetime.strftime(start_time, "%M %p")
		self.get_object('entry1').set_text(day)
		self.get_object('entry2').set_text(hour)
		self.get_object('entry3').set_text(minute)
		if self.active_entry != None:
			self.active_entry.select_region(0,-1)

	def button_release_event (self, entry, event):
		self.original_start_time = self.start_time
		self.original_stop_time = self.stop_time
		self.get_object('spinbutton2').set_value(0)
		self.get_object('spinbutton3').set_value(0)
		self.active_entry = entry
		self.unselect_inactive_entries (entry)

	def unselect_inactive_entries (self, active_entry):
		for line in		[('entry1', timedelta(days=1)),
						('entry2', timedelta(hours=1)),
						('entry3', timedelta(minutes=1)),
						('entry4', timedelta(days=1)),
						('entry5', timedelta(hours=1)),
						('entry6', timedelta(minutes=1))]:
			widget = line[0]
			entry = self.get_object(widget)
			if entry == active_entry:
				entry.select_region(0,-1)
				self.time_object = line[1]
			else:
				entry.select_region(0,0)

	def stop_time_spinbutton_changed (self, spinbutton):
		if self.active_entry == None:
			spinbutton.set_value (0)
			return
		offset = spinbutton.get_value_as_int()
		self.stop_time = self.original_stop_time + (offset * self.time_object)
		self.convert_stop_seconds (self.stop_time) 
		
	def convert_stop_seconds (self, stop_time):
		date_time = stop_time#datetime.fromtimestamp(stop_time)
		day = datetime.strftime(date_time, "%a %b %d %Y")
		hour = datetime.strftime(date_time, "%I")
		minute = datetime.strftime(date_time, "%M %p")
		self.get_object('entry4').set_text(day)
		self.get_object('entry5').set_text(hour)
		self.get_object('entry6').set_text(minute)
		if self.active_entry != None:
			self.active_entry.select_region(0,-1)




