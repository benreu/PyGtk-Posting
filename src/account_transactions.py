# account_transactions.py
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

from gi.repository import Gtk, Gdk, GLib
from decimal import Decimal
from constants import DB, ui_directory

UI_FILE = ui_directory + "/account_transactions.ui"

class GUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.account_number = None

		self.account_store = self.builder.get_object('account_treestore')
		self.completion_liststore = self.builder.get_object('completion_liststore')
		self.account_treestore = self.builder.get_object('account_transaction_store')
		self.treeview = self.builder.get_object('treeview1')
		self.is_parent_account = None
		self.populate_account_treestore ()
		c = DB.cursor()
		fiscal_store = self.builder.get_object('fiscal_store')
		c.execute("SELECT id::text, name FROM fiscal_years "
							"WHERE active = True ORDER BY name ")
		for row in c.fetchall():
			fiscal_store.append(row)
		c.close()
		DB.rollback()
		self.builder.get_object('combobox2').set_active(0)
		account_completion = self.builder.get_object('account_completion')
		account_completion.set_match_func(self.completion_match_func)

		amount_column = self.builder.get_object ('treeviewcolumn2')
		amount_renderer = self.builder.get_object ('cellrenderertext3')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)

		balance_column = self.builder.get_object ('treeviewcolumn4')
		balance_renderer = self.builder.get_object ('cellrenderertext5')
		balance_column.set_cell_data_func(balance_renderer, self.balance_cell_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def amount_cell_func(self, column, cellrenderer, model, iter1, data):
		amount = '{:,.2f}'.format(model.get_value(iter1, 4))
		cellrenderer.set_property("text" , amount)

	def balance_cell_func(self, column, cellrenderer, model, iter1, data):
		balance = '{:,.2f}'.format(model.get_value(iter1, 5))
		cellrenderer.set_property("text" , balance)

	def populate_account_treestore (self):
		c = DB.cursor()
		self.account_treestore.clear()
		c.execute("SELECT number::text, name, is_parent FROM gl_accounts "
							"WHERE parent_number IS NULL ORDER BY number")
		for row in c.fetchall():
			account_number = row[0]
			self.completion_liststore.append(row)
			parent = self.account_store.append(None, row)
			self.get_main_child_accounts (parent, account_number)
		DB.rollback()
		c.close()

	def get_main_child_accounts (self, parent_tree, parent_number):
		c = DB.cursor()
		c.execute("SELECT number::text, name, is_parent FROM gl_accounts "
							"WHERE parent_number = %s ORDER BY number", 
							(parent_number,))
		for row in c.fetchall():
			account_number = row[0]
			self.completion_liststore.append(row)
			parent = self.account_store.append(parent_tree, row)
			self.get_main_child_accounts (parent, account_number)
		c.close()

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.builder.get_object('transaction_menu')
			menu.popup_at_pointer()
		
	def selection_changed (self, selection):
		model, paths = selection.get_selected_rows()
		if len(paths) > 1:
			menu = self.builder.get_object('transaction_menu')
			menu.popup_at_pointer()
	
	def gl_entry_lookup_activated (self, menuitem):
		selection = self.builder.get_object('treeview1').get_selection()
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		if len(paths) > 1:
			path_list = list()
			for path in paths:
				path_list.append(model[path][9])
			path_result = str(tuple(path_list))
		else:
			path_result = "(%s)" % paths[0] 
		from reports import gl_entry_lookup
		gl_entry_lookup.GlEntryLookupGUI(path_result)

	def treecolumn_clicked (self, column):
		label = self.builder.get_object('label1')
		#label.set_label("Balance calculations are no longer valid")

	def scroll_window_to_bottom (self):
		treeview = self.builder.get_object('scrolledwindow1')
		adj = treeview.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())

	def all_fiscal_toggled (self, togglebutton):
		if togglebutton.get_active() == True:
			self.fiscal = "SELECT id FROM fiscal_years"
		else:
			self.fiscal = self.builder.get_object('combobox2').get_active_id()
		self.load_account_store()

	def fiscal_combo_changed (self, combo):
		fiscal_id = combo.get_active_id()
		fiscal_checkbutton = self.builder.get_object('fiscal_checkbutton')
		if fiscal_checkbutton.get_active() == True:
			fiscal_checkbutton.set_active(False)
			# setting the checkbutton false will trigger all_fiscal_toggled
			return 
		if fiscal_id == None:
			return
		self.fiscal = fiscal_id
		self.load_account_store ()

	def account_summary_clicked (self, button):
		self.account_number = None
		self.account_name = 'Accounts summary'
		self.is_parent_account = True
		self.account_treestore.clear()
		self.builder.get_object('box3').set_sensitive(False)
		self.builder.get_object('cellrenderertext5').set_alignment(0.5, 0.5)
		self.builder.get_object('treeviewcolumn3').set_visible(False)
		self.builder.get_object('treeviewcolumn4').set_visible(False)
		self.builder.get_object('treeviewcolumn1').set_visible(True)
		self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
							"WHERE parent_number IS Null ORDER BY number")
		for row in self.cursor.fetchall():
			account_amount = 0.00
			is_parent = row[0]
			account_number = row[1]
			account_name = row[2]
			tree_parent = self.account_treestore.append(None, ['', 
														'', 
														account_number, 
														account_name, 
														0.00, 
														0.00, '',
														Gdk.RGBA(0,0,0,1), 
														Gdk.RGBA(0,0,0,1),
														0])
			for i in self.get_child_accounts(True, account_number, tree_parent):
				account_amount += i[1]
			self.account_treestore.set_value(tree_parent, 4, account_amount)

	def account_match_selected(self, completion, model, iter_):
		self.account_number = model[iter_][0]
		self.account_name = model[iter_][1]
		self.is_parent_account = model[iter_][2]
		self.select_account ()
		return True # block the signal from updating the combobox-entry text

	def account_combo_changed(self, combo):
		iter_ = combo.get_active_iter()
		if iter_ != None: #no account selected
			self.account_number = self.account_store[iter_][0]
			self.account_name = self.account_store[iter_][1]
			self.is_parent_account = self.account_store[iter_][2]
			self.select_account()

	def select_account (self, ):
		account = self.account_number + ' ' + self.account_name
		self.builder.get_object('combobox-entry').set_text(account)
		type_ = str(self.account_number)[0]
		if type_ == '4' or type_ == '5':
			self.n_col = 6 #the column with negative values
		else:
			self.n_col = 4
		self.load_account_store()
		self.scroll_window_to_bottom ()
		
	def refresh(self, widget):
		self.load_account_store()

	def load_account_store(self):
		if self.is_parent_account == None:
			return
		if self.is_parent_account == True:
			self.builder.get_object('box3').set_sensitive(False)
			self.builder.get_object('cellrenderertext3').set_alignment(0.5, 0.5)
			self.builder.get_object('treeviewcolumn3').set_visible(False)
			self.builder.get_object('treeviewcolumn4').set_visible(False)
			self.builder.get_object('treeviewcolumn1').set_title("Account")
			self.builder.get_object('treeviewcolumn5').set_visible(False)
			self.parent_child_account_treeview ()
		else:
			self.builder.get_object('box3').set_sensitive(True)
			self.builder.get_object('cellrenderertext3').set_alignment(1.0, 0.5)
			self.builder.get_object('treeviewcolumn3').set_visible(True)
			self.builder.get_object('treeviewcolumn4').set_visible(True)
			self.builder.get_object('treeviewcolumn1').set_title("Debit")
			self.builder.get_object('treeviewcolumn5').set_visible(True)
			#self.builder.get_object('radiobutton3').set_active(True) #set the individually radiobutton True
			self.update_treeview() 
		self.builder.get_object('window1').set_title(self.account_name + " (transactions)")
		GLib.timeout_add(10, self.scroll_window_to_bottom )
		DB.rollback()
		
	def completion_match_func (self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			number = self.completion_liststore[iter][0]
			name = self.completion_liststore[iter][1].lower()
			if text not in number and text not in name:
				return False
		return True

	def cursor_double_clicked(self, treeview, path, column):
		treeiter = self.account_treestore.get_iter(path)
		account_number = self.account_treestore.get_value(treeiter, 2)
		self.cursor.execute("SELECT number::text, name, is_parent "
							"FROM gl_accounts "
							"WHERE number = %s", (account_number, ))
		for row in self.cursor.fetchall():
			self.account_number = row[0]
			self.account_name = row[1]
			self.is_parent_account = row[2]
			self.select_account()

	def parent_child_account_treeview (self):
		self.account_treestore.clear()
		tree_parent = self.account_treestore.append(None, ['', 
													'', 
													0, 
													self.account_name, 
													0.00, 
													0.00, 
													'', 
													Gdk.RGBA(0,0,0,1), 
													Gdk.RGBA(0,0,0,1),
													0])
		account_amount = 0.00
		for i in self.get_child_accounts(True, self.account_number, tree_parent):
			account_amount += i[1]
		self.account_treestore.set_value(tree_parent, 4, account_amount)

	def get_child_accounts (self, is_parent, parent_account, parent_tree):
		c = DB.cursor()
		if is_parent == True:
			c.execute("SELECT is_parent, number, name FROM gl_accounts "
						"WHERE parent_number = %s ORDER BY number", 
						(parent_account,))
			for row in c.fetchall():
				account_amount = 0.00
				is_parent = row[0]
				account_number = row[1]
				account_name = row[2]
				tree_parent = self.account_treestore.append(parent_tree, ['', 
															'', 
															account_number, 
															str(account_number) + ' ' +account_name, 
															0.00, 
															0.00, 
															'',
															Gdk.RGBA(0,0,0,1), 
															Gdk.RGBA(0,0,0,1),
															0])
				for i in self.get_child_accounts (is_parent, account_number, 
															tree_parent):
					account_amount += i[1]
				self.account_treestore.set_value(tree_parent, 4, account_amount)
				yield account_number, account_amount
		else:
			c.execute("SELECT SUM(debits - credits) AS total FROM "
						"(SELECT COALESCE(SUM(amount),0.00) AS debits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE debit_account = %s AND fy.id IN (%s) ) d, "
						"(SELECT COALESCE(SUM(amount),0.00) AS credits "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN fiscal_years AS fy ON gtl.date_inserted "
								"BETWEEN fy.start_date AND fy.end_date "
							"WHERE credit_account = %s AND fy.id IN (%s) ) c" % 
					(parent_account, self.fiscal, parent_account, self.fiscal))
			for row in c.fetchall():
				account_amount = abs(row[0])
				yield parent_account, float(account_amount)
		c.close()

	#anything after this is the code to show the monthly, daily and individual transaction lines




	def update_treeview (self):
		if self.builder.get_object("radiobutton3").get_active() == True:
			self.update_treeview_individually ()
		elif self.builder.get_object("radiobutton2").get_active() == True:
			self.update_treeview_daily ()
		elif self.builder.get_object("radiobutton1").get_active() == True:
			self.update_treeview_monthly ()

	def update_treeview_individually(self, widget = None):
		if self.account_number == None:
			return
		if widget and widget.get_active() == False:
			return #toggle changed but not active
		treeview = self.builder.get_object("treeview1")
		model = treeview.get_model()
		treeview.set_model(None)
		spinner = self.builder.get_object("spinner1")
		spinner.start()
		spinner.show()
		progressbar = self.builder.get_object("progressbar1")
		progressbar.show()
		self.account_treestore.clear()
		balance = 0.00
		c = DB.cursor()
		c.execute("SELECT gtl.id, gtl.date_inserted::text, "
					"format_date(gtl.date_inserted), ge.amount, "
					"debit_account, debits.name, credit_account, "
					"credits.name, ge.id "
					"FROM gl_entries AS ge "
					"JOIN gl_transactions AS gtl "
						"ON gtl.id = ge.gl_transaction_id "
					"JOIN fiscal_years AS fy ON gtl.date_inserted "
						"BETWEEN fy.start_date AND fy.end_date "
					"LEFT JOIN gl_accounts AS debits "
						"ON ge.debit_account = debits.number "
					"LEFT JOIN gl_accounts AS credits "
						"ON ge.credit_account = credits.number  "
					"WHERE (credit_account = %s OR debit_account = %s) "
						"AND fy.id IN (%s) "
					"ORDER BY gtl.date_inserted, ge.id" %
					(self.account_number, self.account_number, self.fiscal))
		tupl = c.fetchall()
		rows = len(tupl)
		for index, transaction in enumerate(tupl):
			if index == 0:
				index = 0.01
			progress = index/rows
			trans_id = transaction[0]
			date = transaction[1]
			formatted_date = transaction[2]
			debit_account = transaction[4]
			debit_name = transaction[5]
			credit_account = transaction[6]
			credit_name = transaction[7]
			gl_entry_id = transaction[8]
			if transaction[self.n_col] == int(self.account_number): # this is a credit with the account id we are searching for
				amount = float(transaction[3])
				balance += float(transaction[3])
				amount_color = Gdk.RGBA(0,0,0,1)
				balance_color = Gdk.RGBA(0,0,0,1)
			else:# this is a debit with the account id we are searching for
				amount = float(transaction[3]) 
				amount = amount - amount * 2
				balance -= float(transaction[3])
				amount_color = Gdk.RGBA(0.4,0,0,1)
				balance_color = Gdk.RGBA(0.8,0,0,1)
			if balance < 0.00:
				balance_color = Gdk.RGBA(0.7,0,0,1)
			parent = self.account_treestore.append (None, [str(date), 
															formatted_date, 
															0, 
															debit_name, 
															amount, 
															balance, 
															credit_name,
															amount_color, 
															balance_color,
															gl_entry_id])
			if debit_account == None:
				amount_color = Gdk.RGBA(0,0,0,1)
				balance_color = Gdk.RGBA(0,0,0,1)
				c.execute("SELECT ge.amount, debits.name, ge.id "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN gl_accounts AS debits "
								"ON ge.debit_account = debits.number "
							"WHERE gtl.id = %s "
							"ORDER BY ge.id", (trans_id,))
				tuple_ = c.fetchall()
				if len(tuple_) == 1:
					self.account_treestore[parent][3] = tuple_[0][1]
				else:
					self.account_treestore[parent][3] = str(len(tuple_))
					for row in tuple_:
						amount = row[0]
						debit_name = row[1]
						gl_entry_id = row[2]
						self.account_treestore.append (parent, ['', 
																'', 
																0, 
																debit_name, 
																amount, 
																0.00, 
																'',
																amount_color, 
																balance_color,
																gl_entry_id])
			if credit_account == None:
				amount_color = Gdk.RGBA(0,0,0,1)
				balance_color = Gdk.RGBA(0,0,0,1)
				c.execute("SELECT ge.amount, credits.name, ge.id "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl "
								"ON gtl.id = ge.gl_transaction_id "
							"JOIN gl_accounts AS credits "
								"ON ge.credit_account = credits.number "
							"WHERE gtl.id = %s "
							"ORDER BY ge.id", (trans_id,))
				tuple_ = c.fetchall()
				if len(tuple_) == 1:
					self.account_treestore[parent][6] = tuple_[0][1]
				else:
					self.account_treestore[parent][6] = str(len(tuple_))
					for row in tuple_:
						amount = row[0]
						credit_name = row[1]
						gl_entry_id = row[2]
						self.account_treestore.append (parent, ['', 
																'', 
																0, 
																'', 
																amount, 
																0.00, 
																credit_name,
																amount_color, 
																balance_color,
																gl_entry_id])
			progressbar.set_fraction(progress)
			while Gtk.events_pending():
				Gtk.main_iteration()
		spinner.stop()
		spinner.hide()
		progressbar.hide()
		treeview.set_model(model)
		GLib.idle_add(self.scroll_window_to_bottom )
		c.close()

	def update_treeview_daily(self, widget = None):
		if self.account_number == None:
			return
		if widget and widget.get_active() == False:
			return #toggle changed but not active
		store = self.treeview.get_model()
		self.treeview.set_model(None)
		store.clear()
		amount = Decimal()
		c = DB.cursor()
		c.execute("SELECT date_group::text, "
					"format_date(date_group), "
					"COALESCE(d.debits,0.00) - COALESCE(c.credits,0.00) "
					"FROM "
					"("
						"(SELECT date_trunc('day', date_inserted)::date "
						"AS date_group FROM gl_entries "
						"WHERE credit_account = %s OR debit_account = %s "
						"GROUP BY date_group"
						") ge "

						"FULL OUTER JOIN "
						
						"(SELECT date_inserted AS date3, "
						"SUM(amount) AS credits "
						"FROM gl_entries "
						"WHERE credit_account = %s GROUP BY date3"
						") "
						"c ON date3 = date_group "

						"FULL OUTER JOIN "
						
						"(SELECT date_inserted AS date2, "
						"SUM(amount) AS debits "
						"FROM gl_entries "
						"WHERE debit_account = %s GROUP BY date2"
						") "
						"d ON date2 = date_group"
					") "
					"JOIN fiscal_years AS fy ON date_group "
						"BETWEEN fy.start_date AND fy.end_date "
						"AND fy.id IN (%s)"
				"ORDER BY 1" % 
							(self.account_number, self.account_number,
							self.account_number, self.account_number,
							self.fiscal))
		for row in c.fetchall():
			date = row[0]
			formatted_date = row[1]
			balance = row[2]
			amount += balance
			amount_color = Gdk.RGBA(0,0,0,1)
			balance_color = Gdk.RGBA(0,0,0,1)
			self.account_treestore.append (None,[	date,
													formatted_date,
													0,
													'', 
													float(balance), 
													float(amount), 
													'', 
													amount_color, 
													balance_color,
													0
												])
			while Gtk.events_pending():
				Gtk.main_iteration()
		c.close()
		self.treeview.set_model(store)
		GLib.timeout_add(10, self.scroll_window_to_bottom )

	def update_treeview_monthly(self, widget = None):
		if self.account_number == None:
			return
		if widget and widget.get_active() == False:
			return #toggle changed but not active
		store = self.treeview.get_model()
		self.treeview.set_model(None)
		store.clear()
		amount = Decimal()
		c = DB.cursor()
		c.execute("SELECT date_group::text, "
					"format_date(date_group), "
					"COALESCE(d.debits,0.00) - COALESCE(c.credits,0.00) "
					"FROM "
					"("
						"(SELECT date_trunc('month', date_inserted)::date "
						"AS date_group FROM gl_entries "
						"WHERE credit_account = %s OR debit_account = %s "
						"GROUP BY date_group"
						") ge "

						"FULL OUTER JOIN "
						
						"(SELECT date_trunc('month',date_inserted) AS date2, "
						"SUM(amount) AS debits "
						"FROM gl_entries "
						"WHERE debit_account = %s GROUP BY date2"
						") "
						"d ON date2 = date_group "

						"FULL OUTER JOIN "
						
						"(SELECT date_trunc('month',date_inserted) AS date3, "
						"SUM(amount) AS credits "
						"FROM gl_entries "
						"WHERE credit_account = %s GROUP BY date3"
						") "
						"c ON date3 = date_group "
					") "
					"JOIN fiscal_years AS fy ON date_group "
						"BETWEEN fy.start_date AND fy.end_date "
						"AND fy.id IN (%s) "
				"ORDER BY 1" % 
							(self.account_number, self.account_number,
							self.account_number, self.account_number,
							self.fiscal))
		for row in c.fetchall():
			date = row[0]
			formatted_date = row[1]
			balance = row[2]
			amount += balance
			amount_color = Gdk.RGBA(0,0,0,1)
			balance_color = Gdk.RGBA(0,0,0,1)
			store.append (None,[	date, 
													formatted_date,
													0, 
													'', 
													float(balance), 
													float(amount), 
													'', 
													amount_color, 
													balance_color,
													0
												])
			while Gtk.events_pending():
				Gtk.main_iteration()
		c.close()
		self.treeview.set_model(store)
		GLib.timeout_add(10, self.scroll_window_to_bottom )



