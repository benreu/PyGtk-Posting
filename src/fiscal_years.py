# fiscal_years.py
#
# Copyright (C) 2018 - reuben
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
from dateutils import DateTimeCalendar
from datetime import datetime, timedelta
import constants

UI_FILE = constants.ui_directory + "/fiscal_years.ui"

class FiscalYearGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()

		self.start_calendar = DateTimeCalendar(True)
		self.start_calendar.connect('day-selected', self.start_day_selected)
		self.start_calendar.set_today()

		self.end_calendar = DateTimeCalendar(True)
		self.end_calendar.connect('day-selected', self.end_day_selected)
		self.end_calendar.set_date(datetime.today() + timedelta(days=365))

		self.fiscal_year_store = self.builder.get_object('fiscal_year_store')
		self.window = self.builder.get_object('window')
		self.window.show_all()
		
		self.populate_fiscal_years()

	def populate_fiscal_years (self):
		self.fiscal_year_store.clear()
		self.cursor.execute("SELECT "
								"id, "
								"name, "
								"start_date::text, "
								"format_date(start_date), "
								"end_date::text, "
								"format_date(end_date), "
								"active "
							"FROM fiscal_years ORDER BY start_date")
		for row in self.cursor.fetchall():
			self.fiscal_year_store.append(row)

	def active_toggled (self, toggle_renderer, path):
		active = not toggle_renderer.get_active()
		id_ = self.fiscal_year_store[path][0]
		self.cursor.execute("UPDATE fiscal_years SET active = %s "
							"WHERE id = %s", (active, id_))
		self.db.commit()
		self.populate_fiscal_years ()

	def fiscal_years_name_edited (self, textrenderer, path, text):
		id_ = self.fiscal_year_store[path][0]
		self.cursor.execute("UPDATE fiscal_years SET name = %s "
							"WHERE id = %s", (text, id_))
		self.db.commit()
		self.populate_fiscal_years ()

	def create_fiscal_year_clicked (self, button):
		dialog = self.builder.get_object('dialog1')
		response = dialog.run()
		dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			fiscal_name = self.builder.get_object('entry1').get_text()
			self.cursor.execute("INSERT INTO fiscal_years "
								"(name, start_date, end_date, active) "
								"VALUES (%s, %s, %s, True)", 
								(fiscal_name, self.start_date, self.end_date))
			self.db.commit()
			self.builder.get_object('entry1').set_text('')
			self.populate_fiscal_years()
			
	def start_day_selected (self, calendar):
		self.start_date = calendar.get_datetime()
		day_text = calendar.get_text()
		self.builder.get_object('entry2').set_text(day_text)

	def end_day_selected (self, calendar):
		self.end_date = calendar.get_datetime()
		day_text = calendar.get_text()
		self.builder.get_object('entry3').set_text(day_text)

	def start_date_icon_released (self, entry, position, event):
		self.start_calendar.set_relative_to (entry)
		#self.start_calendar.set_position (Gtk.PositionType.TOP)
		self.start_calendar.show()

	def end_date_icon_released (self, entry, position, event):
		self.end_calendar.set_relative_to (entry)
		self.end_calendar.show()

	def fiscal_year_name_entry_changed (self, entry):
		if entry.get_text() != '':
			self.builder.get_object('button1').set_sensitive(True)
		else:
			self.builder.get_object('button1').set_sensitive(False)




		
