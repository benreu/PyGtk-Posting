# database_restore.py
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

import gi
gi.require_version('Vte', '2.91')
from gi.repository import Gtk, GLib, Vte
from constants import DB, ui_directory
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/db/database_restore.ui"

def get_postgres_bin_path ():
	sqlite = get_apsw_connection()
	cursor = sqlite.cursor()
	cursor.execute("SELECT value FROM settings "
					"WHERE setting = 'postgres_bin_path'")
	bin_path = cursor.fetchone()[0]
	sqlite.close()
	return bin_path


class RestoreGUI(Gtk.Builder):
	def __init__(self, db_name, parent):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.parent = parent
		self.db_name = db_name
		self.bin_path = get_postgres_bin_path ()
		self.terminal = Vte.Terminal()
		self.terminal.set_scroll_on_output(True)
		self.terminal.set_scrollback_lines(-1)
		self.get_object('restore_scrolled_window').add(self.terminal)
		self.dialog = self.get_object('restore_dialog')
		sqlite = get_apsw_connection()
		cursor = sqlite.cursor()
		cursor.execute("SELECT value FROM settings "
						"WHERE setting = 'backup_path' AND setting != ''")
		for row in cursor.fetchall():
			backup_path = row[0]
			self.dialog.set_current_folder(backup_path)
		sqlite.close()
		result = self.dialog.run()
		if result == Gtk.ResponseType.APPLY:
			self.dialog.hide()
			self.restore_database()
		self.dialog.destroy()

	def restore_file_selection_changed (self, filechooser):
		filename = filechooser.get_filename()
		if filename != None:
			self.get_object('status_label').set_label(filename)

	def restore_database(self):
		self.window = self.get_object('restore_window')
		self.window.show_all()
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT "
											"user, password, host, port "
											"FROM postgres_conn;"):
			self.sql_user = row[0]
			self.sql_password = row[1]
			self.sql_host = row[2]
			self.sql_port = row[3]
		sqlite.close()
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		create_command = ["%s/createdb" % self.bin_path, 
							"-e",
							"-U", self.sql_user, 
							"-h", self.sql_host, 
							"-p", self.sql_port, 
							"-Ttemplate0", self.db_name]
		pty.spawn_async(None,
						create_command,
						None,
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.create_spawn_callback
						)

	def create_spawn_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.terminal.watch_child(pid)
		self.terminal.connect("child-exited", self.create_finished_callback)

	def create_finished_callback (self, terminal, error):
		if error != 0:
			self.get_object('status_label').set_label('Create failed!')
			return
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		db_file = self.get_object('restore_dialog').get_filename()
		restore_command = ["%s/pg_restore" % self.bin_path, 
							"-v",
							"-U", self.sql_user, 
							"-h", self.sql_host, 
							"-p", self.sql_port, 
							"-d", self.db_name,
							db_file]
		pty.spawn_async(None,
						restore_command,
						None,
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.restore_spawn_callback
						)

	def restore_spawn_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.terminal.watch_child(pid)
		self.terminal.connect("child-exited", self.restore_finished_callback)

	def restore_finished_callback (self, terminal, error):
		if error != 0:
			self.get_object('status_label').set_label('Restore failed!')
		else:
			self.parent.retrieve_dbs ()
			label = "Successfully restored %s" % self.db_name
			self.get_object('status_label').set_label(label)

	def close_clicked (self, button):
		self.window.destroy()

	def window_destroy (self, widget):
		self.dialog.destroy()

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	transient_for = self.window,
									message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE,
									text = error)
		dialog.run()
		dialog.destroy()


