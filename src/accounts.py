# accounts.py
#
# Copyright (C) 2019 - Reuben
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
from constants import DB

expense_account = Gtk.TreeStore(str, str)
revenue_account = Gtk.TreeStore(int, str, str)
revenue_list = Gtk.ListStore(int, str, str)
product_expense_tree = Gtk.TreeStore(str, str)
product_inventory_tree = Gtk.TreeStore(str, str)
product_revenue_tree = Gtk.TreeStore(str, str)
product_expense_list = Gtk.ListStore(str, str, str)
product_inventory_list = Gtk.ListStore(str, str, str)
product_revenue_list = Gtk.ListStore(str, str, str)

def populate_accounts():
	global  expense_account, \
			revenue_account, \
			revenue_list, \
			product_expense_tree, \
			product_inventory_tree, \
			product_revenue_tree, \
			product_expense_list, \
			product_inventory_list, \
			product_revenue_list
	cursor = DB.cursor()

	def populate_child_product_inventory ( number, parent, account_path):
		show = False
		cursor.execute("SELECT number, name, inventory_account, is_parent, "
							" ' / '||name "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			path = account_path + row[4]
			if row[2] == True:
				show = True
				product_inventory_tree.append(parent,[number, name])
				product_inventory_list.append([number, name, path])
			elif row[3] == True:
				p = product_inventory_tree.append(parent,[number, name])
				c_show = False
				if populate_child_product_inventory(number, p, path) == True:
					show = True
					c_show = True
				if c_show == False:
					product_inventory_tree.remove(p)
		return show
		
	def populate_child_revenue (number, parent, path):
		show = False
		cursor.execute("SELECT number, name, ' / '||name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			account_path = path + row[2]
			if row[3] != True:
				revenue_list.append([number, name, account_path])
			p = revenue_account.append(parent,[number, name, account_path])
			populate_child_revenue(number, p, account_path)

	def populate_child_product_revenue ( number, parent, account_path):
		show = False
		cursor.execute("SELECT number, name, revenue_account, is_parent, "
							" ' / '||name "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			path = account_path + row[4]
			if row[2] == True:
				show = True
				product_revenue_tree.append(parent,[number, name])
				product_revenue_list.append([number, name, path])
			elif row[3] == True:
				p = product_revenue_tree.append(parent,[number, name])
				c_show = False
				if populate_child_product_revenue(number, p, path) == True:
					show = True
					c_show = True
				if c_show == False:
					product_revenue_tree.remove(p)
		return show

	def populate_child_product_expense (number, parent, account_path):
		show = False
		cursor.execute("SELECT number, name, expense_account, is_parent, "
							" ' / '||name "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = str(row[0])
			name = row[1]
			path = account_path + row[4]
			if row[2] == True:
				product_expense_tree.append(parent,[number, name])
				product_expense_list.append([number, name, path])
				show = True
			elif row[3] == True:
				p = product_expense_tree.append(parent,[number, name])
				c_show = False
				if populate_child_product_expense(number, p, path) == True:
					show = True
					c_show = True
				if c_show == False:
					product_expense_tree.remove(p)
		return show

	def populate_child_expense ( number, parent):
		cursor.execute("SELECT number::text, name FROM gl_accounts WHERE "
							"parent_number = %s ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			p = expense_account.append(parent, row)
			populate_child_expense(number, p)

	############## finally, populate the accounts
	expense_account.clear()
	cursor.execute("SELECT number::text, name FROM gl_accounts WHERE type = 3 "
						"AND parent_number IS NULL")
	for row in cursor.fetchall():
		number = row[0]
		parent = expense_account.append(None, row)
		populate_child_expense(number, parent)
	#################################################
	product_expense_tree.clear()
	product_expense_list.clear()
	cursor.execute("SELECT number, name, ' / '||name "
						"FROM gl_accounts WHERE type = 3 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = str(row[0])
		name = row[1]
		path = row[2]
		show = False
		parent = product_expense_tree.append(None,[number, name])
		if populate_child_product_expense(number, parent, path) == True:
			show = True
		if show == False:
			product_expense_tree.remove(parent)
	##################################################
	product_revenue_tree.clear()
	product_revenue_list.clear()
	cursor.execute("SELECT number, name, ' / '||name "
						"FROM gl_accounts WHERE type = 4 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = str(row[0])
		name = row[1]
		path = row[2]
		show = False
		parent = product_revenue_tree.append(None,[number, name])
		if populate_child_product_revenue (number, parent, path) == True:
			show = True
		if show == False:
			product_revenue_tree.remove(parent)
	##################################################
	revenue_account.clear()
	revenue_list.clear()
	cursor.execute("SELECT number, name, ' / '||name "
						"FROM gl_accounts WHERE type = 4 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = row[0]
		name = row[1]
		path = row[2]
		parent = revenue_account.append(None,[number, name, path])
		populate_child_revenue (number, parent, path)
	##################################################
	product_inventory_tree.clear()
	product_inventory_list.clear()
	cursor.execute("SELECT number, name, ' / '||name "
						"FROM gl_accounts WHERE type = 1 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = str(row[0])
		name = row[1]
		path = row[2]
		show = False
		parent = product_inventory_tree.append(None,[number, name])
		if populate_child_product_inventory(number, parent, path) == True:
			show = True
		if show == False:
			product_inventory_tree.remove(parent)

	cursor.close()
	DB.rollback()

