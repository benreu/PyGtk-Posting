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
import constants

UI_FILE = constants.ui_directory + "/reports/shipping_history.ui"

class ShippingHistoryGUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.db = constants.db
		
		shipping_store = self.get_object('shipping_store')
		shipping_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
						"si.id, "
						"si.tracking_number, "
						"i.id, "
						"c.name, "
						"COALESCE(amount, 0.00), "
						"COALESCE(amount::text, 'N/A') "
					"FROM shipping_info AS si "
					"JOIN invoices AS i ON i.id = si.invoice_id "
					"JOIN contacts AS c ON c.id = i.customer_id "
					"LEFT JOIN gl_entries AS ge ON ge.id = si.gl_entry_id "
					"ORDER BY dated_for")
		for row in c.fetchall():
			shipping_store.append(row)
		c.close()
		self.window = self.get_object('window')
		self.window.show_all()
		



