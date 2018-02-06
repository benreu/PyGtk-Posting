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
import os, subprocess
from invoice import invoice_create
from dateutils import DateTimeCalendar
from pricing import get_customer_product_price

UI_FILE = "src/invoice_window.ui"

def create_new_invoice (cursor, date, customer_id):
	from datetime import datetime
	cursor.execute ("INSERT INTO invoices (customer_id, date_created, paid, canceled, posted, doc_type, comments) VALUES (%s, %s, False, False, False, 'Invoice', '') RETURNING id", (customer_id, date))
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
	
	def __init__(self, main, invoice_id = None, import_customer_id = None):
		self.import_customer_id = import_customer_id
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
			self.populate_invoice_line_items()
			self.cursor.execute("SELECT customer_id, dated_for FROM invoices "
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
						self.calculate_row_taxes(row)
						break

	def barcode_entry_activate (self, entry):
		self.check_invoice_id()
		barcode = entry.get_text()
		entry.select_region(0,-1)
		if barcode == "":
			return # blank barcode
		self.cursor.execute("SELECT id FROM products "
							"WHERE (barcode, deleted, sellable, stock) = "
							"(%s, False, True, True)", (barcode,))
		for row in self.cursor.fetchall():
			product_id = row[0]
			break
		else:
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
		for row in self.invoice_store:
			if row[2] == product_id:
				row[1] += 1
				self.calculate_row_taxes(row)
				break
			continue
		else:
			self.invoice_store.append([0, 1.0, 0, "", "", "", 0.00, 1, 1, "", False, '', False])
			last = self.invoice_store.iter_n_children ()
			last -= 1 #iter_n_children starts at 1 ; path starts at 0
			self.product_selected(product_id, last)

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
		self.invoice_store.append([0, float(qty), int(product_id), '', '', '', 0.00, 1, 1, "", False, '', False])
		last = self.invoice_store.iter_n_children ()
		path = last - 1 #iter_n_children starts at 1 ; path starts at 0
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(0)
		treeview.set_cursor(path , c, False)	#set the cursor to the last appended item
		self.product_selected (product_id, path)

	def destroy(self, window):
		self.main.disconnect(self.handler_c_id)
		self.main.disconnect(self.handler_p_id)
		self.cursor.close()

	def focus (self, window, event):
		self.populate_location_store ()
		if self.invoice_id != None:
			self.populate_invoice_line_items ()
		#for row in self.invoice_store:
			#self.calculate_row_taxes(row)

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
		self.populate_invoice_line_items()
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
			self.invoice.print_directly()
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

	def populate_invoice_line_items (self):
		self.invoice_store.clear()
		self.cursor.execute("SELECT ili.id, qty, product_id, products.name, "
							"ext_name, remark, price, tax, ext_price, "
							"ili.tax_rate_id, COALESCE(tax_letter, ''), "
							"products.invoice_serial_numbers "
							"FROM invoice_line_items AS ili "
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
			self.invoice_store.append([id, qty, product_id, product_name, 
										ext_name, remark, price, tax, 
										ext_price, tax_rate_id, False, 
										tax_letter, serial_number])
		self.check_serial_numbers()
			
	def tax_exemption_combo_changed(self, widget):
		for line in self.invoice_store:
			self.calculate_row_taxes(line)

	################## start customer

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		if self.import_customer_id != None:
			self.cursor.execute("SELECT id, name, ext_name "
								"FROM contacts WHERE id = %s", 
								(self.import_customer_id,))
			for row in self.cursor.fetchall():
				customer_id = row[0]
				name = row[1]
				ext_name = row[2]
				self.customer_store.append([str(customer_id), name, ext_name])
		else:
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
		if self.import_customer_id != None:
			self.builder.get_object('combobox1').set_active(0)
		
	def customer_match_selected(self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.customer_selected (self.customer_id)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_combobox_changed(self, widget, toggle_button=None): #updates the customer
		customer_id = widget.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			self.customer_selected (self.customer_id)
			self.calculate_totals ()

	def populate_tax_exemption_combo (self):
		exemption_combo = self.builder.get_object('comboboxtext1')
		active = exemption_combo.get_active_id()
		exemption_combo.remove_all()
		exemption_combo.append("0", "No exemption")
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
			exemption_combo.set_active_id(final_id)
			return
		exemption_combo.set_active_id(active)

	def customer_selected(self, name_id):
		self.cursor.execute("SELECT address, phone FROM contacts "
							"WHERE id = (%s)",(name_id,))
		for row in self.cursor.fetchall() :
			self.builder.get_object('entry6').set_text(row[0])
			self.builder.get_object('entry8').set_text(row[1])
		self.populate_tax_exemption_combo ()
		if self.import_customer_id != None:
			return #we are editing an existing invoice
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
		self.populate_invoice_line_items()
		self.cursor.execute("SELECT dated_for FROM invoices WHERE id = %s", (self.invoice_id,))
		for row in self.cursor.fetchall():
			date = row[0]
			self.calendar.set_date(date)
			break
		else:
			self.calendar.set_today()

	################## start qty
	
	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		if model.get_value(iter1, 12) == True:
			qty = str(int(model.get_value(iter1, 1)))
		else:
			qty = '{:,.1f}'.format(model.get_value(iter1, 1))
		cellrenderer.set_property("text" , qty)

	def qty_edited(self, widget, path, text):
		if self.invoice_store[path][12] == True:
			self.invoice_store[path][1] = int(text) # only allow whole numbers for inventory
		else:
			self.invoice_store[path][1] = round(float(text), 1)
		line = self.invoice_store[path]
		self.calculate_row_taxes (line)
		self.check_serial_numbers ()

	################## start remark

	def remark_edited(self, widget, path, text):
		self.invoice_store[path][5] = text
		line = self.invoice_store[path]
		self.save_line_item (line)

	################## start price

	def price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = '{:,.2f}'.format(model.get_value(iter1, 6))
		cellrenderer.set_property("text" , price)
		
	def price_edited(self, widget, path, text):	
		self.invoice_store[path][6] = float(text)
		line = self.invoice_store[path]
		self.calculate_row_taxes (line)

	################## end price

	def tax_cell_func(self, column, cellrenderer, model, iter1, data):
		tax = '{:,.2f}'.format(model.get_value(iter1, 7))
		cellrenderer.set_property("text" , tax)

	def ext_price_cell_func(self, column, cellrenderer, model, iter1, data):
		ext_price = '{:,.2f}'.format(model.get_value(iter1, 8))
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
							"SET invoice_line_item_id = NULL "
							"WHERE invoice_line_item_id = %s", 
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
			self.invoice_store[path][4] = ext_name
			self.invoice_store[path][3] = product_name
			self.invoice_store[path][2] = int(product_id)
			self.invoice_store[path][10] = False
			self.invoice_store[path][11] = tax_letter
			self.invoice_store[path][12] = serial_number
			if serial_number == True:
				self.builder.get_object('treeviewcolumn13').set_visible(True)
				qty = int(self.invoice_store[path][1]) 
				self.invoice_store[path][1] = qty
			self.set_product_price (path)
			self.set_serial_number_box_state(serial_number)
		self.check_serial_numbers ()
		self.populate_serial_numbers ()

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
							"WHERE invoice_line_item_id = %s", 
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
									"WHERE invoice_line_item_id = %s", 
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
			self.show_serial_number_error ("No invoice item selected!")
			return # no invoice item selected
		invoice_line_id = model[path][0]
		product_id = model[path][2]
		self.cursor.execute("SELECT c.name, i.id FROM serial_numbers AS sn "
							"JOIN invoice_line_items AS ili "
							"ON ili.id = sn.invoice_line_item_id "
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
			self.show_serial_number_error(error)
			return  # serial number is in use
		self.cursor.execute("UPDATE serial_numbers "
							"SET invoice_line_item_id = %s "
							"WHERE (product_id, serial_number) = (%s, %s) "
							"AND invoice_line_item_id IS NULL RETURNING id", 
							(invoice_line_id, product_id, serial_number ))
		for row in self.cursor.fetchall():
			product_serial_number_id = row[0]
			break
		else:
			error = ("That serial number was not found in the system.\n "
			"This means it was not manufactured or received yet.\n "
			"If you want to add it manually, you can go to\n "
			"General>Serial Numbers on the main window.")
			self.show_serial_number_error(error)
			return  # no serial number found in the system
		self.db.commit()
		self.check_serial_numbers ()
		self.populate_serial_numbers ()
		entry.select_region(0, -1)
		entry.grab_focus()

	def show_serial_number_error (self, error):
		self.builder.get_object('label2').set_label(error)
		dialog = self.builder.get_object('serial_number_error_dialog')
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
								"SET invoice_line_item_id = NULL "
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
			
	def set_product_price (self, path):
		product_id = self.invoice_store[path][2]
		price = get_customer_product_price (self.db, 
											self.customer_id, product_id)
		self.invoice_store[path][6] = price
		line = self.invoice_store[path]
		self.calculate_row_taxes (line)
		return
		
		self.cursor.execute("SELECT markup_percent_id FROM contacts WHERE id = %s", (self.customer_id, ))
		markup_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT price FROM products_markup_prices WHERE (product_id, markup_id) = (%s, %s)", (product_id, markup_id))
		for row in self.cursor.fetchall():
			price = float(row[0])
			break
		else:
			self.cursor.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
			cost = float(self.cursor.fetchone()[0])
			self.cursor.execute("SELECT markup_percent FROM customer_markup_percent WHERE id = %s", (markup_id,))
			markup = float(self.cursor.fetchone()[0])
			margin = (markup / 100) * cost
			price = margin + cost

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
		
	def calculate_row_taxes(self, line):
		product_id = line[2]
		self.cursor.execute("SELECT tax_rate_id, tax_exemptible "
							"FROM products WHERE id = %s", (product_id,))
		for row in self.cursor.fetchall():
			tax_id = row[0]
			tax_exemptible = row[1]
		if self.builder.get_object('comboboxtext1').get_active() == 0 \
													or tax_exemptible == False:
			self.cursor.execute("SELECT id, rate FROM tax_rates WHERE id = "
													"%s",(tax_id,))
			for row in self.cursor.fetchall():
				tax_id = row[0]
				tax_rate = float(row[1])
		else: # no tax
			tax_id = self.builder.get_object('comboboxtext1').get_active_id()
			tax_rate = 0.00
		self.calculate_row_total(line, tax_id, tax_rate)
		self.calculate_totals ()

	def calculate_row_total(self, line, tax_id, tax_rate):
		if tax_id == None:
			return
		price = float(line[6])
		qty = float(line[1])
		ext_price = price * qty
		tax = (ext_price * tax_rate) / 100
		line[7] = round(tax, 2)
		line[8] = round(ext_price, 2)
		line[9] = str(tax_id)
		self.cursor.execute("SELECT tax_letter FROM tax_rates WHERE id = %s", 
							(tax_id,))
		tax_letter = self.cursor.fetchone()[0]
		line[11] = tax_letter
		self.save_line_item (line)
	
	def calculate_totals(self, widget = None):
		self.tax = 0  #we need to make a global variable with subtotal, tax, and total so we can store it to
		self.subtotal = 0   #the database without all the fancy formatting (making it easier to retrieve later on)
		for item in self.invoice_store:
			self.subtotal = self.subtotal + item[8]
			self.tax = self.tax + item[7]
		self.total = self.subtotal + self.tax
		subtotal = '${:,.2f}'.format(self.subtotal)
		tax = '${:,.2f}'.format(self.tax)
		total = '${:,.2f}'.format(self.total)
		self.builder.get_object('entry3').set_text(subtotal)
		self.builder.get_object('entry4').set_text(tax)
		self.builder.get_object('entry5').set_text(total)

	def save_line_item(self, line):
		id = line [0]
		qty = line[1]
		product_id = line[2]
		remark = line [5]
		price = line[6]
		tax = line[7]
		ext_price = line[8]
		tax_id = line[9]
		if id == 0:
			self.cursor.execute("INSERT INTO invoice_line_items (invoice_id, qty, product_id, remark, price, tax, ext_price, canceled, tax_rate_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (self.invoice_id, qty, product_id, remark, price, tax, ext_price, False, tax_id))
			line[0] = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE invoice_line_items SET (qty, product_id, remark, price, tax, ext_price, tax_rate_id) = (%s, %s, %s, %s, %s, %s, %s) WHERE id = %s", (qty, product_id, remark, price, tax, ext_price, tax_id, id))
		self.db.commit()
		self.invoice = None

	def check_invoice_id (self):
		if self.invoice_id == 0:
			self.invoice_id = create_new_invoice(self.cursor, self.datetime, self.customer_id)
			self.db.commit()
			self.populate_document_list()

	def new_item_clicked (self, widget):
		self.cursor.execute("SELECT id, name, level_1_price FROM products WHERE (deleted, sellable, stock) = (False, True, True) ORDER BY id LIMIT 1")
		for i in self.cursor.fetchall():
			product_id = i[0]
			product_name = i[1]
			price = i[2]
			self.invoice_store.append([0, 1.0, product_id, product_name, "", "",
										price, 1, 1, "", True, '', False])
			treeview = self.builder.get_object('treeview2')
			for index, row in enumerate(self.invoice_store):
				if row[10] == True:
					c = treeview.get_column(0)
					treeview.set_cursor(index , c, True)
					break
		self.check_invoice_id()
		self.set_serial_number_box_state(False)

	def delete_line_item_activated (self, menuitem):
		model, path = self.builder.get_object("treeview-selection").get_selected_rows ()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("WITH deleted AS "
							"(DELETE FROM invoice_line_items WHERE id = %s "
							"RETURNING gl_entries_id) "
							"DELETE FROM gl_entries WHERE id = "
							"(SELECT gl_entries_id FROM deleted)"
							, (row_id,))
		self.db.commit()
		self.populate_invoice_line_items ()

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


	 
