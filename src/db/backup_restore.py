# backup_restore.py
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
from gi.repository import Gtk, GLib, Gdk, Vte
import time
from db.database_tools import get_apsw_connection
from constants import DB, ui_directory, db_name

UI_FILE = ui_directory + "/db/backup_restore.ui"

class Utilities:
	def __init__(self, parent):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.parent_window = parent.window
		self.parent = parent
		self.terminal = Vte.Terminal()
		self.terminal.set_scroll_on_output(True)

	def backup_gui (self):
		self.database = db_name
		self.result = False
		self.builder.get_object('backup_scrolled_window').add(self.terminal)
		backup_window = self.builder.get_object('backupdialog')
		backup_window.set_transient_for(self.parent_window)
		day = time.strftime("%Y-%m-%d-%H:%M")
		backup_window.set_current_name(self.database + "_" + day +".pbk")
		backup_window.show_all()
		result = backup_window.run()
		if result == Gtk.ResponseType.ACCEPT:
			self.backup_database ()
		else:
			backup_window.destroy()
		return self.result

	def backup_database (self):
		self.error = False
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT * FROM connection;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		backup_window = self.builder.get_object('backupdialog')
		db_name = backup_window.get_current_name()
		path = backup_window.get_current_folder()
		full_path = path + "/" + db_name
		backup_command = ["/usr/lib/postgresql/10/bin/pg_dump", 
							"-CWv", "-F", "c", 
							"-U", sql_user, 
							"-h", sql_host, 
							"-p", sql_port, 
							"-d", self.database, 
							"-f", full_path]
		self.terminal.spawn_sync(   Vte.PtyFlags.DEFAULT,
									path,
									backup_command,
									[],
									GLib.SpawnFlags.DO_NOT_REAP_CHILD,
									None,
									None,
									)
		self.handler_id = self.terminal.connect("child-exited", self.dump_callback)
		GLib.timeout_add_seconds(1, self.feed_password, sql_password)

	def feed_password (self, sql_password):
		'run this in a timeout to catch errors, otherwise the password shows up in the terminal'
		if self.error == False:
			self.terminal.feed_child(sql_password + '\n', -1)

	def dump_callback (self, terminal, error):
		terminal.disconnect(self.handler_id)
		if error != 0:
			self.error = True
			self.builder.get_object('button6').set_label('Backup failed!')
		self.builder.get_object('button6').set_visible(True)
		self.builder.get_object('button1').set_visible(False)
		self.builder.get_object('button2').set_visible(False)
			
	def done_clicked (self, dialog):
		c = DB.cursor()
		c.execute("UPDATE settings SET last_backup = CURRENT_DATE")
		DB.commit()
		c.close()
		dialog.destroy()

	def restore_gui(self, db_name, parent):
		self.parent = parent
		self.error = False
		self.builder.get_object('restore_scrolled_window').add(self.terminal)
		restore_window = self.builder.get_object('restoredialog')
		restore_window.set_transient_for(self.parent_window)
		restore_window.show_all()
		response = restore_window.run()
		db_file = restore_window.get_filename()
		if response != Gtk.ResponseType.ACCEPT:
			return
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT * FROM connection;"):
			sql_user = row[0]
			self.sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		create_command = ["/usr/lib/postgresql/10/bin/createdb", 
							"-e",
							"-U", sql_user, 
							"-h", sql_host, 
							"-p", sql_port, 
							"-Ttemplate0", db_name]
		self.terminal.spawn_sync(   Vte.PtyFlags.DEFAULT,
									"/",
									create_command,
									[],
									GLib.SpawnFlags.DO_NOT_REAP_CHILD,
									None,
									None,
									)
		self.handler_id = self.terminal.connect("child-exited", 
													self.create_callback,
													db_name,
													db_file)
		GLib.timeout_add_seconds(1, self.feed_password, self.sql_password)

	def create_callback (self, terminal, error, db_name, db_file):
		terminal.disconnect(self.handler_id)
		if error != 0:
			self.parent.status_update("Could not create %s" % db_name)
			self.error = True
			self.builder.get_object('button7').set_label('Create failed!')
			return
		self.parent.status_update("Created database %s" % db_name)
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT * FROM connection;"):
			sql_user = row[0]
			self.sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		restore_command = ["/usr/lib/postgresql/10/bin/pg_restore", 
							"-v",
							"-U", sql_user, 
							"-h", sql_host, 
							"-p", sql_port, 
							"-d", db_name,
							db_file]
		self.terminal.spawn_sync(   Vte.PtyFlags.DEFAULT,
									'/',
									restore_command,
									[],
									GLib.SpawnFlags.DO_NOT_REAP_CHILD,
									None,
									None,
									)
		self.handler_id = self.terminal.connect("child-exited", 
													self.restore_callback,
													db_name)
		GLib.timeout_add_seconds(1, self.feed_password, self.sql_password)

	def restore_callback (self, terminal, error, db_name):
		terminal.disconnect(self.handler_id)
		if error != 0:
			self.parent.status_update("Could not restore %s" % db_name)
			self.error = True
			self.builder.get_object('button6').set_label('Restore failed!')
		self.builder.get_object('button7').set_visible(True)
		self.builder.get_object('button4').set_visible(False)
		self.builder.get_object('button3').set_visible(False)
		self.parent.builder.get_object('entry6').set_text("")
		self.parent.retrieve_dbs ()
		self.parent.progressbar.set_fraction(1.0)
		self.parent.status_update("Successfully restored %s" % db_name)

		
