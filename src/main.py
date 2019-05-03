#!/usr/bin/python3
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
import psycopg2, apsw, os, shutil, sys

db = None
cursor = None
broadcaster = None
dev_mode = False
is_admin = False

class Broadcast (GObject.GObject):
	__gsignals__ = { 
	'products_changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()) , 
	'contacts_changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()) , 
	'clock_entries_changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()) , 
	'shutdown': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ())
	}
	global db, cursor
	def __init__ (self):
		GObject.GObject.__init__(self)
		GObject.timeout_add_seconds(1, self.poll_connection)
		self.accounts = Accounts ()
		self.accounts.populate_accounts()
		cursor.execute("LISTEN products")
		cursor.execute("LISTEN contacts")
		cursor.execute("LISTEN accounts")
		cursor.execute("LISTEN time_clock_entries")
		
	def poll_connection (self):
		if db.closed == 1:
			return False
		db.poll()
		while db.notifies:
			notify = db.notifies.pop(0)
			if "product" in notify.payload:
				self.emit('products_changed')
			elif "contact" in notify.payload:
				self.emit('contacts_changed')
			elif "account" in notify.payload:
				self.accounts.populate_accounts()
			elif "clock_entry" in notify.payload:
				self.emit('clock_entries_changed')
		return True
		
expense_account = Gtk.TreeStore(int, str)
revenue_account = Gtk.TreeStore(int, str)
product_expense_account = Gtk.TreeStore(str, str)
product_inventory_account = Gtk.TreeStore(str, str)
product_revenue_account = Gtk.TreeStore(str, str)

class Accounts:
	global	expense_account, \
			revenue_account, \
			product_expense_account, \
			product_inventory_account, \
			product_revenue_account
	def populate_accounts (self):
		global cursor
		expense_account.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL")
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = expense_account.append(None,[number, name])
			self.populate_child_expense(number, parent)
		#################################################
		product_expense_account.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL ORDER BY name")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = product_expense_account.append(None,[number, name])
			if self.populate_child_product_expense(number, parent) == True:
				show = True
			if show == False:
				product_expense_account.remove(parent)
		##################################################
		product_revenue_account.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL ORDER BY name")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = product_revenue_account.append(None,[number, name])
			if self.populate_child_product_revenue (number, parent) == True:
				show = True
			if show == False:
				product_revenue_account.remove(parent)
		##################################################
		revenue_account.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL ORDER BY name")
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = revenue_account.append(None,[number, name])
			self.populate_child_revenue (number, parent)
		##################################################
		product_inventory_account.clear()
		cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 1 "
							"AND parent_number IS NULL ORDER BY name")
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = product_inventory_account.append(None,[number, name])
			if self.populate_child_product_inventory(number, parent) == True:
				show = True
			if show == False:
				product_inventory_account.remove(parent)

	def populate_child_product_inventory (self, number, parent):
		global cursor
		show = False
		cursor.execute("SELECT number, name, inventory_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				product_inventory_account.append(parent,[number, name])
			elif row[3] == True:
				p = product_inventory_account.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_inventory(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_inventory_account.remove(p)
		return show
		
	def populate_child_revenue (self, number, parent):
		global cursor
		show = False
		cursor.execute("SELECT number, name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = revenue_account.append(parent,[number, name])
			self.populate_child_revenue(number, p)

	def populate_child_product_revenue (self, number, parent):
		global cursor
		show = False
		cursor.execute("SELECT number, name, revenue_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				product_revenue_account.append(parent,[number, name])
			elif row[3] == True:
				p = product_revenue_account.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_revenue(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_revenue_account.remove(p)
		return show

	def populate_child_product_expense (self, number, parent):
		global cursor
		show = False
		cursor.execute("SELECT number, name, expense_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				p = product_expense_account.append(parent,[number, name])
				show = True
			elif row[3] == True:
				p = product_expense_account.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_expense(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_expense_account.remove(p)
		return show

	def populate_child_expense (self, number, parent):
		global cursor
		cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"parent_number = %s ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = expense_account.append(parent,[number, name])
			self.populate_child_expense(number, p)

def connect_to_db (name):
	global db, cursor, broadcaster
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
		db = psycopg2.connect ( dbname = sql_database, 
								host = sql_host, 
								user = sql_user, 
								password = sql_password, 
								port = sql_port)
		cursor = db.cursor()
		broadcaster = Broadcast()
		return True, db, sql_database
	except psycopg2.OperationalError as e:
		print (e.args[0])
		return False, None, None

home = os.path.expanduser('~')
preferences_path = os.path.join(home, '.config/posting')

help_dir = ''
ui_directory = ''
template_dir = ''
modules_dir = ''
sql_dir = ''
cur_dir = os.getcwd()
def set_directories ():
	global help_dir, ui_directory, template_dir, modules_dir, sql_dir
	if cur_dir.split('/')[1] == "usr": #posting is launching from an installed .deb
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
		sql_dir = os.path.realpath("/usr/lib/python3/dist-packages/pygtk_posting/db/")
	else:                              # use local files
		help_dir = os.path.join(cur_dir, "help/C/pygtk-posting")
		ui_directory = os.path.join(cur_dir, "src")
		template_dir = os.path.join(cur_dir, "templates")
		modules_dir = os.path.join(cur_dir, "src/modules/")
		sql_dir = os.path.join(cur_dir, "src/db/")


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


def main_app():
	import pygtk_posting
	app = pygtk_posting.MainGUI()
	Gtk.main()

		
if __name__ == "__main__":	
	sys.exit(main_app())