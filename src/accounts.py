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

expense_account = Gtk.TreeStore(int, str)
revenue_account = Gtk.TreeStore(int, str)
product_expense_account = Gtk.TreeStore(str, str)
product_inventory_account = Gtk.TreeStore(str, str)
product_revenue_account = Gtk.TreeStore(str, str)

def populate_accounts():
	global  expense_account, \
			revenue_account, \
			product_expense_account, \
			product_inventory_account, \
			product_revenue_account
	cursor = DB.cursor()

	def populate_child_product_inventory ( number, parent):
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
				if populate_child_product_inventory(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_inventory_account.remove(p)
		return show
		
	def populate_child_revenue ( number, parent):
		show = False
		cursor.execute("SELECT number, name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s "
							"ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = revenue_account.append(parent,[number, name])
			populate_child_revenue(number, p)

	def populate_child_product_revenue ( number, parent):
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
				if populate_child_product_revenue(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_revenue_account.remove(p)
		return show

	def populate_child_product_expense ( number, parent):
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
				if populate_child_product_expense(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					product_expense_account.remove(p)
		return show

	def populate_child_expense ( number, parent):
		cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"parent_number = %s ORDER BY name", (number,))
		for row in cursor.fetchall():
			number = row[0]
			name = row[1]
			p = expense_account.append(parent,[number, name])
			populate_child_expense(number, p)

	############## finally, populate the accounts
	expense_account.clear()
	cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
						"AND parent_number IS NULL")
	for row in cursor.fetchall():
		number = row[0]
		name = row[1]
		parent = expense_account.append(None,[number, name])
		populate_child_expense(number, parent)
	#################################################
	product_expense_account.clear()
	cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = str(row[0])
		name = row[1]
		show = False
		parent = product_expense_account.append(None,[number, name])
		if populate_child_product_expense(number, parent) == True:
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
		if populate_child_product_revenue (number, parent) == True:
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
		populate_child_revenue (number, parent)
	##################################################
	product_inventory_account.clear()
	cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 1 "
						"AND parent_number IS NULL ORDER BY name")
	for row in cursor.fetchall():
		number = str(row[0])
		name = row[1]
		show = False
		parent = product_inventory_account.append(None,[number, name])
		if populate_child_product_inventory(number, parent) == True:
			show = True
		if show == False:
			product_inventory_account.remove(parent)

	cursor.close()
	DB.rollback()

