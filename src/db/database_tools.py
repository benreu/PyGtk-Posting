#
#
# Copyright (C) 2016 reuben 
# 
# database_tools is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# database_tools is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
gi.require_version('Vte', '2.91')
from gi.repository import Gtk, GLib, Vte
import subprocess, psycopg2, re, os
from subprocess import Popen, PIPE
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from constants import DB, ui_directory, sql_dir
from constants import log_file as LOG_FILE
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/db/database_tools.ui"


class GUI:
	def __init__(self, error = False):

		self.error = error
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.statusbar = self.builder.get_object("statusbar2")
		self.progressbar = self.builder.get_object("progressbar1")
		if error == False:
			self.db = DB
			self.retrieve_dbs ()
			self.statusbar.push(1,"Ready to edit databases")
			self.set_active_database ()
			self.builder.get_object("box2").set_sensitive(True)
			self.builder.get_object("grid2").set_sensitive(True)
		else:#if error is true we have problems connecting so we have to force the user to reconnect
			self.statusbar.push(1,"Please setup PostgreSQL in the Server (host) tab")
		
		self.get_postgre_settings (None)
		self.window = self.builder.get_object('window')
		self.window.show_all()

	def status_update (self, message):
		self.statusbar.pop(1)
		self.statusbar.push(1, message)

	def destroy(self, window):
		if self.error != False:
			Gtk.main_quit() #quit the whole app if we can't connect to a db
		else:
			return True

	def backup_database_clicked(self, widget):
		from db.database_backup import BackupGUI 
		b = BackupGUI()
		b.window = self.window

	def restore_database_clicked(self, widget):
		restore_database_name = self.builder.get_object('entry6').get_text()
		if restore_database_name == "":
			self.status_update("Database name is blank!")
		else:
			from db.database_restore import RestoreGUI
			RestoreGUI(restore_database_name, self)
			
	def restore_name_changed(self, widget):
		restore_database_name = widget.get_text()
		if " " in restore_database_name:
			self.builder.get_object('button8').set_sensitive(False)
			self.status_update("Database name cannot contain spaces! "
								"Try underscore _ instead.")
		else:
			self.builder.get_object('button8').set_sensitive(True)
			self.status_update("Ready to restore database")
		
	def set_active_database (self ):
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT db_name FROM postgres_conn;"):
			sql_database = row[0]
		self.builder.get_object('combobox1').set_active_id(sql_database)
		self.builder.get_object('label10').set_text("Current database : " + sql_database)
		self.builder.get_object('label14').set_text(sql_database)
		sqlite.close()
	
	def retrieve_dbs(self):
		sqlite = get_apsw_connection()
		db_name_store = self.builder.get_object('db_name_store')
		db_name_store.clear()
		for row in sqlite.cursor().execute("SELECT user, password, host, port "
											"FROM postgres_conn;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		cursor = self.db.cursor()
		cursor.execute("SELECT b.datname FROM pg_catalog.pg_database b ORDER BY 1;")
		for db_tuple in cursor.fetchall():
			try:
				db_name = db_tuple[0]
				db = psycopg2.connect(  database= db_name, 
										host= sql_host, 
										user=sql_user, 
										password = sql_password, 
										port = sql_port)
				cursor = db.cursor()
				cursor.execute("SELECT version FROM settings") # valid pygtk posting database
				version = cursor.fetchone()[0]
				db_name_store.append([version, db_name])
				db.close()
			except Exception as e:
				pass
		cursor.close()

	def db_combo_changed (self, combo):
		model = combo.get_model()
		iter_ = combo.get_active_iter()
		if iter_ == None:
			return
		db_name = combo.get_active_id()
		db_version = model[iter_][0]
		self.builder.get_object('label13').set_label(db_version)
		self.builder.get_object('label14').set_label(db_name)

	def login_multiple_clicked(self, widget):
		selected = self.builder.get_object('combobox-entry').get_text()
		if selected != None:
			self.error = False
			self.window.close()
			subprocess.Popen(["./src/main.py", 
								"database %s" % selected, str(LOG_FILE)])

	def login_single_clicked(self, widget):
		self.db.close()
		selected = self.builder.get_object('combobox-entry').get_text()
		if selected != None:
			sqlite = get_apsw_connection()
			sqlite.cursor().execute("UPDATE postgres_conn SET db_name = '%s'" 
																% (selected))
			self.error = False
			self.window.close()
			subprocess.Popen(["./src/main.py", 
								"database %s" % selected, str(LOG_FILE)])
			Gtk.main_quit()

	def add_db(self,widget):
		self.status_update("Creating database...")
		GLib.idle_add (self.create_db)

	def add_db_entry_changed (self, entry):
		add_database_name = entry.get_text()
		if " " in add_database_name:
			self.builder.get_object('button2').set_sensitive(False)
			self.status_update("Name cannot contain spaces! "
								"Try underscore instead.")
		else:
			self.builder.get_object('button2').set_sensitive(True)
			self.status_update("Ready to restore database")

	def create_db (self):
		self.db_name_entry = self.builder.get_object("entry1")
		db_name= self.db_name_entry.get_text()
		if db_name == "":
			print ("No database name!")
			self.status_update("No database name!")
			return
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT user, password, host, port "
											"FROM postgres_conn;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		pysql = psycopg2.connect( database= "postgres", host= sql_host, 
									user=sql_user, password = sql_password, 
									port = sql_port)
		self.cursor = pysql.cursor()
		pysql.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
		try:
			self.cursor.execute("""CREATE DATABASE "%s";""" % db_name)
		except Exception as e:
			print (e)
			if (e.pgcode == "42P04"):
				self.status_update("Database already exists!")
			return
		while Gtk.events_pending():
			Gtk.main_iteration()
		self.db = psycopg2.connect( database= db_name, host= sql_host, 
								user=sql_user, password = sql_password, 
								port = sql_port)
		#self.db_name = db_name
		if not self.create_tables ():
			self.close_db (db_name)
			return
		if not self.add_primary_data ():
			self.close_db (db_name)
			return
		if not self.update_tables_major ():
			self.close_db (db_name)
			return
		if not self.update_tables_minor ():
			self.close_db (db_name)
			return
		self.db.commit()
		sqlite.cursor().execute("UPDATE postgres_conn SET db_name = ?", (db_name,))
		self.db_name_entry.set_text("")
		self.status_update("Done!")
		subprocess.Popen(["./src/main.py"])
		GLib.timeout_add_seconds (1, Gtk.main_quit)

	def close_db (self, db_name):
		self.db.close()
		self.cursor.execute('DROP DATABASE ' + db_name)

	def execute_file (self, sql_file):
		contents = sql_file.read()
		commands = contents.split("--")
		length = len(commands) - 1
		if length == 0:
			return
		lines = 0
		cursor = self.db.cursor()
		for index, command in enumerate(commands):
			lines += command.count('\n')
			if index == 0 : 
				continue # first command is blank
			self.progressbar.set_fraction(float(index) / float(length))
			description = command[0:command.index("\n")]
			self.progressbar.set_text(description)
			while Gtk.events_pending():
				Gtk.main_iteration()
			try:
				cursor.execute("--" + command)
			except Exception as e:
				sql_buffer = self.builder.get_object('sql_command_buffer')
				error = 'Line number %d in %s:' % (lines + 1, sql_file.name)
				sql_buffer.set_text(error)
				end_iter = sql_buffer.get_end_iter()
				sql_buffer.insert(end_iter, command)
				self.builder.get_object('error_label').set_label(str(e))
				dialog = self.builder.get_object('sql_error_dialog')
				dialog.run()
				dialog.hide()
				cursor.close()
				return False
		cursor.close()
		return True

	def create_tables (self):
		sql_file = os.path.join(sql_dir, 'create_db.sql')
		with open(sql_file, 'r') as sql:
			return self.execute_file(sql)

	def update_tables_major (self):
		self.status_update("Updating tables (major) ...")
		sql_file = os.path.join(sql_dir, 'update_db_major.sql')
		with open(sql_file, 'r') as sql:
			return self.execute_file(sql)

	def update_tables_minor (self):
		self.status_update("Updating tables (minor) ...")
		sql_file = os.path.join(sql_dir, 'update_db_minor.sql')
		with open(sql_file, 'r') as sql:
			return self.execute_file(sql)

	def add_primary_data (self):
		self.status_update("Creating basic information...")
		sql_file = os.path.join(sql_dir, 'insert_basic.sql')
		with open(sql_file, 'r') as sql:
			return self.execute_file(sql)

	def delete_button(self,widget):
		self.warning_dialog = self.builder.get_object('db_delete_dialog')
		warning_label = self.builder.get_object('label11')
		self.db_name = self.builder.get_object('combobox1').get_active_id()
		warning = 'Do you really want to delete\n "%s" ?' % self.db_name
		warning_label.set_label(warning)
		self.warning_dialog.show()

	def delete_db(self, widget):
		self.db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
		cursor = self.db.cursor()
		try:
			cursor.execute('DROP DATABASE ' + self.db_name)
		except Exception as e:
			print (e)
			if (e.pgcode == "55006"):
				self.status_update("You cannot delete an active database!")
		self.status_update("Database deleted")
		self.retrieve_dbs ()
		self.set_active_database ()
		self.warning_dialog.hide()
		
	def close_warning_dialog(self, widget):
		self.warning_dialog.hide()

	def get_postgre_settings(self, widget):
		sqlite = get_apsw_connection()
		cursor = sqlite.cursor()
		for row in cursor.execute("SELECT user, password, host, port "
									"FROM postgres_conn;"):
			self.builder.get_object("entry2").set_text(row[0])
			self.builder.get_object("entry3").set_text(row[1])
			self.builder.get_object("entry4").set_text(row[2])
			self.builder.get_object("entry5").set_text(row[3])
		cursor.execute("SELECT value FROM settings "
						"WHERE setting = 'postgres_bin_path'")
		self.bin_path = cursor.fetchone()[0]
		chooser = self.builder.get_object('bin_path_chooser')
		if os.path.exists(self.bin_path):
			chooser.set_current_folder(self.bin_path)
			chooser.set_tooltip_text(self.bin_path)
		else:
			chooser.set_tooltip_text(self.bin_path + ' does not exist')
		cursor.execute("SELECT value FROM settings "
						"WHERE setting = 'backup_path'")
		path = cursor.fetchone()[0]
		chooser = self.builder.get_object('backup_folder_chooser')
		if os.path.exists(path):
			chooser.set_current_folder(path)
			chooser.set_tooltip_text(path)
		else:
			chooser.set_tooltip_text(path + ' does not exist')
		sqlite.close()

	def test_connection_clicked (self, widget):
		sql_user= self.builder.get_object("entry2").get_text()
		sql_password= self.builder.get_object("entry3").get_text()
		sql_host= self.builder.get_object("entry4").get_text()
		sql_port= self.builder.get_object("entry5").get_text()
		try:
			self.db = psycopg2.connect( host= sql_host, 
										user=sql_user, 
										password = sql_password, 
										port = sql_port)
		except Exception as e:
			print (e)
			self.message_error()
			self.builder.get_object("textbuffer1").set_text(str(e))
			self.builder.get_object("box2").set_sensitive(False)
			self.builder.get_object("grid2").set_sensitive(False)
			return
		sqlite = get_apsw_connection()
		sqlite.cursor().execute("UPDATE postgres_conn SET "
						"(user, password, host, port) = "
						"(?, ?, ?, ?)", 
						(sql_user, sql_password, sql_host, sql_port))
		sqlite.close()
		self.message_success()
		self.retrieve_dbs ()
		self.builder.get_object("textbuffer1").set_text('')
		self.builder.get_object("box2").set_sensitive(True)
		self.builder.get_object("grid2").set_sensitive(True)
		
	def message_success(self):
		self.status_update("Success!")
		GLib.timeout_add(1000, self.status_update, "Saved to settings")

	def message_error(self):
		self.status_update("Your criteria did not match!")
		GLib.timeout_add(3000, self.status_update, "Please check the entries and try again")

	def postgres_bin_folder_set (self, filechooser):
		path = filechooser.get_filename()
		filechooser.set_tooltip_text(path)
		buf = self.builder.get_object('postgres_bin_path_buffer')
		sqlite = get_apsw_connection()
		for row in sqlite.cursor().execute("SELECT user, password, host, port "
											"FROM postgres_conn;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		sqlite.close()
		command = ["%s/pg_isready" % path,
					"-h", sql_host,
					"-p", sql_port
					]
		try:
			p = Popen(command, stdout=PIPE, stderr=PIPE)
			stdout, stderr = p.communicate()
			buf.set_text(stdout.decode('utf-8') + stderr.decode('utf-8'))
		except Exception as e:
			buf.set_text(str(e))
			filechooser.set_filename(self.bin_path)
			return
		sqlite = get_apsw_connection()
		sqlite.cursor().execute("UPDATE settings SET value = ? "
								"WHERE setting = 'postgres_bin_path'", (path,))
		sqlite.close()

	def backup_folder_path_set (self, filechooserbutton):
		path = filechooserbutton.get_filename()
		filechooserbutton.set_tooltip_text(path)
		sqlite = get_apsw_connection()
		sqlite.cursor().execute("UPDATE settings SET value = ? "
								"WHERE setting = 'backup_path'", (path,))
		sqlite.close()





