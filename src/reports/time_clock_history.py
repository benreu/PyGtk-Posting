# time_clock_history.py
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


from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, GObject, Pango
from datetime import datetime
import time, ssl
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/time_clock_history.ui"

class TimeClockHistoryGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.sunday_store = self.builder.get_object('liststore1')
		self.monday_store = self.builder.get_object('liststore2')
		self.tuesday_store = self.builder.get_object('liststore3')
		self.wednesday_store = self.builder.get_object('liststore4')
		self.thursday_store = self.builder.get_object('liststore5')
		self.friday_store = self.builder.get_object('liststore6')
		self.saturday_store = self.builder.get_object('liststore7')

		self.populate_employee_combobox ()
		self.populate_project_combobox ()
		#-----for proper functionality we need to use the last possible second of today-----
		r = datetime.strftime(datetime.fromtimestamp(time.time ()),"%b %d %Y").split()
		f = ssl.cert_time_to_seconds(str(r[0]) + "  "+ str(r[1]) +" 00:00:00 "+ str(r[2]) + " GMT")
		self.last_second_of_target_week =float(f) +86399.5
		self.previous_week_time = self.last_second_of_target_week - 604800
		self.first_day = True
		self.add_day_headers ()
		DB.rollback()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def add_day_headers (self):
		current_time = self.last_second_of_target_week
		first_day = self.first_day
		for i in range(7):
			current_day = datetime.fromtimestamp(current_time)
			self.cursor.execute("SELECT format_date(%s)", (current_day.date(),))
			formatted_date = self.cursor.fetchone()[0]
			day_of_week = datetime.weekday(current_day)
			bold_date = "<b>%s</b>" % formatted_date 
			standard_date = formatted_date
			if day_of_week == 6:
				if first_day == True:
					self.builder.get_object('label5').set_markup (bold_date)
				else:
					self.builder.get_object('label5').set_text(standard_date)
			elif day_of_week == 0:
				if first_day == True:
					self.builder.get_object('label13').set_markup (bold_date)
				else:
					self.builder.get_object('label13').set_text(standard_date)
			elif day_of_week == 1:
				if first_day == True:
					self.builder.get_object('label14').set_markup (bold_date)
				else:
					self.builder.get_object('label14').set_text(standard_date)
			elif day_of_week == 2:
				if first_day == True:
					self.builder.get_object('label15').set_markup (bold_date)
				else:
					self.builder.get_object('label15').set_text(standard_date)
			elif day_of_week == 3:
				if first_day == True:
					self.builder.get_object('label16').set_markup (bold_date)
				else:
					self.builder.get_object('label16').set_text(standard_date)
			elif day_of_week == 4:
				if first_day == True:
					self.builder.get_object('label17').set_markup (bold_date)
				else:
					self.builder.get_object('label17').set_text(standard_date)
			elif day_of_week == 5:
				if first_day == True:
					self.builder.get_object('label18').set_markup (bold_date)
				else:
					self.builder.get_object('label18').set_text(standard_date)
			current_time -= 86400
			first_day = False

	def previous_week_time_clicked (self, widget):
		self.last_second_of_target_week -= 604800
		self.previous_week_time -= 604800
		self.first_day = False
		self.load_time_data()

	def next_week_time_clicked (self, widget):
		self.last_second_of_target_week += 604800
		self.previous_week_time += 604800
		if self.last_second_of_target_week > time.time():
			self.last_second_of_target_week = time.time()
			self.previous_week_time = self.last_second_of_target_week - 604800
			self.first_day = True
		else:
			self.first_day = False
		self.load_time_data()

	def load_time_data (self):
		project_combo = self.builder.get_object('comboboxtext2')
		project_id = project_combo.get_active_id()
		employee_combo = self.builder.get_object('comboboxtext1')
		employee_id = employee_combo.get_active_id()
		view_all_employee = self.builder.get_object('checkbutton1').get_active()
		view_all_project = self.builder.get_object('checkbutton2').get_active()
		if view_all_employee == True and view_all_project == True:
			self.cursor.execute("SELECT id, start_time, stop_time,project_id,employee_paid,actual_seconds "
								"FROM time_clock_entries "
								"WHERE (running) = (False) "
								"AND start_time <= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) "
								"AND start_time >= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) ORDER BY start_time",
								(self.last_second_of_target_week, 
								self.previous_week_time))
		elif view_all_employee == True:
			self.cursor.execute("SELECT id, start_time, stop_time,project_id,employee_paid,actual_seconds "
								"FROM time_clock_entries "
								"WHERE (project_id, running) = (%s, False) "
								"AND start_time <= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) "
								"AND start_time >= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) ORDER BY start_time", 
								(project_id, self.last_second_of_target_week, 
								self.previous_week_time))
		elif view_all_project == True:
			self.cursor.execute("SELECT id, start_time, stop_time,project_id,employee_paid,actual_seconds "
								"FROM time_clock_entries "
								"WHERE (employee_id, running) = (%s, False) "
								"AND start_time <= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) "
								"AND start_time >= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) ORDER BY start_time", 
								(employee_id, self.last_second_of_target_week, 
								self.previous_week_time))
		elif project_id != None and employee_id != None:			
			self.cursor.execute("SELECT id, start_time, stop_time,project_id,employee_paid,actual_seconds "
								"FROM time_clock_entries "
								"WHERE (employee_id, project_id, running) = "
								"(%s, %s, False) "
								"AND start_time <= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) "
								"AND start_time >= (CAST(TO_TIMESTAMP( %s) AS timestamptz)) ORDER BY start_time", 
								(employee_id, project_id,
								self.last_second_of_target_week, 
								self.previous_week_time))
		self.populate_day_stores ()
		self.add_day_headers ()
		DB.rollback()

	def employee_view_toggled (self, widget):
		self.load_time_data ()

	def project_view_toggled (self, widget):
		self.load_time_data ()

	def populate_day_stores (self):
		self.sunday_store.clear()
		self.monday_store.clear()
		self.tuesday_store.clear()
		self.wednesday_store.clear()
		self.thursday_store.clear()
		self.friday_store.clear()
		self.saturday_store.clear()
		total_monday_time = 0
		total_tuesday_time = 0
		total_wednesday_time = 0
		total_thursday_time = 0
		total_friday_time = 0
		total_saturday_time = 0
		total_sunday_time = 0
		total_week_time = 0
		for row in self.cursor.fetchall():
			line_id = row[0]
			start_time = row[1]
			stop_time = row[2]
			punched_in_time = row[5]
			in_time = start_time
			out_time = stop_time
			#print row[4]
			pay_stat = "Paid = " + str(row[4])
			project_id_ = row[3]
			self.cursor.execute("SELECT name FROM time_clock_projects WHERE id =%s", (project_id_,))
			for row1 in self.cursor.fetchall():
				project =  " ,Project = " + row1[0] 
			
			in_tooltip = datetime.strftime(in_time,"%a %b %d %Y %I %M %p")\
													+ ' id ' + str(line_id)\
													+ project\
													+ ", " + pay_stat
			out_tooltip = datetime.strftime(out_time,"%a %b %d %Y %I %M %p")\
													+ ' id ' + str(line_id)\
													+ project\
													+ ", " + pay_stat
			
			day_of_week = datetime.weekday(in_time)
			in_time = str(in_time)[10:19]
			out_time = str(out_time)[10:19]
			if day_of_week == 0:
				self.monday_store.append([line_id, "In", in_time, in_tooltip])
				self.monday_store.append([line_id, "Out", out_time, out_tooltip])
				total_monday_time += punched_in_time
			elif day_of_week == 1:
				self.tuesday_store.append([line_id, "In", in_time,in_tooltip])
				self.tuesday_store.append([line_id, "Out", out_time, out_tooltip])
				total_tuesday_time += punched_in_time
			elif day_of_week == 2:
				self.wednesday_store.append([line_id, "In", in_time,in_tooltip])
				self.wednesday_store.append([line_id, "Out", out_time, out_tooltip])
				total_wednesday_time += punched_in_time
			elif day_of_week == 3:
				self.thursday_store.append([line_id, "In", in_time,in_tooltip])
				self.thursday_store.append([line_id, "Out", out_time, out_tooltip])
				total_thursday_time += punched_in_time
			elif day_of_week == 4:
				self.friday_store.append([line_id, "In", in_time,in_tooltip])
				self.friday_store.append([line_id, "Out", out_time, out_tooltip])
				total_friday_time += punched_in_time
			elif day_of_week == 5:
				self.saturday_store.append([line_id, "In", in_time, in_tooltip])
				self.saturday_store.append([line_id, "Out", out_time, out_tooltip])
				total_saturday_time += punched_in_time
			elif day_of_week == 6:
				self.sunday_store.append([line_id, "In", in_time,in_tooltip])
				self.sunday_store.append([line_id, "Out", out_time, out_tooltip])
				total_sunday_time += punched_in_time
			total_week_time += punched_in_time
		monday_datetime = self.convert_seconds(total_monday_time)
		tuesday_datetime = self.convert_seconds(total_tuesday_time)
		wednesday_datetime = self.convert_seconds(total_wednesday_time)
		thursday_datetime = self.convert_seconds(total_thursday_time)
		friday_datetime = self.convert_seconds(total_friday_time)
		saturday_datetime = self.convert_seconds(total_saturday_time)
		sunday_datetime = self.convert_seconds(total_sunday_time)
		week_datetime = self.convert_seconds(total_week_time)

		self.builder.get_object('label7').set_text(monday_datetime)
		self.builder.get_object('label8').set_text(tuesday_datetime)
		self.builder.get_object('label9').set_text(wednesday_datetime)
		self.builder.get_object('label10').set_text(thursday_datetime)
		self.builder.get_object('label11').set_text(friday_datetime)
		self.builder.get_object('label12').set_text(saturday_datetime)
		self.builder.get_object('label6').set_text(sunday_datetime)
		self.builder.get_object('label4').set_text(week_datetime)

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


	def employee_combo_changed (self, widget):
		self.builder.get_object('checkbutton1').set_active(False)
		self.load_time_data ()

	def project_combo_changed (self, widget):
		self.builder.get_object('checkbutton2').set_active(False)
		self.load_time_data ()

	def populate_employee_combobox (self):
		employee_combo = self.builder.get_object('comboboxtext1')
		self.cursor.execute("SELECT id::text, name "
							"FROM contacts WHERE employee = True")
		for row in self.cursor.fetchall():
			employee_combo.append (row[0], row[1])

	def populate_project_combobox (self):
		project_combo = self.builder.get_object('comboboxtext2')
		self.cursor.execute("SELECT id::text, name "
							"FROM time_clock_projects "
							"WHERE active = True")
		for row in self.cursor.fetchall():
			project_combo.append(row[0], row[1])






