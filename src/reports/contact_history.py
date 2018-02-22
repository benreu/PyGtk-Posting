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

UI_FILE = "src/reports/contact_history.ui"

class ContactHistoryGUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		contact_completion = self.builder.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.contact_store = self.builder.get_object('contact_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			id_ = row[0]
			name = row[1]
			ext_name = row[2]
			self.contact_store.append([id_ , name, ext_name])

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

	def contact_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False# no match
		return True# it's a hit!
		
	def contact_changed(self, combo):
		contact_id = combo.get_active_id ()
		if contact_id == None:
			return
		self.contact_id = contact_id
		self.populate_contact_stores ()

	def contact_match_selected (self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.populate_contact_stores ()

	def populate_contact_stores (self):
		self.populate_contact_invoices()
		self.populate_contact_payments()
		self.populate_resources ()
		self.populate_contact_statements ()
		self.populate_warranty_store ()
		self.populate_incoming_invoice_store ()

	def populate_incoming_invoice_store (self):
		incoming_invoice_store = self.builder.get_object('incoming_invoice_store')
		incoming_invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_created, "
								"amount, description "
								"FROM incoming_invoices "
								"WHERE contact_id = %s "
								"ORDER BY date_created;", (self.contact_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			date = row[1]
			formatted_date = dateutils.datetime_to_text(date)
			amount = row[2]
			description = row[3]
			count += 1
			incoming_invoice_store.append([row_id, str(date), formatted_date,
									amount, description])
		if count == 0:
			self.builder.get_object('label9').set_label('Incoming invoices')
		else:
			label = "<span weight='bold'>Incoming invoices (%s)</span>" % count
			self.builder.get_object('label9').set_markup(label)

	def populate_warranty_store (self):
		warranty_store = self.builder.get_object('warranty_store')
		warranty_store.clear()
		count = 0
		self.cursor.execute("SELECT snh.id, p.name, sn.serial_number, "
							"snh.date_inserted, snh.description "
							"FROM serial_number_history AS snh "
							"JOIN serial_numbers AS sn "
							"ON sn.id = snh.serial_number_id "
							"JOIN products AS p ON p.id = sn.product_id "
							"WHERE contact_id = %s ORDER by date_inserted", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			row_id = row[0]
			product_name = row[1]
			serial_number = row[2]
			date = row[3]
			description = row[4]
			date_formatted = dateutils.datetime_to_text (date)
			warranty_store.append([row_id, product_name, serial_number, 
									str(date), date_formatted, description])
		if count == 0:
			self.builder.get_object('label8').set_label('Warranty')
		else:
			label = "<span weight='bold'>Warranty (%s)</span>" % count
			self.builder.get_object('label8').set_markup(label)

	def populate_contact_statements (self):
		statement_store = self.builder.get_object('statements_store')
		statement_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_inserted, "
								"name, amount, print_date "
								"FROM statements AS s "
								"WHERE customer_id = %s "
								"ORDER BY date_inserted, id", 
								(self.contact_id, ))
		for row in self.cursor.fetchall():
			count += 1
			row_id = row[0]
			date = row[1]
			statement_name = row[2]
			amount = row[3]
			printed = row[4]
			date_formatted = dateutils.datetime_to_text (date)
			date_print_formatted = dateutils.datetime_to_text(printed)
			statement_store.append([row_id, str(date), date_formatted, 
										statement_name, amount, str(printed), 
										date_print_formatted])
		if count == 0:
			self.builder.get_object('label7').set_label('Statements')
		else:
			label = "<span weight='bold'>Statements (%s)</span>" % count
			self.builder.get_object('label7').set_markup(label)

	def populate_resources (self):
		resource_store = self.builder.get_object('resource_store')
		resource_store.clear()
		count = 0
		self.cursor.execute("SELECT r.id, subject, dated_for, notes, "
							"tag, red, green, blue, alpha "
							"FROM resources AS r "
							"JOIN resource_tags AS rt "
							"ON rt.id = r.tag_id WHERE contact_id = %s", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			rgba = Gdk.RGBA(1, 1, 1, 1)
			row_id = row[0]
			subject = row[1]
			dated_for = row[2]
			notes = row[3]
			tag_name = row[4]
			rgba.red = row[5]
			rgba.green = row[6]
			rgba.blue = row[7]
			rgba.alpha = row[8]
			date_formatted = dateutils.datetime_to_text(dated_for)
			resource_store.append([row_id, subject, str(dated_for), 
									date_formatted, notes, tag_name, rgba])
		if count == 0:
			self.builder.get_object('label4').set_label('Resources')
		else:
			label = "<span weight='bold'>Resources (%s)</span>" % count
			self.builder.get_object('label4').set_markup(label)

	def populate_contact_payments (self):
		payment_store = self.builder.get_object('payments_store')
		payment_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_inserted, "
								"amount, payment_info(id) "
								"FROM payments_incoming "
								"WHERE customer_id = %s "
								"ORDER BY date_inserted;", (self.contact_id,))
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
			self.builder.get_object('label3').set_label('Payments received')
		else:
			label = "<span weight='bold'>Payments received (%s)</span>" % count
			self.builder.get_object('label3').set_markup(label)

	def populate_contact_invoices (self):
		invoice_store = self.builder.get_object('invoice_store')
		invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT i.id, dated_for, i.name,  "
							"comments, COALESCE(total, 0.00), date_printed "
							"FROM invoices AS i "
							"WHERE (customer_id, canceled) = "
							"(%s, False) ORDER BY dated_for", 
							(self.contact_id,))
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





			