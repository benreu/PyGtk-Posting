# loan_payments.py
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
from constants import ui_directory, DB, broadcaster
import admin_utils

UI_FILE = ui_directory + "/reports/loan_payments.ui"

class LoanPaymentsGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.loan_payment_store = self.get_object('loan_payments_store')
		self.loan_store = self.get_object('loan_store')
		self.populate_loans ()
		self.handler_ids = list()
		for connection in (("admin_changed", self.admin_changed), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		column = self.get_object ('treeviewcolumn2')
		renderer = self.get_object ('cellrenderertext2')
		column.set_cell_data_func(renderer, self.cell_func, 2)

		column = self.get_object ('treeviewcolumn3')
		renderer = self.get_object ('principal_cellrenderer')
		column.set_cell_data_func(renderer, self.cell_func, 3)

		column = self.get_object ('treeviewcolumn4')
		renderer = self.get_object ('cellrenderertext4')
		column.set_cell_data_func(renderer, self.cell_func, 4)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def cell_func (self, column, cellrenderer, model, iter1, index):
		amount = "{:,.2f}".format(model[iter1][index])
		cellrenderer.set_property("text", amount)

	def populate_loans (self):
		self.cursor.execute("SELECT l.id::text, l.description "
							"FROM loans AS l "
							"ORDER BY description")
		for row in self.cursor.fetchall():
			self.loan_store.append(row)
		DB.rollback()

	def loan_combo_changed (self, combo):
		loan_id = combo.get_active_id ()
		if loan_id != None :
			self.loan_id = loan_id
			self.populate_loan_payments()
			self.populate_loan_totals()
			DB.rollback()


	def populate_loan_payments (self):
		selection = self.get_object('loan_payment_selection')
		model, iter_ = selection.get_selected()
		path = None
		if iter_ != None:
			path = model.get_path(iter_)
		self.loan_payment_store.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"lp.id, "
						"c.name, "
						"total.amount::float, "
						"principal.amount::float, "
						"interest.amount::float, "
						"total.date_inserted::text, "
						"format_date(total.date_inserted), "
						"ga.name, "
						"total.reconciled "
					"FROM loan_payments AS lp "
					"JOIN gl_entries AS total "
						"ON total.id = lp.gl_entries_total_id "
					"JOIN gl_entries AS principal "
						"ON principal.id = lp.gl_entries_principal_id "
					"JOIN gl_entries AS interest "
						"ON interest.id = lp.gl_entries_interest_id "
					"JOIN contacts AS c ON c.id = lp.contact_id "
					"JOIN gl_accounts AS ga "
						"ON ga.number = total.credit_account "
					"WHERE lp.loan_id = %s ORDER BY principal.date_inserted", 
					(self.loan_id,))
		for row in c.fetchall():
			self.loan_payment_store.append(row)
		if path != None:
			selection.select_path(path)
			treeview = self.get_object('treeview1')
			treeview.scroll_to_cell(path, None, True, 0.5, 0.5)

	def populate_loan_totals (self):
		c = DB.cursor()
		c.execute("SELECT "
						"format_date(l.date_received), "
						"l.period_amount::text ||' '||l.period||'(s)', "
						"c.name, "
						"liability.name, "
						"l.finished, "
						"l.amount::money, "
						"COALESCE(SUM(principal.amount), 0.00)::money, "
						"COALESCE(l.amount - SUM(principal.amount), 0.00)::money, "
						"COALESCE(SUM(interest.amount), 0.00)::money "
					"FROM loans AS l "
					"LEFT JOIN loan_payments AS lp ON l.id = lp.loan_id "
					"LEFT JOIN gl_entries AS principal "
						"ON principal.id = lp.gl_entries_principal_id "
					"LEFT JOIN gl_entries AS interest "
						"ON interest.id = lp.gl_entries_interest_id "
					"JOIN gl_accounts AS liability "
						"ON liability.number = l.liability_account "
					"JOIN contacts AS c ON c.id = l.contact_id "
					"WHERE l.id = %s "
					"GROUP BY l.amount, l.date_received, l.period_amount, "
					"l.period, l.finished, liability.name, c.name", 
					(self.loan_id,))
		for row in c.fetchall():
			self.get_object('date_started_entry').set_text(row[0])
			self.get_object('payment_period_entry').set_text(row[1])
			self.get_object('contact_name_entry').set_text(row[2])
			self.get_object('liability_account_entry').set_text(row[3])
			self.get_object('finished_checkbutton').set_active(row[4])
			self.get_object('loan_total_entry').set_text(row[5])
			self.get_object('principal_paid_entry').set_text(row[6])
			self.get_object('principal_unpaid_entry').set_text(row[7])
			self.get_object('interest_paid_entry').set_text(row[8])

### admin section

	def edit_mode_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			self.get_object('treeview_menu').set_visible(False)
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)
		self.get_object('treeview_menu').set_visible(True)

	def admin_changed (self, broadcast_object, value):
		self.get_object('edit_mode_checkbutton').set_active(False)

	def treeview_button_release_event (self, treeview, event):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return
		if event.button == 3:
			menu = self.get_object('treeview_menu')
			menu.popup_at_pointer()

	def edit_amount_activated (self, menuitem):
		model, iter_ = self.get_object('loan_payment_selection').get_selected()
		if iter_ == None:
			return
		renderer = self.get_object('principal_cellrenderer')
		renderer.set_property('editable', True)
		path = model.get_path(iter_)
		treeview = self.get_object('treeview1')
		column = treeview.get_column(2)
		treeview.set_cursor(path, column, True)

	def principal_editing_canceled (self, cellrenderer):
		self.get_object('principal_cellrenderer').set_property('editable', False)

	def principal_editing_started (self, cellrenderer, spinbutton, path):
		spinbutton.set_numeric(True)
		spinbutton.connect('destroy', self.principal_editing_canceled)

	def principal_edited (self, cellrenderertext, path, text):
		model, iter_ = self.get_object('loan_payment_selection').get_selected()
		if iter_ == None:
			return
		renderer = self.get_object('principal_cellrenderer')
		renderer.set_property('editable', False)
		row_id = model[iter_][0]
		total = model[iter_][2]
		c = DB.cursor()
		c.execute("UPDATE gl_entries SET amount = %s WHERE id = "
					"(SELECT gl_entries_principal_id "
						"FROM loan_payments WHERE id = %s); "
					"UPDATE gl_entries SET amount = "
						"(SELECT "
							"(SELECT amount FROM gl_entries WHERE id = "
								"(SELECT gl_entries_total_id "
								"FROM loan_payments WHERE id = %s)) "
						"- %s::numeric(12, 2) ) "
					"WHERE id = "
						"(SELECT gl_entries_interest_id "
						"FROM loan_payments WHERE id = %s) ", 
					(text, row_id, row_id, text, row_id))
		DB.commit()
		self.populate_loan_payments()


