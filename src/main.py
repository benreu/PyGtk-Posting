#!/usr/bin/python3 -Wd
#
# main.py
#
# Copyright (C) 2018 - reuben
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
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject
import psycopg2, apsw, os, shutil, sys, re
import sqlite_utils


def connect_to_db (name):
	import constants
	sqlite = sqlite_utils.get_apsw_connection()
	cursor = sqlite.cursor()
	sqlite_utils.create_apsw_tables(cursor)
	sqlite_utils.update_apsw_tables(cursor)
	sqlite.close() # unlock file after updating
	sqlite = sqlite_utils.get_apsw_connection()
	constants.sqlite_connection = sqlite
	cursor = sqlite.cursor()
	if name == None:
		for row in cursor.execute("SELECT db_name FROM postgres_conn;"):
			sql_database = row[0]
	else:
		sql_database = name
	for row in cursor.execute("SELECT user, password, host, port "
								"FROM postgres_conn;"):
		sql_user = row[0]
		sql_password = row[1]
		sql_host = row[2]
		sql_port = row[3]
	cursor.close()
	try:
		constants.DB = psycopg2.connect ( dbname = sql_database, 
											host = sql_host, 
											user = sql_user, 
											password = sql_password, 
											port = sql_port)
		constants.db_name = sql_database
		constants.start_broadcaster()
		import accounts
		accounts.populate_accounts()
		return True
	except psycopg2.OperationalError as e:
		print (e.args[0])
		constants.db_name = 'False'
		return False

def main_app():
	import constants
	log_file = None
	try:
		variable = sys.argv[1]
		if 'database ' in variable:
			database_to_connect = re.sub('database ', '', variable)
			log_variable = sys.argv[2]
			if log_variable != 'None':
				log_file = variable
		else:
			database_to_connect = None
			log_file = variable
	except Exception as e:
		print ("Non-fatal: %s when trying to retrieve sys args" % e)
		database_to_connect = None
		constants.dev_mode = True
	constants.set_directories()
	constants.log_file = log_file
	result = connect_to_db(database_to_connect)
	if result == True:
		import main_window
		app = main_window.MainGUI()
	else:
		from db import database_tools
		database_tools.GUI(True)
	Gtk.main()

		
if __name__ == "__main__":	
	sys.exit(main_app())
