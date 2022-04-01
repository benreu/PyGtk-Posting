# gl_entry_lookup.py
#
# Copyright (C) 2018 - Reuben
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

UI_FILE = ui_directory + "/reports/gl_entry_lookup.ui"

class GlEntryLookupGUI :
	def __init__ (self, entry_ids):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		store = self.builder.get_object('lookup_store')
		c = DB.cursor()
		c.execute(	"SELECT "
						"'Purchase Order', "
						"po.id, "
						"p.name, "
						"poli.price::text, "
						"v.name, "
						"po.date_created::text, "
						"format_date(po.date_created) "
					"FROM purchase_orders AS po "
					"JOIN contacts AS v ON v.id = po.vendor_id "
					"JOIN purchase_order_items AS poli "
						"ON poli.purchase_order_id = po.id "
					"JOIN gl_entries AS ge ON poli.gl_entries_id = ge.id "
					"JOIN products AS p ON p.id = poli.product_id "
					"WHERE ge.id IN %s "
					
					"UNION "
					"SELECT "
						"'Invoice', "
						"i.id, "
						"p.name, "
						"ii.price::text, "
						"c.name, "
						"i.date_created::text, "
						"format_date(i.date_created) "
					"FROM invoices AS i "
					"JOIN contacts AS c ON c.id = i.customer_id "
					"JOIN invoice_items AS ii "
						"ON ii.invoice_id = i.id "
					"JOIN gl_entries AS ge ON ii.gl_entries_id = ge.id "
					"JOIN products AS p ON p.id = ii.product_id "
					"WHERE ge.id IN %s "
					
					"UNION "
					"SELECT "
						"'Payment', "
						"p.id, "
						"payment_info(p.id), "
						"p.amount::text, "
						"c.name, "
						"p.date_inserted::text, "
						"format_date(p.date_inserted) "
					"FROM payments_incoming AS p "
					"JOIN contacts AS c ON c.id = p.customer_id "
					"JOIN gl_entries AS ge ON p.gl_entries_id = ge.id "
					"WHERE ge.id IN %s " % 
					(entry_ids, entry_ids, entry_ids) )
		for row in c.fetchall():
			store.append(row)
		c.close()
		DB.rollback()
		self.builder.get_object('window').show_all()


