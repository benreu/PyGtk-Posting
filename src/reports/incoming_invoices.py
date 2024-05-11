# incoming_invoices.py
#
# Copyright (C) 2017 - reuben
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
import subprocess, psycopg2
from decimal import Decimal
from constants import ui_directory, DB, broadcaster
from accounts import expense_tree
import admin_utils

UI_FILE = ui_directory + "/reports/incoming_invoices.ui"

class IncomingInvoiceGUI(Gtk.Builder):
	service_provider_id = None
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.service_provider_store = self.get_object('service_provider_store')
		self.get_object('expense_account_combobox').set_model(expense_tree)
		self.fiscal_store = self.get_object('fiscal_store')
		self.incoming_invoice_store = self.get_object('incoming_invoices_store')
		self.invoice_items_store = self.get_object('invoice_items_store')
		sp_completion = self.get_object('service_provider_completion')
		sp_completion.set_match_func(self.sp_match_func)

		self.search_desc_text = ''
		self.filter = self.get_object ('incoming_invoices_filter')
		self.filter.set_visible_func(self.filter_func)
		self.service_provider_join = 'JOIN contacts AS c ON c.id = i.contact_id '
		self.expense_account_join = ''
		self.fiscal_year_join = ''

		self.populate_service_provider_store ()
		self.populate_fiscal_store ()
		self.handler_ids = list()
		for connection in (("admin_changed", self.admin_changed), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def admin_changed (self, broadcast_object, value):
		self.get_object('edit_mode_checkbutton').set_active(False)
		self.get_object('edit_incoming_invoice_menuitem').set_visible(False)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def search_description_entry_changed (self, searchentry):
		self.search_desc_text = searchentry.get_text().lower()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.search_desc_text.split():
			if text not in model[tree_iter][5].lower():
				return False
		return True

	def view_attachment_activated (self, menuitem):
		selection = self.get_object('incoming_invoices_tree_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		file_id = model[path][0]
		self.cursor.execute("SELECT attached_pdf FROM incoming_invoices "
							"WHERE id = %s "
							"AND attached_pdf IS NOT NULL", (file_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/Attachment.pdf"
			file_data = row[0]
			with open(file_name,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_name])
			DB.rollback()
			break
		else: # no pdf found, give the user the option to attach one
			import pdf_attachment
			paw = pdf_attachment.PdfAttachmentWindow(self.window)
			paw.connect("pdf_optimized", self.optimized_callback, file_id)

	def optimized_callback (self, pdf_attachment_window, file_id):
		file_data = pdf_attachment_window.get_pdf ()
		self.cursor.execute("UPDATE incoming_invoices "
							"SET attached_pdf = %s "
							"WHERE id = %s", (file_data, file_id))
		DB.commit()

	def populate_service_provider_store (self):
		self.service_provider_store.clear()
		self.service_provider_store.append(['0', "All service providers", ''])
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE service_provider = True ORDER BY name")
		for row in self.cursor.fetchall():
			self.service_provider_store.append(row)
		DB.rollback()

	def populate_fiscal_store (self):
		self.fiscal_store.clear()
		self.fiscal_store.append(['0', "All fiscal years"])
		self.cursor.execute("SELECT id::text, name FROM fiscal_years "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.fiscal_store.append(row)
		DB.rollback()

	def sp_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.service_provider_store[iter_][1].lower():
				return False# no match
		return True# it's a hit!

	def service_provider_combo_changed (self, combobox):
		service_provider_id = combobox.get_active_id()
		if service_provider_id == None :
			self.service_provider_join = \
				'JOIN contacts AS c ON c.id = i.contact_id '
			return
		elif service_provider_id == '0':
			self.service_provider_join = \
				'JOIN contacts AS c ON c.id = i.contact_id '
		elif service_provider_id != None:
			self.service_provider_join = \
				"JOIN contacts AS c ON c.id = i.contact_id AND " \
				"i.contact_id = %s " % (service_provider_id,)
		self.populate_incoming_invoice_store()

	def service_provider_match_selected (self, completion, model, iter_):
		sp_id = model[iter_][0]
		self.get_object('combobox1').set_active_id (sp_id)

	def expense_account_combo_changed (self, combobox):
		expense_account_id = combobox.get_active_id()
		if expense_account_id == None:
			self.expense_account_join = ''
			return
		elif expense_account_id == '0':
			self.expense_account_join = ''
		elif expense_account_id != None:
			self.expense_account_join = \
				"JOIN LATERAL ( SELECT debit_account FROM gl_entries AS ge " \
				"WHERE gl_transaction_id = i.gl_transaction_id LIMIT 1) AS i_join " \
				"ON i_join.debit_account = %s " \
				% (expense_account_id,)
		self.populate_incoming_invoice_store()

	def fiscal_year_combo_changed (self, combobox):
		fiscal_year_id = combobox.get_active_id()
		if fiscal_year_id == None:
			self.fiscal_year_join = ''
			return
		elif fiscal_year_id == '0':
			self.fiscal_year_join = ''
		elif fiscal_year_id != None:
			self.fiscal_year_join = \
				"JOIN fiscal_years AS fy ON fy.id = %s " \
				"AND i.date_created " \
				"BETWEEN fy.start_date AND fy.end_date " % (fiscal_year_id,)
		self.populate_incoming_invoice_store()

	def refresh_activated (self, button):
		self.populate_incoming_invoice_store()

	def populate_incoming_invoice_store (self):
		treeselection = self.get_object('incoming_invoices_tree_selection')
		model, path = treeselection.get_selected_rows()
		treeview = self.get_object('incoming_invoices_treeview')
		model = treeview.get_model()
		treeview.set_model(None)
		self.incoming_invoice_store.clear()
		self.invoice_items_store.clear()
		c = DB.cursor()
		c.execute("SELECT "
					"i.id, "
					"c.id, "
					"c.name, "
					"i.date_created::text, "
					"format_date(i.date_created), "
					"i.description, "
					"i.amount, "
					"i.amount::text, "
					"(SELECT reconciled FROM gl_entries WHERE id = i.gl_entry_id)"
					"FROM incoming_invoices AS i "
					"%s "
					"%s "
					"%s "
					"ORDER BY date_created, i.id" % 
					(self.service_provider_join, 
					self.expense_account_join, 
					self.fiscal_year_join ))
		for row in c.fetchall():
			self.incoming_invoice_store.append(row)
		DB.rollback()
		treeview.set_model(model)
		if path != []: 
			treeselection.select_path(path)

	def incoming_invoice_selection_changed (self, treeselection):
		self.invoice_items_store.clear()
		model, paths = treeselection.get_selected_rows()
		stack = self.get_object('invoice_info_page')
		if len(paths) == 0:
			stack.set_visible_child_name('invoice_items_page')
			return
		elif len(paths) == 1:
			stack.set_visible_child_name('invoice_items_page')
			self.populate_invoice_items(treeselection)
		elif len(paths) > 1:
			stack.set_visible_child_name('invoice_stats_page')
			self.show_incoming_invoice_stats(treeselection)

	def populate_invoice_items (self, treeselection):
		model, path = treeselection.get_selected_rows()
		row_id = model[path][0]
		self.cursor.execute("SELECT "
								"ge.id, "
								"ge.amount, "
								"ge.amount::text, "
								"ga.name, "
								"iige.id, "
								"iige.remark "
							"FROM "
							"incoming_invoices_gl_entry_expenses_ids AS iige "
							"JOIN gl_entries AS ge ON ge.id = "
								"iige.gl_entry_expense_id "
							"JOIN gl_accounts AS ga ON ga.number = "
								"ge.debit_account "
							"WHERE incoming_invoices_id = %s",
							(row_id,))
		for row in self.cursor.fetchall():
			self.invoice_items_store.append(row)
		DB.rollback()

	def show_incoming_invoice_stats (self, treeselection):
		model, paths = treeselection.get_selected_rows()
		path_list = list()
		for path in paths:
			path_list.append(model[path][0])
		c = DB.cursor()
		c.execute("SELECT "
						"COUNT(id)::text, "
						"format_date(MIN(date_created)), "
						"format_date(MAX(date_created)), "
						"COUNT( DISTINCT contact_id)::text, "
						"MIN(amount)::money, "
						"MAX(amount)::money, "
						"SUM(amount)::money, "
						"AVG(amount)::money, "
						"date_trunc('day',make_interval(days => "
							"MAX(date_created)-MIN(date_created)))::text "
					"FROM incoming_invoices "
					"WHERE id IN %s" %
					(str(tuple(path_list)),))
		for row in c.fetchall():
			self.get_object('invoice_count').set_label(row[0])
			self.get_object('start_date_label').set_label(row[1])
			self.get_object('end_date_label').set_label(row[2])
			self.get_object('service_providers_label').set_label(row[3])
			self.get_object('min_amount_label').set_label(row[4])
			self.get_object('max_amount_label').set_label(row[5])
			self.get_object('total_amount_label').set_label(row[6])
			self.get_object('avg_amount_label').set_label(row[7])
			self.get_object('days_label').set_label(row[8][:-5]) #strip 'days' text
		DB.rollback()
		c.close()

	########## admin section

	def date_edited (self, cellrenderertext, path, text):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return
		selection = self.get_object('incoming_invoices_tree_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		c = DB.cursor()
		try:
			c.execute("WITH update_ii AS (UPDATE incoming_invoices "
						"SET date_created = %s WHERE id = %s "
						"RETURNING gl_transaction_id), "
						"update_ge AS (UPDATE gl_entries SET date_inserted = %s "
						"WHERE gl_transaction_id = "
							"(SELECT gl_transaction_id FROM update_ii)) "
						"UPDATE gl_transactions SET date_inserted = %s "
						"WHERE id = "
							"(SELECT gl_transaction_id FROM update_ii)",
						(text, row_id, text, text))
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_error_dialog(str(e))
			return
		DB.commit()
		self.populate_incoming_invoice_store()

	def reconciled_toggled (self, cellrenderertoggle, path):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return
		model = self.get_object('incoming_invoices_store')
		row_id = model[path][0]
		reconciled = model[path][8]
		if reconciled == True:
			c = DB.cursor()
			c.execute("WITH cte AS (SELECT gl_entry_id AS id "
							"FROM incoming_invoices WHERE id = %s) "
						"UPDATE gl_entries SET (reconciled, date_reconciled) = "
						"(False, NULL) WHERE id = (SELECT id FROM cte)", (row_id,))
			DB.commit()
			model[path][8] = False
			self.populate_incoming_invoice_store()

	def populate_payment_accounts (self):
		model = self.get_object('pay_with_account_store')
		model.clear()
		c = DB.cursor()
		c.execute("SELECT number::text, name FROM gl_accounts "
					"WHERE cash_account = True "
					"OR credit_card_account = True "
					"OR check_writing = True ORDER BY name ")
		for row in c.fetchall():
			model.append(row)
		DB.rollback()

	def edit_mode_checkbutton_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			self.get_object('edit_incoming_invoice_menuitem').set_visible(False)
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)
		self.get_object('edit_incoming_invoice_menuitem').set_visible(True)

	def edit_incoming_invoice_activated (self, menuitem):
		selection = self.get_object('incoming_invoices_tree_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][0]
		from incoming_invoice_edit import EditIncomingInvoiceGUI
		EditIncomingInvoiceGUI(invoice_id)

	def incoming_invoice_description_edited (self, cellrenderer, path, text):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return
		store = self.get_object('incoming_invoices_sort')
		if text == store[path][4]:
			return
		incoming_invoice_id = store[path][0]
		c = DB.cursor()
		c.execute("UPDATE incoming_invoices "
					"SET description = %s WHERE id = %s",
					(text, incoming_invoice_id))
		DB.commit()
		self.populate_incoming_invoice_store()

	def incoming_item_description_edited (self, cellrenderer, path, text):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return
		store = self.get_object('invoice_items_store')
		if text == store[path][5]:
			return
		incoming_invoice_link_id = store[path][4]
		c = DB.cursor()
		c.execute("UPDATE incoming_invoices_gl_entry_expenses_ids "
					"SET remark = %s WHERE id = %s",
					(text, incoming_invoice_link_id))
		DB.commit()
		store[path][5] = text

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (error)
		dialog.run()
		dialog.destroy()



