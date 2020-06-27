# po_payment_matching.py
#
# Copyright (C) 2020 - Reuben
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/po_payment_matching.ui"

class PoPaymentMatchingGUI(Gtk.Builder):
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.populate_vendor_store()
		self.vendor_id = None

		self.window = self.get_object('window')
		self.window.show_all()

	def populate_vendor_store (self):
		cursor = DB.cursor()
		vendor_store = self.get_object('vendor_store')
		cursor.execute("SELECT c.id::text, c.name, c.ext_name "
						"FROM purchase_orders AS p "
						"JOIN contacts AS c ON c.id = p.vendor_id "
						"GROUP BY c.id, c.name "
						"ORDER BY c.name")
		for row in cursor.fetchall():
			vendor_store.append(row)
		cursor.close()

	def vendor_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.vendor_store[iter][1].lower():
				return False
		return True

	def vendor_view_all_toggled (self, togglebutton):
		self.load_purchase_order_payments ()
		
	def vendor_changed(self, combo):
		vendor_id = combo.get_active_id ()
		if vendor_id == None:
			return
		self.vendor_id = vendor_id
		self.get_object('view_all_checkbutton').set_active(False)
		self.load_purchase_order_payments ()

	def vendor_match_selected (self, completion, model, iter):
		self.vendor_id = model[iter][0]
		self.get_object('view_all_checkbutton').set_active(False)
		self.load_purchase_order_payments ()

	def load_purchase_order_payments (self):
		c = DB.cursor()
		store = self.get_object('po_payment_store')
		store.clear()
		if self.get_object('view_all_checkbutton').get_active():
			c.execute("SELECT "
						"p.id, "
						"p.name, "
						"date_created::text, "
						"format_date(date_created), "
						"c.id, "
						"c.name, "
						"date_paid::text, "
						"format_date(date_paid), "
						"COALESCE(ga.name::text, ''), "
						"COALESCE(ge.check_number::text, "
							"ge.transaction_description, '') "
						"FROM purchase_orders AS p "
						"JOIN contacts AS c ON c.id = p.vendor_id "
						"LEFT JOIN gl_transactions AS gt "
							"ON gt.id = p.gl_transaction_payment_id "
						"LEFT JOIN gl_entries AS ge "
							"ON ge.gl_transaction_id = gt.id "
							"AND credit_account IS NOT NULL "
						"LEFT JOIN gl_accounts AS ga "
							"ON ga.number = ge.credit_account "
						"ORDER BY p.id")
		else:
			c.execute("SELECT "
						"p.id, "
						"p.name, "
						"date_created::text, "
						"format_date(date_created), "
						"c.id, "
						"c.name, "
						"date_paid::text, "
						"format_date(date_paid), "
						"COALESCE(ga.name::text, ''), "
						"COALESCE(ge.check_number::text, "
							"ge.transaction_description, '') "
						"FROM purchase_orders AS p "
						"JOIN contacts AS c ON c.id = p.vendor_id "
						"LEFT JOIN gl_transactions AS gt "
							"ON gt.id = p.gl_transaction_payment_id "
						"LEFT JOIN gl_entries AS ge "
							"ON ge.gl_transaction_id = gt.id "
							"AND credit_account IS NOT NULL "
						"LEFT JOIN gl_accounts AS ga "
							"ON ga.number = ge.credit_account "
							"WHERE p.vendor_id = %s "
						"ORDER BY p.id", (self.vendor_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()
		DB.rollback()


