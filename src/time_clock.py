# time_clock.py
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

from gi.repository import Gtk, GLib
from datetime import datetime
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/time_clock.ui"


class TimeClockGUI(Gtk.Builder):
	entry_id = 0
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.timeout_id = None
		self.handler_ids = list()
		for connection in (('clock_entries_changed', self.populate_employees),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.stack = self.get_object('time_clock_stack')
		self.employee_store = self.get_object('employee_store')
		self.project_store = self.get_object('project_store')
		self.populate_employees ()
		self.window = self.get_object('window1')
		self.window.show_all()

	def delete_event (self, window, event):
		window.hide()
		return True

	def destroy (self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def focus_in (self, widget, event):
		self.stack.set_visible_child_name('employee_page')
		self.populate_employees ()
		self.timeout_id = GLib.timeout_add_seconds(1, self.commit_routine)

	def focus_out (self, widget, event):
		"we need to disable db polling when not on "
		"a time clock window for row locking to work "
		if self.timeout_id:
			GLib.source_remove(self.timeout_id)

	def commit_routine (self):
		"we need to commit on a regular basis so that db polling works; "
		"the db polling feature will then broadcast all revelant changes "
		DB.commit()
		return self.window.is_active() # double check that the window is focused

	def populate_employees (self, main_class = None):
		self.employee_store.clear()
		self.cursor.execute("SELECT "
								"c.id, "
								"c.name, "
								"COALESCE(format_timestamp(start_time), ''), "
								"COALESCE (running, False), "
								"COALESCE (tce.id, 0), "
								"COALESCE (tcp.name, '') "
							"FROM contacts AS c "
							"LEFT JOIN time_clock_entries AS tce "
								"ON tce.employee_id = c.id "
								"AND tce.running = True "
							"LEFT JOIN time_clock_projects AS tcp "
								"ON tcp.id = tce.project_id "
							"WHERE (employee, deleted) = (True, False) "
							"ORDER BY c.name")
		for row in self.cursor.fetchall():
			self.employee_store.append(row)
		selection = self.get_object('employee_selection')
		GLib.idle_add(selection.unselect_all)
		DB.rollback()

	def scan_employee_id_activated (self, entry):
		entry.select_region(0, -1)
		employee_id = int(entry.get_text())
		for row in self.employee_store:
			if row[0] == employee_id:
				self.process_employee(row.path)
				return

	def employee_row_activated (self, treeview, path, treeviewcolumn):
		if treeviewcolumn == self.get_object('treeview_time_column'):
			if self.employee_store[path][3] == True:
				treeview.set_cursor(path, treeviewcolumn, True)
				return
		self.process_employee(path)

	def process_employee (self, path):
		self.employee_id = self.employee_store[path][0]
		employee_name = self.employee_store[path][1]
		if self.employee_store[path][3] == False:  # not punched in
			self.stack.set_visible_child_name ('job_page')
			self.populate_job_store ()
			self.get_object('employee_label').set_label(employee_name)
		else:  # punched in
			self.entry_id = self.employee_store[path][4]
			self.get_object('employee_label1').set_label(employee_name)
			project_name = self.employee_store[path][5]
			self.get_object('project_label1').set_label(project_name)
			self.stack.set_visible_child_name ('punchout_page')
			self.get_object('punchout_button').grab_focus()
			DB.commit()
			self.cursor.execute("SELECT EXTRACT ('epoch' FROM CURRENT_TIMESTAMP)")
			self.clock_in_out_time = int(self.cursor.fetchone()[0])
			self.show_date_from_seconds ()
		DB.rollback()

	def populate_job_store (self):
		self.project_store.clear()
		self.cursor.execute("SELECT "
								"tcp.id, "
								"'Previous project     -     '||tcp.name "
							"FROM time_clock_entries AS tce "
							"JOIN time_clock_projects AS tcp "
							"ON tce.project_id = tcp.id "
							"WHERE tce.id = "
								"(SELECT MAX(tce.id) "
								"FROM time_clock_entries AS tce "
								"JOIN time_clock_projects AS tcp "
								"ON tce.project_id = tcp.id "
								"AND tcp.active = True "
								"WHERE tce.employee_id = %s"
								") "
							"UNION ALL "
							"(SELECT "
								"id, "
								"name "
							"FROM time_clock_projects "
							"WHERE active = TRUE "
							"ORDER BY id"
							") "
							"UNION ALL "
							"SELECT 0, 'Cancel'", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			self.project_store.append(row)
		DB.rollback()

	def scan_job_id_activated (self, entry):
		entry.select_region(0, -1)
		project_id = int(entry.get_text())
		for row in self.project_store:
			if row[0] == project_id:
				self.process_job(row.path)
				return

	def job_row_activated (self, treeview, path, treeviewcolumn):
		self.process_job(path)

	def process_job(self, path):
		project_id = self.project_store[path][0]
		if project_id == 0: # cancel row clicked
			self.stack.set_visible_child_name ('employee_page')
			return
		self.project_id = project_id
		job_name = self.project_store[path][1]
		self.get_object('project_label').set_label(job_name)
		self.stack.set_visible_child_name ('punchin_page')
		self.get_object('punchin_button').grab_focus()
		DB.commit()
		self.cursor.execute("SELECT EXTRACT ('epoch' FROM CURRENT_TIMESTAMP);")
		self.clock_in_out_time = int(self.cursor.fetchone()[0])
		c = DB.cursor()
		c.execute("SELECT "
						"to_char(now() - start_time, 'HH24:MI:SS'), "
						"to_char(now() - stop_time, 'HH24:MI:SS'), "
						"(SELECT COUNT(id)::text FROM time_clock_entries "
							"WHERE (project_id, employee_id) = (%s, %s))"
					"FROM time_clock_entries "
					"WHERE (project_id, employee_id) = (%s, %s) "
					"ORDER BY id DESC LIMIT 1", 
					(self.project_id, self.employee_id, 
					self.project_id, self.employee_id))
		for row in c.fetchall():
			self.get_object('last_punched_in_label').set_label(row[0])
			self.get_object('last_punched_out_label').set_label(row[1])
			self.get_object('punched_in_count_label').set_label(row[2])
			break
		else:
			self.get_object('last_punched_in_label').set_label('0:00:00')
			self.get_object('last_punched_out_label').set_label('0:00:00')
			self.get_object('punched_in_count_label').set_label('0')
		c.close()
		self.show_date_from_seconds ()

	def punch_in_clicked (self, button):
		self.cursor.execute("INSERT INTO time_clock_entries "
							"(employee_id, "
							"project_id, "
							"running, "
							"invoiced, "
							"employee_paid, "
							"start_time) "
							"VALUES "
							"(%s, %s, True, False, False, CURRENT_TIMESTAMP)", 
							(self.employee_id, self.project_id))
		DB.commit()
		self.populate_employees ()
		self.stack.set_visible_child_name ('employee_page')

	def manual_punch_in_clicked (self, button):
		self.cursor.execute("INSERT INTO time_clock_entries "
								"(employee_id, "
								"project_id, "
								"running, "
								"invoiced, "
								"employee_paid, "
								"start_time) "
							"VALUES "
								"(%s, "
								"%s, "
								"True, "
								"False, "
								"False, "
								"CAST(TO_TIMESTAMP(%s) AS timestamptz))", 
							(self.employee_id, 
							self.project_id, 
							self.clock_in_out_time))
		DB.commit()
		self.populate_employees ()
		self.stack.set_visible_child_name ('employee_page')

	def punch_out_clicked (self, button):
		self.cursor.execute("UPDATE time_clock_entries "
							"SET (running, stop_time) = "
							"(False, CURRENT_TIMESTAMP) "
							"WHERE id = %s", (self.entry_id,))
		DB.commit()
		self.populate_employees ()
		self.stack.set_visible_child_name ('employee_page')

	def manual_punch_out_clicked (self, button):
		self.cursor.execute("UPDATE time_clock_entries "
							"SET (running, stop_time) = "
							"(False, CAST(TO_TIMESTAMP(%s) AS timestamptz)) "
							"WHERE id = %s", 
							(self.clock_in_out_time, self.entry_id))
		DB.commit()
		self.populate_employees ()
		self.stack.set_visible_child_name ('employee_page')

	def cancel_clicked (self, button):
		self.populate_employees ()
		self.stack.set_visible_child_name ('employee_page')
		
	def increase_day (self, widget):
		self.clock_in_out_time += 86400
		self.show_date_from_seconds ()

	def decrease_day (self, widget):
		self.clock_in_out_time -= 86400
		self.show_date_from_seconds ()

	def increase_hour (self, widget):
		self.clock_in_out_time += 3600
		self.show_date_from_seconds ()

	def decrease_hour (self, widget):
		self.clock_in_out_time -= 3600
		self.show_date_from_seconds ()

	def increase_minute (self, widget):
		self.clock_in_out_time += 60
		self.show_date_from_seconds ()

	def decrease_minute (self, widget):
		self.clock_in_out_time -= 60
		self.show_date_from_seconds ()
		
	def show_date_from_seconds(self):
		date = datetime.fromtimestamp(self.clock_in_out_time)
		date_text = datetime.strftime(date, "%b %d %Y")
		self.get_object('label2').set_label(date_text)
		self.get_object('label5').set_label(date_text)
		date = str(date)
		hour = int(date [11:13])
		minute = date [14:16]
		second = date [17:19]
		if hour > 12:
			hour -= 12
			self.get_object('label4').set_text(minute + " PM")
			self.get_object('label7').set_text(minute + " PM")
		else:
			self.get_object('label4').set_text(minute + " AM")
			self.get_object('label7').set_text(minute + " AM")
		self.get_object('label3').set_text(str(hour))
		self.get_object('label6').set_text(str(hour))
		self.show_punched_in_calculated_time()

	def show_punched_in_calculated_time (self):
		''' self.entry_id may be 0, resulting in nothing'''
		DB.commit()
		self.cursor.execute("SELECT "
								"DATE_TRUNC('second',("
									"CAST(TO_TIMESTAMP(%s) AS timestamptz) - "
									"start_time "
									")"
								")::text "
							"FROM time_clock_entries WHERE id = %s", 
							(self.clock_in_out_time, self.entry_id))
		for row in self.cursor.fetchall():
			interval = row[0]
			self.get_object('time_label_manual_out').set_label(interval)
		DB.rollback()

	def time_renderer_editing_started (self, cellrenderer, celleditable, path):
		celleditable.set_editable(False)
		celleditable.set_alignment(1.00)
		entry_id = self.employee_store[path][4]
		DB.commit()
		self.cursor.execute("SELECT "
								"'     '||"
								"DATE_TRUNC('second',("
									"CURRENT_TIMESTAMP - start_time)"
								")||'     '"
							"FROM time_clock_entries WHERE id = %s", 
							(entry_id,))
		interval = self.cursor.fetchone()[0]
		celleditable.set_text(interval)
		celleditable.select_region(-1, -1)
		DB.rollback()




