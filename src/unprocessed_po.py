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

from gi.repository import Gtk, GLib, Gdk
from decimal import Decimal, ROUND_HALF_UP
from subprocess import Popen
from datetime import datetime
import psycopg2
import purchase_ordering
from db.transactor import post_purchase_order, post_purchase_order_accounts
from constants import ui_directory, DB

UI_FILE = ui_directory + "/unprocessed_po.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass
	
class GUI(Gtk.Builder):
	purchase_order_id = None
	def __init__(self, po_id = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.purchase_order_items_store = self.get_object('purchase_order_items_store')
		self.expense_account_store = self.get_object('expense_account_store')
		self.po_store = self.get_object('po_store')
		self.populate_expense_account_store ()
		if po_id == None:
			self.populate_po_combobox ()
		else:
			self.purchase_order_id = po_id
			self.populate_purchase_order_items_store ()
			self.get_object("button7").set_sensitive(True)

		self.cursor.execute("SELECT qty_prec, price_prec "
							"FROM settings.purchase_order")
		for row in self.cursor.fetchall():
			qty_prec = row[0]
			price_prec = row[1]
			self.qty_places = Decimal(10) ** -qty_prec
			self.price_places = Decimal(10) ** -price_prec

		self.cursor.execute("SELECT cost_decrease_alert, "
							"request_po_attachment FROM settings")
		for row in self.cursor.fetchall():
			self.cost_decrease = row[0]
			self.request_po_attachment = row[1]
		
		qty_renderer = self.get_object('cellrenderertext1')
		qty_column = self.get_object('treeviewcolumn1')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)
		
		price_renderer = self.get_object('cellrenderertext4')
		price_column = self.get_object('treeviewcolumn4')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)
		
		ext_price_renderer = self.get_object('cellrenderertext5')
		ext_price_column = self.get_object('treeviewcolumn5')
		ext_price_column.set_cell_data_func(ext_price_renderer, self.ext_price_cell_func)

		self.populate_terms_listbox()
		self.populate_expense_products ()
		self.window = self.get_object('window')
		self.window.show_all()

	def spinbutton_focus_in_event (self, entry, event):
		GLib.idle_add(entry.select_region, 0, -1)

	def view_attachment_clicked (self, button):
		self.cursor.execute("SELECT attached_pdf FROM purchase_orders "
							"WHERE id = %s AND attached_pdf IS NOT NULL", 
							(self.purchase_order_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/PO %s Attachment.pdf" % self.purchase_order_id
			with open(file_name,'wb') as f:
				f.write(row[0])
			Popen(["xdg-open", file_name])
		DB.rollback()

	def destroy(self, window):
		self.cursor.close()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup_at_pointer()

	def move_down_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = model.get_iter(path)
		iter_next = model.iter_next(iter_)
		if iter_next == None:
			return
		model.swap(iter_, iter_next)
		self.save_row_ordering()

	def move_up_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = model.get_iter(path)
		iter_prev = model.iter_previous(iter_)
		if iter_prev == None:
			return
		model.swap(iter_, iter_prev)
		self.save_row_ordering()

	def save_row_ordering (self):
		for row_count, row in enumerate (self.purchase_order_items_store):
			row_id = row[0]
			self.cursor.execute("UPDATE purchase_order_items "
								"SET sort = %s WHERE id = %s", 
								(row_count, row_id))
		DB.commit()

	def product_hub_activated (self, menuitem):
		selection = self.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def edit_po_clicked (self, widget):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI(self.purchase_order_id)

	def populate_expense_products (self):
		store = self.get_object ('expense_products_store')
		store.clear()
		self.cursor.execute ("SELECT id::text, name FROM products "
							"WHERE expense = True ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		DB.rollback()

	def expense_spinbutton_value_changed (self, spinbutton):
		product = self.get_object('expense_product_combo').get_active_id()
		button = self.get_object('button6')
		if product == None:
			button.set_label("No product selected")
			button.set_sensitive(False)
			return
		button.set_label("Add to Invoice")
		button.set_sensitive(True)

	def expense_product_combo_changed (self, combo):
		value = self.get_object('spinbutton2').get_value()
		button = self.get_object('button6')
		if value == 0.00:
			button.set_label("Amount is 0.00")
			button.set_sensitive(False)
			return
		button.set_label("Add to Invoice")
		button.set_sensitive(True)

	def add_expense_to_invoice_clicked (self, button):
		from purchase_order_window import add_expense_to_po
		product_id = self.get_object('expense_product_combo').get_active_id()
		amount = self.get_object('spinbutton2').get_value()
		add_expense_to_po (self.purchase_order_id, product_id, amount)
		self.populate_purchase_order_items_store ()
		self.get_object('expense_product_combo').set_active(-1)
		self.get_object('spinbutton2').set_value(0.00)

	def calculate_cost_clicked (self, button):
		self.cursor.execute("SELECT SUM(price) FROM purchase_order_items "
							"JOIN products "
							"ON purchase_order_items.product_id "
							"= products.id "
							"WHERE purchase_order_id = %s AND expense = True",
							(self.purchase_order_id,))
		expense = self.cursor.fetchone()[0]
		if expense == None:
			return
		self.cursor.execute("SELECT SUM(qty) FROM purchase_order_items "
							"JOIN products "
							"ON purchase_order_items.product_id "
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
		DB.rollback()

	def save_invoice_button_clicked (self, button):
		if self.request_po_attachment and not self.attachment:
			dialog = self.get_object('missing_attachment_dialog')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.CANCEL:
				return 
			elif result == 0:
				import pdf_attachment
				paw = pdf_attachment.PdfAttachmentWindow(self.window)
				paw.connect("pdf_optimized", self.optimized_callback)
				return
		invoice_number = self.get_object('entry6').get_text()
		self.cursor.execute("UPDATE purchase_orders "
							"SET (amount_due, invoiced, total, "
								"invoice_description) = "
							"(%s, True, %s, %s) WHERE id = %s", 
							(self.total, self.total, invoice_number, 
							self.purchase_order_id))
		post_purchase_order (self.total, self.purchase_order_id)
		self.cursor.execute("SELECT accrual_based FROM settings")
		if self.cursor.fetchone()[0] == True:
			post_purchase_order_accounts (self.purchase_order_id, 
											datetime.today())
		DB.commit()
		self.window.destroy()

	def save_and_pay_invoice(self, widget):
		self.save_invoice()
		import vendor_payment
		vendor_payment.GUI(self.purchase_order_id)

	def focus (self, window, event):
		self.populate_expense_account_store ()

	def populate_expense_account_store (self):
		self.expense_account_store.clear()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE expense_account = True")
		for row in self.cursor.fetchall():
			self.expense_account_store.append(row)
		DB.rollback()

	def populate_po_combobox (self):
		name_combo = self.get_object('combobox1') 
		self.cursor.execute("SELECT "
								"po.id::text, "
								"po.name, "
								"'Vendor: ' || c.name, "
								"(attached_pdf IS NOT NULL), "
								"COALESCE(po.invoice_description, c.name) "
							"FROM purchase_orders AS po "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"WHERE (canceled, invoiced, closed) = "
							"(False, False, True) ORDER by po.id" )
		for row in self.cursor.fetchall():
			self.po_store.append(row)
		DB.rollback()
		
	def po_combobox_changed (self, combo): 
		po_id = combo.get_active_id()
		if po_id == None:
			return
		path = combo.get_active()
		invoice_description = self.po_store[path][4]
		self.get_object('entry6').set_text(invoice_description)
		self.purchase_order_id = po_id
		self.populate_purchase_order_items_store ()
		self.get_object("button7").set_sensitive(True)
		self.attachment = self.po_store[path][3]
		self.get_object("button15").set_sensitive(self.attachment)

	def populate_purchase_order_items_store (self):
		self.purchase_order_items_store.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"poli.id, "
						"qty, "
						"p.id, "
						"p.name, "
						"remark, "
						"price, "
						"ext_price, "
						"a.expense_account, "
						"a.name, "
						"CASE WHEN expense = TRUE THEN 0.00 ELSE price END, "
						"expense, "
						"order_number "
					"FROM purchase_order_items AS poli "
					"JOIN products AS p ON p.id = poli.product_id "
					"LEFT JOIN gl_accounts AS a "
					"ON a.number = poli.expense_account "
					"WHERE purchase_order_id = (%s) "
					"ORDER BY poli.sort, poli.id", 
					(self.purchase_order_id, ))
		for row in c.fetchall() :
			self.purchase_order_items_store.append(row)
		self.calculate_totals ()
		c.close()
		DB.rollback()

	def po_description_changed (self, editable):
		self.check_all_entries_completed()

	def check_all_entries_completed (self):
		button = self.get_object('button5')
		button.set_sensitive(False)
		if self.get_object('entry6').get_text() == '':
			button.set_label("PO description is blank")
			return
		for row in self.purchase_order_items_store:
			if row[7] == 0:
				button.set_label("Missing expense account")
				self.get_object('button2').set_sensitive(False)
				return
			continue
		button.set_sensitive(True)
		button.set_label("Save as invoice")
		self.get_object('button2').set_sensitive(True)

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
		self.cursor.execute("UPDATE purchase_order_items "
							"SET (qty, remark, price, ext_price) = "
							"(%s, %s, %s, %s) WHERE id = %s", 
							(qty, remarks, price, ext_price, row_id))
		DB.commit()
		
	def check_current_cost(self, path):
		self.product_id = self.purchase_order_items_store[path][2]
		product_name = self.purchase_order_items_store[path][3]
		self.get_object('label12').set_label(product_name)
		new_cost = self.purchase_order_items_store[path][5]
		self.cursor.execute("SELECT cost FROM products "
							"WHERE id = %s", (self.product_id,))
		current_cost = self.cursor.fetchone()[0]
		self.get_object('spinbutton1').set_value(current_cost)
		# set the current cost first and the new cost later
		cost_formatted = '${:,.2f}'.format(current_cost)
		self.get_object('label13').set_label(cost_formatted)
		#check if cost went up by any amount, or down by set percentage
		if new_cost > current_cost or \
			new_cost < (current_cost - (current_cost * self.cost_decrease)) :
			self.load_product_terms_prices()
			self.get_object('spinbutton1').set_value(new_cost)
			# set the new cost afterwards to update all the selling prices
			dialog = self.get_object('cost_update_dialog')
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
		self.cursor.execute("UPDATE purchase_order_items "
							"SET expense_account = %s WHERE id = %s", 
							(account_number, row_id))
		DB.commit()
		self.calculate_totals ()

	def calculate_totals(self):
		self.total = Decimal()
		for item in self.purchase_order_items_store:
			self.total += item[6]
		total = '${:,.2f}'.format(self.total)
		self.get_object('entry4').set_text(total)
		self.check_all_entries_completed ()

	def populate_terms_listbox (self):
		listbox = self.get_object('listbox2')
		cost_spinbutton = self.get_object('spinbutton1')
		cost = cost_spinbutton.get_text()
		self.cursor.execute("SELECT id, name, markup_percent "
							"FROM customer_markup_percent ORDER BY name")
		for row in self.cursor.fetchall():
			terms_id = row[0]
			terms_name = row[1]
			terms_markup = row[2]
			terms_id_label = Gtk.Label(label = str(terms_id), xalign=0)
			terms_id_label.set_no_show_all(True)
			terms_name_label = Gtk.Label(label = terms_name, xalign=1)
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
		DB.rollback()

	def cost_changed (self, cost_spin, markup_spin, sell_spin, terms_id):
		cost = self.get_object('spinbutton1').get_text()
		cost = float(cost)
		markup_percent = markup_spin.get_value()
		markup = cost * (markup_percent / 100)
		selling_price = cost + markup
		sell_adjustment = sell_spin.get_adjustment()
		sell_adjustment.set_lower(cost)
		sell_spin.set_value(selling_price)

	def sell_changed (self, sell_spin, markup_spin, markup_id):
		cost = self.get_object('spinbutton1').get_text()
		cost = float(cost)
		sell_price = sell_spin.get_value ()
		margin = sell_price - cost
		markup = (margin / cost) * 100
		markup_spin.set_value(markup)
		
	def markup_changed(self, markup_spin, sell_spin, terms_id):
		cost = self.get_object('spinbutton1').get_text()
		cost = float(cost)
		markup = markup_spin.get_value()
		margin = (markup / 100) * cost
		sell_price = margin + cost
		sell_spin.set_value(sell_price)

	def load_product_terms_prices (self):
		cost = self.get_object('spinbutton1').get_text()
		cost = float(cost)
		listbox = self.get_object('listbox2')
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
			self.cursor.execute("SELECT price FROM products_markup_prices "
								"WHERE (product_id, markup_id) = (%s, %s)", 
								(self.product_id, terms_id))
			for row in self.cursor.fetchall():
				sell_price = float(row[0])
				sell_spin.set_value(sell_price)
				margin = sell_price - cost
				markup = (margin / cost) * 100
				markup_spin.set_value(markup)
				break
			else:
				self.cursor.execute("SELECT markup_percent "
									"FROM customer_markup_percent "
									"WHERE id = %s", (terms_id,))
				markup = float(self.cursor.fetchone()[0])
				markup_spin.set_value(markup)
				margin = (markup / 100) * cost
				sell_price = margin + cost
				sell_spin.set_value(sell_price)
		DB.rollback()

	def save_product_terms_prices (self):
		cost = self.get_object('spinbutton1').get_value()
		self.cursor.execute("UPDATE products SET cost = %s "
							"WHERE id = %s", (cost, self.product_id))
		listbox = self.get_object('listbox2')
		for list_box_row in listbox:
			if list_box_row.get_index() == 0:
				continue # skip the header
			box = list_box_row.get_child()
			widget_list = box.get_children()
			terms_id_label = widget_list[0]
			terms_id = terms_id_label.get_label()
			sell_spin = widget_list[3]
			sell_price = sell_spin.get_value()
			self.cursor.execute("SELECT id FROM products_markup_prices "
								"WHERE (product_id, markup_id) = (%s, %s)", 
								(self.product_id, terms_id))
			for row in self.cursor.fetchall():
				_id_ = row[0]
				self.cursor.execute("UPDATE products_markup_prices "
									"SET price = %s WHERE id = %s", 
									(sell_price, _id_))
				break
			else:
				self.cursor.execute("INSERT INTO products_markup_prices "
									"(product_id, markup_id, price) "
									"VALUES (%s, %s, %s)", 
									(self.product_id, terms_id, sell_price))
		DB.commit()

	def attach_button_clicked (self, button = None):
		import pdf_attachment
		paw = pdf_attachment.PdfAttachmentWindow(self.window)
		paw.connect("pdf_optimized", self.optimized_callback)

	def optimized_callback (self, pdf_attachment_window):
		pdf_data = pdf_attachment_window.get_pdf ()
		self.cursor.execute("UPDATE purchase_orders "
							"SET attached_pdf = %s "
							"WHERE id = %s", 
							(pdf_data, self.purchase_order_id))
		DB.commit()
		# update the attachment status for this po
		active = self.get_object("combobox1").get_active()
		self.po_store[active][3] = True
		self.get_object("button15").set_sensitive(True)
		self.attachment = True

	def expense_products_clicked (self, button):
		import expense_products
		ep = expense_products.GUI()
		ep.connect('expense-products-changed', self.ep_callback)

	def ep_callback (self, expense_product_gui):
		self.populate_expense_products()

	def window_key_release_event (self, widget, event):
		keyname = Gdk.keyval_name(event.keyval)
		if event.get_state() & Gdk.ModifierType.CONTROL_MASK: #Ctrl held down
			if keyname == "h":
				self.product_hub_activated (None)
			elif keyname == "Down":
				self.move_down_activated (None)
			elif keyname == "Up":
				self.move_up_activated (None)




