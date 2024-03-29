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

import gi
gi.require_version('GtkSource', '3.0')
from gi.repository import Gtk, GtkSource, GObject, Gdk
import time
from constants import ui_directory, DB

UI_FILE = ui_directory + "/db/sql_window.ui"

class SQLWindowGUI(Gtk.Builder):
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		GObject.type_register(GtkSource.View)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		language_manager = GtkSource.LanguageManager()
		self.source_view = self.get_object('gtksourceview1')
		self.source_buffer = GtkSource.Buffer()
		self.source_view.set_buffer(self.source_buffer)
		self.source_buffer.set_language(language_manager.get_language('sql'))
		completion = self.source_view.get_completion()
		keyword_provider = GtkSource.CompletionWords.new('Keywords')
		keyword_provider.register(self.source_buffer)
		completion.add_provider(keyword_provider)
		
		self.window = self.get_object('window1')
		self.window.show_all()

		self.populate_sql_commands()

		cursor = DB.cursor()
		cursor.execute("SELECT command FROM sql.history WHERE current = True")
		command = cursor.fetchone()[0]
		self.source_buffer.set_text(command)
		cursor.close()
		DB.rollback()

	def sql_combo_changed (self, combobox):
		if self.get_object('comboboxtext-entry').has_focus():
			return #user is typing new values
		name = combobox.get_active_text()
		cursor = DB.cursor()
		cursor.execute("SELECT command FROM sql.history WHERE name = %s", (name,))
		for row in cursor.fetchall():
			command = row[0]
			self.source_buffer.set_text(command)
		cursor.close()
		DB.rollback()
		
	def sourceview_populate_popup (self, textview, menu):
		separator = Gtk.SeparatorMenuItem()
		separator.show()
		menu.prepend(separator)
		remove = Gtk.MenuItem.new_with_mnemonic('''_Remove "''')
		remove.show()
		remove.connect("activate", self.remove_quote_activated)
		menu.prepend(remove)

	def remove_quote_activated (self, menuitem):
		start_iter = self.source_buffer.get_start_iter ()
		end_iter = self.source_buffer.get_end_iter ()
		string = self.source_buffer.get_text(start_iter, end_iter, True)
		self.source_buffer.set_text(string.replace('''"''', ''))

	def sql_combo_populate_popup (self, combo, menu):
		separator = Gtk.SeparatorMenuItem()
		separator.show()
		menu.prepend(separator)
		save = Gtk.MenuItem.new_with_mnemonic("_Delete")
		save.show()
		save.connect("activate", self.delete_activated)
		menu.prepend(save)

	def populate_sql_commands (self):
		combo = self.get_object('comboboxtext1')
		combo.remove_all()
		cursor = DB.cursor()
		cursor.execute("SELECT name FROM sql.history WHERE current IS NOT TRUE "
						"ORDER BY name")
		for row in cursor.fetchall():
			combo.append(row[0], row[0])
		cursor.close()
		DB.rollback()

	def delete_activated (self, menuitem):
		name = self.get_object('comboboxtext-entry').get_text()
		cursor = DB.cursor()
		cursor.execute("DELETE FROM sql.history WHERE name = %s", (name,))
		DB.commit()
		cursor.close()
		self.populate_sql_commands()

	def save_clicked (self, button):
		cursor = DB.cursor()
		name = self.get_object('comboboxtext-entry').get_text()
		start = self.source_buffer.get_start_iter()
		end = self.source_buffer.get_end_iter()
		command = self.source_buffer.get_text(start, end, True)
		cursor.execute("INSERT INTO sql.history (name, command, date_inserted) "
						"VALUES (%s, %s, CURRENT_DATE) ON CONFLICT (name) "
						"DO UPDATE SET command = %s WHERE history.name = %s", 
						(name, command, command, name))
		DB.commit()
		cursor.close()
		self.populate_sql_commands()

	def run_sql_clicked (self, button):
		treeview = self.get_object('treeview1')
		for column in treeview.get_columns():
			treeview.remove_column(column)
		start_iter = self.source_buffer.get_start_iter ()
		end_iter = self.source_buffer.get_end_iter ()
		string = self.source_buffer.get_text(start_iter, end_iter, True)
		cursor = DB.cursor()
		t = time.time()
		try:
			cursor.execute(string)
			query_time = round(time.time() - t, 4)
			self.get_object('time_label').set_label(str(query_time))
		except Exception as e:
			self.get_object('sql_error_buffer').set_text(str(e))
			self.get_object('textview2').set_visible(True)
			self.get_object('scrolledwindow2').set_visible(False)
			DB.rollback()
			return
		#create treeview columns and a liststore to store the info
		if cursor.description == None: #probably an UPDATE, report rows affected
			result = "%s row(s) affected" % cursor.rowcount
			self.get_object('sql_error_buffer').set_text(result)
			self.get_object('textview2').set_visible(True)
			self.get_object('scrolledwindow2').set_visible(False)
			DB.rollback()
			return
		self.get_object('textview2').set_visible(False)
		self.get_object('scrolledwindow2').set_visible(True)
		type_list = list()
		for index, row in enumerate(cursor.description):
			column_name = row.name
			type_ = row.type_code
			if type_ == 23:
				type_list.append(int)
				renderer = Gtk.CellRendererText()
				column = Gtk.TreeViewColumn(column_name, renderer, text=index)
			elif type_ == 16:
				type_list.append(bool)
				renderer = Gtk.CellRendererToggle()
				column = Gtk.TreeViewColumn(column_name, renderer, active=index)
			else:
				type_list.append(str)
				renderer = Gtk.CellRendererText()
				column = Gtk.TreeViewColumn(column_name, renderer, text=index)
			treeview.append_column(column)
			column.set_sort_column_id(index)
			column.set_reorderable(True)
			column.set_resizable(True)
		store = Gtk.ListStore()
		store.set_column_types(type_list)
		treeview.set_model(store)
		for row in cursor.fetchall():
			# do a convert, cell by cell, to make sure types are correct
			store_row = list()
			for index, element in enumerate(row):
				store_row.append(type_list[index](element))
			store.append (store_row)
		DB.rollback()
		cursor.close()
		self.save_current_sql(string)

	def save_current_sql(self, command):
		cursor = DB.cursor()
		cursor.execute("UPDATE sql.history SET command = %s "
						"WHERE current = True RETURNING name", (command,))
		if cursor.fetchone() == None:
			cursor.execute("INSERT INTO sql.history "
							"(name, command, date_inserted, current) VALUES "
							"('Current', %s, CURRENT_DATE, TRUE)", (command,))
		DB.commit()
		cursor.close()

	def report_hub_clicked (self, button):
		treeview = self.get_object('treeview1')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)



