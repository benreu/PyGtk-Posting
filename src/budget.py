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
		budget_id = combo.get_active_id ()
		if budget_id != None:
			self.budget_id = budget_id
			self.builder.get_object('refresh_button').set_sensitive(True)
			self.populate_budget_treeview()

	def populate_budget_treeview (self):
		treeview = self.builder.get_object('budget_treeview')
		for column in treeview.get_columns():
			treeview.remove_column(column)
		store = Gtk.ListStore()
		store_list = list()
		store_list.append(str)
		blank_list = list()
		budget_amounts = list()
		c = self.db.cursor()
		renderer = Gtk.CellRendererText()
		column = Gtk.TreeViewColumn("Date", renderer, text=0)
		treeview.append_column(column)
		c.execute(	"SELECT id, "
						"amount, "
						"name || '\n' || amount::money "
					"FROM budget_amounts WHERE budget_id = %s ORDER BY id", 
					(self.budget_id,))
		for index, row in enumerate(c.fetchall()):
			budget_amounts.append((row[0], row[1]))
			store_list.append(str)
			blank_list.append('0')
			renderer = Gtk.CellRendererText()
			column = Gtk.TreeViewColumn(row[2], renderer, text=index + 1)
			column.set_reorderable(True)
			column.set_resizable(True)
			treeview.append_column(column)
		store.set_column_types(store_list)
		c.execute("WITH fy AS "
					"(SELECT start_date, end_date FROM fiscal_years "
					"JOIN budgets ON budgets.fiscal_id = fiscal_years.id "
					"WHERE budgets.id = %s) "
					"SELECT to_char(series.day, 'Mon YYYY'), "
					"(SELECT start_date FROM fy), "
					"(SELECT end_date FROM fy) "
					"FROM generate_series ((SELECT start_date FROM fy), "
										"(SELECT end_date FROM fy), "
										"'1 month'::interval) AS series(day) "
					, (self.budget_id,))
		for row in c.fetchall():
			store.append([row[0],] + blank_list)
			start_date = row[1]
			end_date = row[2]
		for column, v in enumerate(budget_amounts):
			c.execute("WITH budget_range AS "
						"(SELECT date_trunc('month', gt.date_inserted) AS month, "
							"SUM(COALESCE(gc.amount, 0.00) - "
							"	COALESCE(gd.amount, 0.00)) AS running_total "
						"FROM budget_amounts AS ba "
						"JOIN budgets AS b ON ba.budget_id = b.id "
						"JOIN fiscal_years AS fy ON b.fiscal_id = fy.id "
						"LEFT JOIN gl_entries AS gd "
							"ON ba.account = gd.debit_account "
							"AND gd.date_inserted "
							"BETWEEN fy.start_date AND fy.end_date "
						"LEFT JOIN gl_entries AS gc "
							"ON ba.account = gc.credit_account "
							"AND gc.date_inserted "
							"BETWEEN fy.start_date AND fy.end_date "
						"JOIN gl_transactions AS gt "
							"ON gt.id = gc.gl_transaction_id "
							"OR gt.id = gd.gl_transaction_id "
						"WHERE ba.id = %s "
						"GROUP BY month"
						") "
						"SELECT to_char(series.day, 'Mon YYYY'), "
							"SUM(COALESCE(SUM(br.running_total), 0.00) + %s) "
								"OVER (ORDER BY series.day) AS budget "
						"FROM generate_series(%s, %s, '1 month'::interval) "
							"AS series(day) "
						"LEFT JOIN budget_range AS br "
							"ON br.month = series.day "
						"GROUP BY series.day", 
							(v[0], v[1], start_date, end_date))
			for row_index, row in enumerate (c.fetchall()):
				store[row_index][column + 1] = str(row[1])
		treeview.set_model(store)

	def configure_budget_clicked (self, button):
		import budget_configuration
		budget_configuration.BudgetConfigurationGUI(self.db)

	def refresh_clicked (self, button):
		self.populate_budget_treeview()
		





