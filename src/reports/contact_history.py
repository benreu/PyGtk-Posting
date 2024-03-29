# contact_history.py
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/contact_history.ui"

class ContactHistoryGUI (Gtk.Builder):
	contact_id = None
	def __init__(self):

		self.search_iter = 0
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		contact_completion = self.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)

		self.invoice_history = None

		self.contact_store = self.get_object('contact_store')
		self.cursor.execute("SELECT "
								"id::text, "
								"name, "
								"ext_name "
							"FROM contacts "
							"WHERE deleted = False "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		self.window = self.get_object('window1')
		self.window.show_all()

	def notebook_create_window (self, notebook, widget, x, y):
		window = Gtk.Window()
		new_notebook = Gtk.Notebook()
		window.add(new_notebook)
		new_notebook.set_group_name('posting')
		new_notebook.connect('page-removed', self.notebook_page_removed, window)
		window.connect('destroy', self.sub_window_destroyed, new_notebook, notebook)
		window.set_transient_for(self.window)
		window.set_destroy_with_parent(True)
		window.set_size_request(400, 400)
		window.set_title('Contact History')
		window.set_icon_name('pygtk-posting')
		window.move(x, y)
		window.show_all()
		return new_notebook

	def notebook_page_removed (self, notebook, child, page, window):
		#destroy the window after the notebook is empty
		if notebook.get_n_pages() == 0:
			window.destroy()

	def sub_window_destroyed (self, window, notebook, dest_notebook):
		# detach the notebook pages in reverse sequence to avoid index errors
		for page_num in reversed(range(notebook.get_n_pages())):
			widget = notebook.get_nth_page(page_num)
			tab_label = notebook.get_tab_label(widget)
			notebook.detach_tab(widget)
			dest_notebook.append_page(widget, tab_label)
			dest_notebook.set_tab_detachable(widget, True)
			dest_notebook.set_tab_reorderable(widget, True)
			dest_notebook.child_set_property(widget, 'tab-expand', True)

	def destroy (self, window):
		self.cursor.close()

	def contact_hub_clicked (self, button):
		if self.contact_id == None:
			return
		import contact_hub
		contact_hub.ContactHubGUI(self.contact_id)

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
		DB.rollback()

	def shipping_treeview_button_release_event (self, treeview, event):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('shipping_menu')
			menu.popup_at_pointer()

	def shipping_invoice_history_activated (self, menuitem):
		selection = self.get_object('shipping-selection')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][5]
		if invoice_id == 'N/A':
			return
		invoice_id = int(invoice_id)
		self.show_invoice_history (invoice_id)

	def invoice_treeview_button_release_event (self, treeview, event):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('invoice_menu')
			menu.popup_at_pointer()

	def invoice_history_activated (self, menuitem):
		selection = self.get_object('invoice-selection')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][0]
		self.show_invoice_history (invoice_id)

	def show_invoice_history (self, invoice_id):
		if not self.invoice_history or self.invoice_history.exists == False:
			from reports import invoice_history as ih
			self.invoice_history = ih.InvoiceHistoryGUI()
		combo = self.invoice_history.get_object('combobox1')
		combo.set_active_id(self.contact_id)
		store = self.invoice_history.get_object('invoice_store')
		selection = self.invoice_history.get_object('treeview-selection1')
		treeview = self.invoice_history.get_object('treeview1')
		selection.unselect_all()
		for row in store:
			if row[0] == invoice_id:
				selection.select_iter(row.iter)
				treeview.scroll_to_cell(row.path, None, False)
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
		
	def statement_treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('statement_menu')
			menu.popup_at_pointer()

	def view_pdf_activated (self, menuitem):
		selection = self.get_object('statement_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		c = DB.cursor()
		c.execute("SELECT name, pdf FROM statements "
					"WHERE id = %s AND pdf IS NOT NULL", (row_id,))
		for row in c.fetchall():
			file_name = row[0]
			if file_name == None:
				break
			pdf_data = row[1]
			with open(file_name,'wb') as f:
				f.write(pdf_data)
			subprocess.call(["xdg-open", file_name])
		c.close()
		DB.rollback()

	def product_treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('product_menu')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('product_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(product_id)

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
		self.populate_contact_shipping()
		self.get_object('resource_buffer').set_text('')
		DB.rollback()

	def populate_incoming_invoice_store (self):
		incoming_invoice_store = self.get_object('incoming_invoice_store')
		incoming_invoice_store.clear()
		count = 0
		self.cursor.execute("SELECT "
								"id, "
								"date_created::text, "
								"format_date(date_created), "
								"amount, "
								"amount::text, "
								"description "
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
		self.cursor.execute("SELECT "
								"snh.id, "
								"p.name, "
								"sn.serial_number, "
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
		c = DB.cursor()
		c.execute("SELECT * FROM "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Invoice', "
					"SUM(price), "
					"SUM(price)::text, "
					"SUM(ext_price), "
					"SUM(ext_price)::text "
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
					"'Purchase order', "
					"SUM(price), "
					"SUM(price)::text, "
					"SUM(ext_price), "
					"SUM(ext_price)::text "
					"FROM products AS p "
					"JOIN purchase_order_items AS poli ON poli.product_id = p.id "
					"JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
					"WHERE vendor_id = %s "
					"GROUP BY p.id, p.name, remark) "
				"UNION "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Documents', "
					"SUM(price), "
					"SUM(price)::text, "
					"SUM(ext_price), "
					"SUM(ext_price)::text "
					"FROM products AS p "
					"JOIN document_items AS di ON di.product_id = p.id "
					"JOIN documents AS d ON d.id = di.document_id "
					"WHERE contact_id = %s "
					"GROUP BY p.id, p.name, remark) "
				"UNION "
					"(SELECT SUM(qty), "
					"SUM(qty)::text, "
					"p.id, "
					"p.name AS name, "
					"remark, "
					"'Job Sheet', "
					"0.0, "
					"'N/A', "
					"0.0, "
					"'N/A'::text "
					"FROM products AS p "
					"JOIN job_sheet_items AS jsi ON jsi.product_id = p.id "
					"JOIN job_sheets AS js ON js.id = jsi.job_sheet_id "
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
		self.cursor.execute("SELECT "
								"id, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"name, "
								"amount, "
								"amount::text, "
								"print_date::text, "
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
		self.cursor.execute("SELECT "
								"r.id, "
								"subject, "
								"dated_for::text, "
								"format_date(dated_for), "
								"notes, "
								"tag, "
								"red, "
								"green, "
								"blue, "
								"alpha, "
								"phone_number "
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
			phone = row[10]
			resource_store.append([row_id, subject, dated_for, date_formatted, 
									notes, tag_name, rgba, phone])
		if count == 0:
			self.get_object('label4').set_label('Resources')
		else:
			label = "<span weight='bold'>Resources (%s)</span>" % count
			self.get_object('label4').set_markup(label)

	def populate_contact_payments (self):
		payment_store = self.get_object('payments_store')
		payment_store.clear()
		count = 0
		self.cursor.execute("SELECT "
								"id, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"amount, "
								"amount::text, "
								"payment_info(id), "
								"misc_income "
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
		self.cursor.execute("SELECT "
								"i.id, "
								"dated_for::text, "
								"format_date(dated_for), "
								"i.name,  "
								"'Comments: ' || comments, "
								"COALESCE(total, 0.00), "
								"COALESCE(total, 0.00)::text, "
								"date_printed::text, "
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

	def populate_contact_shipping (self):
		shipping_store = self.get_object('shipping_store')
		shipping_store.clear()
		count = 0
		c = DB.cursor()
		c.execute("SELECT "
						"si.id, "
						"si.tracking_number, "
						"si.reason, "
						"si.date_shipped::text, "
						"format_date(si.date_shipped), "
						"COALESCE(si.invoice_id::text, 'N/A'), "
						"COALESCE(ii.amount, 0.00), "
						"COALESCE(ii.amount::text, 'N/A') "
					"FROM shipping_info AS si "
					"LEFT JOIN incoming_invoices AS ii "
						"ON ii.id = si.incoming_invoice_id "
					"WHERE si.contact_id = %s"
					"ORDER BY date_shipped", 
					(self.contact_id,))
		for row in c.fetchall():
			count += 1
			shipping_store.append(row)
		if count == 0:
			self.get_object('label11').set_label('Shipping')
		else:
			label = "<span weight='bold'>Shipping (%s)</span>" % count
			self.get_object('label11').set_markup(label)
		c.close()

	def resource_selection_changed (self, selection):
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		c = DB.cursor()
		c.execute("SELECT notes FROM "
					"resources WHERE id = %s", (row_id,))
		notes = c.fetchone()[0]
		self.get_object('resource_buffer').set_text(notes)
		c.close()
		DB.rollback()


