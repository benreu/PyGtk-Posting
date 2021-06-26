# invoice_product_statistics.py
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


from gi.repository import Gtk
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/reports/product_invoice_statistics.ui"

class ProductInvoiceStatisticsGUI(Gtk.Builder):
	def __init__(self, product_id = None):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.invoice_list = list()
		self.product_id = product_id

	def show_all(self):
		invoice_list = str(tuple(self.invoice_list))
		c = DB.cursor()
		c.execute("SELECT "
					"COUNT(dated_for)::text, "
					"format_date(MIN(dated_for)), format_date(MAX(dated_for)), "
					"AGE(MAX(dated_for), MIN(dated_for))::text, "
					"MAX(total)::text, MIN(total)::text, "
					"ROUND(AVG(total), 2)::text, SUM(total)::text "
					"FROM invoices WHERE id IN %s" % (invoice_list,))
		for row in c.fetchall():
			invoice_str = "<b>Invoices</b> (%s)" % row[0]
			self.get_object('invoices_label').set_markup(invoice_str)
			self.get_object('min_date').set_label(row[1])
			self.get_object('max_date').set_label(row[2])
			self.get_object('date_range').set_label(row[3])
			self.get_object('min_amount').set_label(row[4])
			self.get_object('max_amount').set_label(row[5])
			self.get_object('avg_amount').set_label(row[6])
			self.get_object('sum_amount').set_label(row[7])
		c.execute("SELECT "
					"COUNT(ii.id), "
					"MIN(ii.qty)::text, "
					"MAX(ii.qty)::text, "
					"ROUND(AVG(ii.qty), 2)::text, "
					"SUM(ii.qty)::text, "
					"MIN(ii.price)::text, "
					"MAX(ii.price)::text, "
					"ROUND(AVG(ii.price), 2)::text, "
					"SUM(ii.price)::text, "
					"MIN(ii.ext_price)::text, "
					"MAX(ii.ext_price)::text, "
					"ROUND(AVG(ii.ext_price), 2)::text, "
					"SUM(ii.ext_price)::text, "
					"p.name "
					"FROM invoice_items AS ii "
					"JOIN products AS p ON p.id = ii.product_id "
					"WHERE invoice_id IN %s AND product_id = %s "
					"GROUP BY p.name" 
										% (invoice_list, self.product_id))
		for row in c.fetchall():
			invoice_str = "<b>Invoice items</b> (%s)" % row[0]
			self.get_object('invoice_items_label').set_markup(invoice_str)
			self.get_object('min_qty').set_label(row[1])
			self.get_object('max_qty').set_label(row[2])
			self.get_object('avg_qty').set_label(row[3])
			self.get_object('sum_qty').set_label(row[4])
			self.get_object('min_price').set_label(row[5])
			self.get_object('max_price').set_label(row[6])
			self.get_object('avg_price').set_label(row[7])
			self.get_object('sum_price').set_label(row[8])
			self.get_object('min_ext_price').set_label(row[9])
			self.get_object('max_ext_price').set_label(row[10])
			self.get_object('avg_ext_price').set_label(row[11])
			self.get_object('sum_ext_price').set_label(row[12])
			window_title = "'%s' invoice statistics" % row[13]
		window = self.get_object('window')
		window.set_title(window_title)
		window.show_all()

	def append_invoice(self, invoice_id):
		self.invoice_list.append(invoice_id)

	def set_product_id (self, product_id):
		self.product_id = product_id



