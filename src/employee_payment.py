# daniel_employee_time.py
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

from gi.repository import Gtk, Gdk, GLib, GObject
import os, sys, subprocess, time, re, psycopg2
from datetime import datetime, timedelta
from dateutils import datetime_to_text, calendar_to_text, \
					calendar_to_datetime, set_calendar_from_datetime 
import constants

UI_FILE = constants.ui_directory + "/employee_time.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class EmployeePaymentGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = constants.db
		self.cursor = self.db.cursor()
		self.datetime = datetime.today()
		date_text = datetime_to_text(self.datetime)
		self.builder.get_object('entry8').set_text(date_text)
		morrow = self.datetime + timedelta(days = 1)
		morrow_string = str(morrow)[0:10]
		struct_time = time.strptime(morrow_string,"%Y-%m-%d")
		self.stop_time = time.mktime(struct_time)
		calendar = self.builder.get_object('calendar1')
		self.popover = Gtk.Popover()
		self.popover.add(calendar)

		self.employee_store = self.builder.get_object('employee_store')
		self.employee_payment_store = self.builder.get_object('employee_payment_store')
		self.employee_id = 0

		self.adjusted_seconds = 0
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		self.populate_employees ()

	def focus_in_event (self, window, event):
		self.populate_employees ()

	def populate_employees (self):
		self.employee_store.clear()
		self.cursor.execute("SELECT employee_id, name "
							"FROM time_clock_entries "
							"JOIN contacts ON contacts.id = "
							"time_clock_entries.employee_id "
							"WHERE employee_paid = False "
							"GROUP BY employee_id, name ORDER BY name")
		for row in self.cursor.fetchall():
			employee_id = row[0]
			employee_name = row[1]
			self.employee_store.append([str(employee_id), employee_name])

	def employee_combo_changed (self, combo):
		employee_id = combo.get_active_id()
		if employee_id != None:
			self.employee_id = employee_id
			self.populate_employee_statistics ()
			self.calculate_payment ()

	def hourly_wage_changed (self, spinbutton):
		self.calculate_payment ()

	def calculate_payment (self):
		wage = self.builder.get_object('spinbutton1').get_value()
		adjust_h = self.adjusted_seconds / 3600
		adjusted_hours = round(adjust_h, 2)
		payment = round(wage * adjusted_hours, 2)
		self.payment = payment
		#self.builder.get_object('label10').set_label('${:,.2f}'.format(payment))

	def populate_employee_statistics (self):
		if self.employee_id == 0:
			return
		self.employee_payment_store.clear()
		'''self.cursor.execute ("SELECT COUNT(id) FROM time_clock_entries "
							"WHERE (employee_id, state) = "
							"(%s, 'running') AND start_time < %s",
							(self.employee_id, self.stop_time))
		for row in self.cursor.fetchall():
			count = row[0]
			if count == 0:
				self.builder.get_object('button1').set_sensitive(True)
				message = "%s is punched out of all jobs." % employee_name
			else:
				message = "%s is still punched in." % employee_name
				self.builder.get_object('button1').set_sensitive(False)
			self.builder.get_object('label9').set_label(message)'''
		self.cursor.execute("SELECT id "
							"FROM time_clock_entries "
							"WHERE (employee_id, employee_paid) = "
							"(%s, False) "
							"AND stop_time < %s",
							(self.employee_id, self.stop_time))
		self.time_clock_entries_ids = self.cursor.fetchall()
		self.cursor.execute("SELECT SUM(actual_seconds), SUM(adjusted_seconds) "
							"FROM time_clock_entries "
							"WHERE (employee_id, employee_paid) = "
							"(%s, False) "
							"AND stop_time < %s",
							(self.employee_id, self.stop_time))
		for row in self.cursor.fetchall():
			self.actual_seconds = row[0]
			self.adjusted_seconds = row[1]
			if self.actual_seconds == None:
				self.actual_seconds = 0.0
			if self.adjusted_seconds == None:
				self.adjusted_seconds = 0.0
			actual_time = self.convert_seconds (self.actual_seconds)
			adjusted_time = self.convert_seconds (self.adjusted_seconds)
		
		if self.adjusted_seconds == 0 and self.actual_seconds == 0:
			self.efficiency = 0
		else:
			self.efficiency = self.adjusted_seconds/self.actual_seconds * 100

		self.builder.get_object('entry1').set_text(actual_time)
		self.builder.get_object('entry6').set_text(adjusted_time)
		self.builder.get_object('entry4').set_text(cost_sharing_time)
		self.builder.get_object('entry5').set_text(profit_sharing_time)
		self.builder.get_object('entry7').set_text(str(self.efficiency))

	def post_employee_payment_clicked (self, button):
		actual_hours = self.actual_seconds / 3600
		adjusted_hours = self.adjusted_seconds / 3600
		cost_sharing_hours = self.cost_sharing_seconds / 3600
		profit_sharing_hours = self.profit_sharing_seconds / 3600
		wage = self.builder.get_object('spinbutton1').get_value()
		self.cursor.execute ("INSERT INTO pay_stubs "
							"(employee_id, date_inserted, regular_hours, "
							"cost_sharing_hours, profit_sharing_hours, "
							"hourly_wage) "
							"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
							(self.employee_id, datetime.today(), adjusted_hours,
							cost_sharing_hours, profit_sharing_hours, wage))
		self.pay_stub_id = self.cursor.fetchone()[0]		
		self.view_report ()
		subprocess.call('odt2pdf ' + self.time_file, shell = True)
		f = open(self.time_file_pdf,'rb')
		data = f.read()
		binary = psycopg2.Binary(data)
		f.close()
		self.cursor.execute("UPDATE pay_stubs SET pdf_data = %s WHERE id = %s",
							(binary, self.pay_stub_id))
							
		for row in self.time_clock_entries_ids:
			row_id = row[0]
			self.cursor.execute("UPDATE time_clock_entries SET "
								"(employee_paid, pay_stub_id) = "
								"(True, %s) WHERE id = %s",
								(self.pay_stub_id, row_id))
		self.db.commit()
		self.populate_employees ()
		self.builder.get_object('button1').set_sensitive(False)

	def view_report_clicked (self, button):
		self.view_report ()
		
	def view_report (self):
		self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",
								[self.employee_id])
		customer = Item()
		for row in self.cursor.fetchall():
			self.customer_id = row[0]
			customer.name = row[1]
			name = row[1]
			customer.ext_name = row[2]
			customer.street = row[3]
			customer.city = row[4]
			customer.state = row[5]
			customer.zip = row[6]
			customer.fax = row[7]
			customer.phone = row[8]
			customer.email = row[9]
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
		actual_hours = self.actual_seconds / 3600
		adjusted_hours = self.adjusted_seconds / 3600
		cost_sharing_hours = self.cost_sharing_seconds / 3600
		profit_sharing_hours = self.profit_sharing_seconds / 3600
		time = Item()
		time.actual = round(actual_hours, 2)
		time.adjusted = round(adjusted_hours, 2)
		time.cost_sharing = round(cost_sharing_hours, 2)
		time.profit_sharing = round(profit_sharing_hours, 2)
		time.efficiency = round(self.efficiency, 2)
		payment = Item()
		time.payment_due = '${:,.2f}'.format(self.payment)
		wage = self.builder.get_object('spinbutton1').get_value()
		time.wage = '${:,.2f}'.format(wage)
		self.data = dict(contact = customer, time = time, company = company, 
						payment = payment)
		from py3o.template import Template #import for every use or there is an error about invalid magic header numbers
		self.time_file = "/tmp/employee_time.odt"
		self.time_file_pdf = "/tmp/employee_time.pdf"
		t = Template(constants.template_dir+"/employee_time.odt", self.time_file , True)
		t.render(self.data) #the self.data holds all the info of the invoice
				
		subprocess.call('soffice ' + self.time_file, shell = True)
		

	def calendar_day_selected (self, calendar):
		date_tuple = calendar.get_date()
		self.datetime = calendar_to_datetime(date_tuple)
		day_text = datetime_to_text(self.datetime)
		self.builder.get_object('entry8').set_text(day_text)
		morrow = self.datetime + timedelta(days = 1)
		morrow_string = str(morrow)[0:10]
		struct_time = time.strptime(morrow_string,"%Y-%m-%d")
		self.stop_time = time.mktime(struct_time)
		self.populate_employee_statistics ()

	def calendar_icon_clicked (self, widget, icon, event):
		calendar = self.builder.get_object('calendar1')
		set_calendar_from_datetime (calendar, self.datetime)
		self.popover.set_relative_to(widget)
		self.popover.show()

	def convert_seconds(self, start_seconds):
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

	def seconds_to_day (self, seconds):
		date = datetime.fromtimestamp(seconds)
		day_formatted = datetime.strftime(date,"%b %d %y %I:%M %p")
		return day_formatted


		
