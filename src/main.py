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



def get_apsw_connection ():
	import constants
	if constants.dev_mode == True:
		pref_file = os.path.join(os.getcwd(), 'local_settings')
	else:
		pref_file = os.path.join(constants.preferences_path, 'local_settings')
	if not os.path.exists(pref_file):
		con = apsw.Connection(pref_file)
		cursor = con.cursor()
		create_apsw_tables(cursor)
	else:
		con = apsw.Connection(pref_file)
	return con

def create_apsw_tables(cursor):
	cursor.execute("CREATE TABLE connection "
											"(user text, password text, "
											"host text, port text, "
											"db_name text)")
	cursor.execute("INSERT INTO connection VALUES "
											"('postgres', 'None', "
											"'localhost', '5432', 'None')")

def update_apsw_tables(connection):
	cursor = connection.cursor()
	cursor.execute("CREATE TABLE IF NOT EXISTS settings "
							"(setting TEXT UNIQUE NOT NULL,"
							"value TEXT NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO settings VALUES "
							"('postgres_bin_path', '/usr/bin')")
	cursor.execute("CREATE TABLE IF NOT EXISTS widget_size "
											"(widget_id text UNIQUE NOT NULL, "
											"size integer NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS product_edit "
											"(widget_id text UNIQUE NOT NULL, "
											"size integer NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO product_edit VALUES "
					"('window_width', 900)")
	cursor.execute("INSERT OR IGNORE INTO product_edit VALUES "
					"('window_height', 500)")
	# product window layout
	cursor.execute("CREATE TABLE IF NOT EXISTS product_overview "
											"(widget_id text UNIQUE NOT NULL, "
											"size integer NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('window_width', 850)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('window_height', 500)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('ext_name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('description_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('barcode_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('unit_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('weight_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('tare_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('manufacturer_sku_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('expense_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('inventory_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('revenue_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('sellable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('purchasable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('manufactured_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('job_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('stocked_column', 25)")
	# contact window layout
	cursor.execute("CREATE TABLE IF NOT EXISTS contact_overview "
											"(widget_id text UNIQUE NOT NULL, "
											"size integer NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('window_width', 850)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('window_height', 500)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('ext_name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('address_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('city_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('state_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('zip_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('fax_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('phone_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('email_column', 125)")
	# keybindings
	cursor.execute("CREATE TABLE IF NOT EXISTS keybindings "
											"(widget_id text UNIQUE NOT NULL, "
											"keybinding text NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO keybindings VALUES "
					"('Main window', 'F9')")
	# resource calendar window layout
	cursor.execute("CREATE TABLE IF NOT EXISTS resource_calendar "
											"(widget_id text UNIQUE NOT NULL, "
											"size integer NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('pane1', 500)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('pane2', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('show_details_checkbutton', 1)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('row_height_value', 3)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('row_width_value', 10)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('edit_window_width', 600)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('edit_window_height', 200)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('subject_column', 200)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('qty_column', 50)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('type_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('contact_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('category_column', 100)")
	


def connect_to_db (name):
	import constants
	sqlite = get_apsw_connection()
	update_apsw_tables(sqlite)
	sqlite.close() # release database lock from updating tables
	sqlite = get_apsw_connection()
	constants.sqlite_connection = sqlite
	cursor = sqlite.cursor()
	if name == None:
		for row in cursor.execute("SELECT db_name FROM connection;"):
			sql_database = row[0]
	else:
		sql_database = name
	for row in cursor.execute("SELECT * FROM connection;"):
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
		#constants.cursor = constants.DB.cursor()
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
