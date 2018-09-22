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

from gi.repository import Gtk, GLib, Gdk
import os, sys, time, subprocess
from subprocess import Popen, PIPE
from multiprocessing import Queue, Process
from queue import Empty
from datetime import datetime, date
from db.database_tools import get_apsw_cursor
import main

UI_FILE = main.ui_directory + "/db/backup_restore.ui"

class Utilities:
	def __init__(self, parent):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.parent_window = parent.window
		self.parent = parent

	def backup_gui (self, database):
		self.database = database
		self.result = False
		backup_window = self.builder.get_object('backupdialog')
		backup_window.set_transient_for(self.parent_window)
		day = time.strftime("%Y-%m-%d-%H:%M")
		backup_window.set_current_name(database + "_" + day +".pbk")
		result = backup_window.run()
		if result == Gtk.ResponseType.ACCEPT:
			self.backup_database ()
		else:
			backup_window.destroy()
		return self.result

	def backup_database (self):
		cursor_sqlite = get_apsw_cursor ()
		for row in cursor_sqlite.execute("SELECT * FROM connection;"):
			sql_user = row[0]
			sql_host = row[2]
			sql_port = row[3]
		backup_window = self.builder.get_object('backupdialog')
		progressbar = self.builder.get_object('progressbar1')
		progressbar.set_text("Back up running...")
		db_name = backup_window.get_current_name()
		path = backup_window.get_current_folder()
		full_path = path + "/" + db_name
		backup_command = ("pg_dump -C -F c -U%s -h%s -p%s -d%s -f'%s'" 
															% (sql_user, 
															sql_host, 
															sql_port, 
															self.database, 
															full_path))
		p = Popen(backup_command, shell = True, 
					stdin = PIPE, stdout = PIPE, stderr = PIPE)
		while p.poll() == None:
			while Gtk.events_pending():
				Gtk.main_iteration()
			progressbar.pulse()
			time.sleep(.05)
		stderr, stdout = p.communicate()
		stdout = stdout.decode(encoding="utf-8", errors="strict")
		if stdout != '':
			self.show_error_message(stdout)
			self.result = False
		else:
			progressbar.set_fraction(1.0)
			progressbar.set_text("Backed up successfully to %s/%s" 
														% (path,db_name))
			self.builder.get_object('button6').set_visible(True)
			self.result = True
		self.builder.get_object('button1').set_visible(False)
		self.builder.get_object('button2').set_visible(False)
			
	def done_clicked (self, dialog):
		dialog.destroy()

	def restore_gui(self, db_name, parent):
		restore_window = self.builder.get_object('restoredialog')
		restore_window.set_transient_for(self.parent_window)
		response = restore_window.run()
		db_file = restore_window.get_filename()
		restore_window.destroy()
		if response == Gtk.ResponseType.ACCEPT:
			cursor_sqlite = get_apsw_cursor ()
			for row in cursor_sqlite.execute("SELECT * FROM connection;"):
				sql_user = row[0]
				sql_password = row[1]
				sql_host = row[2]
				sql_port = row[3]
			sql_password = sql_password.encode(encoding = "utf-8")
			self.data_queue = Queue()
			command = ("createdb -U%s -h%s -p%s -Ttemplate0 %s" 
							% (sql_user, sql_host, sql_port, db_name))
			create_db = Popen(command ,shell = True,
								stdin = PIPE, stdout = PIPE, stderr = PIPE)
			def create ():
				stderr, stdout = create_db.communicate(sql_password)
				stdout = stdout.decode(encoding="utf-8", errors="strict")
				self.data_queue.put(stdout)
			thread = Process(target=create)
			thread.start()
			GLib.timeout_add(10, self.check_stdout )
			while create_db.poll() == None:
				while Gtk.events_pending():
					Gtk.main_iteration()
				self.parent.progressbar.pulse()
				time.sleep(.05)
			if create_db.poll() != 0 :
				self.parent.progressbar.set_fraction(0.0)
				self.parent.status_update("Could not create %s" % db_name)
				return
			self.parent.status_update("Created database %s" % db_name)
			command = ("pg_restore -U%s -h%s -p%s -d %s '%s'" 
						% (sql_user, sql_host, sql_port, db_name, db_file))
			restore_db = Popen(command , shell = True,
							stdin = PIPE, stdout = PIPE, stderr = PIPE)
			def create ():				
				stderr, stdout = restore_db.communicate(sql_password)
				stdout = stdout.decode(encoding="utf-8", errors="strict")
				self.data_queue.put(stdout)
			thread = Process(target=create)
			thread.start()
			GLib.timeout_add(10, self.check_stdout )
			while restore_db.poll() == None:
				while Gtk.events_pending():
					Gtk.main_iteration()
				self.parent.progressbar.pulse()
				time.sleep(.05)
			if restore_db.poll() != 0 :
				self.parent.progressbar.set_fraction(0.0)
				self.parent.status_update("Could not restore %s" % db_name)
				return
			parent.builder.get_object('entry6').set_text("")
			parent.retrieve_dbs ()
			self.parent.progressbar.set_fraction(1.0)
			self.parent.status_update("Successfully restored %s" % db_name)

	def check_stdout (self):
		try:
			stdout = self.data_queue.get_nowait()
			if stdout != "":
				self.show_error_message(stdout)
		except Empty:
			return True

	def show_error_message (self, message):
		print (str(message))
		self.builder.get_object('textbuffer1').set_text(message)
		error_dialog = self.builder.get_object('dialog1')
		error_dialog.set_transient_for(self.parent_window)
		error_dialog.run()
		error_dialog.destroy()

		
