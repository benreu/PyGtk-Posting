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
import constants

UI_FILE = constants.ui_directory + "/job_types.ui"


class GUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.job_store = Gtk.ListStore(str, int)
		self.treeview = self.builder.get_object('treeview1')
		self.job_treeview_populate ()

		self.id_ = 0
		self.treeview.set_model(self.job_store)		
		renderer_1 = Gtk.CellRendererText() 
		column_1 = Gtk.TreeViewColumn('Job type', renderer_1, text=0)
		self.treeview.append_column(column_1)
		
		self.window = self.builder.get_object('window1')			
		self.window.show_all()

	def row_activate(self, treeview, path, treeviewcolumn):
		treeiter = self.job_store.get_iter(path)
		self.id_ = self.job_store.get_value(treeiter, 1)
		self.cursor.execute("SELECT * FROM job_types WHERE id = (%s)", (self.id_, ) )
		for string in self.cursor.fetchall():
			
			name = string[1]
			self.builder.get_object('entry1').set_text(name)

	def job_treeview_populate (self):
		self.job_store.clear()
		self.cursor.execute("SELECT * FROM job_types")
		for i in self.cursor.fetchall():
			id_ = i[0]
			name = i[1]
			self.job_store.append([name,id_])

	def save(self, widget):
		job = widget.get_text()
		if self.id_ == 0:
			self.cursor.execute("INSERT INTO job_types (name) VALUES (%s)", (job,))
		else:
			self.cursor.execute("UPDATE job_types SET (name) = (%s) WHERE id = %s", (job,self.id_))
		self.db.commit()
		self.job_treeview_populate ()
		self.new(widget)

	def delete (self, widget):
		store, path = self.builder.get_object("treeview-selection1").get_selected_rows ()
		if path != []:
			treeiter = self.job_store.get_iter(path)
			id_ = self.job_store.get_value(treeiter, 1)
			self.cursor.execute("DELETE FROM job_types WHERE id = %s", (id_ ,))
			self.db.commit()
			self.job_treeview_populate ()

	def new(self, widget):
		widget.set_text("")
		self.id_ = 0







		
