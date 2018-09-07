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

from gi.repository import Gtk
import psycopg2, apsw, os

class Connection:
	database = None
	@staticmethod
	def get_cursor ():
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
			
class Accounts(Connection):
	expense_acc = Gtk.TreeStore(int, str)
	revenue_acc = Gtk.TreeStore(int, str)
	product_expense_acc = Gtk.TreeStore(str, str)
	product_inventory_acc = Gtk.TreeStore(str, str)
	product_revenue_acc = Gtk.TreeStore(str, str)
	def __init__ (self):
		Connection.__init__(self)
	@staticmethod
	def populate_accounts ():
		cursor = Connection.get_cursor()
		Accounts.expense_acc.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = Accounts.expense_acc.append(None,[number, name])
			Accounts.populate_child_expense(number, parent)
		#################################################
		Accounts.product_expense_acc.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = Accounts.product_expense_acc.append(None,[number, name])
			if Accounts.populate_child_product_expense(number, parent) == True:
				show = True
			if show == False:
				Accounts.product_expense_acc.remove(parent)
		##################################################
		Accounts.product_revenue_acc.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = Accounts.product_revenue_acc.append(None,[number, name])
			if Accounts.populate_child_product_revenue (number, parent) == True:
				show = True
			if show == False:
				Accounts.product_revenue_acc.remove(parent)
		##################################################
		Accounts.revenue_acc.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = Accounts.revenue_acc.append(None,[number, name])
			Accounts.populate_child_revenue (number, parent)
		##################################################
		Accounts.product_inventory_acc.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 1 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = Accounts.product_inventory_acc.append(None,[number, name])
			if Accounts.populate_child_product_inventory(number, parent) == True:
				show = True
			if show == False:
				Accounts.product_inventory_acc.remove(parent)
		cursor.close()

	@staticmethod
	def populate_child_product_inventory (number, parent):
		cursor = Connection.get_cursor()
		show = False
		cursor.execute("SELECT number, name, inventory_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				Accounts.product_inventory_acc.append(parent,[number, name])
			elif row[3] == True:
				p = Accounts.product_inventory_acc.append(parent,[number, name])
				c_show = False
				if Accounts.populate_child_product_inventory(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					Accounts.product_inventory_acc.remove(p)
		cursor.close()
		return show

	@staticmethod
	def populate_child_revenue (number, parent):
		cursor = Connection.get_cursor()
		show = False
		cursor.execute("SELECT number, name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = Accounts.revenue_acc.append(parent,[number, name])
			Accounts.populate_child_revenue(number, p)
		cursor.close()

	@staticmethod
	def populate_child_product_revenue (number, parent):
		cursor = Connection.get_cursor()
		show = False
		cursor.execute("SELECT number, name, revenue_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				Accounts.product_revenue_acc.append(parent,[number, name])
			elif row[3] == True:
				p = Accounts.product_revenue_acc.append(parent,[number, name])
				c_show = False
				if Accounts.populate_child_product_revenue(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					Accounts.product_revenue_acc.remove(p)
		cursor.close()
		return show

	@staticmethod
	def populate_child_product_expense (number, parent):
		cursor = Connection.get_cursor()
		show = False
		cursor.execute("SELECT number, name, expense_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				p = Accounts.product_expense_acc.append(parent,[number, name])
				show = True
			elif row[3] == True:
				p = Accounts.product_expense_acc.append(parent,[number, name])
				c_show = False
				if Accounts.populate_child_product_expense(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					Accounts.product_expense_acc.remove(p)
		cursor.close()
		return show

	@staticmethod
	def populate_child_expense (number, parent):
		cursor = Connection.get_cursor()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"parent_number = %s", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = Accounts.expense_acc.append(parent,[number, name])
			Accounts.populate_child_expense(number, p)
		cursor.close()
		
class Connection:
	database = None
	@staticmethod
	def get_cursor ():
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

cur_dir = os.getcwd()
if cur_dir.split("/")[1] == "usr":
	ui_directory = "/usr/local/share/pygtk_posting/ui/"
else:
	ui_directory = os.path.join(os.getcwd(), "src")


dev_mode = False
preferences_path = None

def get_apsw_cursor ():
	global dev_mode, preferences_path
	home = os.path.expanduser('~')
	preferences_path = os.path.join(home, '.config/posting')
	if not os.path.exists(preferences_path):
		os.mkdir(preferences_path)
	if dev_mode == True:
		pref_file = os.path.join(os.getcwd(), 'local_settings')
	else:
		pref_file = os.path.join(preferences_path, 'local_settings')
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
		