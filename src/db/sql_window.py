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
from db_connection import DB
from constants import ui_directory
import user_manual
import query_results

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
		user_manual.bind_f1(self.window, "sql_window")
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
			self.show_message(str(e))
			DB.rollback()
			cursor.close()
			return
		if cursor.description == None: #probably an UPDATE, report rows affected
			row_count = cursor.rowcount
			cursor.close()
			committed = self.end_transaction()
			if committed == None:
				return
			if committed:
				result = "%s row(s) affected and committed" % row_count
			else:
				result = ("%s row(s) would be affected; rolled back, "
							"nothing changed" % row_count)
			self.show_message(result)
			self.save_current_sql(string)
			return
		# end the transaction before converting cells, so a conversion error
		# cannot leave it open for some other window's commit to keep
		rows = cursor.fetchall()
		description = cursor.description
		cursor.close()
		if self.end_transaction() == None:
			return
		self.get_object('textview2').set_visible(False)
		self.get_object('scrolledwindow2').set_visible(True)
		query_results.fill_treeview(treeview, description, rows)
		self.save_current_sql(string)

	def show_message (self, text):
		self.get_object('sql_error_buffer').set_text(text)
		self.get_object('textview2').set_visible(True)
		self.get_object('scrolledwindow2').set_visible(False)

	def end_transaction (self):
		"True when committed, False when rolled back, None when the commit failed"
		if not self.get_object('commit_checkbutton').get_active():
			DB.rollback()
			return False
		try:
			DB.commit()
		except Exception as e: # a deferred constraint, say
			self.show_message(str(e))
			DB.rollback()
			return None
		return True

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



