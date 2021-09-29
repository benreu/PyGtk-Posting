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


from gi.repository import Gtk
import subprocess
from constants import ui_directory, DB, broadcaster
from accounts import expense_account
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
		self.get_object('expense_account_combobox').set_model(expense_account)
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

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def search_description_entry_changed (self, searchentry):
		self.search_desc_text = searchentry.get_text().lower()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.search_desc_text.split():
			if text not in model[tree_iter][4].lower():
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
				"JOIN incoming_invoices_gl_entry_expenses_ids AS iigl " \
				"ON iigl.incoming_invoices_id = i.id " \
				"JOIN LATERAL (SELECT id FROM gl_entries AS ge " \
				"WHERE ge.debit_account = %s AND " \
				"iigl.gl_entry_expense_id = geda.id LIMIT 1) geda " \
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
		self.incoming_invoice_store.clear()
		self.invoice_items_store.clear()
		print(self.expense_account_join)
		c = DB.cursor()
		c.execute("SELECT "
					"i.id, "
					"c.name, "
					"i.date_created::text, "
					"format_date(i.date_created), "
					"i.description, "
					"i.amount, "
					"i.amount::text "
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

	def incoming_invoice_selection_changed (self, treeselection):
		model, path = treeselection.get_selected_rows()
		if path == []:
			return
		self.invoice_items_store.clear()
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

	########## admin section

	def edit_mode_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)

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




