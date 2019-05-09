# jobs.py
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

from gi.repository import Gtk, GdkPixbuf, Gdk
import os, sys
import main

UI_FILE = main.ui_directory + "/job_types.ui"


class GUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.db = main.db
		self.cursor = self.db.cursor()

		self.job_store = self.get_object('job_type_store')
		self.job_treeview_populate ()

		self.id_ = 0
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def row_activate(self, treeview, path, treeviewcolumn):
		treeiter = self.job_store.get_iter(path)
		self.id_ = self.job_store.get_value(treeiter, 0)
		self.cursor.execute("SELECT name FROM job_types "
							"WHERE id = %s", (self.id_, ) )
		for row in self.cursor.fetchall():
			name = row[0]
			self.get_object('entry1').set_text(name)

	def job_treeview_populate (self):
		self.job_store.clear()
		self.cursor.execute("SELECT id, name FROM job_types ORDER BY name")
		for row in self.cursor.fetchall():
			self.job_store.append(row)

	def save(self, widget):
		job = widget.get_text()
		if self.id_ == 0:
			self.cursor.execute("INSERT INTO job_types (name) "
								"VALUES (%s)", (job,))
		else:
			self.cursor.execute("UPDATE job_types "
								"SET name = %s "
								"WHERE id = %s", (job,self.id_))
		self.db.commit()
		self.job_treeview_populate ()

	def delete (self, widget):
		selection = self.get_object("treeview-selection1")
		store, path = selection.get_selected_rows ()
		if path != []:
			treeiter = self.job_store.get_iter(path)
			id_ = self.job_store.get_value(treeiter, 0)
			self.cursor.execute("UPDATE job_types SET deleted = True "
								"WHERE id = %s", (id_ ,))
			self.db.commit()
			self.job_treeview_populate ()

	def new(self, widget):
		widget.set_text("New job type")
		self.id_ = 0







		
