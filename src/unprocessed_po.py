# unprocessed_po.py
#
# 
# Copyright (C) 2016 reuben
# 
# unprocessed_po is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# unprocessed_po is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib, GObject
from decimal import Decimal, ROUND_HALF_UP
from multiprocessing import Queue, Process
from queue import Empty
from subprocess import Popen, PIPE, STDOUT
from datetime import datetime
import os, sane, psycopg2
import purchase_ordering
from db.transactor import post_purchase_order, post_purchase_order_accounts

UI_FILE = "src/unprocessed_po.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass
	
class GUI:
	def __init__(self, main, po_id = None):

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.purchase_order_id = None
		self.text = 0
		self.path = None
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1
		
		self.purchase_order_items_store = self.builder.get_object('purchase_order_items_store')
		self.expense_account_store = self.builder.get_object('expense_account_store')
		self.po_store = self.builder.get_object('po_store')
		self.expense_products_store = self.builder.get_object('expense_products_store')
		self.populate_expense_account_store ()
		if po_id == None:
			self.populate_po_combobox ()
		else:
			self.purchase_order_id = po_id
			self.populate_purchase_order_items_store ()
			self.builder.get_object("button7").set_sensitive(True)

		self.cursor.execute("SELECT qty_prec, price_prec FROM settings.purchase_order")
		for row in self.cursor.fetchall():
			qty_prec = row[0]
			price_prec = row[1]
			self.qty_places = Decimal(10) ** -qty_prec
			self.price_places = Decimal(10) ** -price_prec

		self.cursor.execute("SELECT cost_decrease_alert FROM settings")
		self.cost_decrease = self.cursor.fetchone()[0]
		
		qty_renderer = self.builder.get_object('cellrenderertext1')
		qty_column = self.builder.get_object('treeviewcolumn1')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)
		
		price_renderer = self.builder.get_object('cellrenderertext4')
		price_column = self.builder.get_object('treeviewcolumn4')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)
		
		ext_price_renderer = self.builder.get_object('cellrenderertext5')
		ext_price_column = self.builder.get_object('treeviewcolumn5')
		ext_price_column.set_cell_data_func(ext_price_renderer, self.ext_price_cell_func)

		self.populate_terms_listbox()
		self.populate_expense_account_store ()
		self.populate_expense_product_combo ()
		self.window = self.builder.get_object('unprocessed')
		self.window.show_all()

		self.data_queue = Queue()
		self.scanner_store = self.builder.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GLib.timeout_add(100, self.populate_scanners)
		
		self.cursor.execute("SELECT accrual_based FROM settings")
		if self.cursor.fetchone()[0] == True:
			self.builder.get_object('button1').set_visible(False)

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(self.highlight, entry)

	def highlight (self, entry):
		entry.select_region(0, -1)

	def populate_scanners(self):
		try:
			devices = self.data_queue.get_nowait()
			for scanner in devices:
				device_id = scanner[0]
				device_manufacturer = scanner[1]
				name = scanner[2]
				given_name = scanner[3]
				self.scanner_store.append([str(device_id), device_manufacturer,
											name, given_name])
		except Empty:
			return True
		
	def get_scanners(self):
		sane.init()
		devices = sane.get_devices()
		self.data_queue.put(devices)

	def destroy(self, window):
		self.window.destroy()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			self.menu_visible = True
		else:
			self.menu_visible = False

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(self.main, product_id)

	def edit_po_clicked (self, widget):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI(self.main, self.purchase_order_id)

	def populate_expense_product_combo (self):
		combo = self.builder.get_object ('comboboxtext1')
		combo.remove_all()
		self.cursor.execute ("SELECT id, name FROM products "
							"WHERE expense = True")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			combo.append(str(product_id), product_name)

	def expense_spinbutton_value_changed (self, spinbutton):
		product = self.builder.get_object('comboboxtext1').get_active_id()
		button = self.builder.get_object('button6')
		if product == None:
			button.set_label("No product selected")
			button.set_sensitive(False)
			return
		button.set_label("Add to Invoice")
		button.set_sensitive(True)

	def expense_reason_combo_changed (self, combo):
		value = self.builder.get_object('spinbutton2').get_value()
		button = self.builder.get_object('button6')
		if value == 0.00:
			button.set_label("Amount is 0.00")
			button.set_sensitive(False)
			return
		button.set_label("Add to Invoice")
		button.set_sensitive(True)

	def add_expense_to_invoice_clicked (self, button):
		from purchase_order_window import add_expense_to_po
		product_id = self.builder.get_object(
										'comboboxtext1').get_active_id()
		amount = self.builder.get_object('spinbutton2').get_value()
		add_expense_to_po (self.db, self.purchase_order_id, product_id, amount)
		self.populate_purchase_order_items_store ()
		self.builder.get_object('comboboxtext1').set_active(-1)
		self.builder.get_object('spinbutton2').set_value(0.00)

	def calculate_cost_clicked (self, button):
		self.cursor.execute("SELECT SUM(price) FROM purchase_order_line_items "
							"JOIN products "
							"ON purchase_order_line_items.product_id "
							"= products.id "
							"WHERE purchase_order_id = %s AND expense = True",
							(self.purchase_order_id,))
		expense = self.cursor.fetchone()[0]
		if expense == None:
			return
		self.cursor.execute("SELECT SUM(qty) FROM purchase_order_line_items "
							"JOIN products "
							"ON purchase_order_line_items.product_id "
							"= products.id "
							"WHERE purchase_order_id = %s AND expense = False",
							(self.purchase_order_id,))
		qty = self.cursor.fetchone()[0]
		expense_adder = expense / qty
		for index, row in enumerate (self.purchase_order_items_store):
			if row[10] == True: #expense product
				continue
			calculated_cost = Decimal(row[5]) + expense_adder
			row[9] = float(calculated_cost)
			self.check_current_cost (index)

	def save_invoice_button_clicked (self, button):
		invoice_number = self.builder.get_object('entry6').get_text()
		self.cursor.execute("UPDATE purchase_orders "
							"SET (amount_due, invoiced, total, "
								"invoice_description) = "
							"(%s, True, %s, %s) WHERE id = %s", 
							(self.total, self.total, invoice_number, 
							self.purchase_order_id))
		self.populate_po_combobox ()
		post_purchase_order (self.db, self.total, 
														self.purchase_order_id)
		self.cursor.execute("SELECT accrual_based FROM settings")
		if self.cursor.fetchone()[0] == True:
			post_purchase_order_accounts (self.db, self.purchase_order_id, 
											datetime.today())
		self.window.hide()
		self.db.commit()

	def save_and_pay_invoice(self, widget):
		self.save_invoice()
		import vendor_payment
		vendor_payment.GUI(self.purchase_order_id)

	def focus (self, window, event):
		self.populate_expense_account_store ()

	def populate_expense_account_store (self):
		self.expense_account_store.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE expense_account = True")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.expense_account_store.append([str(account_number), account_name])

	def populate_po_combobox (self):
		name_combo = self.builder.get_object('combobox1') 
		self.cursor.execute("SELECT po.id, po.name, c.name "
							"FROM purchase_orders AS po "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"WHERE (canceled, invoiced, closed) = "
							"(False, False, True) ORDER by po.id" )
		for row in self.cursor.fetchall():
			serial = row[0]
			po = row[1]
			vendor_name = "Vendor: "+ row[2]
			self.po_store.append([str(serial),po, vendor_name])
		
	def po_combobox_changed (self, combo): 
		po_id = combo.get_active_id()
		if po_id == None:
			return
		path = combo.get_active()
		vendor_name = self.po_store[path][2]
		self.builder.get_object('entry6').set_text(vendor_name.split(":")[1])
		self.purchase_order_id = po_id
		self.populate_purchase_order_items_store ()
		self.builder.get_object("button7").set_sensitive(True)

	def populate_purchase_order_items_store (self):
		self.purchase_order_items_store.clear()
		self.cursor.execute("SELECT poli.id, qty, p.id, p.name, remark, price, "
							"ext_price, a.expense_account, a.name, expense "
							"FROM purchase_order_line_items AS poli "
							"JOIN products AS p ON p.id = poli.product_id "
							"LEFT JOIN gl_accounts AS a "
							"ON a.number = poli.expense_account "
							"WHERE purchase_order_id = (%s) ORDER BY poli.id", 
							(self.purchase_order_id, ))
		for row in self.cursor.fetchall() :
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			remark = row[4]
			price = row[5]
			ext_price = row[6]
			expense_account = row[7]
			expense_account_name = row[8]
			expense = row[9]
			calculated_cost = price
			if expense == True:
				calculated_cost = 0.00
			self.purchase_order_items_store.append([row_id, qty, product_id, 
												product_name, remark, price, 
												ext_price, expense_account, 
												expense_account_name, 
												calculated_cost, expense])
		self.calculate_totals ()

	def check_expense_accounts (self):
		for row in self.purchase_order_items_store:
			if row[7] == 0:
				button = self.builder.get_object('button5')
				button.set_label("Missing expense account")
				button.set_sensitive(False)
				self.builder.get_object('button2').set_sensitive(False)
				return
			continue
		else:
			button = self.builder.get_object('button5')
			button.set_label("Save as invoice")
			button.set_sensitive(True)
			self.builder.get_object('button2').set_sensitive(True)

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = model.get_value(iter1, 1)
		cellrenderer.set_property("text" , str(qty))

	def price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = model.get_value(iter1, 5)
		cellrenderer.set_property("text" , str(price))

	def ext_price_cell_func(self, column, cellrenderer, model, iter1, data):
		ext_price = model.get_value(iter1, 6)
		cellrenderer.set_property("text" , str(ext_price))

	def qty_edited(self, widget, path, text):
		t = Decimal(text).quantize(self.qty_places, rounding = ROUND_HALF_UP)
		self.purchase_order_items_store[path][1] = t
		self.calculate_row_amounts (path)

	def ext_price_edited (self, renderer, path, text):
		ext_price = Decimal(text)
		self.purchase_order_items_store[path][6] = ext_price
		self.calculate_totals ()
		self.save_line_item (path)

	def calculate_row_amounts (self, path):
		line = self.purchase_order_items_store [path]
		qty = line[1]
		price = line[5]
		ext_price = price * qty
		q = Decimal(10) ** -2
		line[6] = Decimal(ext_price).quantize(q)
		self.calculate_totals ()
		self.save_line_item (path)

	def remark_edited(self, widget, path, text):
		self.purchase_order_items_store[path][4] = text
		self.save_line_item (path)

	def price_edited(self, widget, path, text):
		t = Decimal(text).quantize(self.price_places, rounding = ROUND_HALF_UP)
		self.purchase_order_items_store[path][5] = t
		self.calculate_row_amounts (path)
		self.check_current_cost(path)

	def save_line_item (self, path):
		line = self.purchase_order_items_store[path]
		row_id = line[0]
		qty = line[1]
		remarks = line[4]
		price = line[5]
		ext_price = line[6]
		expense_account_id = line[7]
		self.cursor.execute("UPDATE purchase_order_line_items "
							"SET (qty, remark, price, ext_price) = "
							"(%s, %s, %s, %s) WHERE id = %s", 
							(qty, remarks, price, ext_price, row_id))
		self.db.commit()
		
	def check_current_cost(self, path):
		self.product_id = self.purchase_order_items_store[path][2]
		product_name = self.purchase_order_items_store[path][3]
		self.builder.get_object('label12').set_label(product_name)
		new_cost = self.purchase_order_items_store[path][5]
		self.cursor.execute("SELECT cost FROM products "
							"WHERE id = %s", (self.product_id,))
		current_cost = self.cursor.fetchone()[0]
		self.builder.get_object('spinbutton1').set_value(current_cost)
		# set the current cost first and the new cost later
		cost_formatted = '${:,.2f}'.format(current_cost)
		self.builder.get_object('label13').set_label(cost_formatted)
		#check if cost went up by any amount, or down by set percentage
		if new_cost > current_cost or \
			new_cost < (current_cost - (current_cost * self.cost_decrease)) :
			self.load_product_terms_prices()
			self.builder.get_object('spinbutton1').set_value(new_cost)
			# set the new cost afterwards to update all the selling prices
			dialog = self.builder.get_object('cost_update_dialog')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				self.save_product_terms_prices ()

	def expense_account_combo_changed (self, renderer, path, tree_iter):
		account_number = self.expense_account_store.get_value(tree_iter, 0)
		account_name = self.expense_account_store.get_value(tree_iter, 1)
		self.purchase_order_items_store[path][7] = int(account_number)
		self.purchase_order_items_store[path][8] = account_name
		row_id = self.purchase_order_items_store[path][0]
		self.cursor.execute("UPDATE purchase_order_line_items "
							"SET expense_account = %s WHERE id = %s", 
							(account_number, row_id))
		self.db.commit()
		self.calculate_totals ()

	def calculate_totals(self):
		self.total = Decimal()
		for item in self.purchase_order_items_store:
			self.total += item[6]
		total = '${:,.2f}'.format(self.total)
		self.builder.get_object('entry4').set_text(total)
		self.check_expense_accounts ()

	def populate_terms_listbox (self):
		listbox = self.builder.get_object('listbox2')
		cost_spinbutton = self.builder.get_object('spinbutton1')
		cost = cost_spinbutton.get_text()
		self.cursor.execute("SELECT id, name, markup_percent FROM terms_and_discounts ORDER BY name")
		for row in self.cursor.fetchall():
			terms_id = row[0]
			terms_name = row[1]
			terms_markup = row[2]
			terms_id_label = Gtk.Label(str(terms_id), xalign=0)
			terms_id_label.set_no_show_all(True)
			terms_name_label = Gtk.Label(terms_name, xalign=1)
			markup_spinbutton = Gtk.SpinButton.new_with_range(0.00, 5000.00, 1.00)
			markup_spinbutton.set_digits(2)
			markup_spinbutton.set_value(terms_markup)
			margin = (float(terms_markup) / 100) * float(cost)
			sell_price = margin + float(cost)
			sell_spinbutton = Gtk.SpinButton.new_with_range(0.00, 100000.00, 1.00)
			sell_spinbutton.set_digits(2)
			sell_spinbutton.set_value(sell_price)
			cost_spinbutton.connect('value-changed', self.cost_changed, markup_spinbutton, sell_spinbutton, terms_id)
			markup_spinbutton.connect('value-changed', self.markup_changed, sell_spinbutton, terms_id)
			sell_spinbutton.connect('value-changed', self.sell_changed, markup_spinbutton, terms_id)
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
			hbox.pack_start(terms_id_label, False, False, 5)
			hbox.pack_start(terms_name_label, True, False, 5)
			hbox.pack_end(sell_spinbutton, False, False, 5)
			hbox.pack_end(markup_spinbutton, False, False, 5)
			list_box_row = Gtk.ListBoxRow()
			list_box_row.add(hbox)
			listbox.add(list_box_row)
		listbox.show_all()

	def cost_changed (self, cost_spin, markup_spin, sell_spin, terms_id):
		cost = self.builder.get_object('spinbutton1').get_text()
		cost = float(cost)
		markup_percent = markup_spin.get_value()
		markup = cost * (markup_percent / 100)
		selling_price = cost + markup
		sell_adjustment = sell_spin.get_adjustment()
		sell_adjustment.set_lower(cost)
		sell_spin.set_value(selling_price)

	def sell_changed (self, sell_spin, markup_spin, term_id):
		cost = self.builder.get_object('spinbutton1').get_text()
		cost = float(cost)
		sell_price = sell_spin.get_value ()
		margin = sell_price - cost
		markup = (margin / cost) * 100
		markup_spin.set_value(markup)
		
	def markup_changed(self, markup_spin, sell_spin, terms_id):
		cost = self.builder.get_object('spinbutton1').get_text()
		cost = float(cost)
		markup = markup_spin.get_value()
		margin = (markup / 100) * cost
		sell_price = margin + cost
		sell_spin.set_value(sell_price)

	def load_product_terms_prices (self):
		cost = self.builder.get_object('spinbutton1').get_text()
		cost = float(cost)
		listbox = self.builder.get_object('listbox2')
		for list_box_row in listbox:
			if list_box_row.get_index() == 0:
				continue # skip the header
			box = list_box_row.get_child()
			widget_list = box.get_children()
			terms_id_label = widget_list[0]
			terms_id = terms_id_label.get_label()
			markup_spin = widget_list[2]
			sell_spin = widget_list[3]
			sell_adjustment = sell_spin.get_adjustment()
			sell_adjustment.set_lower(cost)
			self.cursor.execute("SELECT price FROM products_terms_prices WHERE (product_id, term_id) = (%s, %s)", (self.product_id, terms_id))
			for row in self.cursor.fetchall():
				sell_price = float(row[0])
				sell_spin.set_value(sell_price)
				margin = sell_price - cost
				markup = (margin / cost) * 100
				markup_spin.set_value(markup)
				break
			else:
				self.cursor.execute("SELECT markup_percent FROM terms_and_discounts WHERE id = %s", (terms_id,))
				markup = float(self.cursor.fetchone()[0])
				markup_spin.set_value(markup)
				margin = (markup / 100) * cost
				sell_price = margin + cost
				sell_spin.set_value(sell_price)

	def save_product_terms_prices (self):
		cost = self.builder.get_object('spinbutton1').get_value()
		self.cursor.execute("UPDATE products SET cost = %s WHERE id = %s", (cost, self.product_id))
		listbox = self.builder.get_object('listbox2')
		for list_box_row in listbox:
			if list_box_row.get_index() == 0:
				continue # skip the header
			box = list_box_row.get_child()
			widget_list = box.get_children()
			terms_id_label = widget_list[0]
			terms_id = terms_id_label.get_label()
			sell_spin = widget_list[3]
			sell_price = sell_spin.get_value()
			self.cursor.execute("SELECT id FROM products_terms_prices WHERE (product_id, term_id) = (%s, %s)", (self.product_id, terms_id))
			for row in self.cursor.fetchall():
				_id_ = row[0]
				self.cursor.execute("UPDATE products_terms_prices SET price = %s WHERE id = %s", (sell_price, _id_))
				break
			else:
				self.cursor.execute("INSERT INTO products_terms_prices (product_id, term_id, price) VALUES (%s, %s, %s)", (self.product_id, terms_id, sell_price))
		self.db.commit()

	def attach_button_clicked (self, button):
		dialog = self.builder.get_object('scan_dialog')
		self.builder.get_object('button8').set_sensitive (False)
		combo = self.builder.get_object('combobox2')
		combo.set_active(-1)
		combo.set_sensitive(True)
		chooser = self.builder.get_object('filechooserbutton1')
		chooser.unselect_all()
		chooser.set_sensitive(True)
		result = dialog.run()
		self.builder.get_object('pdf_opt_result_buffer').set_text('', -1)
		if result == Gtk.ResponseType.ACCEPT:
			if self.attach_origin == 1:
				self.scan_file()
			elif self.attach_origin == 2:
				self.attach_file_from_disk()
		dialog.hide()

	def scanner_combo_changed (self, combo):
		self.builder.get_object('filechooserbutton1').set_sensitive (False)
		self.attach_origin = 1
		self.builder.get_object('button8').set_sensitive (True)

	def filechooser_file_set (self, chooser):
		if os.path.exists("/tmp/opt.pdf"):
			os.remove("/tmp/opt.pdf")
		self.spinner = self.builder.get_object('spinner1')
		self.spinner.start()
		self.spinner.set_visible(True)
		self.result_buffer = self.builder.get_object('pdf_opt_result_buffer')
		self.result_buffer.set_text('', -1)
		self.sw = self.builder.get_object('scrolledwindow3')
		file_a = chooser.get_filename()
		cmd = "./src/pdf_opt/pdfsizeopt '%s' '/tmp/opt.pdf'" % file_a
		p = Popen(cmd, stdout = PIPE,
						stderr = STDOUT,
						stdin = PIPE,
						shell = True)
		self.io_id = GObject.io_add_watch(p.stdout, GObject.IO_IN, self.optimizer_thread)
		GObject.io_add_watch(p.stdout, GObject.IO_HUP, self.thread_finished)

	def thread_finished (self, stdout, condition):
		GObject.source_remove(self.io_id)
		stdout.close()
		if os.path.exists("/tmp/opt.pdf"):
			self.builder.get_object('combobox2').set_sensitive (False)
			self.builder.get_object('button8').set_sensitive (True)
			self.spinner.stop()
			self.spinner.set_visible(False)
			self.attach_origin = 2

	def optimizer_thread (self, stdout, condition):
		line = stdout.readline()
		line = line.decode(encoding="utf-8", errors="strict")
		adj = self.sw.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())
		iter_ = self.result_buffer.get_end_iter()
		self.result_buffer.insert(iter_, line, -1)
		return True

	def scan_file (self):
		device_address = self.builder.get_object("combobox2").get_active_id()
		device = sane.open(device_address)
		document = device.scan()
		document.save("/tmp/opt.pdf")
		self.attach_file_from_disk ()

	def attach_file_from_disk (self):
		f = open("/tmp/opt.pdf",'rb')
		file_data = f.read ()
		binary = psycopg2.Binary (file_data)
		f.close()
		self.cursor.execute("UPDATE purchase_orders SET attached_pdf = %s "
							"WHERE id = %s", (binary, self.purchase_order_id))
		self.db.commit()

	def expense_products_clicked (self, button):
		self.populate_expense_products_store ()
		dialog = self.builder.get_object("expense_products_dialog")
		dialog.run()
		dialog.hide()
		self.populate_expense_product_combo()

	def populate_expense_products_store (self):
		self.expense_products_store.clear()
		self.cursor.execute("SELECT p.id, p.name, cost, "
							"default_expense_account, a.name "
							"FROM products AS p LEFT JOIN gl_accounts "
							"AS a ON a.number = p.default_expense_account "
							"WHERE (deleted, expense) = (False, True)")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name  = row[1]
			cost = row[2]
			expense_account = row[3]
			expense_account_name = row[4]
			self.expense_products_store.append([product_id, product_name, 
												cost, expense_account, 
												expense_account_name])
		self.check_expense_accounts ()

	def product_expense_account_combo_changed (self, combo, path, iter_):
		expense_account = self.expense_account_store[iter_][0]
		expense_account_name = self.expense_account_store[iter_][1]
		self.expense_products_store[path][3] = int(expense_account)
		self.expense_products_store[path][4] = expense_account_name
		self.save_expense_product (path)

	def product_expense_name_renderer_edited (self, entry, path, text):
		self.expense_products_store[path][1] = text
		self.save_expense_product (path)

	def product_expense_spin_value_edited (self, spin, path, value):
		self.expense_products_store[path][2] = float(value)
		self.save_expense_product (path)

	def save_expense_product (self, path):
		product_id = self.expense_products_store[path][0]
		product_name = self.expense_products_store[path][1]
		product_cost = self.expense_products_store[path][2]
		expense_account = self.expense_products_store[path][3]
		if expense_account == 0:
			expense_account = None
		self.cursor.execute("UPDATE products SET (name, cost, default_expense_account) = (%s, %s, %s) WHERE id = %s", (product_name, product_cost, expense_account, product_id))
		self.db.commit()

	def new_expense_product_clicked (self, button):
		self.cursor.execute("INSERT INTO products (name, cost, expense) VALUES ('New expense product', 0.00, True)")
		self.db.commit()
		self.populate_expense_products_store ()

	def delete_expense_product_clicked (self, button):
		model, path = self.builder.get_object("treeview-selection2").get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		try:
			self.cursor.execute("DELETE FROM products WHERE id = %s ", 
								(product_id,))
		except psycopg2.IntegrityError as e:
			print (e)
			self.db.rollback()
			self.cursor.execute("UPDATE products SET deleted = TRUE "
								"WHERE id = %s ", (product_id,))
		self.db.commit()
		self.populate_expense_products_store ()



		
		
