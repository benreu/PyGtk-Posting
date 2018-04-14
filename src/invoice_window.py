# invoice_window.py
# Copyright (C) 2016 reuben
# 
# invoice_window is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# invoice_window is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, Gdk, GLib
import os, subprocess, psycopg2
from invoice import invoice_create
from dateutils import DateTimeCalendar
from pricing import get_customer_product_price

UI_FILE = "src/invoice_window.ui"

def create_new_invoice (cursor, date, customer_id):
	from datetime import datetime
	cursor.execute ("INSERT INTO invoices "
					"(customer_id, date_created, paid, canceled, "
					"posted, doc_type, comments) "
					"VALUES (%s, %s, False, False, False, 'Invoice', '') "
					"RETURNING id", (customer_id, date))
	invoice_id = cursor.fetchone()[0]
	cursor.execute("SELECT name FROM contacts WHERE id = %s", (customer_id,))
	name = cursor.fetchone()[0]
	split_name = name.split(' ')
	name_str = ""
	for i in split_name:
		name_str += i[0:3]
	name = name_str.lower()
	invoice_date = str(datetime.today())[0:10]
	doc_name = "Inv_" + str(invoice_id) + "_"  + name + "_" + invoice_date
	cursor.execute("UPDATE invoices SET name = %s WHERE id = %s", (doc_name, invoice_id))
	return invoice_id

class Item(object):#this is used by py3o library see their example for more info
	pass

class InvoiceGUI:
	
	def __init__(self, main, invoice_id = None):
		
		self.invoice_id = invoice_id
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.window = self.builder.get_object('window')
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1
		self.invoice = None

		self.main = main
		self.db = main.db
		
		self.populating = False
		self.invoice_store = self.builder.get_object('invoice_store')
		self.location_store = self.builder.get_object('location_store')
		self.document_list_store = self.builder.get_object('document_list_store')
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.treeview = self.builder.get_object('treeview2')
		self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		self.treeview.connect("drag-data-received", self.on_drag_data_received)
		self.treeview.drag_dest_set_target_list([enforce_target])
		self.cursor = self.db.cursor()
		self.handler_c_id = main.connect ("contacts_changed", self.populate_customer_store )
		self.handler_p_id = main.connect ("products_changed", self.populate_product_store )
		self.customer_id = 0
		self.menu_visible = False
			
		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('product_store')
		self.barcodes_not_found_store = self.builder.get_object('barcodes_not_found_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		qty_column = self.builder.get_object ('treeviewcolumn1')
		qty_renderer = self.builder.get_object ('cellrenderertext2')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)

		price_column = self.builder.get_object ('treeviewcolumn4')
		price_renderer = self.builder.get_object ('cellrenderertext5')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)

		tax_column = self.builder.get_object ('treeviewcolumn5')
		tax_renderer = self.builder.get_object ('cellrenderertext6')
		tax_column.set_cell_data_func(tax_renderer, self.tax_cell_func)

		ext_price_column = self.builder.get_object ('treeviewcolumn6')
		ext_price_renderer = self.builder.get_object ('cellrenderertext7')
		ext_price_column.set_cell_data_func(ext_price_renderer, self.ext_price_cell_func)

		self.document_type = "Invoice"
		self.populate_location_store ()
		self.populate_customer_store ()
		self.populate_product_store ()
		self.builder.get_object('combobox2').set_active(0)
		
		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_relative_to(self.builder.get_object('entry1'))
		self.calendar.set_today()

		if invoice_id != None:  # edit an existing invoice; put all the existing items in the liststore
			self.populate_customer_store ()
			self.set_widgets_sensitive ()
			self.populate_invoice_items()
			self.cursor.execute("SELECT customer_id, COALESCE(dated_for, now())"
								"FROM invoices "
								"WHERE id = %s", (self.invoice_id,))
			for row in self.cursor.fetchall():
				customer_id = row[0]
				date = row[1]
				self.calendar.set_date(date)
			self.builder.get_object('combobox1').set_active_id(str(customer_id))

		self.tax = 0
		self.window.show_all()
		self.calculate_totals ()
		
		GLib.idle_add(self.load_settings)

	def load_settings (self):
		self.cursor.execute("SELECT column_id, visible FROM settings.invoice_columns")
		for row in self.cursor.fetchall():
			column_id = row[0]
			visible = row[1]
			self.builder.get_object(column_id).set_visible(visible)
		self.cursor.execute("SELECT print_direct, email_when_possible FROM settings")
		print_direct, email = self.cursor.fetchone()
		self.builder.get_object('menuitem1').set_active(print_direct) #set the direct print checkbox
		self.builder.get_object('menuitem4').set_active(email) #set the email checkbox

	def populate_location_store (self):
		location_combo = self.builder.get_object('combobox2')
		active_location = location_combo.get_active_id()
		self.location_store.clear()
		self.cursor.execute("SELECT id, name FROM locations ORDER BY name")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			self.location_store.append([str(location_id), location_name])
		location_combo.set_active_id(active_location)

	def transfer_invoice_activated (self, menuitem):
		dialog = self.builder.get_object('transfer_invoice_dialog')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			combo = self.builder.get_object('combobox3')
			transfer_customer_id = combo.get_active_id()
			self.cursor.execute("UPDATE invoices SET customer_id = %s "
								"WHERE id = %s", 
								(transfer_customer_id, self.invoice_id))
			self.db.commit()
			combo = self.builder.get_object('combobox1')
			combo.set_active_id(transfer_customer_id)
			self.update_invoice_name ("Inv")

	def invoice_transfer_match_selected (self, completion, model, iter):
		transfer_customer_id = model[iter][0]
		combo = self.builder.get_object('combobox3')
		combo.set_active_id(transfer_customer_id)

	def barcode_entry_key_pressed (self, entry, event):
		if event.get_state() & Gdk.ModifierType.SHIFT_MASK: #shift held down
			barcode = entry.get_text()
			if barcode == "":
				return # blank barcode
			self.cursor.execute("SELECT id FROM products "
								"WHERE (barcode, deleted, sellable, stock) = "
								"(%s, False, True, True)", (barcode,))
			for row in self.cursor.fetchall():
				product_id = row[0]
				break
			else:
				return
			keyname = Gdk.keyval_name(event.keyval)
			if keyname == 'Return' or keyname == "KP_Enter": # enter key(s)
				for row in self.invoice_store:
					if row[2] == product_id:
						row[1] -= 1
						break

	def barcode_entry_activate (self, entry):
		self.check_invoice_id()
		barcode = entry.get_text()
		entry.select_region(0,-1)
		if barcode == "":
			return # blank barcode
		self.cursor.execute("SELECT process_invoice_barcode(%s, %s)", 
							(barcode, self.invoice_id))
		for row in self.cursor.fetchall():
			if row[0] != 0:
				self.populate_invoice_items()
				row_id = row[0]
			else:            #barcode not found
				for row in self.barcodes_not_found_store:
					if row[2] == barcode:
						row[1] += 1
						break
					continue
				else:
					self.barcodes_not_found_store.append([0, 1, barcode])
				self.builder.get_object('entry10').grab_focus()
				barcode_error_dialog = self.builder.get_object('barcode_error_dialog')
				barcode_error_dialog.run()
				barcode_error_dialog.hide()
				return
		for row in self.invoice_store:   #select the item we scanned
			if row[0] == row_id:
				treeview = self.builder.get_object('treeview2')
				c = treeview.get_column(0)
				#path = self.invoice_store.get_path(row.path)
				treeview.set_cursor(row.path, c, False)

	def import_time_clock_window(self, widget):
		self.check_invoice_id ()
		from invoice import import_time_clock_entries as itce
		self.time_clock_import = itce.ImportGUI(self.db, self.customer_id, self.invoice_id)		

	def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
		list_ = data.get_text().split(' ')
		if len(list_) != 2:
			raise Exception("invalid drag data received")
			return
		if self.customer_id == 0:
			return
		qty, product_id = list_[0], list_[1]
		self.check_invoice_id()
		iter_ = self.invoice_store.append([0, '1', product_id, product_name,
											"", "", price, '1', '1', "", 
											True, '', False])
		self.check_invoice_item_id (iter_)
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(0)
		path = self.invoice_store.get_path(iter_)
		treeview.set_cursor(path, c, True)
		self.product_selected (product_id, path)

	def destroy(self, window):
		self.main.disconnect(self.handler_c_id)
		self.main.disconnect(self.handler_p_id)
		self.cursor.close()

	def focus (self, window, event):
		self.populate_location_store ()
		if self.invoice_id != None:
			self.populate_invoice_items ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3 and self.menu_visible == False:
			selection = self.builder.get_object("treeview-selection")
			model, path = selection.get_selected_rows ()
			cancel_time_import_menuitem = self.builder.get_object("menuitem13")
			cancel_time_import_menuitem.set_visible(False)
			if path != []:
				line_id = model[path][0]
				self.cursor.execute("SELECT id FROM time_clock_entries "
									"WHERE invoice_line_id = %s LIMIT 1", 
									(line_id,))
				self.time_clock_entries_ids = self.cursor.fetchall()
				for row in self.time_clock_entries_ids:
					cancel_time_import_menuitem.set_visible(True)
			menu = self.builder.get_object('invoice_line_item_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			self.menu_visible = True
		else:
			self.menu_visible = False

	def cancel_time_clock_import_activated (self, menuitem):
		for row in self.time_clock_entries_ids:
			self.cursor.execute("UPDATE time_clock_entries "
								"SET (invoiced, invoice_line_id) = "
								"(False, NULL) WHERE id = %s", (row[0],))
		self.db.commit()

	def refresh_price_activated (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		self.set_product_price (path)

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(self.main, product_id)

	def tax_exemption_window (self, widget):
		import customer_tax_exemptions as cte
		cte.CustomerTaxExemptionsGUI(self.window, self.db, self.customer_id)
		self.populate_tax_exemption_combo ()

	def product_clicked (self, menuitem):
		import products
		products.ProductsGUI(self.main)

	def customer_button_release_event (self, button, event):
		if event.button == 3:
			import contacts
			contacts.GUI(self.main, self.customer_id)

	def document_list_clicked (self, menuitem):
		self.show_document_list_window ()

	def show_document_list_window (self):
		self.populate_document_list ()
		pos = self.window.get_position()
		x, y = pos[0], pos[1]
		x_size = self.window.get_size()[0]
		x = int(x) + int(x_size)
		window = self.builder.get_object('document_list_window')
		window.move(x , int(y))
		window.show_all()

	def populate_document_list (self):
		selection = self.builder.get_object('treeview-selection4')
		self.document_list_store.clear()
		self.cursor.execute("SELECT id, name, doc_type, active "
							"FROM invoices "
							"WHERE (customer_id, posted, canceled) = "
							"(%s, False, False)", (self.customer_id,))
		for row in self.cursor.fetchall():
			_id_ = row[0]
			name = row[1]
			doc_type = row[2]
			active = row[3]
			self.document_list_store.append ([_id_, name, doc_type, active])
		for row in self.document_list_store:
			if row[0] == self.invoice_id:
				selection.select_path(row.path)

	def active_cell_renderer_toggled (self, renderer, path):
		active = self.document_list_store[path][3]
		invoice_id = self.document_list_store[path][0]
		self.document_list_store[path][3] = not active
		self.cursor.execute("UPDATE invoices SET active = %s WHERE id = %s",
							(not active, invoice_id))
		self.db.commit()

	def document_window_delete (self, window, event):
		window.hide()
		return True

	def document_list_row_activated (self, treeview, path, column):
		self.invoice_id = self.document_list_store[path][0]
		self.cursor.execute("SELECT comments FROM invoices WHERE id = %s",
														(self.invoice_id,))
		comments = self.cursor.fetchone()[0]
		self.builder.get_object("comment_buffer").set_text(comments)
		self.document_type = self.document_list_store[path][2]
		self.populate_invoice_items()
		self.cursor.execute("SELECT dated_for FROM invoices WHERE id = %s", (self.invoice_id,))
		date = self.cursor.fetchone()[0]
		self.calendar.set_date(date)

	def update_invoice_name (self, document_prefix):
		self.cursor.execute("SELECT name FROM contacts WHERE id = %s", (self.customer_id,))
		name = self.cursor.fetchone()[0]
		split_name = name.split(' ')
		name_str = ""
		for i in split_name:
			name_str += i[0:3]
		name = name_str.lower()
		invoice_date = str(self.datetime)[0:10]
		doc_prefix = document_prefix[0:3]
		doc_name = doc_prefix + "_" + str(self.invoice_id) + "_"  + name + "_" + invoice_date
		self.cursor.execute("UPDATE invoices SET name = %s WHERE id = %s", (doc_name, self.invoice_id))
		self.db.commit()

	def document_type_edited(self, cell_renderer, path, text):
		self.document_type = text
		self.update_invoice_name (text)
		self.cursor.execute("UPDATE invoices SET doc_type = %s WHERE id = %s", (text, self.invoice_id))
		self.populate_document_list()
		
	def contacts_window(self, widget):
		import contacts
		contacts.GUI(self.main)

	def delete_invoice_clicked (self, button):
		self.cursor.execute("UPDATE invoices SET canceled = True "
							"WHERE id = %s", (self.invoice_id,))
		self.db.commit()
		self.populate_document_list ()
		self.invoice_store.clear()

	def new_invoice_clicked (self, button):
		self.invoice_id = 0
		self.invoice_store.clear()

	def comment_textbuffer_changed (self, buf):
		start = buf.get_start_iter()
		end = buf.get_end_iter()
		comment = buf.get_text(start, end, True)
		self.cursor.execute("UPDATE invoices SET comments = %s WHERE id = %s", 
													(comment, self.invoice_id))
		self.db.commit()
		self.invoice = None  #comments changed, recreate odt file

	def view_invoice(self, widget):
		buf = self.builder.get_object('comment_buffer')
		start = buf.get_start_iter()
		end = buf.get_end_iter()
		comment = buf.get_text(start, end, True)
		if not self.invoice:
			self.invoice = invoice_create.Setup(self.db, self.invoice_store, 
												self.customer_id, comment, 
												self.datetime, self.invoice_id, 
												self, self.document_type)
		self.invoice.view()

	def post_invoice(self, widget):
		buf = self.builder.get_object('comment_buffer')
		start = buf.get_start_iter()
		end = buf.get_end_iter()
		comment = buf.get_text(start, end, True)
		if not self.invoice:
			self.invoice = invoice_create.Setup(self.db, self.invoice_store, 
												self.customer_id, comment, 
												self.datetime, self.invoice_id,
												self, self.document_type)
		else:
			self.invoice.save()
		if os.path.exists(self.invoice.lock_file):
			dialog = self.builder.get_object('dialog1')
			response = dialog.run()
			dialog.hide()
			if response != Gtk.ResponseType.ACCEPT:
				return
		if self.builder.get_object('menuitem1').get_active() == True:
			self.invoice.print_directly(self.window)
		else:
			self.invoice.print_dialog(self.window)
		self.invoice.post()
		if self.builder.get_object('menuitem4').get_active() == True:
			self.cursor.execute("SELECT * FROM contacts WHERE id = %s", 
														(self.customer_id, ))
			for row in self.cursor.fetchall():
				name = row[1]
				email = row[9]
				if email != "":
					email = "%s '< %s >'" % (name, email)
					self.invoice.email(email)
		location_id = self.builder.get_object('combobox2').get_active_id()
		from inventory import inventorying
		inventorying.sell(self.db, self.invoice_store, location_id, self.customer_id, self.datetime)
		self.db.commit()
		self.window.destroy()

	def populate_invoice_items (self):
		self.invoice_store.clear()
		self.cursor.execute("SELECT ili.id, qty, product_id, products.name, "
							"ext_name, remark, price::text, tax::text, ext_price::text, "
							"ili.tax_rate_id, COALESCE(tax_letter, ''), "
							"products.invoice_serial_numbers "
							"FROM invoice_items AS ili "
							"JOIN products ON products.id = ili.product_id "
							"LEFT JOIN tax_rates "
							"ON tax_rates.id = ili.tax_rate_id "
							"WHERE (invoice_id, canceled) = (%s, False) "
							"ORDER BY ili.id", (self.invoice_id,))
		for row in self.cursor.fetchall():
			id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			ext_name = row[4]
			remark = row[5]
			price = row[6]
			tax = row[7]
			ext_price = row[8]
			tax_rate_id = str(row[9])
			tax_letter = row[10]
			serial_number = row[11]
			if serial_number == True:
				self.builder.get_object('treeviewcolumn13').set_visible(True)
				qty = int(qty)
			self.invoice_store.append([id, str(qty), product_id, product_name, 
										ext_name, remark, price, tax, 
										ext_price, tax_rate_id, False, 
										tax_letter, serial_number])
		self.check_serial_numbers()
			
	def tax_exemption_combo_changed(self, combo):
		'''if tax_rate_id is NULL, trigger will use default tax rate'''
		if self.populating == True:
			return
		tax_rate_id = combo.get_active_id()
		self.cursor.execute("UPDATE invoice_items SET tax_rate_id = %s "
							"WHERE invoice_id = %s", 
							(tax_rate_id, self.invoice_id))
		self.db.commit()
		self.populate_invoice_items ()
		self.calculate_totals ()

	################## start customer

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		self.cursor.execute("SELECT id, name, ext_name, "
								"(( SELECT COALESCE(SUM(total), 0.00) "
								"FROM invoices "
								"WHERE canceled = False "
								"AND customer_id = c_outer.id) - "
								"(SELECT COALESCE(SUM(amount), 0.00) "
								"FROM payments_incoming "
								"WHERE (customer_id, misc_income) = "
								"(c_outer.id, False) ))"
							"FROM contacts AS c_outer "
							"WHERE (deleted, customer) = "
							"(False, True) ORDER BY name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			name = row[1]
			ext_name = row[2]
			unpaid = row[3]
			unpaid = "Unpaid balance  " + '${:,.2f}'.format(unpaid)
			self.customer_store.append([str(customer_id),name + "  :  " + unpaid, ext_name])
		
	def customer_match_selected(self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.customer_selected (self.customer_id)

	def customer_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter_][1].lower():
				return False
		return True

	def customer_combobox_changed(self, widget, toggle_button=None): #updates the customer
		customer_id = widget.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			self.customer_selected (self.customer_id)
			self.calculate_totals ()

	def populate_tax_exemption_combo (self):
		self.populating = True
		exemption_combo = self.builder.get_object('comboboxtext1')
		active = exemption_combo.get_active_id()
		exemption_combo.remove_all()
		exemption_combo.append(None, "No exemption")
		final_id = '0'
		self.cursor.execute("SELECT tax_rates.id, tax_rates.name FROM "
							"customer_tax_exemptions "
							"JOIN tax_rates "
							"ON customer_tax_exemptions.tax_rate_id = "
							"tax_rates.id "
							"WHERE customer_tax_exemptions.customer_id = (%s)",
							(self.customer_id,))
		for row in self.cursor.fetchall():
			exemption_combo.append(str(row[0]), row[1])
			final_id = str(row[0])
		if active == None:
			self.populating = False
			exemption_combo.set_active_id(final_id)
			return
		exemption_combo.set_active_id(active)
		self.populating = False

	def customer_selected(self, name_id):
		self.cursor.execute("SELECT address, phone FROM contacts "
							"WHERE id = (%s)",(name_id,))
		for row in self.cursor.fetchall() :
			self.builder.get_object('entry6').set_text(row[0])
			self.builder.get_object('entry8').set_text(row[1])
		self.populate_tax_exemption_combo ()
		self.set_widgets_sensitive ()
		self.cursor.execute("SELECT id, comments FROM invoices "
							"WHERE (customer_id, posted) = (%s, False) ", 
							(name_id,))
		tupl = self.cursor.fetchall()
		if len(tupl) > 1:
			self.invoice_id = 0
			self.show_document_list_window ()
			self.builder.get_object("comment_buffer").set_text('')
		elif len(tupl) == 1:
			self.invoice_id = tupl[0][0]
			comments = tupl[0][1]
			self.builder.get_object("comment_buffer").set_text(comments)
		else:
			self.invoice_id = 0
			self.builder.get_object("comment_buffer").set_text('')
		self.populate_invoice_items()
		self.cursor.execute("SELECT dated_for FROM invoices WHERE id = %s "
							"AND dated_for IS NOT NULL", (self.invoice_id,))
		for row in self.cursor.fetchall():
			date = row[0]
			self.calendar.set_date(date)
			break
		else:
			self.calendar.set_today()

	################## start qty
	
	def qty_cell_func(self, column, cellrenderer, model, iter_, data):
		return
		if model.get_value(iter_, 12) == True:
			qty = int(model.get_value(iter_, 1))
			cellrenderer.set_property("text" , str(qty))

	def qty_edited(self, widget, path, text):
		if self.invoice_store[path][12] == True:
			text = int(text) # only allow whole numbers for inventory
		iter_ = self.invoice_store.get_iter (path)
		self.check_invoice_item_id (iter_)
		line_id = self.invoice_store[iter_][0]
		try:
			self.cursor.execute("UPDATE invoice_items SET qty = %s "
								"WHERE id = %s;"
								"SELECT qty::text, ext_price::text, tax::text "
								"FROM invoice_items WHERE id = %s", 
								(text, line_id, line_id))
			self.db.commit()
		except psycopg2.DataError as e:
			self.show_error_dialog (str(e))
			self.db.rollback()
			return
		for row in self.cursor.fetchall():
			qty = row[0]
			ext_price = row[1]
			tax = row[2]
			self.invoice_store[iter_][1] = qty
			self.invoice_store[iter_][7] = tax
			self.invoice_store[iter_][8] = ext_price
		self.check_serial_numbers ()
		self.calculate_totals ()

	################## start remark

	def remark_edited(self, widget, path, text):
		iter_ = self.invoice_store.get_iter(path)
		self.invoice_store[iter_][5] = text
		line_id = self.invoice_store[iter_][0]
		self.cursor.execute("UPDATE invoice_items SET remark = %s "
							"WHERE id = %s", (text, line_id))
		self.db.commit()

	################## start price

	def price_cell_func(self, column, cellrenderer, model, iter_, data):
		return
		price = '{:,.2f}'.format(model.get_value(iter_, 6))
		cellrenderer.set_property("text" , price)
		
	def price_edited(self, widget, path, text):
		iter_ = self.invoice_store.get_iter(path)
		line_id = self.invoice_store[iter_][0]
		try:
			self.cursor.execute("UPDATE invoice_items SET price = %s "
								"WHERE id = %s;"
								"SELECT price::text, ext_price::text, tax::text "
								"FROM invoice_items WHERE id = %s", 
								(text, line_id, line_id))
			self.db.commit()
		except psycopg2.DataError as e:
			self.show_error_dialog (str(e))
			self.db.rollback()
			return
		for row in self.cursor.fetchall():
			price = row[0]
			ext_price = row[1]
			tax = row[2]
			self.invoice_store[iter_][6] = price
			self.invoice_store[iter_][7] = tax
			self.invoice_store[iter_][8] = ext_price
		self.calculate_totals()

	################## end price

	def tax_cell_func(self, column, cellrenderer, model, iter_, data):
		return
		tax = '{:,.2f}'.format(model.get_value(iter_, 7))
		cellrenderer.set_property("text" , tax)

	def ext_price_cell_func(self, column, cellrenderer, model, iter_, data):
		return
		ext_price = '{:,.2f}'.format(model.get_value(iter_, 8))
		cellrenderer.set_property("text" , ext_price)
		
	################## start product
	
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_match_selected(self, completion, model, iter_):
		product_id = self.product_store[iter_][0]
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.product_selected (product_id, path)

	def product_renderer_started (self, renderer, combo, path):
		completion = self.builder.get_object('product_completion')
		entry = combo.get_child()
		entry.set_completion(completion)
		
	def product_renderer_changed (self, widget, path, iter_):
		product_id = self.product_store[iter_][0]
		self.product_selected (product_id, path)

	def product_selected (self, product_id, path):
		invoice_line_id = self.invoice_store[path][0]
		self.cursor.execute("UPDATE serial_numbers "
							"SET invoice_item_id = NULL "
							"WHERE invoice_item_id = %s", 
							(invoice_line_id,))
		self.cursor.execute("SELECT products.name, ext_name, tax_letter, "
							"invoice_serial_numbers "
							"FROM products JOIN tax_rates "
							"ON tax_rates.id = products.tax_rate_id "  
							"WHERE products.id = %s", (product_id,))
		for row in self.cursor.fetchall ():
			product_name = row[0]
			ext_name = row[1]
			tax_letter = row[2]
			serial_number = row[3]
			iter_ = self.invoice_store.get_iter(path)
			if serial_number == True:
				self.builder.get_object('treeviewcolumn13').set_visible(True)
				#allow only whole numbers for inventory
				qty = self.invoice_store[iter_][1].split('.')[0] 
				self.invoice_store[iter_][1] = qty
			self.invoice_store[iter_][2] = int(product_id)
			self.invoice_store[iter_][3] = product_name
			self.invoice_store[iter_][4] = ext_name
			self.invoice_store[iter_][10] = False
			self.invoice_store[iter_][11] = tax_letter
			self.invoice_store[iter_][12] = serial_number
			self.set_product_price (iter_)
			line_id = self.invoice_store[iter_][0]
			self.cursor.execute("UPDATE invoice_items SET product_id = %s "
								"WHERE id = %s;"
								"SELECT price::text, tax::text, ext_price::text "
								"FROM invoice_items WHERE id = %s", 
								(product_id, line_id, line_id))
			for row in self.cursor.fetchall():
				price = row[0]
				tax = row[1]
				ext_price = row[2]
				self.invoice_store[iter_][6] = price
				self.invoice_store[iter_][7] = tax
				self.invoice_store[iter_][8] = ext_price
			self.db.commit()
			self.set_serial_number_box_state(serial_number)
		self.check_serial_numbers ()
		self.populate_serial_numbers ()
		self.calculate_totals()

	def populate_serial_numbers (self):
		serial_number_store = self.builder.get_object('serial_number_store')
		serial_number_store.clear()
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return # no row selected
		invoice_line_id = model[path][0]
		product_id = model[path][2]
		product_name = model[path][3]
		self.cursor.execute("SELECT id, serial_number FROM serial_numbers "
							"WHERE invoice_item_id = %s", 
							(invoice_line_id,))
		for row in self.cursor.fetchall():
			id_ = row[0]
			serial_number = row[1]
			serial_number_store.append([product_id, invoice_line_id, product_name, serial_number, id_])

	def check_serial_numbers (self):
		mismatch = False
		box = self.builder.get_object('box4')
		for row in self.invoice_store:
			if row[12] == True:
				box.set_visible(True)
				invoice_line_id = row[0]
				qty = int(row[1])
				product_id = row[2]
				product_name = row[3]
				self.cursor.execute("SELECT COUNT(id) FROM serial_numbers "
									"WHERE invoice_item_id = %s", 
									(invoice_line_id,))
				ser_qty = self.cursor.fetchone()[0]
				if qty != ser_qty:
					mismatch = True
					break
		button = self.builder.get_object('button2')
		if mismatch == True:
			button.set_label('Qty/serial number mismatch')
			button.set_sensitive(False)
		else:
			button.set_label('Post invoice')
			button.set_sensitive(True)

	def invoice_item_row_activated (self, treeview, path, column):
		store = treeview.get_model()
		invoice_item_id = store[path][0]
		if invoice_item_id == 0:
			return # no valid invoice item yet
		enforce_serial_numbers = store[path][12]
		self.set_serial_number_box_state(enforce_serial_numbers)
		product_id = store[path][2]
		self.check_serial_numbers()
		self.populate_serial_numbers ()

	def set_serial_number_box_state (self, sensitive):
		box = self.builder.get_object('box4')
		box.set_sensitive(sensitive)

	def serial_number_entry_activated (self, entry):
		serial_number = entry.get_text()
		item_selection = self.builder.get_object('treeview-selection')
		model, path = item_selection.get_selected_rows()
		if path == []:
			self.show_error_dialog ("No invoice item selected!")
			return # no invoice item selected
		invoice_line_id = model[path][0]
		product_id = model[path][2]
		self.cursor.execute("SELECT c.name, i.id FROM serial_numbers AS sn "
							"JOIN invoice_items AS ili "
							"ON ili.id = sn.invoice_item_id "
							"JOIN invoices AS i ON i.id = ili.invoice_id "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE (sn.product_id, sn.serial_number) = (%s, %s) ",
							(product_id, serial_number))
		for row in self.cursor.fetchall():
			customer_name = row[0]
			invoice_number = row[1]
			error = "Serial number %s is in use on invoice number %s, "\
			"customer name %s.\n Most likely you entered the serial number "\
			"twice or maybe the serial number\n got entered wrong now, or "\
			"sometime before today."\
			%(serial_number, invoice_number, customer_name)
			self.show_error_dialog(error)
			return  # serial number is in use
		self.cursor.execute("UPDATE serial_numbers "
							"SET invoice_item_id = %s "
							"WHERE (product_id, serial_number) = (%s, %s) "
							"AND invoice_item_id IS NULL RETURNING id", 
							(invoice_line_id, product_id, serial_number ))
		for row in self.cursor.fetchall():
			product_serial_number_id = row[0]
			break
		else:
			error = ("That serial number was not found in the system.\n "
			"This means it was not manufactured or received yet.\n "
			"If you want to add it manually, you can go to\n "
			"General>Serial Numbers on the main window.")
			self.show_error_dialog(error)
			return  # no serial number found in the system
		self.db.commit()
		self.check_serial_numbers ()
		self.populate_serial_numbers ()
		entry.select_region(0, -1)
		entry.grab_focus()

	def show_error_dialog (self, error):
		self.builder.get_object('label2').set_label(error)
		dialog = self.builder.get_object('error_dialog')
		dialog.run()
		dialog.hide()

	def serial_number_treeview_row_activated (self, treeview, path, column):
		entry = self.builder.get_object('entry11')
		entry.select_region(0, -1)
		entry.grab_focus()

	def remove_serial_number_clicked (self, button):
		selection = self.builder.get_object('treeview-selection5')
		model, path = selection.get_selected_rows()
		if path != []:
			product_serial_number_id = model[path][4]
			self.cursor.execute("UPDATE serial_numbers "
								"SET invoice_item_id = NULL "
								"WHERE id = %s", (product_serial_number_id,))
			self.db.commit()
		self.check_serial_numbers ()
		self.populate_serial_numbers ()
		
	def populate_product_store(self, m=None, i=None):
		self.product_store.clear()
		self.cursor.execute("SELECT id, name, ext_name FROM products "
							"WHERE (deleted, sellable) = (False, True) "
							"ORDER BY name")
		for i in self.cursor.fetchall():
			_id_ = i[0]
			name = i[1]
			ext_name = i[2]
			self.product_store.append([str(_id_), "%s {%s}" % (name, ext_name)])
			
	def set_product_price (self, iter_):
		product_id = self.invoice_store[iter_][2]
		price = get_customer_product_price (self.db, 
											self.customer_id, product_id)
		self.invoice_store[iter_][6] = str(price)
		line_id = self.invoice_store[iter_][0]
		self.cursor.execute("UPDATE invoice_items SET price = %s "
							"WHERE id = %s", (price, line_id))
		self.db.commit()

	################## end product

	def set_widgets_sensitive (self):
		self.builder.get_object('button1').set_sensitive(True)
		self.builder.get_object('button2').set_sensitive(True)
		self.builder.get_object('button3').set_sensitive(True)
		self.builder.get_object('menuitem14').set_sensitive(True)
		self.builder.get_object('entry9').set_sensitive(True)
		self.builder.get_object('menuitem2').set_sensitive(True)
		self.builder.get_object('menuitem6').set_sensitive(True)
		self.builder.get_object('menuitem7').set_sensitive(True)
		self.builder.get_object('menuitem8').set_sensitive(True)
		self.builder.get_object('comment_textview').set_sensitive(True)

	def refresh_all_prices_clicked (self, menuitem):
		for row in self.invoice_store:
			self.set_product_price (row.path)
	
	def calculate_totals (self, widget = None):
		c = self.db.cursor()
		c.execute("WITH totals AS "
					"(SELECT COALESCE(SUM(ext_price), 0.00) AS subtotal, "
					"COALESCE(SUM(tax), 0.00) AS tax, "
					"(COALESCE(SUM(ext_price) + SUM(tax), 0.00)) "
					"AS total FROM invoice_items "
					"WHERE invoice_id = %s"
					"),"
					"update AS "
					"(UPDATE invoices SET (subtotal, tax, total) = "
						"((SELECT subtotal FROM totals), "
						"(SELECT tax FROM totals), "
						"(SELECT total FROM totals)) "
					"WHERE id = %s"
					")"
					"SELECT * FROM totals",
					(self.invoice_id, self.invoice_id))
		for row in c.fetchall():
			self.subtotal = row[0]
			self.tax = row[1] 
			self.total = row[2]
		self.db.commit()
		subtotal = '${:,.2f}'.format(self.subtotal)
		tax = '${:,.2f}'.format(self.tax)
		total = '${:,.2f}'.format(self.total)
		self.builder.get_object('entry3').set_text(subtotal)
		self.builder.get_object('entry4').set_text(tax)
		self.builder.get_object('entry5').set_text(total)

	def check_invoice_item_id (self, iter_):
		id = self.invoice_store[iter_][0]
		qty = self.invoice_store[iter_][1]
		product_id = self.invoice_store[iter_][2]
		remark = self.invoice_store[iter_] [5]
		price = self.invoice_store[iter_][6]
		tax = self.invoice_store[iter_][7]
		ext_price = self.invoice_store[iter_][8]
		tax_id = self.builder.get_object('comboboxtext1').get_active_id()
		if id == 0:
			self.check_invoice_id()
			self.cursor.execute("INSERT INTO invoice_items "
								"(invoice_id, qty, product_id, remark, price, "
								"canceled, tax_rate_id) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id", 
								(self.invoice_id, qty, product_id, remark, 
								price, False, tax_id))
			self.invoice_store[iter_][0] = self.cursor.fetchone()[0]
			self.db.commit()
		self.invoice = None #the generated .odt is no longer valid

	def check_invoice_id (self):
		if self.invoice_id == 0:
			self.invoice_id = create_new_invoice(self.cursor, self.datetime, self.customer_id)
			self.db.commit()
			self.populate_document_list()

	def new_item_clicked (self, button):
		self.cursor.execute("SELECT id, name, level_1_price::text "
							"FROM products WHERE (deleted, sellable, stock) = "
							"(False, True, True) ORDER BY id LIMIT 1")
		for i in self.cursor.fetchall():
			product_id = i[0]
			product_name = i[1]
			price = i[2]
			iter_ = self.invoice_store.append([0, '1', product_id, product_name,
												"", "", price, '1', '1', "", 
												True, '', False])
			self.check_invoice_item_id (iter_)
			treeview = self.builder.get_object('treeview2')
			c = treeview.get_column(0)
			path = self.invoice_store.get_path(iter_)
			treeview.set_cursor(path, c, True)
		self.set_serial_number_box_state(False)

	def delete_line_item_activated (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("WITH deleted AS "
							"(DELETE FROM invoice_items WHERE id = %s "
							"RETURNING gl_entries_id) "
							"DELETE FROM gl_entries WHERE id = "
							"(SELECT gl_entries_id FROM deleted)"
							, (row_id,))
		self.db.commit()
		self.populate_invoice_items ()

	def key_tree_tab(self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab" or keyname=="Esc":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass

	def help_clicked (self, widget):
		import subprocess
		subprocess.Popen("yelp ./help/invoice.page", shell = True)

	def window_key_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'F1':
			self.help_clicked (None)
		if keyname == 'F2':
			self.new_item_clicked (None)
		if keyname == 'F3':
			self.delete_entry(None)

	def calendar_day_selected (self, calendar):
		self.datetime = calendar.get_date()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)

	def calendar(self, widget, icon, event):
		self.calendar.show()


	 
