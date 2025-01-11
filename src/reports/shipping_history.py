# shipping_info.py
#
# Copyright (C) 2019 - reuben
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

UI_FILE = ui_directory + "/reports/shipping_history.ui"

class ShippingHistoryGUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		
		self.filter = self.get_object ('shipping_store_filter')
		self.filter.set_visible_func(self.filter_func)

		self.tracking_number = ''
		self.invoice_id = ''
		self.contact = ''
		self.populate_shipping_store()
		
		self.handler_ids = list()
		for connection in (("admin_changed", self.admin_changed), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		
		self.window = self.get_object('window')
		self.window.show_all()

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def admin_changed (self, broadcast_object, value):
		self.get_object('edit_mode_checkbutton').set_active(False)

	def edit_mode_checkbutton_toggled (self, checkmenuitem):
		if checkmenuitem.get_active() == False:
			return # Warning, only check for admin when toggling to True
		if not admin_utils.check_admin(self.window):
			checkmenuitem.set_active(False)
			return True
		'''some wierdness going on with showing a dialog without letting the
		checkmenuitem update its state'''
		checkmenuitem.set_active(True)

	def populate_shipping_store(self):
		shipping_store = self.get_object('shipping_store')
		shipping_store.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"si.id, "
						"si.tracking_number, "
						"COALESCE(i.id, 0), "
						"reason, "
						"c.name, "
						"COALESCE(ii.amount, 0.00), "
						"COALESCE(ii.amount::text, 'N/A'), "
						"date_shipped::text, "
						"format_date(date_shipped), "
						"ii.id "
					"FROM shipping_info AS si "
					"JOIN contacts AS c ON c.id = si.contact_id "
					"LEFT JOIN invoices AS i ON i.id = si.invoice_id "
					"LEFT JOIN incoming_invoices AS ii "
						"ON ii.id = si.incoming_invoice_id "
					"ORDER BY date_shipped")
		for row in c.fetchall():
			shipping_store.append(row)
		c.close()
		DB.rollback()

	def refresh_clicked (self, menuitem):
		self.populate_shipping_store()
		
	def treeview_button_release_event (self, widget, event):
		if self.get_object('edit_mode_checkbutton').get_active() == False:
			return False
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def edit_incoming_invoice_clicked (self, menuitem):
		selection = self.get_object('tree_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][9]
		from incoming_invoice_edit import EditIncomingInvoiceGUI
		EditIncomingInvoiceGUI(invoice_id)

	def search_changed (self, search_entry):
		self.tracking_number = self.get_object('tracking_entry').get_text()
		self.invoice_id = self.get_object('invoice_entry').get_text()
		self.contact = self.get_object('contact_entry').get_text()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.tracking_number.split():
			if text not in model[tree_iter][1]:
				return False
		for text in self.invoice_id.split():
			if text not in str(model[tree_iter][2]):
				return False
		for text in self.contact.split():
			if text not in model[tree_iter][4]:
				return False
		return True

