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
from constants import DB, ui_directory

UI_FILE = ui_directory + "/accounts_configuration.ui"


class GUI():
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
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
		GLib.idle_add(spinbutton.select_region, 0, -1)

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
		c = DB.cursor()
		c.execute("SELECT number, name FROM gl_accounts "
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
		for row in c.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.parent_account_store.append([str(account_number), account_name])
		c.close()
		DB.rollback()

	def edit_account_clicked (self, menuitem):
		c = DB.cursor()
		c.execute("SELECT number, parent_number FROM gl_accounts "
							"WHERE number = %s", (self.active_account_number,))
		for row in c.fetchall():
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
			c.execute("UPDATE gl_accounts SET (number, parent_number) "
								"= (%s, %s) WHERE number = %s", 
								(new_number, parent_number, account_number))
			DB.commit()
			self.populate_account_treestore ()
		else:
			DB.rollback()
		c.close()
		
	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()

	def populate_account_treestore (self):
		c = DB.cursor()
		self.account_treestore.clear()
		c.execute("SELECT name, number, type FROM gl_accounts "
							"WHERE parent_number IS NULL ORDER BY number")
		for row in c.fetchall():
			account_name = row[0]
			account_number = row[1]
			account_type = row[2]
			parent = self.account_treestore.append(None, 
														[account_name, 
														account_number, 
														account_type])
			self.get_child_accounts (parent, account_number)
		DB.rollback()
		c.close()

	def get_child_accounts (self, parent_tree, parent_number):
		c = DB.cursor()
		c.execute("SELECT name, number, type FROM gl_accounts "
							"WHERE parent_number = %s ORDER BY number", 
							(parent_number,))
		for row in c.fetchall():
			account_name = row[0]
			account_number = row[1]
			account_type = row[2]
			parent = self.account_treestore.append(parent_tree, 
														[account_name, 
														account_number, 
														account_type])
			self.get_child_accounts (parent, account_number)
		c.close()

	def account_name_edited (self, cellrenderer_text, path, account_text):
		c = DB.cursor()
		account_number = self.account_treestore[path][1]
		c.execute("UPDATE gl_accounts SET name = %s WHERE number = %s", 
													(account_text, account_number))
		DB.commit()
		self.account_treestore[path][0] = account_text
		c.close()

	def customer_discount_combo_changed (self, combo):
		c = DB.cursor()
		if self.populating is True:
			return
		credit_account = combo.get_active_id()
		c.execute("UPDATE gl_account_flow SET account = %s "
							"WHERE function = 'customer_discount'", 
							( credit_account,))
		DB.commit()
		c.close()

	################ from here on is account deletion / creation / types

	def save_new_account(self, widget):
		c = DB.cursor()
		name = self.builder.get_object('entry1').get_text()
		number = self.builder.get_object('spinbutton1').get_value_as_int()
		acc_type = str(number)[0:1]
		try:
			c.execute("INSERT INTO gl_accounts "
								"(name, type, number, parent_number) "
								"VALUES (%s, %s, %s, %s)", 
								(name, acc_type, number, self.parent_number))
		except Exception as e:
			DB.rollback()
			self.show_message(str(e))
			return
		DB.commit()
		c.close()
		self.builder.get_object('spinbutton1').set_value(0)
		self.builder.get_object('entry1').set_text("")
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.account_treestore.clear()
		self.populate_account_treestore ()
		self.select_account_path (path[0])

	def account_error_dialog (self, num_accounts):
		c = DB.cursor()
		c.execute("SELECT name FROM gl_accounts WHERE number = %s", 
												(self.active_account_number,))
		account_name = c.fetchone()[0]
		error = ("You are trying to set '%s' as a selectable account.\n" 
				"'%s' has %s child accounts, therefore it is not allowed." 
				) % (account_name, account_name, num_accounts)
		self.builder.get_object('label1').set_label(error)
		error_dialog = self.builder.get_object('dialog1')
		result = error_dialog.run()
		error_dialog.hide()
		DB.rollback()
		c.close()

	def revenue_account_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		revenue_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if revenue_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET revenue_account = %s "
							"WHERE number = %s", 
							(revenue_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def expense_account_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		expense_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if expense_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET expense_account = %s "
							"WHERE number = %s", 
							(expense_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def check_writing_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		bank_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET check_writing = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def deposit_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		bank_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET deposits = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def bank_statement_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		bank_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = "
							"(SELECT number FROM gl_accounts "
							"WHERE parent_number = %s LIMIT 1)", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if bank_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET bank_account = %s "
							"WHERE number = %s", 
							(bank_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def credit_card_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		credit_card_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if credit_card_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET credit_card_account = %s "
							"WHERE number = %s", 
							(credit_card_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def cash_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		cash_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if cash_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET cash_account = %s "
							"WHERE number = %s", 
							(cash_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def inventory_checkbutton_toggled (self, checkbutton):
		c = DB.cursor()
		cash_account_boolean = checkbutton.get_active()
		c.execute("SELECT COUNT(name) FROM gl_accounts "
							"WHERE parent_number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
			num_accounts = row[0]
			if cash_account_boolean == False or num_accounts == 0:
				break #block popping an error on unsetting an account
			checkbutton.set_active(False)
			self.account_error_dialog(num_accounts)
			return # account has child accounts
		c.execute("UPDATE gl_accounts SET inventory_account = %s "
							"WHERE number = %s", 
							(cash_account_boolean, self.active_account_number))
		DB.commit()
		c.close()

	def check_if_used_account (self):
		c = DB.cursor()
		c.execute("SELECT expense_account, bank_account, "
							"credit_card_account, revenue_account, "
							"number, name, cash_account, inventory_account, "
							"deposits, check_writing "
							"FROM gl_accounts WHERE number = %s", 
							(self.active_account_number,))
		for row in c.fetchall():
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
		c.execute("SELECT function FROM gl_account_flow "
							"WHERE account = %s", (account_number,))
		for row in c.fetchall():
			DB.rollback()
			return
		# no active account, maybe we can add an account: continue ->
		c.execute("SELECT id FROM gl_entries "
							"WHERE debit_account = %s OR credit_account = %s", 
							(account_number, account_number))
		for row in c.fetchall():
			DB.rollback()
			return
		#no transactions for this account, we can add a child
		self.parent_number = account_number
		self.builder.get_object('label9').set_text(account_name)
		DB.rollback()
		c.close()

	def new_account_number_changed (self, spinbutton):
		self.check_if_new_account_valid ()
		
	def new_account_entry_changed (self, entry):
		self.check_if_new_account_valid ()

	def check_if_new_account_valid (self):
		c = DB.cursor()
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
		c.execute("SELECT number FROM gl_accounts WHERE number = %s", 
													(new_account_number, ))
		for row in c.fetchall():
			button.set_label("Number in use")
			DB.rollback()
			return
		button.set_sensitive(True)
		button.set_label("Save")
		DB.rollback()
		c.close()

	def delete_account(self, widget):
		c = DB.cursor()
		c.execute("DELETE FROM gl_accounts WHERE number = %s", 
							(self.active_account_number, ))
		DB.commit()
		c.close()
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.account_treestore.clear()
		self.populate_account_treestore ()
		self.select_account_path (path)

	def check_if_deleteable_account(self):
		c = DB.cursor()
		delete_button = self.builder.get_object('button6')
		delete_button.set_sensitive(False)
		c.execute("SELECT number, parent_number "
							"FROM gl_accounts WHERE number = %s", 
							(self.active_account_number, ))
		for row in c.fetchall():
			account_number = row[0]
			parent_number = row[1]
			if parent_number == None: #block deleting top level accounts as there is no way to add them (yet)
				delete_button.set_label("Top level account")
				DB.rollback()
				return
		c.execute("SELECT number FROM gl_accounts "
							"WHERE parent_number = %s", (account_number, ))
		for row in c.fetchall():
			delete_button.set_label("Has child account")
			DB.rollback()
			return
		# no dependants, maybe we can delete this account: continue ->
		c.execute("SELECT function FROM gl_account_flow "
							"WHERE account = %s", (account_number,))
		for row in c.fetchall():
			delete_button.set_label("Account used in configuration")
			DB.rollback()
			return
		# no active account, maybe we can delete this account: continue ->
		c.execute("SELECT id FROM gl_entries "
							"WHERE debit_account = %s "
							"OR credit_account = %s", 
							(account_number, account_number))
		for row in c.fetchall():
			delete_button.set_label("Account has transactions")
			DB.rollback()
			return
		# no transaction lines, we can delete this account
		delete_button.set_label("Delete")
		delete_button.set_sensitive(True) #set the delete button active
		DB.rollback()
		c.close()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
			
		

