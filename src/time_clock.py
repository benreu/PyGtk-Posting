# time_clock.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

UI_FILE = "src/time_clock.ui"

from gi.repository import Gtk, GLib
from datetime import datetime
from dateutils import datetime_to_text
import settings

class TimeClockGUI :
	
	def __init__(self, db):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.previous_project = None
		listbox = self.builder.get_object('listbox1')
		self.listbox = listbox

		self.db = db
		self.cursor = self.db.cursor()
		self.timeclock_liststore = Gtk.ListStore (str, str)
		self.populate_timeclock_liststore ()
		self.cursor.execute("SELECT id, name FROM contacts WHERE employee = True AND deleted = False")
		for row, line in enumerate(self.cursor.fetchall()):
			employee_id = line[0]
			employee_name = line[1]
			employee_name_label = Gtk.Label(employee_name, xalign=1)
			employee_id_label = Gtk.Label(employee_id, xalign=1)
			employee_id_label.set_visible(False)
			
			#self.cursor.execute("SELECT * FROM time_clock_projects WHERE active = True")
			combo = Gtk.ComboBox.new_with_model (self.timeclock_liststore)
			#entry = combo.get_child ()
			#entry.set_editable (False)
			combo.set_tooltip_text("Project")
			cell = Gtk.CellRendererText()
			combo.pack_start(cell, True)
			combo.add_attribute(cell, 'text', 1)
			combo.set_id_column(0)
			#combo.set_entry_text_column(1)
			self.project_combo_grabbed = True
			combo.connect("grab-notify", self.project_combo_grab_notify)
			combo.set_property("can-focus", True)
			
			#for project in self.cursor.fetchall():
			#	combo.append(str(project[0]), project[1])

			list_box_row = Gtk.ListBoxRow()
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
			list_box_row.add(hbox)
		
			switch = Gtk.Switch()
			switch.props.valign = Gtk.Align.CENTER
			
			self.cursor.execute("SELECT * FROM time_clock_entries WHERE (employee_id, state) = (%s, 'running')", (employee_id,))
			for entry in self.cursor.fetchall():
				switch.set_active(True)
				combo.set_active_id(str(entry[4]))
				break
			else:
				switch.set_sensitive(False)
				
			project_time_label = Gtk.Label("0:00:00", xalign=1 )
			project_time_label.set_property('width-chars', 8)

			switch.connect("button-release-event", self.switch_activated, employee_id, combo)
			combo.connect("changed", self.combo_changed, employee_id, switch, list_box_row)
			combo.connect("scroll-event", self.combo_scroll_event)
			hbox.pack_start(employee_name_label, True, False, 5)
			hbox.pack_end(employee_id_label, False, False, 0)
			hbox.pack_end(project_time_label, False, False, 5)
			hbox.pack_end(switch, False, False, 5)
			hbox.pack_end(combo, False, False, 5)
			

			listbox.add(list_box_row)

		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.manual_window = self.builder.get_object('dialog1')
		GLib.timeout_add_seconds(1, self.update_time )
		GLib.timeout_add(1100, self.unselect_rows)

	def combo_scroll_event (self, combo, eventscroll):
		combo.emit_stop_by_name("scroll-event")

	def unselect_rows (self):
		listbox = self.builder.get_object('listbox1')
		listbox.select_row(None)
		
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
		date_text = datetime_to_text(date)
		self.builder.get_object('label2').set_label(date_text)
		date = str(date)
		hour = int(date [11:13])
		minute = date [14:16]
		second = date [17:19]
		if hour > 12:
			hour -= 12
			self.builder.get_object('label4').set_text(minute + " PM")
		else:
			self.builder.get_object('label4').set_text(minute + " AM")
		self.builder.get_object('label3').set_text(str(hour) + " :")

	def projects_clicked(self, widget):
		settings.GUI(self.db, 'time_clock')

	def manual_entry_clicked(self, widget):
		self.cursor.execute("SELECT EXTRACT ('epoch' FROM CURRENT_TIMESTAMP);")
		self.clock_in_out_time = int(self.cursor.fetchone()[0])
		list_box_row = self.builder.get_object('listbox1').get_selected_rows()[0]
		box = list_box_row.get_children()[0]
		widget_list = box.get_children()
		employee_id_label = widget_list[4]
		employee_id = employee_id_label.get_label()
		self.employee_id = employee_id
		project_combo = widget_list[1]
		project_id = project_combo.get_active_id()
		if project_id == None:
			return # no project selected
		punched_in_switch = widget_list[2]
		active = punched_in_switch.get_active()
		self.show_date_from_seconds ()
		clock_label = self.builder.get_object('label1')
		if active == True:
			clock_label.set_label("Do you wish to clock out on")
			self.clock_state = "in"
		else:
			clock_label.set_label("Do you wish to clock in on")
			self.clock_state = "out"
		result = self.manual_window.run()
		self.manual_window.hide()
		self.unselect_rows ()
		if result == Gtk.ResponseType.ACCEPT:
			punched_in_switch.set_active(not active)
			if active == True:
				self.cursor.execute("UPDATE time_clock_entries SET (state, stop_time) = ('complete', %s) WHERE (employee_id, state) = (%s, 'running')", (self.clock_in_out_time, employee_id))
			else:
				self.cursor.execute("SELECT id FROM time_clock_entries WHERE (employee_id, state) = (%s, 'pending')", (employee_id,))
				for row in self.cursor.fetchall():
					row_id = row[0]
					self.cursor.execute("UPDATE time_clock_entries SET (project_id, start_time, state) = (%s, %s, 'running') WHERE id = %s", (project_id, self.clock_in_out_time, row_id))
					break
				else:
					self.cursor.execute("INSERT INTO time_clock_entries ( employee_id, start_time, project_id, state, invoiced, employee_paid ) VALUES (%s, %s, %s, 'running', False, False)", (employee_id, self.clock_in_out_time, project_id))
			self.db.commit()

	def focus(self, window, event):
		self.focusing = True
		self.populate_timeclock_liststore ()
		self.update_time ()
		self.focusing = False

	def populate_timeclock_liststore (self):
		self.timeclock_liststore.clear()
		self.cursor.execute("SELECT id, name FROM time_clock_projects "
							"WHERE active = True")
		for row in self.cursor.fetchall():
			project_id = row[0]
			project_name = row[1]
			self.timeclock_liststore.append([str(project_id), project_name])

	def update_time(self):
		listbox = self.builder.get_object('listbox1')
		self.focusing = True
		for list_box_row in listbox:
			box = list_box_row.get_child()
			widget_list = box.get_children()
			employee_id_label = widget_list[4]
			employee_id_label.set_visible(False)
			employee_id = employee_id_label.get_label()
			project_combo = widget_list[1]
			punched_in_switch = widget_list[2]
			time_label = widget_list[3]
			self.cursor.execute("SELECT EXTRACT ('epoch' FROM CURRENT_TIMESTAMP) - start_time, project_id FROM time_clock_entries WHERE (employee_id, state) = (%s, 'running')", (employee_id,))
			for row in self.cursor.fetchall():
				calc_time_running = row[0]
				time_string = self.convert_seconds (calc_time_running)
				time_label.set_label(time_string)
				if self.project_combo_grabbed is True: # only change the project combo when it's unfocused
					project_id = row[1]
					project_combo.set_active_id(str(project_id))
				punched_in_switch.set_active(True)
				punched_in_switch.set_sensitive(True)
				break
			else: # check for pending punch in for this employee
				self.cursor.execute("SELECT project_id FROM time_clock_entries WHERE (employee_id, state) = (%s, 'pending')", (employee_id,))
				for row in self.cursor.fetchall():
					if self.project_combo_grabbed is True:
						project_id = row[0]
						project_combo.set_active_id(str(project_id))
					punched_in_switch.set_sensitive(True)
					break
				else:
					if self.project_combo_grabbed is True:
						project_combo.set_active(-1)
					punched_in_switch.set_sensitive(False)
				punched_in_switch.set_active(False)
		self.focusing = False
		self.db.commit()
		return True

	def switch_activated (self, switch, event, employee_id, combo):
		#self.project_id = combo.get_active_id()
		active = switch.get_active()
		self.db.commit()
		if active == True:
			self.cursor.execute("UPDATE time_clock_entries SET (state, stop_time) = ('complete', EXTRACT ('epoch' FROM CURRENT_TIMESTAMP)) WHERE (employee_id, state) = (%s, 'running')", ( employee_id, ))
		else:
			self.cursor.execute("SELECT id FROM time_clock_entries WHERE (employee_id, state) = (%s, 'pending')", (employee_id,))
			for row in self.cursor.fetchall():
				row_id = row[0]
				self.cursor.execute("UPDATE time_clock_entries SET (start_time, state) = (EXTRACT ('epoch' FROM CURRENT_TIMESTAMP), 'running') WHERE id = %s", (row_id, ))
				#self.window.iconify()
				#break
			#else:
				#self.cursor.execute("INSERT INTO time_clock_entries ( employee_id, start_time, project_id, state, invoiced, employee_paid ) VALUES (%s, EXTRACT ('epoch' FROM CURRENT_TIMESTAMP), %s, 'running', False, False)", (employee_id, self.project_id))
			#combo.set_active(0)
		self.db.commit()
		self.unselect_rows ()

	def combo_changed (self, combo, employee_id, switch, row):
		#print combo.get_event()
		if self.focusing == True:
			return # we do not change anything if focus is active (repopulating combo)
		active = switch.get_active()
		project_id = combo.get_active_id()
		self.db.commit()
		if active == False:
			self.listbox.select_row(row)
			switch.set_sensitive(True)
			self.cursor.execute("SELECT id FROM time_clock_entries WHERE (employee_id, state) = (%s, 'pending')", (employee_id,))
			for row in self.cursor.fetchall():
				row_id = row[0]
				self.cursor.execute("UPDATE time_clock_entries SET project_id = %s WHERE id = %s", (project_id, row_id))
				break
			else:
				self.cursor.execute("INSERT INTO time_clock_entries ( employee_id, project_id, state, invoiced, employee_paid ) VALUES (%s, %s, 'pending', False, False)", (employee_id, project_id))
		else:
			self.cursor.execute("UPDATE time_clock_entries SET (state, stop_time) = ('complete', EXTRACT ('epoch' FROM CURRENT_TIMESTAMP)) WHERE (employee_id, state) = (%s, 'running')", ( employee_id,))
			self.cursor.execute("INSERT INTO time_clock_entries ( employee_id, start_time, project_id, state, invoiced, employee_paid ) VALUES (%s, EXTRACT ('epoch' FROM CURRENT_TIMESTAMP), %s, 'running', False, False)", (employee_id, project_id))
		self.db.commit()

	def project_combo_grab_notify (self, widget, boolean):
		self.project_combo_grabbed = boolean

	def listbox_row_selected (self, listbox, listbox_row):
		if listbox_row == None:
			self.builder.get_object('button8').set_sensitive(False)
			return # no row is selected
		box = listbox_row.get_children()[0]
		widget_list = box.get_children()
		employee_id_label = widget_list[4]
		employee_id = employee_id_label.get_label()
		project_combo = widget_list[1]
		if project_combo.get_active() < 0:
			self.builder.get_object('button8').set_sensitive(False)
			self.unselect_rows()
		else:
			self.builder.get_object('button8').set_sensitive(True)
		#GLib.timeout_add(5000, self.unselect_rows)

	def convert_seconds(self, start_seconds):
		leftover_seconds = int(start_seconds) 
		hours = int(leftover_seconds / 3600)
		leftover_seconds = (leftover_seconds - (hours * 3600))
		minutes = int(leftover_seconds / 60)
		leftover_seconds = (leftover_seconds - (minutes * 60))
		seconds = int(leftover_seconds)
		if minutes < 10:
			minutes = "0" + str(minutes)
		if seconds < 10:
			seconds = "0" + str(seconds)
		time_string = str(hours) + ":" + str(minutes) + ":" + str(seconds)
		return time_string





		
