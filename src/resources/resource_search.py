# resource_search.py
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
import re
from dateutils import DateTimeCalendar
from constants import ui_directory, DB

UI_FILE = ui_directory + "/resources/resource_search.ui"

class ResourceSearchGUI:
	def __init__ (self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def resource_search_changed (self, entry):
		store = self.builder.get_object('resource_store')
		store.clear()
		search = entry.get_text().lower()
		search = re.sub("%", " ", search)
		search = "%" + search + "%" 
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"id, "
								"subject, "
								"dated_for::text, "
								"format_date(dated_for) "
							"FROM resources WHERE diary = True "
							"AND LOWER(subject) LIKE %s ORDER BY dated_for", 
							(search,))
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

		
