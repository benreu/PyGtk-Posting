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
from constants import ui_directory, DB, template_dir

UI_FILE = ui_directory + "/reports/time_clock_project.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class GUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.time_store = self.builder.get_object('time_store')
		self.employee_time_store = self.builder.get_object('employee_time_store')
		self.project_store = self.builder.get_object('project_store')
		completion = self.builder.get_object('project_completion')
		completion.set_match_func(self.project_match_func )

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def focus_in_event (self, window, event):
		self.populate_project_store ()

	def populate_project_store (self):
		self.project_store.clear()
		self.cursor.execute("SELECT time_clock_projects.id::text, name, "
							"SUM(stop_time-start_time)::text "
							"FROM time_clock_projects "
							"JOIN time_clock_entries "
							"ON time_clock_projects.id = "
							"time_clock_entries.project_id "
							"GROUP BY time_clock_projects.id "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.project_store.append(row)
		DB.rollback()

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

	def report_clicked (self, button):
		company = Item()
		c = DB.cursor()
		c.execute("SELECT * FROM company_info")
		for row in c.fetchall():
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
		c.execute("SELECT "
								"c.name, "
								"c.ext_name, "
								"c.address, "
								"c.city, "
								"c.state, "
								"c.zip, "
								"c.fax, "
								"c.phone, "
								"c.email "
							"FROM contacts AS c "
							"JOIN time_clock_entries AS tce "
							"ON tce.employee_id = c.id "
							"WHERE tce.id = (%s)", (self.project_id,))
		employee = Item()
		for row in c.fetchall():
			employee.name = row[0]
			employee.ext_name = row[1]
			employee.street = row[2]
			employee.city = row[3]
			employee.state = row[4]
			employee.zip = row[5]
			employee.fax = row[6]
			employee.phone = row[7]
			employee.email = row[8]
		employees = list()
		c.execute("SELECT "
						"name, "
						"make_interval(secs => SUM(actual_seconds))::text, "
						"COUNT(time_clock_entries.id) "
					"FROM time_clock_entries "
					"JOIN contacts ON contacts.id = "
					"time_clock_entries.employee_id "
					"WHERE time_clock_entries.project_id = %s "
					"GROUP BY contacts.name",
					(self.project_id,))
		for row in c.fetchall():
			line = Item()
			line.employee_name = row[0]
			line.total_time = row[1]
			line.entries = row[2]
			employees.append(line)
		c.execute("SELECT "
						"name, "
						"make_interval(secs => SUM(actual_seconds))::text "
					"FROM time_clock_projects "
					"JOIN time_clock_entries "
					"ON time_clock_projects.id = "
					"time_clock_entries.project_id "
					"WHERE time_clock_projects.id = %s "
					"GROUP BY name", 
					(self.project_id,))
		for row in c.fetchall():
			document = Item()
			document.name = row[0]
			document.total = row[1]
		time_slots = list()
		c.execute("SELECT "
						"format_timestamp(start_time), "
						"format_timestamp(stop_time), "
						"make_interval(secs => actual_seconds)::text, "
						"c.name "
					"FROM time_clock_entries AS tce "
					"JOIN contacts AS c ON c.id = tce.employee_id "
					"WHERE project_id = %s "
					"ORDER BY tce.start_time",
					(self.project_id,))
		for row in c.fetchall():
			line = Item()
			line.time_in = row[0]
			line.time_out = row[1]
			line.total = row[2]
			line.employee = row[3]
			time_slots.append(line)
		data = dict(contact = employee, time_slots = time_slots, 
					employees = employees, company = company, 
					document = document)
		from py3o.template import Template #import for every use or there is an error about invalid magic header numbers
		time_file = "/tmp/employee_time.odt"
		time_file_pdf = "/tmp/employee_time.pdf"
		t = Template(template_dir+"/employee_time.odt", time_file, True)
		t.render(data) #the self.data holds all the info of the invoice
		subprocess.call('odt2pdf ' + time_file, shell = True)
		subprocess.Popen('soffice ' + time_file, shell = True)
		DB.rollback()
		c.close()

	def close_dialog (self, dialog):
		dialog.hide()

	def populate_time_store (self):
		self.time_store.clear()
		self.employee_time_store.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"employee_id::text, "
						"name, "
						"make_interval(secs => SUM(actual_seconds))::text, "
						"make_interval(secs => SUM(adjusted_seconds))::text "
					"FROM time_clock_entries "
					"JOIN contacts "
					"ON time_clock_entries.employee_id = contacts.id "
					"WHERE project_id = %s "
					"GROUP BY employee_id, name ORDER BY name",
					(self.project_id, ))
		for row in c.fetchall():
			self.time_store.append(row)
		c.execute("SELECT "
						"time_clock_entries.id::text, "
						"name, "
						"format_timestamp(start_time), "
						"format_timestamp(stop_time), "
						"make_interval(secs => adjusted_seconds)::text "
					"FROM time_clock_entries "
					"JOIN contacts "
					"ON time_clock_entries.employee_id = contacts.id "
					"WHERE project_id = %s ", (self.project_id, ))
		for row in c.fetchall():
			self.employee_time_store.append(row)
		c.execute("SELECT COUNT(employee_id) FROM "
					"time_clock_entries WHERE (running, project_id) = "
					"(True, %s)", (self.project_id,))
		count = c.fetchone()[0]
		if int(count) == 0:
			message = "There are no employees punched in to this WO."
			self.builder.get_object('button1').set_sensitive(True)
		else:
			message = "There are %s employee(s) punched in to this WO." % count
			self.builder.get_object('button1').set_sensitive(False)
		self.builder.get_object('label1').set_label(message)
		DB.rollback()
		c.close()

		
		
