# accounts_configuration.py
#
# Copyright (C) 2016 - reuben
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

UI_FILE = main.ui_directory + "/accounts_configuration.ui"


class GUI():
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = main.db
		self.cursor = self.db.cursor()
		
		self.account_treestore = self.builder.get_object('account_treestore')
		self.parent_account_store = self.builder.get_object('parent_account_store')
		self.account_treestore.set_sort_column_id (0,Gtk.SortType.ASCENDING )
		
		self.populate_account_treestore ()
		account_completion = self.builder.get_object('account_completion')
		account_completion.set_match_func(self.account_match_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		GLib.timeout_add(5, self.select_account_path, 0)

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(self.highlight, spinbutton)

	def highlight (self, spinbutton):
		spinbutton.select_region(0, -1)

	def report_hub_activated (self, menuitem):
		treeview = self.builder.get_object('treeview1')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def expand_all_clicked (self, button):
		treeview = self.builder.get_object('treeview1')
		treeview.expand_all()

	def collapse_all_clicked (self, button):
		treeview = self.builder.get_object('treeview1')
		treeview.collapse_all()

	def account_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.parent_account_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def parent_account_match_selected (self, completion, model, iter_):
		parent_account = model[iter_][0]
		self.builder.get_object('combobox1').set_active_id(str(parent_account))

	def parent_account_combo_changed (self, combo):
		account = combo.get_active_id ()
		if account != -1:
			self.dialog_parent_account = account

	def select_account_path(self, path):
		self.builder.get_object('treeview-selection').select_path(path)

	def account_treerow_changed (self, treeview):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path != []:
			self.account_treerow_activated(treeview, path)

	def account_treerow_activated (self, treeview, path, treeviewcolumn = None):
		treeiter = self.account_treestore.get_iter(path)
		self.active_account_number = self.account_treestore[treeiter][1]
		self.check_if_used_account ()
		self.check_if_deleteable_account()

	def populate_parent_account_store (self):
		self.parent_account_store.clear ()
		selection = self.builder.get_object ('treeview-selection')
		model, path = selection.get_selected_rows ()
		account_type = model[path][2]
		self.cursor.execute("SELECT number, name FROM gl_accounts "
					"WHERE number NOT IN "
					"(SELECT gl_accounts.number FROM public.gl_accounts, "
					"public.gl_entries, "
					"public.gl_account_flow "
					"WHERE gl_entries.debit_account = "
						"gl_accounts.number "
					"OR gl_entries.credit_account = "
						"gl_accounts.number "
					"OR gl_account_flow.account = gl_accounts.number "
					"GROUP BY number) "
				"AND (bank_account, credit_card_account, "
				"expense_account, revenue_account, cash_account, type) = "
				"(False, False, False, False, False, %s) "
				"ORDER BY name;", (account_type,))
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.parent_account_store.append([str(account_number), account_name])

	def edit_account_clicked (self, menuitem):
		self.cursor.execute("SELECT number, parent_number FROM gl_accounts "
							"WHERE number = %s", (self.active_account_number,))
		for row in self.cursor.fetchall():
			if row[1] == None:
				return #do not allow changing top level accounts
			account_number = row[0]
			parent_number = row[1]
		self.populate_parent_account_store()
		self.builder.get_object('spinbutton3').set_value(account_number)
		self.builder.get_object('combobox1').set_active_id(str(parent_number))
		dialog = self.builder.get_object('dialog3')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			new_number = self.builder.get_object('spinbutton3').get_value()
			parent_number = self.builder.get_object('combobox1').get_active_id()
			self.cursor.execute("UPDATE gl_accounts SET (number, parent_number) "
								"= (%s, %s) WHERE number = %s", 
								(new_number, parent_number, account_number))
			self.db.commit()
			self.populate_account_treestore ()
		
	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def populate_account_treestore (self):
		self.account_treestore.clear()
		self.cursor.execute("SELECT name, number, type FROM gl_accounts "
							"WHERE parent_number IS NULL ORDER BY number")
		for row in self.cursor.fetchall():
			account_name = row[0]
			account_number = row[1]
			account_type = row[2]
			parent = self.account_treestore.append(None, 
														[account_name, 
														account_number, 
														account_type])
			self.get_child_accounts (parent, account_number)

	def get_child_accounts (self, parent_tree, parent_number):
		self.cursor.execute("SELECT name, number, type FROM gl_accounts "
							"WHERE parent_number = %s ORDER BY number", 
							(parent_number,))
		for row in self.cursor.fetchall():
			account_name = row[0]
			account_number = row[1]
			account_type = row[2]
			parent = self.account_treestore.append(parent_tree, 
														[account_name, 
														account_number, 
														account_type])
			self.get_child_accounts (parent, account_number)

	def account_name_edited (self, cellrenderer_text, path, account_text):
		account_number = self.account_treestore[path][1]
		self.cursor.execute("UPDATE gl_accounts SET name = %s WHERE number = %s", 
													(account_text, account_number))
		self.db.commit()
		self.account_treestore[path][0] = account_text

	def customer_discount_combo_changed (self, combo):
		if self.populating is True:
			return
		credit_account = combo.get_active_id()
		self.cursor.execute("UPDATE gl_account_flow SET account = %s "
							"WHERE function = 'customer_discount'", 
							( credit_account,))
		self.db.commit()

	################ from here on is account deletion / creation / types

	def save_new_account(self, widget):
		name = self.builder.get_object('entry1').get_text()
		number = self.builder.get_object('spinbutton1').get_value_as_int()
		acc_type = str(number)[0:1]
		try:
			self.cursor.execute("INSERT INTO gl_accounts "
								"(name, type, number, parent_number) "
								"VALUES (%s, %s, %s, %s)", 
								(name, acc_type, number, self.parent_number))
		except Exception as e:
			self.db.rollback()
			self.show_message(str(e))
			return
		self.db.commit()
		self.builder.get_object('spinbutton1').set_value(0)
		self.builder.get_object('entry1').set_text("")
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.account_treestore.clear()
		self.populate_account_treestore ()
		self.select_account_path (path[0])

	def account_error_dialog (self, num_accounts):
		self.cursor.execute("SELECT name FROM gl_accounts WHERE number = %s", 
												(self.active_account_number,))
		account_name = self.cursor.fetchone()[0]
		error = ("You are trying to set '%s' as a selectable account.\n" 
				"'%s' has %s child accounts, therefore it is not allowed." 
				) % (account_name, account_name, num_accounts)
		self.builder.get_object('label1').set_label(error)
		error_dialog = self.builder.get_object('dialog1')
		result = error_dialog.run()
		error_dialog.hide()

	def revenue_account_checkbutton_toggled (self, checkbutton):
		revenue_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if revenue_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET revenue_account = %s "
							"WHERE number = %s", 
							(revenue_account_boolean, self.active_account_number))
		self.db.commit()

	def expense_account_checkbutton_toggled (self, checkbutton):
		expense_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if expense_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET expense_account = %s "
							"WHERE number = %s", 
							(expense_account_boolean, self.active_account_number))
		self.db.commit()

	def check_writing_checkbutton_toggled (self, checkbutton):
		bank_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET check_writing = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		self.db.commit()
		self.db.commit()

	def deposit_checkbutton_toggled (self, checkbutton):
		bank_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET deposits = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		self.db.commit()

	def bank_statement_checkbutton_toggled (self, checkbutton):
		bank_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET bank_account = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		self.db.commit()

	def credit_card_checkbutton_toggled (self, checkbutton):
		credit_card_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if credit_card_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET credit_card_account = %s "
							"WHERE number = %s", 
							(credit_card_account_boolean, self.active_account_number))
		self.db.commit()

	def cash_checkbutton_toggled (self, checkbutton):
		cash_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if cash_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET cash_account = %s "
							"WHERE number = %s", 
							(cash_account_boolean, self.active_account_number))
		self.db.commit()

	def inventory_checkbutton_toggled (self, checkbutton):
		cash_account_boolean = checkbutton.get_active()
		self.cursor.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			num_accounts = row[0]
			if cash_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		self.cursor.execute("UPDATE gl_accounts SET inventory_account = %s "
							"WHERE number = %s", 
							(cash_account_boolean, self.active_account_number))
		self.db.commit()

	def check_if_used_account (self):
		self.cursor.execute("SELECT expense_account, bank_account, "
							"credit_card_account, revenue_account, "
							"number, name, cash_account, inventory_account, "
							"deposits, check_writing "
							"FROM gl_accounts WHERE number = %s", 
							(self.active_account_number,))
		for row in self.cursor.fetchall():
			expense_account_bool = row[0]
			bank_account_bool = row[1]
			c_c_account_bool = row[2]
			revenue_account_bool = row[3]
			account_number = row[4]
			account_name = row[5]
			cash_account_bool = row[6]
			inventory_account_bool = row[7]
			deposits_bool = row[8]
			check_writing_bool = row[9]
		self.builder.get_object('checkbutton1').set_active(expense_account_bool)
		self.builder.get_object('checkbutton8').set_active(bank_account_bool)
		self.builder.get_object('checkbutton3').set_active(c_c_account_bool)
		self.builder.get_object('checkbutton4').set_active(revenue_account_bool)
		self.builder.get_object('checkbutton5').set_active(cash_account_bool)
		self.builder.get_object('checkbutton6').set_active(inventory_account_bool)
		self.builder.get_object('checkbutton7').set_active(deposits_bool)
		self.builder.get_object('checkbutton2').set_active(check_writing_bool)
		self.cursor.execute("SELECT function FROM gl_account_flow "
							"WHERE account = %s", (account_number,))
		for row in self.cursor.fetchall():
			return
		# no active account, maybe we can add an account: continue ->
		self.cursor.execute("SELECT id FROM gl_entries "
							"WHERE debit_account = %s OR credit_account = %s", 
							(account_number, account_number))
		for row in self.cursor.fetchall():
			return
		#no transactions for this account, we can add a child
		self.parent_number = account_number
		self.builder.get_object('label9').set_text(account_name)

	def new_account_number_changed (self, spinbutton):
		self.check_if_new_account_valid ()
		
	def new_account_entry_changed (self, entry):
		self.check_if_new_account_valid ()

	def check_if_new_account_valid (self):
		button = self.builder.get_object('button5')
		button.set_sensitive(False)
		name_entry = self.builder.get_object('entry1')
		if name_entry.get_text() == '':
			button.set_label("No account name")
			return
		number_entry = self.builder.get_object('spinbutton1')
		new_account_number = number_entry.get_value_as_int()
		if len(str(new_account_number)) < 4: #enforce at least 4 character account numbers
			button.set_label("Number too short")
			return
		self.cursor.execute("SELECT number FROM gl_accounts WHERE number = %s", 
													(new_account_number, ))
		for row in self.cursor.fetchall():
			button.set_label("Number in use")
			return
		button.set_sensitive(True)
		button.set_label("Save")

	def delete_account(self, widget):
		self.cursor.execute("DELETE FROM gl_accounts WHERE number = %s", 
							(self.active_account_number, ))
		self.db.commit()
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.account_treestore.clear()
		self.populate_account_treestore ()
		self.select_account_path (path)

	def check_if_deleteable_account(self):
		delete_button = self.builder.get_object('button6')
		delete_button.set_sensitive(False)
		self.cursor.execute("SELECT number, parent_number "
							"FROM gl_accounts WHERE number = %s", 
							(self.active_account_number, ))
		for row in self.cursor.fetchall():
			account_number = row[0]
			parent_number = row[1]
			if parent_number == None: #block deleting top level accounts as there is no way to add them (yet)
				delete_button.set_label("Top level account")
				return
		self.cursor.execute("SELECT number FROM gl_accounts "
							"WHERE parent_number = %s", (account_number, ))
		for row in self.cursor.fetchall():
			delete_button.set_label("Has child account")
			return
		# no dependants, maybe we can delete this account: continue ->
		self.cursor.execute("SELECT function FROM gl_account_flow "
							"WHERE account = %s", (account_number,))
		for row in self.cursor.fetchall():
			delete_button.set_label("Account used in configuration")
			return
		# no active account, maybe we can delete this account: continue ->
		self.cursor.execute("SELECT id FROM gl_entries "
							"WHERE debit_account = %s "
							"OR credit_account = %s", 
							(account_number, account_number))
		for row in self.cursor.fetchall():
			delete_button.set_label("Account has transactions")
			return
		# no transaction lines, we can delete this account
		delete_button.set_label("Delete")
		delete_button.set_sensitive(True) #set the delete button active

	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()
			
		

