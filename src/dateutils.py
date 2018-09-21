# dateutils.py
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

from gi.repository import Gtk, GObject, GLib
from datetime import datetime, date, timedelta
from main import cursor
import time

PARSE_STRING = "%b %d %Y"
USER_FORMAT_DATE_TIME = "%a %b %d %Y %I:%M:%S %p"
USER_FORMAT_DATE = "%a %b %d %Y"
DB_FORMAT_DATE = "%Y-%m-%d"

# -- datetime utils -- #

def datetime_to_user_date_time (date_time):
	print ("datetime_to_user_date_time is deprecated, please use Postgres function")
	if date_time == None:
		return ''
	date_string = datetime.strftime(date_time, USER_FORMAT_DATE_TIME)
	return date_string

def datetime_to_compact_string (date_time):
	print ("datetime_to_compact_string is deprecated, please use Postgres function")
	if date_time == None:
		return ''
	date_string = datetime.strftime(date_time, "%H:%M:%S")
	return date_string

def datetime_to_user_date (date_time):
	print ("datetime_to_user_date is deprecated, please use Postgres function")
	if date_time == None:
		return ''
	date_string = datetime.strftime(date_time, USER_FORMAT_DATE)
	return date_string

def text_to_datetime (text):
	date_time = datetime.strptime (text, PARSE_STRING)
	return date_time

def datetime_to_text (date_time):
	print ("datetime_to_text is deprecated, please use Postgres function")
	if date_time == None or date_time == '':
		return ''
	date_string = datetime.strftime(date_time, PARSE_STRING)
	return date_string

def calendar_to_text (calendar_date):
	if calendar_date == None or calendar_date == '':
		return ''
	date = calendar_to_datetime (calendar_date)
	day_text = datetime_to_text (date)
	return day_text

def calendar_to_datetime (calendar_date):
	day = calendar_date[2]
	month = int(calendar_date[1])
	year = calendar_date[0]
	date = str(year)[2:4] + " " + str(month + 1) + " " + str(day)
	date_time = datetime.strptime(date,"%y %m %d")
	return date_time

def set_calendar_from_datetime (calendar, date_time):
	date_time = str(date_time)
	year = date_time[0:4]
	month = date_time[5:7]
	day = date_time[8:10]
	calendar.select_month(int(month) - 1, int(year))
	calendar.select_day(int(day))

#-- date (not datetime) utils --#

def date_to_text (date):
	print ("date_to_text is deprecated, please use Postgres function")
	date_string = date.strftime(PARSE_STRING)
	return date_string

def date_to_user_format (date):
	print ("date_to_user_format is deprecated, please use Postgres function")
	date_string = date.strftime(USER_FORMAT_DATE)
	return date_string

def calendar_to_text (calendar_date):
	date = calendar_to_date(calendar_date)
	day_text = date_to_text (date)
	return day_text

def calendar_to_date (calendar_date):
	_day_ = calendar_date[2]
	_month_ = int(calendar_date[1]) + 1
	_year_ = calendar_date[0]
	_date_ = date(year = _year_, month = _month_, day = _day_)
	return _date_

def set_calendar_from_date (calendar, date):
	date = str(date)
	year = date[0:4]
	month = date[5:7]
	day = date[8:10]
	calendar.select_month(int(month) - 1, int(year))
	calendar.select_day(int(day))

#-- seconds converter --#

def seconds_to_user_format (seconds):
	if seconds == None:
		return ''
	date = datetime.fromtimestamp(seconds)
	day_formatted = datetime.strftime(date,USER_FORMAT_DATE_TIME)
	return day_formatted

def seconds_to_compact_string (start_seconds):
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


#### calendar class ####

class DateTimeCalendar (Gtk.Popover):
	'''A Gtk Calendar within a Gtk Popover that recognizes Python datetimes'''
	__gsignals__ = { 'day_selected': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ())}
	
	__gtype_name__ = 'DateTimeCalendar'
	
	def __init__(self, override = False):
		Gtk.Popover.__init__(self)
		self.calendar = Gtk.Calendar()
		date_label = Gtk.Label('No date')
		s = "<span foreground='#d40000'>No fiscal range applicable</span>"
		fiscal_label = Gtk.Label(s, use_markup = True)
		fiscal_label.set_no_show_all(True)
		self.box = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.box.pack_start (self.calendar, False, False, 0 )
		self.box.pack_start (date_label, False, False, 0 )
		self.box.pack_start (fiscal_label, False, False, 0 )
		self.box.show_all()
		self.add (self.box)
		self.timeout = None
		self.error = False
		self.calendar.connect('day-selected', self.day_selected, date_label, fiscal_label, override)
		self.calendar.connect('day-selected-double-click', self.day_double_click)
		self.calendar.connect("unmap-event", self.do_focus_out_event)

	@classmethod
	def new (self):
		return self

	def pack_start (self, widget):
		self.box.pack_start(widget, False, False, 0)

	def get_first_d_of_yr (self):
		date_time = self.get_datetime ()
		first_d_of_yr_str = datetime.strftime(date_time,"%Y" ) + '-01-01'
		return first_d_of_yr_str 

	def day_double_click (self, calendar):
		self.hide()

	def get_date (self):
		'''gets a Pythonic date from the calendar'''
		if self.error == True:
			return None
		date_time = self.get_datetime ()
		return date_time.date()

	def get_datetime (self):
		'''gets a Pythonic datetime from the calendar'''
		calendar_date = self.calendar.get_date()
		day = calendar_date[2]
		month = int(calendar_date[1])
		year = calendar_date[0]
		date = str(year)[2:4] + " " + str(month + 1) + " " + str(day)
		date_time = datetime.strptime(date,"%y %m %d")
		return date_time

	def get_text(self):
		global cursor
		if self.error == True:
			return ''
		date = self.get_datetime().date()
		cursor.execute("SELECT format_date(%s)", (date,))
		return cursor.fetchone()[0]

	def set_datetime (self, date_time):
		date_time = str(date_time)
		year = date_time[0:4]
		month = date_time[5:7]
		day = date_time[8:10]
		self.calendar.select_month(int(month) - 1, int(year))
		self.calendar.select_day(int(day))

	def set_date (self, date):
		date_time = str(date)
		year = date_time[0:4]
		month = date_time[5:7]
		day = date_time[8:10]
		self.calendar.select_month(int(month) - 1, int(year))
		self.calendar.select_day(int(day))

	def get_user_text (self):
		if self.error == True:
			return ''
		date_time = self.get_datetime ()
		date_string = datetime.strftime(date_time, USER_FORMAT_DATE)
		return date_string

	def get_last_second_of_date (self):
		datetime = self.get_datetime ()
		morrow = datetime + timedelta(seconds = 86399)
		struct_time = time.strptime(str(morrow),"%Y-%m-%d %H:%M:%S")
		last_second = time.mktime(struct_time)
		return last_second

	def set_today(self):
		date_time = datetime.today()
		self.set_datetime (date_time)

	def day_selected (self, calendar, date_label, fiscal_label, override):
		global cursor
		date_time = self.get_datetime ()
		cursor.execute("SELECT id FROM fiscal_years "
							"WHERE active = True AND %s >= start_date "
							"AND %s <= end_date", (date_time, date_time))
		if cursor.fetchone() == None and override == False:
			fiscal_label.show()
			date_string = ''
			date_label.hide()
			self.error = True
			if self.timeout == None:
				self.timeout = GLib.timeout_add_seconds(2, self.force_show)
		else:
			date_string = datetime.strftime(date_time, "%m-%d-%Y")
			date_label.show()
			self.error = False
			if self.timeout != None:
				fiscal_label.hide()
				GLib.source_remove(self.timeout)
				self.timeout = None		
		date_label.set_label(str(date_string))
		self.emit('day-selected')

	def force_show (self):
		self.show()
		return self.error

GObject.type_register(DateTimeCalendar)


	
	