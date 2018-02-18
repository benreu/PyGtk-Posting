# customer_history.py
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


from gi.repository import Gtk, GObject, Gdk, GLib
from decimal import Decimal
import subprocess
import dateutils

UI_FILE = "src/reports/customer_history.ui"

class CustomerHistoryGUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.customer_store = self.builder.get_object('customer_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE (customer, deleted) = "
							"(True, False) ORDER BY name")
		for customer in self.cursor.fetchall():
			id_ = customer[0]
			name = customer[1]
			ext_name = customer[2]
			self.customer_store.append([id_ , name, ext_name])

		amount_column = self.builder.get_object ('treeviewcolumn5')
		amount_renderer = self.builder.get_object ('cellrenderertext5')
		#amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def close_transaction_window (self, window):
		self.cursor.close()

	def amount_cell_func(self, column, cellrenderer, model, iter1, data):
		price = '{:,.2f}'.format(model.get_value(iter1, 6))
		cellrenderer.set_property("text" , price)
		
	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('invoice_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!
		
	def customer_changed(self, combo):
		customer_id = combo.get_active_id ()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.populate_customer_stores ()

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.populate_customer_stores ()

	def populate_customer_stores (self):
		self.populate_customer_invoices()
		self.populate_customer_payments()

	def populate_customer_payments (self):
		payment_store = self.builder.get_object('payments_store')
		payment_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_inserted, "
								"amount, payment_info(id) "
								"FROM payments_incoming "
								"WHERE customer_id = %s "
								"ORDER BY date_inserted;", (self.customer_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			date = row[1]
			formatted_date = dateutils.datetime_to_text(date)
			amount = row[2]
			payment_text = row[3]
			count += 1
			payment_store.append([row_id, str(date), formatted_date,
									amount, payment_text])
		if count == 0:
			self.builder.get_object('label3').set_label('Payments')
		else:
			label = "<span weight='bold'>Payments (%s)</span>" % count
			self.builder.get_object('label3').set_markup(label)

	def populate_customer_invoices (self):
		invoice_store = self.builder.get_object('invoice_store')
		invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT i.id, dated_for, i.name,  "
							"comments, COALESCE(total, 0.00), date_printed "
							"FROM invoices AS i "
							"WHERE (customer_id, canceled) = "
							"(%s, False) ORDER BY dated_for", 
							(self.customer_id,))
		for row in self.cursor.fetchall():
			count += 1
			id_ = row[0]
			date = row[1]
			date_formatted = dateutils.datetime_to_text(date)
			i_name = row[2]
			remark = "Comments: " + row[3]
			amount = row[4]
			date_printed = row[5]
			date_print_formatted = dateutils.datetime_to_text(date_printed)
			invoice_store.append([id_, str(date), date_formatted, i_name, 
									remark, amount, str(date_printed), 
									date_print_formatted])
		if count == 0:
			self.builder.get_object('label2').set_label('Invoices')
		else:
			label = "<span weight='bold'>Invoices (%s)</span>" % count
			self.builder.get_object('label2').set_markup(label)





			