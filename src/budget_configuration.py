# budget_configuration.py
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
import main

UI_FILE = main.ui_directory + "/budget_configuration.ui"

class BudgetConfigurationGUI:
	def __init__(self, db):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.populate_budgets()
		self.populate_fiscals()
		
		self.window = self.builder.get_object('window')
		self.window.show_all()

	def add_budget_clicked (self, button):
		name = self.builder.get_object('name_entry').get_text()
		fiscal_id = self.builder.get_object('fiscal_combo').get_active_id()
		total = self.builder.get_object('total_spinbutton').get_value()

	def populate_budgets (self):
		budget_store = self.builder.get_object('budget_store')
		budget_store.clear()
		self.cursor.execute("SELECT id::text, name FROM budgets "
							"WHERE active = True")
		for row in self.cursor.fetchall():
			budget_store.append(row)

	def populate_fiscals (self):
		fiscal_store = self.builder.get_object('fiscal_store')
		fiscal_store.clear()
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"WHERE active = True")
		for row in self.cursor.fetchall():
			fiscal_store.append(row)

	def remove_clicked (self, button):
		selection = self.builder.get_object('configuration_selection')
		store, path = selection.get_selected_rows()
		if path == []:
			return

	def add_clicked (self, button):
		store = self.builder.get_object('configuration_store')
		iter_ = store.append()

	def budget_combo_changed (self, combobox):
		budget_id = combo_get_active_id ()
		if budget_id != None:
			self.budget_id = budget_id

