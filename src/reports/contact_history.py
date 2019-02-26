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
import main

UI_FILE = main.ui_directory + "/reports/contact_history.ui"

class ContactHistoryGUI (Gtk.Builder):
	def __init__(self, main):

		self.search_iter = 0
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		contact_completion = self.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.invoice_history = None

		self.contact_store = self.get_object('contact_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			id_ = row[0]
			name = row[1]
			ext_name = row[2]
			self.contact_store.append([id_ , name, ext_name])

		amount_column = self.get_object ('treeviewcolumn22')
		amount_renderer = self.get_object ('cellrenderertext25')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func, 3)

		amount_column = self.get_object ('treeviewcolumn15')
		amount_renderer = self.get_object ('cellrenderertext18')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func, 4)

		amount_column = self.get_object ('treeviewcolumn10')
		amount_renderer = self.get_object ('cellrenderertext11')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func, 3)

		amount_column = self.get_object ('treeviewcolumn5')
		amount_renderer = self.get_object ('cellrenderertext5')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func, 5)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def close_transaction_window (self, window, event):
		self.cursor.close()

	def amount_cell_func(self, view_column, cellrenderer, model, iter1, column):
		price = '{:,.2f}'.format(model.get_value(iter1, column))
		cellrenderer.set_property("text" , price)
		
	def invoice_row_activated (self, treeview, treepath, treeviewcolumn):
		model = treeview.get_model()
		file_id = model[treepath][0]
		self.cursor.execute("SELECT name, pdf_data FROM invoices WHERE id = %s", 
																	(file_id ,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/" + row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.call(["xdg-open", file_name])
			f.close()

	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('invoice_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def invoice_history_activated (self, menuitem):
		selection = self.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][0]
		if not self.invoice_history or self.invoice_history.exists == False:
			from reports import invoice_history as ih
			self.invoice_history = ih.InvoiceHistoryGUI(self.main)
		combo = self.invoice_history.builder.get_object('combobox1')
		combo.set_active_id(self.contact_id)
		store = self.invoice_history.builder.get_object('invoice_store')
		selection = self.invoice_history.builder.get_object('treeview-selection1')
		selection.unselect_all()
		for row in store:
			if row[0] == invoice_id:
				selection.select_iter(row.iter)
				break
		self.invoice_history.present()

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

	def report_hub_clicked (self, button):
		tab_num = self.get_object('notebook1').get_current_page()
		scrolled_window = self.get_object('notebook1').get_nth_page(tab_num)
		treeview = scrolled_window.get_child()
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def product_selection_changed (self, selection):
		rows = len(selection.get_selected_rows()[1])
		if rows > 1:
			menu = self.get_object('product_menu')
			menu.show_all()
			menu.popup_at_pointer()

	def hide_rows_activated (self, menuitem):
		"we need to convert paths to iters, because paths are wrong after "
		"deleting a row in the model "
		model, paths = self.get_object('product_selection').get_selected_rows()
		iter_list = list()
		if paths != []:
			for path in paths:
				iter_list.append(model.get_iter(path))
			for iter_ in iter_list:
				model.remove(iter_)

	def populate_contact_stores (self):
		self.populate_contact_invoices()
		self.populate_contact_payments()
		self.populate_product_store ()
		self.populate_resources ()
		self.populate_contact_statements ()
		self.populate_warranty_store ()
		self.populate_incoming_invoice_store ()

	def populate_incoming_invoice_store (self):
		incoming_invoice_store = self.get_object('incoming_invoice_store')
		incoming_invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_created::text, "
								"format_date(date_created), "
								"amount, description "
								"FROM incoming_invoices "
								"WHERE contact_id = %s "
								"ORDER BY date_created;", (self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			incoming_invoice_store.append(row)
		if count == 0:
			self.get_object('label9').set_label('Incoming invoices')
		else:
			label = "<span weight='bold'>Incoming invoices (%s)</span>" % count
			self.get_object('label9').set_markup(label)

	def populate_warranty_store (self):
		warranty_store = self.get_object('warranty_store')
		warranty_store.clear()
		count = 0
		self.cursor.execute("SELECT snh.id, p.name, sn.serial_number, "
							"snh.date_inserted::text, "
							"format_date(snh.date_inserted), "
							"snh.description "
							"FROM serial_number_history AS snh "
							"JOIN serial_numbers AS sn "
							"ON sn.id = snh.serial_number_id "
							"JOIN products AS p ON p.id = sn.product_id "
							"WHERE contact_id = %s ORDER by date_inserted", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			warranty_store.append(row)
		if count == 0:
			self.get_object('label8').set_label('Warranty')
		else:
			label = "<span weight='bold'>Warranty (%s)</span>" % count
			self.get_object('label8').set_markup(label)

	def populate_product_store (self):
		product_store = self.get_object('product_store')
		product_store.clear()
		count = 0
		c_id = self.contact_id
		c = self.db.cursor()
		c.execute("SELECT * FROM "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Invoice' "
					"FROM products AS p "
					"JOIN invoice_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON i.id = ili.invoice_id "
					"WHERE customer_id = %s "
					"GROUP BY p.id, p.name, remark) inv "
				"UNION "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Purchase order' "
					"FROM products AS p "
					"JOIN purchase_order_line_items AS poli ON poli.product_id = p.id "
					"JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
					"WHERE vendor_id = %s "
					"GROUP BY p.id, p.name, remark) "
				"UNION "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Documents' "
					"FROM products AS p "
					"JOIN document_lines AS dl ON dl.product_id = p.id "
					"JOIN documents AS d ON d.id = dl.document_id "
					"WHERE contact_id = %s "
					"GROUP BY p.id, p.name, remark) "
				"UNION "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Job Sheet' "
					"FROM products AS p "
					"JOIN job_sheet_line_items AS jsli ON jsli.product_id = p.id "
					"JOIN job_sheets AS js ON js.id = jsli.job_sheet_id "
					"WHERE contact_id = %s "
					"GROUP BY p.id, p.name, remark) "
					"ORDER BY name", 
					(c_id, c_id, c_id, c_id))
		for row in c.fetchall():
			count += 1
			product_store.append(row)
		if count == 0:
			self.get_object('label10').set_label('Products')
		else:
			label = "<span weight='bold'>Products (%s)</span>" % count
			self.get_object('label10').set_markup(label)
		c.close()

	def populate_contact_statements (self):
		statement_store = self.get_object('statements_store')
		statement_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_inserted::text, "
								"format_date(date_inserted), "
								"name, amount::float, print_date::text, "
								"format_date(print_date) "
								"FROM statements AS s "
								"WHERE customer_id = %s "
								"ORDER BY date_inserted, id", 
								(self.contact_id, ))
		for row in self.cursor.fetchall():
			count += 1
			statement_store.append(row)
		if count == 0:
			self.get_object('label7').set_label('Statements')
		else:
			label = "<span weight='bold'>Statements (%s)</span>" % count
			self.get_object('label7').set_markup(label)

	def populate_resources (self):
		resource_store = self.get_object('resource_store')
		resource_store.clear()
		count = 0
		self.cursor.execute("SELECT r.id, subject, dated_for::text, "
							"format_date(dated_for), notes, "
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
			date_formatted = row[3]
			notes = row[4]
			tag_name = row[5]
			rgba.red = row[6]
			rgba.green = row[7]
			rgba.blue = row[8]
			rgba.alpha = row[9]
			resource_store.append([row_id, subject, dated_for, 
									date_formatted, notes, tag_name, rgba])
		if count == 0:
			self.get_object('label4').set_label('Resources')
		else:
			label = "<span weight='bold'>Resources (%s)</span>" % count
			self.get_object('label4').set_markup(label)

	def populate_contact_payments (self):
		payment_store = self.get_object('payments_store')
		payment_store.clear()
		count = 0
		self.cursor.execute("SELECT id, date_inserted::text, "
								"format_date(date_inserted), "
								"amount, payment_info(id) "
								"FROM payments_incoming "
								"WHERE customer_id = %s "
								"ORDER BY date_inserted;", (self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			payment_store.append(row)
		if count == 0:
			self.get_object('label3').set_label('Payments received')
		else:
			label = "<span weight='bold'>Payments received (%s)</span>" % count
			self.get_object('label3').set_markup(label)

	def populate_contact_invoices (self):
		invoice_store = self.get_object('invoice_store')
		invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT i.id, dated_for::text, "
							"format_date(dated_for), i.name,  "
							"'Comments: ' || comments, "
							"COALESCE(total, 0.00), date_printed::text, "
							"format_date(date_printed) "
							"FROM invoices AS i "
							"WHERE (customer_id, canceled) = "
							"(%s, False) ORDER BY dated_for", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			count += 1
			invoice_store.append(row)
		if count == 0:
			self.get_object('label2').set_label('Invoices')
		else:
			label = "<span weight='bold'>Invoices (%s)</span>" % count
			self.get_object('label2').set_markup(label)





			
