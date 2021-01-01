# /reports/credit_card_statement_history.py
#
# Copyright (C) 2020 - reuben
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
from queue import Queue
from threading import Thread
import time
from constants import ui_directory, DB, broadcaster
import admin_utils

UI_FILE = ui_directory + "/reports/credit_card_statement_history.ui"

class CreditCardHistoryGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.progressbar = self.get_object('progressbar')

		self.date_filter = ''
		self.account_number = None
		self.populate_stores ()
		self.statement_store = self.get_object('statement_store')

		self.handler_ids = list()
		for connection in (("admin_changed", self.admin_changed), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.window = self.get_object('window1')
		self.window.show_all()

	def populate_stores (self):
		c = DB.cursor()
		c_c_store = self.get_object('c_c_account_store')
		c.execute("SELECT number::text, name FROM gl_accounts "
					"WHERE credit_card_account = True")
		for row in c.fetchall():
			c_c_store.append(row)
		date_store = self.get_object('reconcile_date_store')
		date_store.append(['0', 'No filter'])
		date_store.append(['1', 'All reconciled'])
		date_store.append(['2', 'All unreconciled'])
		c.execute("WITH credit_card_accounts AS "
					"(SELECT number FROM gl_accounts "
					"WHERE credit_card_account = True) "
					"SELECT date_reconciled::text AS date_sort, "
					"format_date(date_reconciled) AS date_format "
					"FROM gl_entries AS ge "
					"WHERE (ge.debit_account IN "
					"(SELECT number FROM credit_card_accounts) "
					"OR ge.credit_account IN "
					"(SELECT number FROM credit_card_accounts)) "
					"AND date_reconciled IS NOT NULL "
					"GROUP BY date_reconciled "
					"ORDER BY date_sort")
		for row in c.fetchall():
			date_store.append(row)
		self.get_object('reconcile_date_combo').set_active(0)
		DB.rollback()
		
	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def admin_changed (self, broadcast_object, value):
		self.get_object('edit_mode_checkbutton').set_active(False)

	def edit_mode_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)

	def description_edited (self, cellrenderertext, path, text):
		if not self.get_object('edit_mode_checkbutton').get_active():
			return
		store = self.get_object('statement_store')
		if text == store[path][3]:
			return
		row_id = store[path][0]
		c = DB.cursor()
		c.execute("UPDATE gl_entries "
					"SET transaction_description = %s "
					"WHERE id = %s", (text, row_id))
		DB.commit()
		store[path][3] = text

	def reconciled_toggled (self, cellrenderertoggle, path):
		if not self.get_object('edit_mode_checkbutton').get_active():
			return
		store = self.get_object('statement_store')
		''' do not allow setting reconciled to True
		it should be done in credit card statement window '''
		if store[path][4] == False: 
			return 
		row_id = store[path][0]
		c = DB.cursor()
		c.execute("UPDATE gl_entries "
					"SET (reconciled, date_reconciled) = (False, NULL) "
					"WHERE id = %s", (row_id,))
		DB.commit()
		store[path][4] = False
		store[path][5] = ''
		store[path][6] = ''

	def date_renderer_edited (self, renderer, path, text):
		if not self.get_object('edit_mode_checkbutton').get_active():
			return
		store = self.get_object('statement_store')
		c = DB.cursor()
		row_id = store[path][0]
		try:
			c.execute("UPDATE gl_entries "
						"SET date_inserted = %s WHERE id = %s "
						"RETURNING date_inserted::text, "
						"format_date(date_inserted)",
						(text, row_id))
		except psycopg2.DataError as e:
			DB.rollback()
			print (e)
			self.get_object('label10').set_label(str(e))
			dialog = self.get_object('dialog2')
			dialog.run()
			dialog.hide()
			return
		DB.commit()
		for row in c.fetchall():
			date_sorted = row[0]
			date_formatted = row[1]
			store[path][1] = date_sorted
			store[path][2] = date_formatted

	def collapse_all_activated (self, menuitem):
		self.get_object('treeview1').collapse_all()

	def expand_all_activated (self, menuitem):
		self.get_object('treeview1').expand_all()

	def report_hub_activated (self, button):
		treeview = self.get_object('treeview1')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def reconcile_date_match_selected (self, completion, model, treeiter):
		date_filter = model[treeiter][0]
		self.generate_date_filter (date_filter)
		text = model[treeiter][1]
		self.get_object('reconcile_date_combo_entry').set_text(text)
		self.populate_c_c_statement_store()
		return True # do not update the combobox entry text by default

	def reconcile_date_combo_changed (self, combobox):
		treeiter = combobox.get_active_iter()
		if treeiter == None:
			return
		model = combobox.get_model()
		date_filter = model[treeiter][0]
		self.generate_date_filter (date_filter)
		self.populate_c_c_statement_store()

	def generate_date_filter (self, date_filter):
		if date_filter == '0':
			self.date_filter = ""
		elif date_filter == '1':
			self.date_filter = "WHERE date_reconciled IS NOT NULL"
		elif date_filter == '2':
			self.date_filter = "WHERE date_reconciled IS NULL"
		else:
			self.date_filter = "WHERE date_reconciled = '%s'" % date_filter

	def radiobutton_toggled (self, radiobutton):
		# only load one time (filter by the radiobutton being active)
		if radiobutton.get_active() and self.account_number:
			self.populate_c_c_statement_store()

	def c_c_account_combo_changed (self, combobox):
		account_number = combobox.get_active_id()
		if account_number == None:
			return
		c = DB.cursor()
		c.execute("CREATE OR REPLACE TEMP VIEW "
					"c_c_statement_report_view AS "
					"WITH account_numbers AS "
						"(SELECT number FROM gl_accounts "
						"WHERE number = %s OR parent_number = %s"
						") "
						"SELECT id, amount, debit_account, "
						"credit_account, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, TRUE AS debit, FALSE AS credit, "
						"gl_transaction_id "
						"FROM gl_entries WHERE debit_account "
						"IN (SELECT * FROM account_numbers) "
						"UNION "
						"SELECT id, amount, debit_account, "
						"credit_account, date_inserted, "
						"reconciled, transaction_description, "
						"date_reconciled, FALSE AS debit, TRUE AS credit, "
						"gl_transaction_id "
						"FROM gl_entries WHERE credit_account "
						"IN (SELECT * FROM account_numbers)"
						, (account_number, account_number))
		c.close()
		DB.commit()
		self.account_number = account_number
		self.populate_c_c_statement_store ()

	def populate_c_c_statement_store (self):
		if not self.account_number:
			return
		start = time.time()
		treeview = self.get_object('treeview1')
		treeview.set_model(None)
		self.get_object('tools_box').set_sensitive(False)
		self.progressbar.show()
		spinner = self.get_object("spinner1")
		spinner.start()
		spinner.show()
		self.statement_store.clear()
		if self.get_object('radiobutton_single').get_active():
			rows = self.populate_statement()
		elif self.get_object('radiobutton_grouped').get_active():
			rows = self.populate_statement_grouped ()
		elif self.get_object('radiobutton_linked').get_active():
			rows = self.populate_statement_linked ()
		DB.rollback()
		self.get_object('treeview1').set_model(self.statement_store)
		spinner = self.get_object("spinner1")
		spinner.stop()
		spinner.hide()
		self.progressbar.hide()
		self.get_object('infobar').set_revealed(True)
		time_string = "%s seconds" % '{:,.2f}'.format(time.time()-start)
		self.get_object('time_label').set_label(time_string)
		self.get_object('rows_label').set_label('%d rows' % rows)
		self.get_object('tools_box').set_sensitive(True)

	def populate_statement (self):
		c = DB.cursor()
		c.execute("SELECT ge.id, "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN transaction_description IS NULL "
						"OR transaction_description = '' "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"ge.gl_transaction_id "
					"FROM c_c_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					" %s "
					"ORDER BY date_inserted" % 
					(self.date_filter,))
		tupl = c.fetchall()
		rows = len(tupl)
		for index, row in enumerate(tupl):
			if index == 0:
				index = 0.01
			progress = index/rows
			self.progressbar.set_fraction(progress)
			self.statement_store.append(None, row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		c.close()
		return rows

	def populate_statement_grouped (self):
		previous_date = 0 # current_date may be None, so use 0 to force mismatch
		c = DB.cursor()
		c.execute("SELECT ge.id, "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN transaction_description IS NULL "
						"OR transaction_description = '' "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"ge.gl_transaction_id "
					"FROM c_c_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					" %s "
					"ORDER BY date_reconciled, date_inserted" %
					(self.date_filter,))
		tupl = c.fetchall()
		rows = len(tupl)
		for index, row in enumerate(tupl):
			if index == 0:
				index = 0.01
			progress = index/rows
			self.progressbar.set_fraction(progress)
			current_date = row[5]
			if current_date != previous_date:
				parent = self.statement_store.append(None, [0, 
															row[1], 
															row[2], 
															'', 
															False, 
															'',
															'',
															0.00, 
															'', 
															0.00,
															'', 
															0])
				previous_date = current_date
			self.statement_store.append(parent, row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		c.close()
		return rows

	def populate_statement_linked (self):
		c = DB.cursor()
		db_queue = Queue()
		model_queue = Queue()
		t = Thread(target=self.db_query, args=(db_queue, model_queue))
		t.start()
		c.execute("SELECT ge.id, "
					"ge.date_inserted::text, "
					"format_date(ge.date_inserted), "
					"CASE WHEN transaction_description IS NULL "
						"OR transaction_description = '' "
						"THEN contacts.name "
						"ELSE transaction_description END, "
					"reconciled, "
					"ge.date_reconciled::text, "
					"format_date(ge.date_reconciled), "
					"CASE WHEN ge.credit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.credit THEN ge.amount::text ELSE '' END, "
					"CASE WHEN ge.debit THEN ge.amount ELSE 0.00 END, "
					"CASE WHEN ge.debit THEN ge.amount::text ELSE '' END, "
					"ge.gl_transaction_id "
					"FROM c_c_statement_report_view AS ge "
					"LEFT JOIN payments_incoming AS pi "
					"ON ge.id = pi.gl_entries_id "
					"LEFT JOIN contacts ON contacts.id = "
					"pi.customer_id "
					" %s "
					"ORDER BY date_inserted" %
					(self.date_filter,))
		tupl = c.fetchall()
		rows = len(tupl)
		for index, row in enumerate(tupl):
			if index == 0:
				index = 0.01
			progress = index/rows
			self.progressbar.set_fraction(progress)
			parent = self.statement_store.append(None, row)
			entry_id = row[0]
			tx_id = row[11]
			db_queue.put([parent, entry_id, tx_id, progress])
			while Gtk.events_pending():
				Gtk.main_iteration()
		db_queue.put('End')
		c.close()
		while True:
			list_ = model_queue.get()
			if list_ == 'End':
				break
			parent, progress, row = list_
			self.progressbar.set_fraction(progress)
			self.statement_store.append(parent, row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		return rows

	def db_query (self, db_queue, model_queue):
		c = DB.cursor()
		while True:
			list_ = db_queue.get()
			if list_ == 'End':
				break
			parent, entry_id, tx_id, progress = list_
			c.execute("SELECT ge.id, "
						"ge.date_inserted::text, "
						"format_date(ge.date_inserted), "
						"ga.name, "
						"reconciled, "
						"ge.date_reconciled::text, "
						"format_date(ge.date_reconciled), "
						"CASE WHEN ge.credit_account IS NOT NULL "
							"THEN ge.amount ELSE 0.00 END, "
						"CASE WHEN ge.credit_account IS NOT NULL "
							"THEN ge.amount::text ELSE '' END, "
						"CASE WHEN ge.debit_account IS NOT NULL "
							"THEN ge.amount ELSE 0.00 END, "
						"CASE WHEN ge.debit_account IS NOT NULL "
							"THEN ge.amount::text ELSE '' END, "
						"ge.gl_transaction_id "
						"FROM gl_entries AS ge "
						"JOIN gl_accounts AS ga "
							"ON ga.number = ge.credit_account "
							"OR ga.number = ge.debit_account "
						"WHERE ge.id != %s AND ge.gl_transaction_id = %s "
						"UNION "
						# handle POs with special treatment
						"SELECT 0, "
						"'', "
						"'', "
						"ga.name, "
						"False, "
						"'', "
						"'', "
						"0.00, "
						"'', "
						"SUM(ge.amount), "
						"SUM(ge.amount)::text, "
						"0 "
						"FROM purchase_orders AS po "
						"JOIN purchase_order_items AS poli "
							"ON poli.purchase_order_id = po.id "
						"JOIN gl_entries AS ge "
							"ON ge.id = poli.gl_entries_id "
						"JOIN gl_accounts AS ga "
							"ON ga.number = ge.debit_account "
						"WHERE po.gl_transaction_payment_id = %s "
						"GROUP BY ga.name "
						"ORDER BY date_inserted",
						(entry_id, tx_id, tx_id))
			for row in c.fetchall():
				model_queue.put((parent, progress, row))
		model_queue.put('End')
		c.close()

	def info_bar_close (self, infobar):
		infobar.set_revealed(False)

	def info_bar_response (self, infobar, response):
		if response == -7:
			infobar.set_revealed(False)





