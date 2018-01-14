# pay_stub.py
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


from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, GObject, Pango
from datetime import datetime
import time, re, ssl, calendar, subprocess

UI_FILE = "src/pay_stub.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class Month(object):       #converts the month number to text
	def __new__(self ):
		self.month = (["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov","Dec"])
		return self.month

class PayStubGUI:
	def __init__(self, db):
		#pdb.set_trace()
		#Gdk.beep()
		#print Gdk.Display.get_pointer(Gdk.MODIFIER_MASK)
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		self.cursor = self.db.cursor()
		self.cursor2 = self.db.cursor()
		date = str(datetime.today())
		self.date = re.sub("-"," ",date)
		self.entry = 'entry1'
		self.day = 1
		self.get_date()
		self.day = self.date[8:11]
		
		self.entry = 'entry2'
		self.get_date()


		self.populate_employee_combobox ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		
	def update_database(self,widget = None):
		for ids in self.paid_id_loop:
			self.cursor.execute("UPDATE time_clock_entries SET employee_paid = True WHERE id = %s",(ids,))
		self.db.commit()


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
		self.load_time_data ()


	def populate_employee_combobox (self):
		employee_combo = self.builder.get_object('comboboxtext1')
		self.cursor.execute("SELECT id, name FROM contacts WHERE employee = True")
		for row in self.cursor.fetchall():
			employee_id = row[0]
			employee_name = row[1]
			employee_combo.append (str(employee_id), employee_name)

	def populate_project_combobox (self):
		project_combo = self.builder.get_object('comboboxtext2')
		self.cursor.execute ("SELECT id, name FROM time_clock_projects WHERE active = True")
		for row in self.cursor.fetchall():
			project_id = row[0]
			project_name = row[1]
			project_combo.append(str(project_id), project_name)



	def get_date(self, widget = None):
		if widget == None:
			current_date_tuple = list()
			date_tuple = tuple ()
			day_rendered = 1
			date_str = self.date[0:4] + ' ' + str(int(self.date[5:8])-1) + ' ' + str(int(self.day)) + ' '#self.date[8:11]
			courier =''
			for i in date_str:
				if i == ' ':
					current_date_tuple.append(int(courier))
					courier = ''
				else:
					courier = courier + i
			date_tuple = current_date_tuple
		else:
			date_tuple = self.builder.get_object('calendar1').get_date()

		day_numeric = date_tuple[2]
		day = str(day_numeric)
		if len(day) < 2:
			day = "0" + day 
		month_numeric = date_tuple[1]
		month_text = Month()[month_numeric] 
		month = str(month_numeric)
		if len(month) < 2:
			month = "0" + month
		year_numeric = date_tuple[0]
		day_text = month_text + " " + str(day_numeric) + " " + str(year_numeric)#format the string so we can read it easily
		self.builder.get_object(self.entry).set_text(day_text)


	def pay_period_begin(self,widget,icon,void):
		
		self.entry = ''
		self.day = 1
		self.calendar()
		
		self.builder.get_object('window2').show()
		self.entry = 'entry1'

	def pay_period_end(self,widget,icon,void):
		self.entry = ''
		self.day = self.date[8:11]
		self.calendar()
		self.builder.get_object('window2').show()
		self.entry = 'entry2'
		
	def calendar(self, widget = None):
		year = self.date[2:4]
		month = int(self.date[5:8])-1
		calendar = self.builder.get_object('calendar1')
		calendar.select_month(int(month), int("20" + year))
		calendar.select_day(int(self.day))


	def calendar_close(self, widget=None, dummy=None):
		self.day = ''
		self.builder.get_object('window2').hide()
		return True

	def create_seconds_from_date(self,date_entry): # Assumes midnight AM as referance
		split_date = date_entry.split(" ")
		year = split_date[2]
		month = split_date[0]
		day = split_date[1]
		self.date_seconds = ssl.cert_time_to_seconds(str(month) + "  "+ str(day) +" 00:00:00 "+ str(year) + " GMT")

	def generate_pay_stub(self,widget):
		self.paid_id_loop = list()
		date_entry = self.builder.get_object('entry1').get_text()
		begin_date = date_entry
		self.create_seconds_from_date(date_entry)
		begin = self.date_seconds
		date_entry = self.builder.get_object('entry2').get_text()
		end_date = date_entry 
		self.create_seconds_from_date(date_entry)
		end = self.date_seconds
		self.cursor.execute("SELECT * FROM company_info")
		company = Item()
		for row in self.cursor.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.email = row[9]
			company.fax = row[8]
			company.website = row[10]
			company.tax_number = row[11]
		
		pp_info = Item() # currently hardcoded ToDo: Build payperiod info data base
		pp_info.ppd_begin = begin_date
		pp_info.ppd_end = end_date
		pp_info.ppd_frequency =  ''
		pp_info.ppd_number = 1
		pp_info.temporary_copy = 'Temporary Copy'


		self.cursor.execute("SELECT id FROM contacts WHERE employee = True AND deleted = False")
		for t in self.cursor.fetchall():
			employee_id = t[0]
			self.cursor.execute("SELECT * FROM company_info")
			company = Item()
			for row in self.cursor.fetchall():
				company.name = row[1]
				company.street = row[2]
				company.city = row[3]
				company.state = row[4]
				company.zip = row[5]
				company.country = row[6]
				company.phone = row[7]
				company.email = row[9]
				company.fax = row[8]
				company.website = row[10]
				company.tax_number = row[11]


				self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",(employee_id,))
				customer = Item()
				for row in self.cursor.fetchall():
					self.customer_id = row[0]
					customer.name = row[1]
					customer.c_o = row[2]
					customer.street = row[3]
					customer.city = row[4]
					customer.state = row[5]
					customer.zip = row[6]
					customer.fax = row[7]
					customer.phone = row[8]
					customer.email = row[9]
					customer.label = row[10]
					customer.tax_exempt = row[11]
					customer.tax_exempt_number = row[12]

					time_card = Item()
					self.cursor.execute("SELECT id,start_time,stop_time,state,employee_id,project_id,employee_paid FROM time_clock_entries WHERE start_time < %s  AND (employee_id,employee_paid) = (%s,False) ORDER BY start_time ASC",(end,int(employee_id))) #employee_paid == False
					items = list()
					overtime_accumulator = 0
					total_seconds_accumulator = 0
					roll_call_date_courier = ''
					roll_call_day_counter = 0
					for loop in self.cursor.fetchall():
						item = Item()
						self.paid_id_loop.append(loop[0])
						roll_call_date = datetime.strftime(datetime.fromtimestamp(loop[1]),"%a %b %d %Y")
						if  loop[1] >= end   or roll_call_date == roll_call_date_courier:
							continue
						else:#now we're computing the multiple values and consolidating their values into a single line for every day.
							roll_call_day_counter += 1
							roll_call_date_courier = roll_call_date
							self.create_seconds_from_date (datetime.strftime(datetime.fromtimestamp(loop[1]),"%b %d %Y"))#function call needed to set global variable 'self.date_seconds'
							total_time_in_seconds = 0
							seconds_am = self.date_seconds
							seconds_pm = seconds_am + 86399.5
							self.cursor2.execute("SELECT id,start_time,stop_time,state,employee_id,project_id,employee_paid FROM time_clock_entries WHERE start_time <= %s  AND start_time > %s AND (employee_id,employee_paid) = (%s,False) ORDER BY start_time ASC",(seconds_pm,seconds_am,int(employee_id))) 
							
							for loop2 in self.cursor2.fetchall():
								project_change_start_time_in_seconds = float(loop2[1])
								last_entry_of_project = float(loop2[2])
								time_elapsed = last_entry_of_project - project_change_start_time_in_seconds
								total_time_in_seconds =  time_elapsed + total_time_in_seconds
								


							 

							item.roll_call_date = roll_call_date_courier
							item.start_time = datetime.strftime(datetime.fromtimestamp(loop[1]),"%I %M %p")
							item.ending_time = datetime.strftime(datetime.fromtimestamp(last_entry_of_project),"%I %M %p")
							fmt_time = str(round(float(total_time_in_seconds)/3600,2))
							fmt_time = fmt_time.split(".")
							item.hrs_today = str(fmt_time[0]) + ' hr ' + str(int(round((3600 * float('.' + fmt_time[1])/60),0))) +' min'
							time_off_seconds = float(last_entry_of_project - loop[1])- total_time_in_seconds
							calc = str(round(time_off_seconds/3600,2))
							calc = calc.split(".")
							item.time_out = str(calc[0]) + ' hr ' + str(int(round((3600 * float('.' + calc[1])/60),0))) +' min'
							if total_time_in_seconds > 28800:
								decimal_equiv_over_8 = round((total_time_in_seconds-28800)/3600,2)
								calc2 = str(decimal_equiv_over_8)
								calc2 = calc2.split(".")
								item.over_eight = str(calc2[0]) + ' hr ' + str(int(round((3600 * float('.' + calc2[1])/60),0))) +' min'
							else:
								decimal_equiv_over_8 = 0
								item.over_eight = ''
							items.append(item)
						total_seconds_accumulator = total_seconds_accumulator + total_time_in_seconds
						overtime_accumulator = overtime_accumulator + decimal_equiv_over_8
					decimal_equiv_over_8_ttl = overtime_accumulator
					decimal_equiv_ttl_hrs = round((total_seconds_accumulator)/3600,2)



	
				base_pay_rate = round(float(self.builder.get_object('entry4').get_text()),2)
				totals = Item()
				totals.days_in_pp = str(roll_call_day_counter)
				totals.av_hr_day = round(decimal_equiv_ttl_hrs/roll_call_day_counter,2)
				totals.ttl_time_out = 'N/A'
				totals.acc_overtime = round(decimal_equiv_over_8_ttl,2)
				totals.base_pay_rate = round (base_pay_rate,2)
				totals.non_overtime_hrs = round(decimal_equiv_ttl_hrs-decimal_equiv_over_8_ttl)
				totals.overtime_pay_rate = round (base_pay_rate*1.5,2)
				totals.reg_rate_ttl = round (decimal_equiv_ttl_hrs*base_pay_rate,2)
				totals.overtime_rate_ttl = round(decimal_equiv_over_8_ttl*totals.overtime_pay_rate,2)
				totals.tip = ''
				totals.dues = ''
				totals.pretax_sub_ttl = round (totals.overtime_rate_ttl+totals.reg_rate_ttl,2)
				totals.ss = ''
				totals.medicare = ''
				totals.state_with_holding = ''
				totals.federal_with_holding = ''
				totals.wage_ttl_pmt = ''
				self.data = dict(contact = customer,company = company,totals = totals,items = items,pp_info = pp_info)
				from py3o.template import Template #import for every invoice or there is an error about invalid magic header numbers
				self.tmp_file = "/tmp/time_card.odt"
				t = Template("./templates/time_card_template.odt", self.tmp_file , True)
				t.render(self.data) #the self.data holds all the info of the invoice
				subprocess.call("soffice   " + self.tmp_file, shell = True)
		#self.update_database()
		self.window.hide()
		return True

	def view_temp_copy(self,widget):
		pass
