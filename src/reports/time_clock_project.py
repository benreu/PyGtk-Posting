# time_clock_project.py
#
# Copyright (C) 2017 - reuben
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
import subprocess
from datetime import datetime
from dateutils import seconds_to_compact_string
						

UI_FILE = "src/reports/time_clock_project.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class GUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		self.cursor = db.cursor()

		self.time_store = self.builder.get_object('time_store')
		self.employee_time_store = self.builder.get_object('employee_time_store')
		self.project_store = self.builder.get_object('project_store')
		completion = self.builder.get_object('project_completion')
		completion.set_match_func(self.project_match_func )

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def focus_in_event (self, window, event):
		self.populate_project_store ()

	def populate_project_store (self):
		self.project_store.clear()
		self.cursor.execute("SELECT time_clock_projects.id, name, "
							"SUM(stop_time-start_time)::text "
							"FROM time_clock_projects "
							"JOIN time_clock_entries "
							"ON time_clock_projects.id = "
							"time_clock_entries.project_id "
							"GROUP BY time_clock_projects.id "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			project_id = row[0]
			project_name = row[1]
			time = row[2]
			self.project_store.append([str(project_id), project_name, time])

	def project_combo_changed (self, combo):
		project_id = combo.get_active_id()
		if project_id != None:
			self.project_id = project_id
			self.populate_time_store ()

	def project_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.project_store[iter_][1].lower():
				return False
		return True

	def project_completion_match_selected (self, completion, model, iter_):
		self.project_id = model[iter_][0]
		self.populate_time_store ()

	def employee_row_activated (self, treeview, path, treeviewcolumn):
		self.employee_id = self.time_store[path][0]
		return
		self.cursor.execute("SELECT SUM(actual_seconds), SUM(adjusted_seconds) "
							"FROM time_clock_entries "
							"WHERE (project_id, employee_id) = "
							"(%s, %s) ",
							(self.project_id, self.employee_id))
		for row in self.cursor.fetchall():
			actual_seconds = row[0]
			adjusted_seconds = row[1]
		efficiency = adjusted_seconds/actual_seconds * 100
		self.builder.get_object('spinbutton1').set_value(efficiency)

	def report_clicked (self, button):
		company = Item()
		self.cursor.execute("SELECT * FROM company_info")
		for row in self.cursor.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
			company.tax_number = row[11]
		items = list()
		self.cursor.execute("SELECT name, SUM(actual_seconds), "
							"SUM(adjusted_seconds), "
							"COUNT(time_clock_entries.id) "
							"FROM time_clock_entries "
							"JOIN contacts ON contacts.id = "
							"time_clock_entries.employee_id "
							"WHERE time_clock_entries.project_id = %s "
							"GROUP BY contacts.name",
							(self.project_id,))
		for row in self.cursor.fetchall():
			employee = Item()
			employee.name = row[0]
			employee.actual = seconds_to_user_date_time(row[1])
			employee.adjusted = seconds_to_user_date_time (row[2])
			employee.time_slots = row[3]
			items.append(employee)
		self.cursor.execute("SELECT name, SUM(actual_seconds), "
							"SUM(adjusted_seconds) FROM time_clock_projects "
							"JOIN time_clock_entries "
							"ON time_clock_projects.id = "
							"time_clock_entries.project_id "
							"WHERE time_clock_projects.id = %s "
							"GROUP BY name", 
							(self.project_id,))
		for row in self.cursor.fetchall():
			wo = Item()
			wo.name = row[0]
			actual_seconds = row[1]
			adjusted_seconds = row[2]
			time = Item()
			time.actual = self.convert_seconds (actual_seconds)
			time.adjusted = self.convert_seconds (adjusted_seconds)
			cost_sharing_seconds = actual_seconds - adjusted_seconds
			if cost_sharing_seconds < 0:
				cost_sharing_seconds = 0
			profit_sharing_seconds = adjusted_seconds - actual_seconds 
			if profit_sharing_seconds < 0:
				profit_sharing_seconds = 0
			time.cost_sharing = self.convert_seconds (cost_sharing_seconds)
			time.profit_sharing = self.convert_seconds (profit_sharing_seconds)
			if adjusted_seconds == 0 and actual_seconds == 0:
				time.efficiency = 0
			else:
				efficiency = (adjusted_seconds / actual_seconds) * 100
				time.efficiency = round(efficiency, 6)
		data = dict(contact = employee, time = time, items = items, 
					company = company, wo = wo)
		from py3o.template import Template #import for every use or there is an error about invalid magic header numbers
		time_file = "/tmp/employee_time.odt"
		time_file_pdf = "/tmp/employee_time.pdf"
		t = Template("./templates/employee_time.odt", time_file , False)
		t.render(data) #the self.data holds all the info of the invoice
		subprocess.call('odt2pdf ' + time_file, shell = True)
		subprocess.Popen('soffice ' + time_file, shell = True)

	def close_dialog (self, dialog):
		dialog.hide()

	def populate_time_store (self):
		self.time_store.clear()
		self.employee_time_store.clear()
		self.cursor.execute("SELECT employee_id, name, "
							"SUM(actual_seconds), "
							"SUM(adjusted_seconds) "
							"FROM time_clock_entries "
							"JOIN contacts "
							"ON time_clock_entries.employee_id = contacts.id "
							"WHERE project_id = %s "
							"GROUP BY employee_id, name ORDER BY name",
							(self.project_id, ))
		for row in self.cursor.fetchall():
			employee_id = row[0]
			employee_name = row[1]
			actual_seconds = seconds_to_compact_string (row[2])
			adjusted_seconds = seconds_to_compact_string (row[3])
			self.time_store.append([str(employee_id), employee_name, 
									actual_seconds, adjusted_seconds])
		#self.builder.get_object('label3').set_label(total_actual)
		#self.builder.get_object('label5').set_label(total_adjusted)
		self.cursor.execute("SELECT "
								"time_clock_entries.id, "
								"name, "
								"format_timestamp(start_time), "
								"format_timestamp(stop_time), "
								"adjusted_seconds "
							"FROM time_clock_entries "
							"JOIN contacts "
							"ON time_clock_entries.employee_id = contacts.id "
							"WHERE project_id = %s ", (self.project_id, ))
		for row in self.cursor.fetchall():
			row_id = row[0]
			employee_name = row[1]
			in_time = row[2]
			out_time = row[3]
			seconds = seconds_to_compact_string (row[4])
			self.employee_time_store.append([str(row_id), employee_name,
											in_time, out_time, seconds])
		self.cursor.execute("SELECT COUNT(employee_id) FROM "
							"time_clock_entries WHERE (running, project_id) = "
							"(True, %s)", (self.project_id,))
		count = self.cursor.fetchone()[0]
		if int(count) == 0:
			message = "There are no employees punched in to this WO."
			self.builder.get_object('button1').set_sensitive(True)
		else:
			message = "There are %s employee(s) punched in to this WO." % count
			self.builder.get_object('button1').set_sensitive(False)
		self.builder.get_object('label1').set_label(message)
			
	def convert_seconds (self, start_seconds):
		if start_seconds == None:
			return "0"
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

		
		