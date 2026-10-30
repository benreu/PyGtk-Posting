# query_results.py
#
# Copyright (C) 2026 - reuben
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

'''A treeview showing whatever rows a query returned, for the SQL window and
Complete search's record view.

A NULL is a blank cell, or unticked in a true/false column. An integer column
has to hold real ints, so that it sorts as numbers and Report hub's xls export
writes numbers, but an int column cannot hold a NULL: int(None) raised, and
the record view showed it as 0. So an integer column with a NULL in it is made
a text column instead, sorted as numbers by number_sort_func.'''

from gi.repository import Gtk

INT4 = 23
BOOL = 16

def fill_treeview (treeview, description, rows):
	"add a column for each in description, and a store of rows, to treeview"
	type_list = list()
	for index, row in enumerate(description):
		nulls = any(record[index] is None for record in rows)
		if row.type_code == INT4 and not nulls:
			type_list.append(int)
			renderer = Gtk.CellRendererText()
			column = Gtk.TreeViewColumn(row.name, renderer, text=index)
		elif row.type_code == BOOL:
			type_list.append(bool)
			renderer = Gtk.CellRendererToggle()
			column = Gtk.TreeViewColumn(row.name, renderer, active=index)
		else:
			type_list.append(str)
			renderer = Gtk.CellRendererText()
			column = Gtk.TreeViewColumn(row.name, renderer, text=index)
		treeview.append_column(column)
		column.set_sort_column_id(index)
		column.set_reorderable(True)
		column.set_resizable(True)
	store = Gtk.ListStore()
	store.set_column_types(type_list)
	for index, row in enumerate(description):
		if row.type_code == INT4 and type_list[index] == str:
			store.set_sort_func(index, number_sort_func, index)
	for row in rows:
		# do a convert, cell by cell, to make sure types are correct
		store_row = list()
		for index, element in enumerate(row):
			if element is None and type_list[index] == str:
				element = ''
			store_row.append(type_list[index](element))
		store.append (store_row)
	treeview.set_model(store)
	return store

def number_sort_func (model, iter_a, iter_b, column):
	"blanks first, then the numbers in order"
	a = number_key(model[iter_a][column])
	b = number_key(model[iter_b][column])
	# not a - b: two int4s can differ by more than the C int GTK wants back
	return (a > b) - (a < b)

def number_key (text):
	if text == '':
		return (0, 0)
	return (1, int(text))
