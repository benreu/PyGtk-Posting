# sql_window.py
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
from decimal import getcontext

getcontext().prec = 8

UI_FILE = "src/db/sql_window.ui"

class SQLWindowGUI :
	def __init__(self, db):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		button = self.builder.get_object('button1')
		#self.builder.get_object('overlay1').add_overlay(button)

	def run_sql_clicked (self, button):
		sql_buffer = self.builder.get_object('textbuffer1')
		treeview = self.builder.get_object('treeview1')
		for column in treeview.get_columns():
			treeview.remove_column(column)
		start_iter = sql_buffer.get_start_iter ()
		end_iter = sql_buffer.get_end_iter ()
		string = sql_buffer.get_text(start_iter, end_iter, True)
		cursor = self.db.cursor()
		try:
			cursor.execute(string)
		except Exception as e:
			self.builder.get_object('sql_error_buffer').set_text(str(e))
			self.builder.get_object('textview2').set_visible(True)
			self.builder.get_object('scrolledwindow2').set_visible(False)
			self.db.rollback()
			return
		#create treeview columns and a liststore to store the info
		if cursor.description == None: #probably an UPDATE, report rows affected
			result = "%s row(s) affected" % cursor.rowcount
			self.builder.get_object('sql_error_buffer').set_text(result)
			self.builder.get_object('textview2').set_visible(True)
			self.builder.get_object('scrolledwindow2').set_visible(False)
			self.db.rollback()
			return
		self.builder.get_object('textview2').set_visible(False)
		self.builder.get_object('scrolledwindow2').set_visible(True)
		type_list = list()
		for index, row in enumerate(cursor.description):
			column_name = row.name
			type_ = row.type_code
			if type_ == 23:
				type_list.append(int)
				renderer = Gtk.CellRendererText()
				column = Gtk.TreeViewColumn(column_name, renderer, text=index)
				treeview.append_column(column)
				column.set_sort_column_id(index)
			elif type_ == 16:
				type_list.append(bool)
				renderer = Gtk.CellRendererToggle()
				column = Gtk.TreeViewColumn(column_name, renderer, active=index)
				treeview.append_column(column)
				column.set_sort_column_id(index)
			else:
				type_list.append(str)
				renderer = Gtk.CellRendererText()
				column = Gtk.TreeViewColumn(column_name, renderer, text=index)
				treeview.append_column(column)
				column.set_sort_column_id(index)
		store = Gtk.ListStore()
		store.set_column_types(type_list)
		treeview.set_model(store)
		for row in cursor.fetchall():
			# do a convert, cell by cell, to make sure types are correct
			store_row = list()
			for index, element in enumerate(row):
				store_row.append(type_list[index](element))
			store.append (store_row)
		self.db.rollback()
		cursor.close()

	
