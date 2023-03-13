# profit_loss_report.py
#
# Copyright (C) 2019 - reuben rissler
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
import os
from constants import ui_directory, DB
from decimal import Decimal

UI_FILE = ui_directory + "/reports/profit_loss_report.ui"

class ProfitLossReportGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.populate_fiscals ()

		self.window = self.get_object("window")
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def populate_fiscals (self):
		fiscal_store = self.get_object('fiscal_store')
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"ORDER BY name ")
		for account in self.cursor.fetchall():
			fiscal_store.append(account)
		DB.rollback()

	def fiscal_year_combo_changed (self, combobox):
		fiscal_id = combobox.get_active_id()
		if fiscal_id == None:
			return
		self.fiscal = fiscal_id
		store = self.get_object("revenue_store")
		store.clear()
		# Revenues first
		self.cursor.execute("SELECT is_parent, number::text, name "
							"FROM gl_accounts "
							"WHERE type = 4 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = store.append(None, [number, name, '0.00', False])
			revenue = Decimal()
			for i in self.get_child_accounts(store, 
												is_parent, 
												number, 
												tree_parent):
				revenue += i
			store.set_value(tree_parent, 2, str(revenue))
		# Expenses next
		store = self.get_object("expense_store")
		store.clear()
		self.cursor.execute("SELECT is_parent, number::text, name "
							"FROM gl_accounts "
							"WHERE type = 3 AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			is_parent = row[0]
			number = row[1]
			name = row[2]
			tree_parent = store.append(None, [number, name, '0.00', False])
			expenses = Decimal()
			for i in self.get_child_accounts(store, 
												is_parent, 
												number, 
												tree_parent):
				expenses += i
			store.set_value(tree_parent, 2, str(expenses))
		income = revenue - expenses
		label = self.get_object("income_amount_label")
		label.set_label('${:,.2f}'.format(income))
		DB.rollback()

	def get_child_accounts (self, store, is_parent, p_account, parent_tree):
		c = DB.cursor()
		if is_parent == True:
			c.execute("SELECT is_parent, number::text, name, 0.00::text "
						"FROM gl_accounts "
						"WHERE parent_number = %s ORDER BY number", 
						(p_account,))
			for row in c.fetchall():
				account_amount = Decimal()
				is_parent = row[0]
				account_number = row[1]
				account_name = row[2]
				tree_parent = store.append(parent_tree,[
														account_number,
														account_name,
														'0.00',
														False])
				for i in self.get_child_accounts (store, 
													is_parent, 
													account_number, 
													tree_parent):
					account_amount += i
				store.set_value(tree_parent, 2, str(account_amount))
				yield account_amount
		else:
			c.execute("SELECT SUM(debits - credits) AS total FROM "
						"(SELECT COALESCE(SUM(amount),0.00) AS debits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE debit_account = %s AND fy.id = %s ) d, "
						"(SELECT COALESCE(SUM(amount),0.00) AS credits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE credit_account = %s AND fy.id = %s ) c" , 
					(p_account, self.fiscal, p_account, self.fiscal))
			for row in c.fetchall():
				account_amount = abs(row[0])
				yield account_amount
		c.close()

	def revenue_treeview_button_press_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('revenue_menu')
			menu.popup_at_pointer()
			return True

	def revenue_export_to_csv_activated (self, menuitem):
		selection = self.get_object('revenue_selection')
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		import csv
		dialog = self.get_object ('filechooserdialog1')
		uri = os.path.expanduser('~')
		dialog.set_current_folder_uri("file://" + uri)
		dialog.set_current_name("Revenue.csv")
		response = dialog.run()
		dialog.hide()
		if response != Gtk.ResponseType.ACCEPT:
			return
		selected_file = dialog.get_filename()
		with open(selected_file, 'w') as csvfile:
			exportfile = csv.writer(csvfile, 
									delimiter=',',
									quotechar='|', 
									quoting=csv.QUOTE_MINIMAL)
			for path in paths:
				row = model[path]
				exportfile.writerow(row)

	def expense_calculate_total_toggled (self, cellrenderertoggle, path):
		store = self.get_object("expense_store")
		store[path][3] = not store[path][3]
		total = Decimal()
		root_iter = store.get_iter_first()
		if store[root_iter][3] == True:
			total += Decimal(store[root_iter][2])
			if store.iter_has_child(root_iter):
				childiter = store.iter_children(root_iter)
				self.clear_children_total_toggle(store, childiter)
		else:
			total += self.get_children_totals(store, root_iter)
		label = self.get_object("expense_total_label")
		label.set_label("${:,.2f}".format(total))

	def revenue_calculate_total_toggled (self, cellrenderertoggle, path):
		store = self.get_object("revenue_store")
		store[path][3] = not store[path][3]
		total = Decimal()
		root_iter = store.get_iter_first()
		if store[root_iter][3] == True:
			total += Decimal(store[root_iter][2])
			if store.iter_has_child(root_iter):
				childiter = store.iter_children(root_iter)
				self.clear_children_total_toggle(store, childiter)
		else:
			total += self.get_children_totals(store, root_iter)
		label = self.get_object("revenue_total_label")
		label.set_label("${:,.2f}".format(total))

	def get_children_totals(self, store, tree_iter):
		child_amount = Decimal()
		while tree_iter != None:
			if store[tree_iter][3] == True:
				child_amount += Decimal(store[tree_iter][2])
				if store.iter_has_child(tree_iter):
					childiter = store.iter_children(tree_iter)
					self.clear_children_total_toggle(store, childiter)
			elif store.iter_has_child(tree_iter):
				childiter = store.iter_children(tree_iter)
				child_amount += self.get_children_totals(store, childiter)
			tree_iter = store.iter_next(tree_iter)
		return child_amount

	def clear_children_total_toggle(self, store, tree_iter):
		# unselect all children totals if parent total is selected
		while tree_iter != None:
			store[tree_iter][3] = False
			if store.iter_has_child(tree_iter):
				childiter = store.iter_children(tree_iter)
				self.clear_children_total_toggle(store, childiter)
			tree_iter = store.iter_next(tree_iter)

	def expense_treeview_button_press_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('expense_menu')
			menu.popup_at_pointer()
			return True

	def expense_export_to_csv_activated (self, menuitem):
		selection = self.get_object('expense_selection')
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		import csv
		dialog = self.get_object ('filechooserdialog1')
		uri = os.path.expanduser('~')
		dialog.set_current_folder_uri("file://" + uri)
		dialog.set_current_name("Expense.csv")
		response = dialog.run()
		dialog.hide()
		if response != Gtk.ResponseType.ACCEPT:
			return
		selected_file = dialog.get_filename()
		with open(selected_file, 'w') as csvfile:
			exportfile = csv.writer(csvfile, 
									delimiter=',',
									quotechar='|', 
									quoting=csv.QUOTE_MINIMAL)
			for path in paths:
				row = model[path]
				exportfile.writerow(row)

	def revenue_report_hub_clicked (self, button):
		treeview = self.get_object('revenue_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)
		
	def expense_report_hub_clicked (self, button):
		treeview = self.get_object('expense_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)



