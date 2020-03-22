# manufacturing.py
#
# Copyright (C) 2020 - reuben
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


from gi.repository import Gtk, GLib
from constants import ui_directory, template_dir, DB, broadcaster

UI_FILE = ui_directory + "/manufacturing/projects.ui"


class ManufacturingProjectsGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.window = self.get_object('window')
		self.window.show_all()
		self.populate_projects ()

	def populate_projects (self):
		store = self.get_object('manufacturing_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT mp.id, "
						"p.name, "
						"p.ext_name, "
						"mp.qty, "
						"mp.name, "
						"(SELECT COUNT(id) FROM serial_numbers "
							"WHERE manufacturing_id = mp.id) "
						"FROM manufacturing_projects AS mp "
						"JOIN products AS p ON p.id = mp.product_id "
						"WHERE mp.active = True")
		for row in cursor.fetchall():
			store.append(row)
		DB.rollback()
		cursor.close()

	def new_clicked (self, button):
		from manufacturing import project_edit_main
		meg = project_edit_main.ProjectEditGUI(self)
		meg.window.set_transient_for(self.window)

	def edit_clicked (self, button):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		project_id = model[path][0]
		from manufacturing import project_edit_main
		meg = project_edit_main.ProjectEditGUI(self, project_id)
		meg.window.set_transient_for(self.window)




