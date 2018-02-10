#!/usr/bin/python
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

from gi.repository import Gtk, GLib
import os, subprocess, time, psycopg2, apsw
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from db import database_utils
from main import get_apsw_cursor
import log_utils

UI_FILE = "src/db/database_tools.ui"


class GUI:
	def __init__(self, db, error):

		self.error = error
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.statusbar = self.builder.get_object("statusbar2")
		self.progressbar = self.builder.get_object("progressbar1")
		database_utils.PROGRESSBAR = self.progressbar
		self.log_file = log_utils.log_file
		if self.log_file == None:
			self.log_file = 'None'
		if error == False: 
			self.db = db
			self.cursor = self.db.cursor()
			self.retrieve_dbs ()
			self.statusbar.push(1,"Ready to edit databases")
			self.set_active_database ()
			self.builder.get_object("button3").set_sensitive(True)
			self.builder.get_object("button2").set_sensitive(True)
			self.builder.get_object("button1").set_sensitive(True)
			self.builder.get_object("button10").set_sensitive(True)
		else:#if error is true we have problems connecting so we have to force the user to reconnect
			self.statusbar.push(1,"Please setup PostgreSQL in the Connection tab")
			self.builder.get_object('window').set_modal(True)
		
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
		from db.backup_restore import Utilities 
		u = Utilities(parent = self )
		u.backup_gui(self.active_database )

	def restore_database_clicked(self, widget):
		restore_database_name = self.builder.get_object('entry6').get_text()
		if restore_database_name == "":
			self.status_update("Database name is blank!")
		else:
			from db.backup_restore import Utilities
			u = Utilities(parent = self)
			u.restore_gui(restore_database_name, self)
			
	def restore_name_changed(self, widget):
		restore_database_name = widget.get_text()
		self.cursor.execute("SELECT b.datname FROM pg_catalog.pg_database b "
															"ORDER BY 1;")
		for db_name in self.cursor.fetchall():
			if db_name[0] == restore_database_name:
				self.builder.get_object('button8').set_sensitive(False)
				self.status_update("Database already exists!")
				return
		if " " in restore_database_name:
			self.builder.get_object('button8').set_sensitive(False)
			self.status_update("Name cannot contain spaces! "
								"Try underscore instead.")
		else:
			self.builder.get_object('button8').set_sensitive(True)
			self.status_update("Ready to restore database")
		
	def set_active_database (self ):
		cursor_sqlite = get_apsw_cursor ()
		for row in cursor_sqlite.execute("SELECT db_name FROM connection;"):
			sql_database = row[0]
			self.active_database = sql_database
		self.builder.get_object('combobox1').set_active_id(sql_database)
		self.builder.get_object('label10').set_text("Current database : " + sql_database)
		self.builder.get_object('label14').set_text(sql_database)
	
	def retrieve_dbs(self):
		db_name_store = self.builder.get_object('db_name_store')
		db_name_store.clear()
		cursor_sqlite = get_apsw_cursor ()
		for row in cursor_sqlite.execute("SELECT * FROM connection;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		cursor = self.db.cursor()
		cursor.execute("SELECT b.datname FROM pg_catalog.pg_database b ORDER BY 1;")
		for db_tuple in cursor.fetchall():
			try:
				db_name = db_tuple[0]
				db = psycopg2.connect( database= db_name, host= sql_host, 
										user=sql_user, password = sql_password, 
										port = sql_port)
				cursor = db.cursor()
				cursor.execute("SELECT version FROM settings") # valid pygtk posting database
				version = cursor.fetchone()[0]
				db_name_store.append([version, db_name])
			except Exception as e:
				pass

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
			cursor_sqlite = get_apsw_cursor ()
			for row in cursor_sqlite.execute("SELECT * FROM connection;"):
				sql_user = row[0]
				sql_password = row[1]
				sql_host = row[2]
				sql_port = row[3]
			db = psycopg2.connect( database= selected, host= sql_host, 
									user=sql_user, password = sql_password, 
									port = sql_port)
			database_utils.check_and_update_version (db, self.statusbar)
			self.error = False
			self.window.close()
			subprocess.Popen(["./src/pygtk_posting.py", 
								"database %s" % selected, self.log_file])

	def login_single_clicked(self, widget):
		self.db.close()
		selected = self.builder.get_object('combobox-entry').get_text()
		if selected != None:
			cursor_sqlite = get_apsw_cursor ()
			for row in cursor_sqlite.execute("SELECT * FROM connection;"):
				sql_user = row[0]
				sql_password = row[1]
				sql_host = row[2]
				sql_port = row[3]
			self.db = psycopg2.connect( database= selected, host= sql_host, 
										user=sql_user, password = sql_password, 
										port = sql_port)
			self.cursor = self.db.cursor()
			database_utils.check_and_update_version (self.db, self.statusbar)
			cursor_sqlite.execute("UPDATE connection SET db_name = '%s'" % (selected))
			self.error = False
			self.window.close()
			subprocess.Popen(["./src/pygtk_posting.py", 
								"database %s" % selected, self.log_file])
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
		cursor_sqlite = get_apsw_cursor ()
		for row in cursor_sqlite.execute("SELECT * FROM connection;"):
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
			self.cursor.execute('CREATE DATABASE ' + db_name)
		except Exception as e:
			print (e)
			if (e.pgcode == "42P04"):
				self.status_update("Database already exists!")
			return
		while Gtk.events_pending():
			Gtk.main_iteration()
		db = psycopg2.connect( database= db_name, host= sql_host, 
								user=sql_user, password = sql_password, 
								port = sql_port)
		database_utils.add_new_tables (db, self.statusbar)
		cursor_sqlite.execute("UPDATE connection SET db_name = ('%s')" % (db_name))
		self.db_name_entry.set_text("")
		self.status_update("Done!")
		GLib.idle_add (self.add_db_done, db_name)

	def add_db_done (self, db_name):
		time.sleep(1)
		subprocess.Popen(["./src/pygtk_posting.py", db_name])
		Gtk.main_quit()

	def label_update(self):
		self.builder.get_object('label12').set_text(self.message)

	def delete_button(self,widget):
		self.warning_dialog = self.builder.get_object('dialog1')
		warning_label = self.builder.get_object('label11')
		self.db_name = self.builder.get_object('combobox1').get_active_id()
		warning = 'Do you really want to delete\n "%s" ?' % self.db_name
		warning_label.set_label(warning)
		self.warning_dialog.show()

	def delete_db(self, widget):
		self.db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
		try:
			self.cursor.execute('DROP DATABASE ' + self.db_name)
			self.status_update("Database deleted")
		except Exception as e:
			print (e)
			if (e.pgcode == "55006"):
				self.status_update("You cannot delete an active database!")
		self.retrieve_dbs ()
		self.set_active_database ()
		self.warning_dialog.hide()
		
	def close_warning_dialog(self, widget):
		self.warning_dialog.hide()

	def get_postgre_settings(self, widget):
		cursor_sqlite = get_apsw_cursor ()
		for row in cursor_sqlite.execute("SELECT * FROM connection;"):
			self.builder.get_object("entry2").set_text(row[0])
			self.builder.get_object("entry3").set_text(row[1])
			self.builder.get_object("entry4").set_text(row[2])
			self.builder.get_object("entry5").set_text(row[3])

	def test_connection_clicked (self, widget):
		sql_user= self.builder.get_object("entry2").get_text()
		sql_password= self.builder.get_object("entry3").get_text()
		sql_host= self.builder.get_object("entry4").get_text()
		sql_port= self.builder.get_object("entry5").get_text()
		try:
			pysql = psycopg2.connect( host= sql_host, user=sql_user, 
										password = sql_password, 
										port = sql_port)
			self.db = pysql # connection successful
			cursor_sqlite = get_apsw_cursor ()
			cursor_sqlite.execute("UPDATE connection SET user = ('%s')" % (sql_user))
			cursor_sqlite.execute("UPDATE connection SET password = ('%s')" % (sql_password))
			cursor_sqlite.execute("UPDATE connection SET host = ('%s')" % (sql_host))
			cursor_sqlite.execute("UPDATE connection SET port = ('%s')" % (sql_port))
			self.message_success()
			self.retrieve_dbs ()
			self.builder.get_object("textbuffer1").set_text('')
			self.builder.get_object("button3").set_sensitive(True)
			self.builder.get_object("button2").set_sensitive(True)
			self.builder.get_object("button1").set_sensitive(True)
			self.builder.get_object("button10").set_sensitive(True)
		except Exception as e:
			print (e)
			self.message_error()
			self.builder.get_object("textbuffer1").set_text(str(e))
			self.builder.get_object("button3").set_sensitive(False)
			self.builder.get_object("button2").set_sensitive(False)
			self.builder.get_object("button1").set_sensitive(False)
			self.builder.get_object("button10").set_sensitive(False)

	def message_success(self):
		self.status_update("Success!")
		GLib.timeout_add(1000, self.status_update, "Saved to settings")

	def message_error(self):
		self.status_update("Your criteria did not match!")
		GLib.timeout_add(3000, self.status_update, "Please check the entries and try again")

