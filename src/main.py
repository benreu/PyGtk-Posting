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
import psycopg2, apsw, os, shutil

cursor = None
dev_mode = False
is_admin = False

class Accounts:
	expense_acc = Gtk.TreeStore(int, str)
	revenue_acc = Gtk.TreeStore(int, str)
	product_expense_acc = Gtk.TreeStore(str, str)
	product_inventory_acc = Gtk.TreeStore(str, str)
	product_revenue_acc = Gtk.TreeStore(str, str)
	def __init__ (self):
		pass
		
	@staticmethod
	def populate_accounts ():
		global cursor
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

	@staticmethod
	def populate_child_product_inventory (number, parent):
		global cursor
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
		return show

	@staticmethod
	def populate_child_revenue (number, parent):
		global cursor
		show = False
		cursor.execute("SELECT number, name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = Accounts.revenue_acc.append(parent,[number, name])
			Accounts.populate_child_revenue(number, p)

	@staticmethod
	def populate_child_product_revenue (number, parent):
		global cursor
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
		return show

	@staticmethod
	def populate_child_product_expense (number, parent):
		global cursor
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
		return show

	@staticmethod
	def populate_child_expense (number, parent):
		global cursor
		cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"parent_number = %s", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = Accounts.expense_acc.append(parent,[number, name])
			Accounts.populate_child_expense(number, p)

def connect_to_db (name):
	global cursor
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
		database = psycopg2.connect (dbname = sql_database, 
												host = sql_host, 
												user = sql_user, 
												password = sql_password, 
												port = sql_port)
		cursor = database.cursor()
		return True, database, sql_database
	except psycopg2.OperationalError as e:
		print (e.args)
		return False, None, None

home = os.path.expanduser('~')
preferences_path = os.path.join(home, '.config/posting')

help_dir = ''
ui_directory = ''
template_dir = ''
modules_dir = ''
cur_dir = os.getcwd()
def set_directories ():
	global help_dir, ui_directory, template_dir, modules_dir
	if dev_mode == False: #posting is launching from an installed .deb
		help_dir = os.path.relpath("/usr/share/help/C/pygtk-posting")
		ui_directory = os.path.relpath("/usr/share/pygtk_posting/ui/")
		template_orig = os.path.relpath("/usr/share/pygtk_posting/templates/")
		template_dir = os.path.join(home, ".config/posting/templates")
		if not os.path.exists(template_dir): #copy templates
			shutil.copytree(template_orig, template_dir)
			print ("copied *.odt templates to %s" % template_dir)
		modules_orig = os.path.relpath("/usr/lib/python3/dist-packages/pygtk_posting/modules/")
		modules_dir = os.path.join(home, ".config/posting/modules/")
		if not os.path.exists(modules_dir): #copy modules
			shutil.copytree(modules_orig, modules_dir)
			print ("copied *.py modules to %s" % modules_dir)
	else:                              # use local files
		help_dir = os.path.join(cur_dir, "help/C/pygtk-posting")
		ui_directory = os.path.join(cur_dir, "src")
		template_dir = os.path.join(cur_dir, "templates")
		modules_dir = os.path.join(cur_dir, "src/modules/")


def get_apsw_cursor ():
	global dev_mode, preferences_path
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
		