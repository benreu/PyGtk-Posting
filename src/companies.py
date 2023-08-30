# companies.py
#
# Copyright (C) 2023 - Reuben Rissler
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
from constants import ui_directory
from constants import log_file as LOG_FILE
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/companies.ui"

class OpenCompanyGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		window = self.get_object('window')
		window.show_all()
		self.populate_companies()

	def populate_companies(self):
		store = self.get_object('companies_store')
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT id, name, server "
											"FROM db_connections"):
			store.append(row)
		sqlite.close()

	def open_company_clicked (self, button):
		selection = self.get_object('treeview_selection')
		model, iter_ = selection.get_selected()
		if iter_ == None:
			return
		row_id = model[iter_][0]
		subprocess.Popen(["./src/main.py", 
							"database %s" % row_id, str(LOG_FILE)])

	def switch_to_company_clicked (self, button):
		selection = self.get_object('treeview_selection')
		model, iter_ = selection.get_selected()
		if iter_ == None:
			return
		row_id = model[iter_][0]
		subprocess.Popen(["./src/main.py", 
							"database %s" % row_id, str(LOG_FILE)])
		Gtk.main_quit()


