# database_backup.py
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
import time, os
from constants import DB, ui_directory
from constants import db_name as DB_NAME
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/db/database_backup.ui"

def get_postgres_bin_path ():
	sqlite = get_apsw_connection()
	cursor = sqlite.cursor()
	cursor.execute("SELECT value FROM settings "
					"WHERE setting = 'postgres_bin_path'")
	bin_path = cursor.fetchone()[0]
	sqlite.close()
	return bin_path


class BackupGUI(Gtk.Builder):
	def __init__(self, automatic = False):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.bin_path = get_postgres_bin_path ()
		self.terminal = Vte.Terminal()
		self.terminal.set_scroll_on_output(True)
		self.terminal.set_scrollback_lines(-1)
		self.automatic = automatic
		self.get_object('backup_scrolled_window').add(self.terminal)
		day = time.strftime("%Y-%m-%d-%H:%M")
		name = DB_NAME + "_" + day +".pbk"
		dialog = self.get_object('backup_dialog')
		dialog.set_current_name(name)
		sqlite = get_apsw_connection()
		cursor = sqlite.cursor()
		cursor.execute("SELECT value FROM settings "
						"WHERE setting = 'backup_path'")
		for row in cursor.fetchall():
			backup_path = row[0]
			dialog.set_current_folder(backup_path)
		sqlite.close()
		if automatic and os.path.exists(backup_path):
			full_filepath = backup_path + "/" + name
			self.get_object('status_label').set_label(full_filepath)
			self.backup_database(full_filepath)
		else:
			result = dialog.run()
			if result == Gtk.ResponseType.APPLY:
				filename = dialog.get_filename()
				dialog.hide()
				self.backup_database(filename)
		dialog.destroy()

	def feed_password(self, password):
		self.terminal.feed_child((password + '\n').encode('utf-8'))

	def backup_file_selection_changed (self, filechooser):
		name = filechooser.get_current_name()
		if name[-4:] != '.pbk':
			name = name + '.pbk'
		filechooser.set_current_name(name)
		self.get_object('status_label').set_label(filechooser.get_filename())

	def backup_cancel_clicked (self, button):
		self.window.destroy()

	def backup_database (self, filename):
		self.window = self.get_object('backup_window')
		self.window.show_all()
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT "
											"user, password, host, port "
											"FROM postgres_conn;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		backup_command = ["%s/pg_dump" % self.bin_path, 
							"-Cwv", "-F", "c",
							"-U", sql_user,
							"-h", sql_host,
							"-p", sql_port,
							"-d", DB_NAME,
							"-f", filename]
		pty.spawn_async(None,
						backup_command,
						None,
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.spawn_finished_callback,
						)

	def spawn_finished_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.get_object('button1').set_sensitive(False)
		self.terminal.watch_child(pid)
		self.terminal.connect("child-exited", self.backup_finished_callback)

	def backup_finished_callback (self, terminal, error):
		self.get_object('button1').set_sensitive(True)
		if error != 0:
			self.get_object('status_label').set_label('Backup failed!')
		else:
			button = self.get_object('button2')
			button.set_visible(True)
			button.set_sensitive(True)
			if self.automatic:
				self.save_backup_date()
			
	def save_backup_date_clicked (self, button):
		self.save_backup_date()

	def save_backup_date(self):
		c = DB.cursor()
		c.execute("UPDATE settings SET last_backup = CURRENT_DATE")
		DB.commit()
		c.close()
		self.window.destroy()

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	transient_for = self.window,
									message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE,
									text = error)
		dialog.run()
		dialog.destroy()


