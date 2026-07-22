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

from collections import defaultdict
from gi.repository import Gtk
from db_connection import DB

all_accounts_tree = Gtk.TreeStore(str, str, str)
expense_tree = Gtk.TreeStore(str, str, str)
expense_list = Gtk.ListStore(str, str, str)
revenue_account = Gtk.TreeStore(int, str, str)
revenue_list = Gtk.ListStore(int, str, str)
product_expense_tree = Gtk.TreeStore(str, str)
product_inventory_tree = Gtk.TreeStore(str, str)
product_revenue_tree = Gtk.TreeStore(str, str)
product_expense_list = Gtk.ListStore(str, str, str)
product_inventory_list = Gtk.ListStore(str, str, str)
product_revenue_list = Gtk.ListStore(str, str, str)

def populate_accounts():
	global  all_accounts_tree, \
			expense_tree, \
			revenue_account, \
			revenue_list, \
			product_expense_tree, \
			product_inventory_tree, \
			product_revenue_tree, \
			product_expense_list, \
			product_inventory_list, \
			product_revenue_list

	# Single round trip: fetch the whole chart of accounts once and build every
	# tree/list below from an in-memory parent_number -> children map, instead
	# of issuing a recursive query per node for each of the six trees.
	cursor = DB.cursor()
	cursor.execute("SELECT number, name, parent_number, type, is_parent, "
						"inventory_account, revenue_account, expense_account "
						"FROM gl_accounts ORDER BY name")
	rows = cursor.fetchall()
	cursor.close()
	DB.rollback()

	children_by_parent = defaultdict(list)
	for row in rows:
		children_by_parent[row[2]].append(row)

	def children_of(number):
		return children_by_parent.get(number, [])

	def populate_child_product_inventory(number, parent, account_path):
		show = False
		for row in children_of(number):
			child_number = str(row[0])
			name = row[1]
			path = account_path + ' / ' + name
			if row[5] == True:
				show = True
				product_inventory_tree.append(parent,[child_number, name])
				product_inventory_list.append([child_number, name, path])
			elif row[4] == True:
				p = product_inventory_tree.append(parent,[child_number, name])
				c_show = populate_child_product_inventory(row[0], p, path)
				if c_show == True:
					show = True
				else:
					product_inventory_tree.remove(p)
		return show

	def populate_child_revenue (number, parent, path):
		for row in children_of(number):
			child_number = row[0]
			name = row[1]
			account_path = path + ' / ' + name
			if row[4] != True:
				revenue_list.append([child_number, name, account_path])
			p = revenue_account.append(parent,[child_number, name, account_path])
			populate_child_revenue(child_number, p, account_path)

	def populate_child_product_revenue ( number, parent, account_path):
		show = False
		for row in children_of(number):
			child_number = str(row[0])
			name = row[1]
			path = account_path + ' / ' + name
			if row[6] == True:
				show = True
				product_revenue_tree.append(parent,[child_number, name])
				product_revenue_list.append([child_number, name, path])
			elif row[4] == True:
				p = product_revenue_tree.append(parent,[child_number, name])
				c_show = populate_child_product_revenue(row[0], p, path)
				if c_show == True:
					show = True
				else:
					product_revenue_tree.remove(p)
		return show

	def populate_child_product_expense (number, parent, account_path):
		show = False
		for row in children_of(number):
			child_number = str(row[0])
			name = row[1]
			path = account_path + ' / ' + name
			if row[7] == True:
				product_expense_tree.append(parent,[child_number, name])
				product_expense_list.append([child_number, name, path])
				show = True
			elif row[4] == True:
				p = product_expense_tree.append(parent,[child_number, name])
				c_show = populate_child_product_expense(row[0], p, path)
				if c_show == True:
					show = True
				else:
					product_expense_tree.remove(p)
		return show

	def populate_child_expense ( number, parent, account_path):
		for row in children_of(number):
			child_number = str(row[0])
			name = row[1]
			path = account_path + ' / ' + name
			expense_list.append([child_number, name, path])
			p = expense_tree.append(parent, [child_number, name, path])
			populate_child_expense(row[0], p, path)

	def populate_child_all ( number, parent, account_path):
		for row in children_of(number):
			child_number = str(row[0])
			name = row[1]
			path = account_path + ' / ' + name
			p = all_accounts_tree.append(parent, [child_number, name, path])
			populate_child_all(row[0], p, path)

	top_level_rows = children_by_parent.get(None, [])

	############## finally, populate the accounts
	all_accounts_tree.clear()
	for row in top_level_rows:
		number = str(row[0])
		name = row[1]
		path = ' / ' + name
		parent = all_accounts_tree.append(None, [number, name, path])
		populate_child_all (row[0], parent, path)
	#################################################
	expense_tree.clear()
	expense_list.clear()
	for row in top_level_rows:
		if row[3] != 3:
			continue
		number = str(row[0])
		name = row[1]
		path = ' / ' + name
		expense_list.append([number, name, path])
		parent = expense_tree.append(None, [number, name, path])
		populate_child_expense (row[0], parent, path)
	#################################################
	product_expense_tree.clear()
	product_expense_list.clear()
	for row in top_level_rows:
		if row[3] != 3:
			continue
		number = str(row[0])
		name = row[1]
		path = ' / ' + name
		show = False
		parent = product_expense_tree.append(None,[number, name])
		if populate_child_product_expense(row[0], parent, path) == True:
			show = True
		if show == False:
			product_expense_tree.remove(parent)
	##################################################
	product_revenue_tree.clear()
	product_revenue_list.clear()
	for row in top_level_rows:
		if row[3] != 4:
			continue
		number = str(row[0])
		name = row[1]
		path = ' / ' + name
		show = False
		parent = product_revenue_tree.append(None,[number, name])
		if populate_child_product_revenue (row[0], parent, path) == True:
			show = True
		if show == False:
			product_revenue_tree.remove(parent)
	##################################################
	revenue_account.clear()
	revenue_list.clear()
	for row in top_level_rows:
		if row[3] != 4:
			continue
		number = row[0]
		name = row[1]
		path = ' / ' + name
		parent = revenue_account.append(None,[number, name, path])
		populate_child_revenue (row[0], parent, path)
	##################################################
	product_inventory_tree.clear()
	product_inventory_list.clear()
	for row in top_level_rows:
		if row[3] != 1:
			continue
		number = str(row[0])
		name = row[1]
		path = ' / ' + name
		show = False
		parent = product_inventory_tree.append(None,[number, name])
		if populate_child_product_inventory(row[0], parent, path) == True:
			show = True
		if show == False:
			product_inventory_tree.remove(parent)
