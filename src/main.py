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

import psycopg2, apsw, os

dev_mode = False

def get_apsw_cursor ():
	global dev_mode
	home = os.path.expanduser('~')
	pref_path = os.path.join(home, '.config/posting')
	if not os.path.exists(pref_path):
		os.mkdir(pref_path)
	if dev_mode == True:
		pref_file = os.path.join(os.getcwd(), 'local_settings')
	else:
		pref_file = os.path.join(pref_path, 'local_settings')
	if not os.path.exists(pref_file):
		con = apsw.Connection(pref_file)
		cursor = con.cursor()
		cursor.execute("CREATE TABLE connection "
												"(user text, password text, "
												"host text, port text, "
												"db_name text)")
		cursor.execute("INSERT INTO connection VALUES "
												"('postgres', 'None', "
												"'localhost', '5432', 'None')")
	else:
		con = apsw.Connection(pref_file)
		cursor = con.cursor()
	return cursor

class Connection:
	database = None
	@staticmethod
	def cursor ():
		return Connection.database.cursor()

	@staticmethod
	def connect_to_db (name):
		Connection.database = name
		cursor_sqlite = get_apsw_cursor ()
		if name == None:
			for row in cursor_sqlite.execute("SELECT db_name FROM connection;"):
				sql_database = row[0]
		else:
			sql_database = name
		for row in cursor_sqlite.execute("SELECT * FROM connection;"):
			sql_user = row[0]
			sql_password = row[1]
			sql_host = row[2]
			sql_port = row[3]
		try:
			Connection.database = psycopg2.connect (dbname = sql_database, 
													host = sql_host, 
													user = sql_user, 
													password = sql_password, 
													port = sql_port)
			return True, Connection.database, sql_database
		except psycopg2.OperationalError as e:
			print (e.args)
			return False, None, None

class Admin:
	is_admin = False
	@staticmethod
	def set_admin (value):
		Admin.is_admin = value

	@staticmethod
	def get_admin ():
		return Admin.is_admin


		