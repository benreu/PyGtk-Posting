# resource_diary.py
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
from datetime import datetime, timedelta, date
from dateutils import datetime_to_user_date, DateTimeCalendar
import spell_check

UI_FILE = "src/resource_diary.ui"

class ResourceDiaryGUI:
	def __init__(self, db):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		textview = self.builder.get_object('textview1')
		spell_check.add_checker_to_widget (textview)

		self.day = date.today()
		self.add_day_info ()
		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def add_day_info (self):
		text = datetime_to_user_date (self.day)
		self.builder.get_object('label5').set_label(text)
		self.builder.get_object('entry1').set_text(text)
		diary = self.get_diary (self.day)
		self.builder.get_object('textbuffer1').set_text(diary)
		
		year_ago = self.day.replace(year = (self.day.year - 1))
		text = datetime_to_user_date (year_ago)
		self.builder.get_object('label13').set_label(text)
		diary = self.get_diary (year_ago)		
		self.builder.get_object('textbuffer2').set_text(diary)
		
		two_year_ago = year_ago.replace (year = (year_ago.year - 1))
		text = datetime_to_user_date (two_year_ago)
		self.builder.get_object('label14').set_label(text)
		diary = self.get_diary (two_year_ago)		
		self.builder.get_object('textbuffer3').set_text(diary)
		
		three_year_ago = two_year_ago.replace (year = (two_year_ago.year - 1))
		text = datetime_to_user_date (three_year_ago)
		self.builder.get_object('label15').set_label(text)
		diary = self.get_diary (three_year_ago)		
		self.builder.get_object('textbuffer4').set_text(diary)
		
		four_year_ago = three_year_ago.replace (year = (three_year_ago.year - 1))
		text = datetime_to_user_date (four_year_ago)
		self.builder.get_object('label16').set_label(text)
		diary = self.get_diary (four_year_ago)		
		self.builder.get_object('textbuffer5').set_text(diary)
		
	def get_diary (self, date):
		diary = '' # blank string in case there are no results
		self.cursor.execute("SELECT subject FROM resources "
							"WHERE dated_for = %s AND "
							"diary = True", 
							(date,))
		for row in self.cursor.fetchall():
			diary = row[0]
			if diary == None: # diary might be None
				diary = ''
		return diary

	def next_day_clicked (self, button):
		self.day = (self.day + timedelta(days = 1))
		self.add_day_info ()

	def previous_day_clicked (self, button):
		self.day = (self.day - timedelta(days = 1))
		self.add_day_info ()

	def diary_textbuffer_changed (self, textbuffer):
		end = textbuffer.get_end_iter()
		start = textbuffer.get_start_iter()
		text = textbuffer.get_text(start, end, True)
		self.cursor.execute("UPDATE resources SET subject = %s "
							"WHERE dated_for = %s AND "
							"diary = True RETURNING id", (text, self.day))
		for row in self.cursor.fetchall():
			break # record found
		else: # no diary found for this date; create one
			self.cursor.execute("INSERT INTO resources "
								"(subject, dated_for, diary) "
								"VALUES (%s, %s, True) ", (text, self.day))
		self.db.commit()

	def entry_icon_release (self, entry, position, button):
		self.calendar.set_relative_to (entry)
		self.calendar.show()

	def calendar_day_selected (self, calendar):
		self.day = calendar.get_date ()
		text = calendar.get_user_text ()
		self.add_day_info ()

		
		
		