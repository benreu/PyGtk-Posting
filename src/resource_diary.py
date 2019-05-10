# resource_diary.py
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


from gi.repository import Gtk
from datetime import timedelta
from dateutils import DateTimeCalendar
import spell_check
import constants

UI_FILE = constants.ui_directory + "/resource_diary.ui"

class ResourceDiaryGUI:
	def __init__(self):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()
		self.populating = False

		textview = self.builder.get_object('textview1')
		spell_check.add_checker_to_widget (textview)

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def add_day_info (self):
		self.populating = True
		cursor = self.db.cursor()
		cursor.execute("WITH date_range AS "
							"(SELECT generate_series "
								"(%s - INTERVAL '4 year', "
								"%s,  '1 year' "
								") AS diary_date "
							") "
						"SELECT "
							"COALESCE(subject, ''), "
							"to_char(date_range.diary_date, 'Dy FMMonth DD YYYY') "
						"FROM date_range "
						"LEFT JOIN resources "
						"ON date_range.diary_date = resources.dated_for "
						"AND diary = True "
						"ORDER BY date_range.diary_date DESC", 
						(self.day, self.day))
		tupl = cursor.fetchall()
		
		subject0 = tupl[0][0]
		date0 = tupl[0][1]
		
		self.builder.get_object('label1').set_label(date0)
		self.builder.get_object('entry1').set_text(date0)
		self.builder.get_object('textbuffer1').set_text(subject0)
		
		subject1 = tupl[1][0]
		date1 = tupl[1][1]
		
		self.builder.get_object('label2').set_label(date1)
		self.builder.get_object('textbuffer2').set_text(subject1)
		
		subject2 = tupl[2][0]
		date2 = tupl[2][1]
				
		self.builder.get_object('label3').set_label(date2)
		self.builder.get_object('textbuffer3').set_text(subject2)
		
		subject3 = tupl[3][0]
		date3 = tupl[3][1]
		
		self.builder.get_object('label4').set_label(date3)
		self.builder.get_object('textbuffer4').set_text(subject3)
		
		subject4 = tupl[4][0]
		date4 = tupl[4][1]
		
		self.builder.get_object('label5').set_label(date4)
		self.builder.get_object('textbuffer5').set_text(subject4)
		cursor.close()
		self.populating = False

	def next_day_clicked (self, button):
		self.day = (self.day + timedelta(days = 1))
		self.calendar.set_date(self.day) # this will fire signal and update views

	def previous_day_clicked (self, button):
		self.day = (self.day - timedelta(days = 1))
		self.calendar.set_date(self.day) # this will fire signal and update views

	def diary_textbuffer_changed (self, textbuffer):
		if self.populating == True:
			return
		end = textbuffer.get_end_iter()
		start = textbuffer.get_start_iter()
		text = textbuffer.get_text(start, end, True)
		self.cursor.execute("INSERT INTO resources "
							"(subject, dated_for, diary) "
							"VALUES (%s, %s, True) "
							"ON CONFLICT (dated_for, diary) "
							"DO UPDATE SET subject = %s " 
							"WHERE (resources.diary, resources.dated_for) = "
							"(True, %s)", 
							(text, self.day, text, self.day))
		self.db.commit()

	def entry_icon_release (self, entry, position, button):
		self.calendar.set_relative_to (entry)
		self.calendar.show()

	def calendar_day_selected (self, calendar):
		self.day = calendar.get_date ()
		text = calendar.get_user_text ()
		self.add_day_info ()

		
		
		
