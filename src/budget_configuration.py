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


from gi.repository import Gtk, GLib
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
		self.account_store = self.builder.get_object('account_store')
		self.populate_accounts()
		
		self.window = self.builder.get_object('window')
		self.window.show_all()

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def populate_accounts(self):
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE parent_number IS NULL ORDER BY name")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = self.account_store.append(None,[number, name])
			self.populate_child_accounts(parent, number)

	def populate_child_accounts (self, parent, number):
		self.cursor.execute("SELECT number::text, name, is_parent "
						"FROM gl_accounts WHERE parent_number = %s "
						"ORDER BY name", (number,))
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			p = self.account_store.append(parent,[number, name])
			self.populate_child_accounts (p, number)

	def add_budget_clicked (self, button):
		name = self.builder.get_object('budget_name_entry').get_text()
		fiscal_id = self.builder.get_object('fiscal_combo').get_active_id()
		total = self.builder.get_object('total_spinbutton').get_value()
		self.cursor.execute("INSERT INTO budgets "
							"(name, fiscal_id, total) VALUES (%s, %s, %s)", 
							(name, fiscal_id, total))
		self.db.commit()
		self.populate_budgets ()

	def populate_budgets (self):
		budget_store = self.builder.get_object('budget_store')
		budget_store.clear()
		self.cursor.execute("SELECT id::text, name, total::text, active FROM budgets "
							"WHERE active = True ORDER BY name")
		for row in self.cursor.fetchall():
			budget_store.append(row)

	def populate_fiscals (self):
		fiscal_store = self.builder.get_object('fiscal_store')
		fiscal_store.clear()
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"WHERE active = True ORDER BY name")
		for row in self.cursor.fetchall():
			fiscal_store.append(row)

	def remove_amount_clicked (self, button):
		selection = self.builder.get_object('amount_selection')
		store, path = selection.get_selected_rows()
		if path == []:
			return

	def add_amount_clicked (self, button):
		store = self.builder.get_object('amount_store')
		name = self.builder.get_object('amount_name_entry').get_text()
		amount = self.builder.get_object('amount_spinbutton').get_value()
		account = self.builder.get_object('amount_account_combo').get_active_id()
		self.cursor.execute("INSERT INTO budget_amounts "
							"(budget_id, name, amount, account) "
							"VALUES (%s, %s, %s, %s) ",
							(self.budget_id, name, amount, account))
		self.db.commit()
		self.populate_budget_amounts()

	def amount_edited (self, cellrenderertext, path, amount):
		store = self.builder.get_object('amount_store')
		amount_id = store[path][0]
		self.cursor.execute("UPDATE budget_amounts SET amount = %s "
							"WHERE id = %s", (amount, amount_id))
		self.db.commit()
		self.populate_budget_amounts()

	def budget_combo_changed (self, combo):
		budget_id = combo.get_active_id ()
		store = combo.get_model()
		active_iter = combo.get_active_iter()
		self.budget_total = store[active_iter][2]
		if budget_id != None:
			self.budget_id = budget_id
		self.builder.get_object('amounts_edit_box').set_sensitive(True)
		label = self.builder.get_object('total_amount_label')
		label.set_label(str(self.budget_total))
		self.populate_budget_amounts ()

	def populate_budget_amounts (self):
		store = self.builder.get_object('amount_store')
		store.clear()
		c = self.db.cursor()
		c.execute(	"SELECT "
					"ba.id, "
					"ba.name, "
					"gl.name, "
					"amount::text, "
					"ROUND((ba.amount/b.total)*100, 2)::varchar "
					"FROM budget_amounts AS ba "
					"JOIN gl_accounts AS gl ON gl.number = ba.account "
					"JOIN budgets AS b ON b.id = ba.budget_id "
					"WHERE budget_id = %s",
					(self.budget_id,))
		for row in c.fetchall():
			store.append(row)
		c.execute(	"SELECT "
					"ROUND((SUM(ba.amount)/b.total)*100, 2)::varchar "
					"FROM budget_amounts AS ba "
					"JOIN budgets AS b ON b.id = ba.budget_id "
					"WHERE budget_id = %s "
					"GROUP BY ba.budget_id, b.total",
					(self.budget_id,))
		for row in c.fetchall():
			self.builder.get_object('total_percent_label').set_label(row[-1])
		c.close()




