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
import main

UI_FILE = main.ui_directory + "/account_transactions.ui"

class GUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.account_number = None

		self.account_store = self.builder.get_object('account_store')
		self.account_treestore = self.builder.get_object('account_transaction_store')
		self.db = db
		self.cursor = self.db.cursor()
		self.cursor.execute("SELECT number, name, is_parent FROM gl_accounts "
							"ORDER BY number")
		for account in self.cursor.fetchall():
			number = str(account[0])
			name = account[1]
			is_parent_account = account[2]
			self.account_store.append([number, number + " " + name, 
										is_parent_account])
		fiscal_store = self.builder.get_object('fiscal_store')
		self.cursor.execute("SELECT id, name FROM fiscal_years "
							"ORDER BY name")
		for account in self.cursor.fetchall():
			number = str(account[0])
			name = account[1]
			fiscal_store.append([number, name])
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

	def treecolumn_clicked (self, column):
		label = self.builder.get_object('label1')
		#label.set_label("Balance calculations are no longer valid")

	def scroll_window_to_bottom (self):
		treeview = self.builder.get_object('scrolledwindow1')
		adj = treeview.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())

	def fiscal_combo_changed (self, combo):
		pass

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
														'', account_number, 
														account_name, 
														0.00, 0.00, '',
														Gdk.RGBA(0,0,0,1), 
														Gdk.RGBA(0,0,0,1)])
			for i in self.get_child_accounts(True, account_number, tree_parent):
				account_amount += i[1]
			self.account_treestore.set_value(tree_parent, 4, account_amount)

	def account_match_selected(self, completion, model, iter_):
		self.select_account (iter_)

	def account_combo_changed(self, combo):
		path = combo.get_active()
		if path != -1: #no account selected
			self.select_account (path)

	def select_account (self, path):
		self.account_number = self.account_store[path][0]
		self.account_name = self.account_store[path][1]
		self.is_parent_account = self.account_store[path][2]
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
			GLib.idle_add (self.update_treeview) 
		self.builder.get_object('window1').set_title(self.account_name + " (transactions)")
		GLib.timeout_add(10, self.scroll_window_to_bottom )
		
	def completion_match_func (self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.account_store[iter][1].lower():
				return False
		return True

	def cursor_double_clicked(self, treeview, path, column):
		treeiter = self.account_treestore.get_iter(path)
		account_number = self.account_treestore.get_value(treeiter, 2)
		self.cursor.execute("SELECT name, number, is_parent FROM gl_accounts "
							"WHERE number = %s", (account_number, ))
		for line in self.cursor.fetchall():
			self.account_name = line[0]
			self.account_number = str(line[1])
			self.is_parent_account = line[2]
			account_combo = self.builder.get_object('combobox1')
			account_combo.set_active_id (self.account_number)

	def parent_child_account_treeview (self):
		self.account_treestore.clear()
		tree_parent = self.account_treestore.append(None, ['', '', 0, 
													self.account_name, 0.00, 
													0.00, '', Gdk.RGBA(0,0,0,1), 
													Gdk.RGBA(0,0,0,1)])
		account_amount = 0.00
		for i in self.get_child_accounts(True, self.account_number, tree_parent):
			account_amount += i[1]
		self.account_treestore.set_value(tree_parent, 4, account_amount)

	def get_child_accounts (self, is_parent, parent_account, parent_tree):
		if is_parent == True:
			self.cursor.execute("SELECT is_parent, number, name FROM gl_accounts "
								"WHERE parent_number = %s ORDER BY number", 
								(parent_account,))
			for row in self.cursor.fetchall():
				account_amount = 0.00
				is_parent = row[0]
				account_number = row[1]
				account_name = row[2]
				tree_parent = self.account_treestore.append(parent_tree, ['', 
															'', account_number, 
															str(account_number) + ' ' +account_name, 
															0.00, 0.00, '',
															Gdk.RGBA(0,0,0,1), 
															Gdk.RGBA(0,0,0,1)])
				for i in self.get_child_accounts (is_parent, account_number, 
															tree_parent):
					account_amount += i[1]
				self.account_treestore.set_value(tree_parent, 4, account_amount)
				yield account_number, account_amount
		else:
			self.cursor.execute("SELECT SUM(debits - credits) AS total FROM "
									"(SELECT COALESCE(SUM(amount),0.00) AS debits "
									"FROM gl_entries "
									"WHERE debit_account = %s) d, "
									"(SELECT COALESCE(SUM(amount),0.00) AS credits "
									"FROM gl_entries "
									"WHERE credit_account= %s) c", 
								(parent_account, parent_account))
			for row in self.cursor.fetchall():
				account_amount = abs(row[0])
				yield parent_account, float(account_amount)
				

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
		self.cursor.execute("SELECT gtl.id, gtl.date_inserted::text, "
							"format_date(gtl.date_inserted), ge.amount, "
							"debit_account, debits.name, credit_account, "
							"credits.name, ge.id "
							"FROM gl_entries AS ge "
							"JOIN gl_transactions AS gtl ON gtl.id = ge.gl_transaction_id "
							"LEFT JOIN gl_accounts AS debits ON ge.debit_account = debits.number "
							"LEFT JOIN gl_accounts AS credits ON ge.credit_account = credits.number  "
							"WHERE credit_account = %s OR debit_account = %s "
							"ORDER BY gtl.date_inserted, ge.id",
							(self.account_number, self.account_number))
		tupl = self.cursor.fetchall()
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
			parent = self.account_treestore.append (None, [str(date), formatted_date, 0, 
											debit_name, amount, balance, credit_name,
											amount_color, balance_color])
			if debit_account == None:
				amount_color = Gdk.RGBA(0,0,0,1)
				balance_color = Gdk.RGBA(0,0,0,1)
				self.cursor.execute("SELECT ge.amount, debits.name "
								"FROM gl_entries AS ge "
								"JOIN gl_transactions AS gtl ON gtl.id = ge.gl_transaction_id "
								"JOIN gl_accounts AS debits ON ge.debit_account = debits.number "
								"WHERE gtl.id = %s "
								"ORDER BY ge.id", (trans_id,))
				tuple_ = self.cursor.fetchall()
				if len(tuple_) == 1:
					self.account_treestore[parent][3] = tuple_[0][1]
				else:
					self.account_treestore[parent][3] = str(len(tuple_))
					for row in tuple_:
						amount = row[0]
						debit_name = row[1]
						self.account_treestore.append (parent, ['', '', 0, 
												debit_name, amount,  0.00, '',
												amount_color, balance_color])
			if credit_account == None:
				amount_color = Gdk.RGBA(0,0,0,1)
				balance_color = Gdk.RGBA(0,0,0,1)
				self.cursor.execute("SELECT ge.amount, credits.name "
								"FROM gl_entries AS ge "
								"JOIN gl_transactions AS gtl ON gtl.id = ge.gl_transaction_id "
								"JOIN gl_accounts AS credits ON ge.credit_account = credits.number "
								"WHERE gtl.id = %s "
								"ORDER BY ge.id", (trans_id,))
				tuple_ = self.cursor.fetchall()
				if len(tuple_) == 1:
					self.account_treestore[parent][6] = tuple_[0][1]
				else:
					self.account_treestore[parent][6] = str(len(tuple_))
					for row in tuple_:
						amount = row[0]
						credit_name = row[1]
						self.account_treestore.append (parent, ['', '', 0, 
												'', amount,  0.00, credit_name,
												amount_color, balance_color])
			progressbar.set_fraction(progress)
			while Gtk.events_pending():
				Gtk.main_iteration()
		spinner.stop()
		spinner.hide()
		progressbar.hide()
		treeview.set_model(model)
		GLib.idle_add(self.scroll_window_to_bottom )

	def update_treeview_daily(self, widget = None):
		if self.account_number == None:
			return
		self.account_treestore.clear()
		amount = 0.00
		self.cursor.execute("SELECT date_group, "
								"formatted_date, "
								"COALESCE(d.debits - c.credits, 0.00) "
								"FROM "
								"((SELECT date_trunc('day', date_inserted)::text "
								"AS date_group, format_date(date_inserted) "
								"AS formatted_date FROM gl_entries "
								"WHERE credit_account = %s OR debit_account = %s "
								"GROUP BY date_group, formatted_date) ge "

								"LEFT JOIN "
								
								"(SELECT  date_inserted::text AS date2, "
								"COALESCE(SUM(amount),0.00) AS debits "
								"FROM gl_entries "
								"WHERE debit_account = %s GROUP BY date2) "
								"d ON date2 = date_group "

								"LEFT JOIN "
								
								"(SELECT date_inserted::text AS date3, "
								"COALESCE(SUM(amount),0.00) AS credits "
								"FROM gl_entries "
								"WHERE credit_account = %s GROUP BY date3) "
								"c ON date3 = date_group ) "
							"ORDER BY 1", 
							(self.account_number, self.account_number,
							self.account_number, self.account_number))
		for row in self.cursor.fetchall():
			date = row[0]
			formatted_date = row[1]
			balance = float(row[2])
			amount += balance
			amount_color = Gdk.RGBA(0,0,0,1)
			balance_color = Gdk.RGBA(0,0,0,1)
			self.account_treestore.append (None, [date, formatted_date,
											0, '', balance, float(amount), '', 
											amount_color, balance_color])
			while Gtk.events_pending():
				Gtk.main_iteration()
				self.scroll_window_to_bottom ()
		GLib.timeout_add(10, self.scroll_window_to_bottom )

	def update_treeview_monthly(self, widget = None):
		if self.account_number == None:
			return
		self.account_treestore.clear()
		amount = 0.00
		self.cursor.execute("SELECT date_group, "
								"format_date(date_inserted), "
								"COALESCE(d.debits - c.credits, 0.00)::float FROM "
								"((SELECT date_trunc('month', date_inserted) "
								"AS date_group, date_inserted FROM gl_entries GROUP BY date_group, date_inserted) ge "

								"LEFT JOIN "
								
								"(SELECT date_trunc('month', date_inserted) "
								"AS date_group2, COALESCE(SUM(amount),0.00) AS debits "
								"FROM gl_entries "
								"WHERE debit_account = %s GROUP BY date_group2) "
								"d ON date_group2 = date_group "

								"LEFT JOIN "
								
								"(SELECT date_trunc('month', date_inserted) "
								"AS date_group3, COALESCE(SUM(amount),0.00) AS credits "
								"FROM gl_entries "
								"WHERE credit_account = %s GROUP BY date_group3) "
								"c ON date_group3 = date_group ) "
							"ORDER BY 1"
							, (self.account_number, self.account_number))
		for row in self.cursor.fetchall():
			date = row[0]
			formatted_date = row[1]
			balance = row[2]
			amount += balance
			amount_color = Gdk.RGBA(0,0,0,1)
			balance_color = Gdk.RGBA(0,0,0,1)
			self.account_treestore.append (None, [str(date), formatted_date,
											0, '', balance, float(amount), '', 
											amount_color, balance_color])
			while Gtk.events_pending():
				Gtk.main_iteration()
				self.scroll_window_to_bottom ()		
		GLib.timeout_add(10, self.scroll_window_to_bottom )



		



		
