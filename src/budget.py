# budget.py
#
# Copyright (C) 2018 - house
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
import main

UI_FILE = main.ui_directory + "/budget.ui"

class BudgetGUI:
	def __init__(self, db):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.populate_budgets()
		
		self.window = self.builder.get_object('budget_window')
		self.window.show_all()

	def populate_budgets (self):
		budget_store = self.builder.get_object('budget_store')
		budget_store.clear()
		self.cursor.execute("SELECT id::text, name FROM budgets")
		for row in self.cursor.fetchall():
			budget_store.append(row)

	def budget_combo_changed (self, combo):
		budget_id = combo_get_active_id ()
		if budget_id != None:
			self.budget_id = budget_id
		self.populate_budget_treeview()

	def populate_budget_treeview (self):
		store = Gtk.ListStore()
		store_list = list()
		treeview = self.builder.get_object('budget_treeview')
		self.cursor.execute("SELECT name || ' (' || amount::text || ')' "
							"FROM budget_amounts WHERE budget_id = %s", 
							(self.budget_id,))
		for index, row in self.cursor.fetchall():
			store_list.append(int)
			renderer = Gtk.CellRendererText()
			column = Gtk.TreeViewColumn(row[0], renderer, text=index)
			treeview.append_column(column)
		store.set_column_types(store_list)
		treeview_set_model(store)

	def configure_budget_clicked (self, button):
		import budget_configuration
		budget_configuration.BudgetConfigurationGUI(self.db)





