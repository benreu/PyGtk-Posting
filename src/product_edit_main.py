# product_edit_main.py
# Copyright (C) 2016 reuben
# 
# products.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# products.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
import subprocess, psycopg2
from constants import 	broadcaster, \
						DB, \
						ui_directory, \
						is_admin, \
						help_dir, \
						template_dir
from accounts import 	product_revenue_tree, \
						product_expense_tree, \
						product_inventory_tree, \
						product_revenue_list, \
						product_expense_list, \
						product_inventory_list
from main import get_apsw_connection
import spell_check, barcode_generator


UI_FILE = ui_directory + "/product_edit_main.ui"

def add_non_stock_product (vendor_id, product_name, product_number, #FIXME
							expense_account, revenue_account):
	
	cursor = DB.cursor()
	cursor.execute("SELECT id FROM tax_rates WHERE standard = True")
	default_tax_rate = cursor.fetchone()[0]
	cursor.execute("INSERT INTO products (name, description, unit, cost, "
					" tax_rate_id, deleted, sellable, "
					"purchasable, min_inventory, reorder_qty, tax_exemptible, "
					"manufactured, weight, tare, ext_name, stock, "
					"inventory_enabled, default_expense_account, "
					"revenue_account) "
					"VALUES (%s, '', 1, 1.00, "
					"%s, False, False, True, 0, 0, True, False, 0.00, 0.00, "
					"'', False, False, %s, %s) RETURNING id", ( product_name, 
					default_tax_rate, expense_account, revenue_account))
	product_id = cursor.fetchone()[0]
	cursor.execute("UPDATE products SET barcode = %s WHERE id = %s", 
					(product_id, product_id))
	cursor.execute("INSERT INTO vendor_product_numbers "
					"(vendor_sku, vendor_id, product_id, vendor_barcode) "
					"VALUES (%s, %s, %s, '')", 
					(product_number, vendor_id, product_id))
	DB.commit()
	cursor.close()
	return product_id

class Item(object):#this is used by py3o library see their example for more info
	pass

class ProductEditMainGUI (Gtk.Builder):
	product_id = 0
	def __init__(self, product_overview = None):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.product_overview = product_overview
		self.set_models ()
		textview = self.get_object('textview1')
		spell_check.add_checker_to_widget (textview)
		self.treeview = self.get_object('treeview2')
		self.populate_terms_listbox()
		self.populate_account_combos ()
		self.set_window_layout_from_settings ()
		self.window = self.get_object('window')
		self.window.show_all()
		GLib.idle_add(self.window.set_position, Gtk.WindowPosition.NONE)

	def set_models (self):
		self.get_object('combobox1').set_model(product_expense_tree)
		self.get_object('combobox2').set_model(product_revenue_tree)
		self.get_object('combobox3').set_model(product_inventory_tree)
		comp = self.get_object('expense_completion')
		comp.set_model(product_expense_list)
		comp.set_match_func(self.account_match_func, product_expense_list)
		comp = self.get_object('inventory_completion')
		comp.set_model(product_inventory_list)
		comp.set_match_func(self.account_match_func, product_inventory_list)
		comp = self.get_object('revenue_completion')
		comp.set_model(product_revenue_list)
		comp.set_match_func(self.account_match_func, product_revenue_list)

	def set_window_layout_from_settings (self):
		sqlite = get_apsw_connection ()
		c = sqlite.cursor()
		c.execute("SELECT size FROM product_edit "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT size FROM product_edit "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.get_object('window').resize(width, height)
		sqlite.close()

	def save_window_layout_clicked (self, button):
		sqlite = get_apsw_connection ()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO product_edit (widget_id, size) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO product_edit (widget_id, size) "
					"VALUES ('window_height', ?)", (height,))
		sqlite.close()

	def destroy(self, window):
		self.window = None
		DB.rollback() # unlock the row, in case the user didn't save

	def help_button_activated (self, menuitem):
		subprocess.Popen(["yelp", help_dir + "/products.page"])
	
	def widget_focus_in (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)

	def account_match_func(self, completion, key, tree_iter, account):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in account[tree_iter][1].lower():
				return False
		return True

	def populate_account_combos(self):
		c = DB.cursor()
		tax_combobox = self.get_object('comboboxtext4')
		current_tax = tax_combobox.get_active_id()
		tax_combobox.remove_all()
		c.execute("SELECT id, name FROM tax_rates "
							"WHERE exemption = False ORDER BY name")
		for item in c.fetchall():
			tax_combobox.append(str(item[0]),item[1])
		if current_tax != None:
			tax_combobox.set_active_id(current_tax)
		c.close()
		DB.rollback()

	def tax_window(self, widget):
		import tax_rates
		tax_rates.TaxRateGUI()

	def purchasable_checkbutton_clicked(self, widget):
		if widget.get_active() == True:
			self.get_object('checkbutton3').set_active(False)

	def manufactured_checkbutton_clicked(self, widget):
		if widget.get_active() == True:
			self.get_object('checkbutton5').set_active(False)

	def populate_terms_listbox (self):
		listbox = self.get_object('listbox2')
		cost_spinbutton = self.get_object('spinbutton1')
		cost = cost_spinbutton.get_text()
		c = DB.cursor()
		c.execute("SELECT id, name, markup_percent "
							"FROM customer_markup_percent ORDER BY name")
		for row in c.fetchall():
			terms_id = row[0]
			terms_name = row[1]
			terms_markup = row[2]
			terms_id_label = Gtk.Label(label = str(terms_id), xalign=0)
			terms_id_label.set_visible(False)
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
		c.close()
		DB.rollback()

	def cost_changed (self, cost_spin, markup_spin, sell_spin, terms_id):
		cost = self.get_object('spinbutton1').get_value()
		markup_percent = markup_spin.get_value()
		markup = cost * (markup_percent / 100)
		selling_price = cost + markup
		sell_adjustment = sell_spin.get_adjustment()
		sell_adjustment.set_lower(cost)
		sell_spin.set_value(selling_price)

	def sell_changed (self, sell_spin, markup_spin, markup_id):
		cost = self.get_object('spinbutton1').get_value()
		sell_price = sell_spin.get_value ()
		margin = sell_price - cost
		if cost != 0.00:
			markup = (margin / cost) * 100
			markup_spin.set_value(markup)

	def markup_changed(self, markup_spin, sell_spin, terms_id):
		cost = self.get_object('spinbutton1').get_value()
		markup = markup_spin.get_value()
		margin = (markup / 100) * cost
		sell_price = margin + cost
		sell_spin.set_value(sell_price)

	def save_product_terms_prices (self):
		c = DB.cursor()
		cost = self.get_object('spinbutton1').get_value()
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
			c.execute("INSERT INTO products_markup_prices "
						"(product_id, markup_id, price) VALUES (%s, %s, %s) "
						"ON CONFLICT (product_id, markup_id) "
						"DO UPDATE SET price = %s "
						"WHERE (products_markup_prices.product_id, "
								"products_markup_prices.markup_id) = (%s, %s)", 
						(self.product_id, terms_id, sell_price,
						sell_price, self.product_id, terms_id))
		c.close()

	def load_product_terms_prices (self):
		c = DB.cursor()
		cost = self.get_object('spinbutton1').get_value()
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
			c.execute("SELECT price FROM products_markup_prices "
								"WHERE (product_id, markup_id) = (%s, %s)", 
								(self.product_id, terms_id))
			for row in c.fetchall():
				sell_price = float(row[0])
				sell_spin.set_value(sell_price)
				margin = sell_price - cost
				if cost != 0.00:
					markup = (margin / cost) * 100
					markup_spin.set_value(markup)
				break
			else:
				c.execute("SELECT markup_percent "
									"FROM customer_markup_percent WHERE id = %s", 
									(terms_id,))
				markup = float(c.fetchone()[0])
				markup_spin.set_value(markup)
				margin = (markup / 100) * cost
				sell_price = margin + cost
				sell_spin.set_value(sell_price)
		c.close()

	def cancel_clicked (self, button):
		self.window.destroy()

	def adjust_inventory_clicked (self, button):
		from inventory import inventory_adjustment
		inventory_adjustment.InventoryAdjustmentGUI(self.product_id)
			
	def window_key_press_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if event.get_state() & Gdk.ModifierType.CONTROL_MASK: #Control held down
			if keyname == "q":
				window.destroy()
		
	def product_name_changed (self, editable):
		self.window.set_title(editable.get_text())

	def select_product (self, product_id):
		self.product_id = product_id
		c = DB.cursor()
		try:
			c.execute("SELECT name, description, barcode, unit, "
						"cost, tax_rate_id, sellable, purchasable, "
						"min_inventory, reorder_qty, tax_exemptible, "
						"manufactured, weight, tare, ext_name, "
							"(SELECT name FROM gl_accounts "
							"WHERE number = p.default_expense_account), "
						"default_expense_account, "
							"(SELECT name FROM gl_accounts "
							"WHERE number = p.revenue_account), "
						"p.revenue_account, "
							"COALESCE ((SELECT name FROM gl_accounts "
							"WHERE number = p.inventory_account), ''), "
						"p.inventory_account, "
						"manufacturer_sku, job, invoice_serial_numbers, stock "
						"FROM products AS p "
						"WHERE id = %s FOR UPDATE NOWAIT", (self.product_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			c.close()
			error = str(e) + "Hint: somebody else is editing this product"
			self.show_message (error)
			self.window.destroy()
			return False
		for row in c.fetchall():
			self.get_object('id_label').set_label(str(self.product_id))
			self.get_object('entry1').set_text(row[0])
			self.get_object("textbuffer1").set_text(row[1])
			self.get_object('entry2').set_text(row[2])
			self.get_object('comboboxtext1').set_active_id(str(row[3]))
			self.get_object('spinbutton1').set_value(float(row[4]))
			self.get_object('comboboxtext4').set_active_id(str(row[5]))
			self.get_object('checkbutton4').set_active(row[6])
			self.get_object('checkbutton5').set_active(row[7])
			self.get_object('spinbutton10').set_text(str(row[8]))
			self.get_object('spinbutton11').set_text(str(row[9]))
			self.get_object('checkbutton2').set_active(row[10])
			self.get_object('checkbutton3').set_active(row[11])
			self.get_object('spinbutton13').set_text(str(row[12]))
			self.get_object('spinbutton14').set_text(str(row[13]))
			self.get_object('entry10').set_text(row[14]) 
			#set_active_id does not work with treestore
			self.get_object('expense_entry').set_text(row[15])
			self.expense_account = row[16]
			self.get_object('revenue_entry').set_text(row[17])
			self.revenue_account = row[18]
			self.get_object('inventory_entry').set_text(row[19])
			self.inventory_account = row[20]
			self.get_object('entry13').set_text(row[21])
			self.get_object('checkbutton6').set_active(row[22])
			self.get_object('checkbutton7').set_active(row[23])
			self.get_object('stock_checkbutton').set_active(row[24])
		c.close()
		self.load_product_terms_prices ()

	def expense_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None:
			return
		self.expense_account = account_number

	def expense_completion_match_selected (self, completion, model, treeiter):
		self.expense_account = model[treeiter][0]

	def revenue_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None:
			return
		self.revenue_account = account_number

	def revenue_completion_match_selected (self, completion, model, treeiter):
		self.revenue_account = model[treeiter][0]

	def inventory_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None:
			return
		self.inventory_account = account_number

	def inventory_completion_match_selected (self, completion, model, treeiter):
		self.inventory_account = model[treeiter][0]

	def window_focus_out (self, widget, event):
		self.window.set_urgency_hint(True)

	def window_focus_in (self, widget, event):
		self.window.set_urgency_hint(False)

	def save_clicked (self, button = None):
		name = self.get_object('entry1').get_text()
		ext_name = self.get_object('entry10').get_text()
		barcode = self.get_object('entry2').get_text()
		unit = self.get_object('comboboxtext1').get_active_id()
		cost = self.get_object('spinbutton1').get_text()
		tax = self.get_object('comboboxtext4').get_active_id()
		tax_exemptible = self.get_object('checkbutton2').get_active()
		description_buffer = self.get_object("textbuffer1")
		start = description_buffer.get_start_iter()
		end = description_buffer.get_end_iter()
		description = description_buffer.get_text(start,end,True)
		sellable = self.get_object('checkbutton4').get_active()
		purchasable = self.get_object('checkbutton5').get_active()
		manufactured = self.get_object('checkbutton3').get_active()
		job = self.get_object('checkbutton6').get_active()
		invoice_serial = self.get_object('checkbutton7').get_active()
		min_stock = self.get_object('spinbutton10').get_text()
		reorder_qty = self.get_object('spinbutton11').get_text()
		weight = self.get_object('spinbutton13').get_text()
		tare = self.get_object('spinbutton14').get_text()
		manufacturer_number = self.get_object('entry13').get_text()
		stock = self.get_object('stock_checkbutton').get_active()
		c = DB.cursor()
		if self.product_id == 0:  #new product
			try:
				c.execute("INSERT INTO products (name, description, "
							"unit, cost, tax_rate_id, deleted, "
							"sellable, purchasable, min_inventory, "
							"reorder_qty, tax_exemptible, manufactured, "
							"weight, tare, ext_name, stock, "
							"default_expense_account, "
							"inventory_account, revenue_account, "
							"manufacturer_sku, job, "
							"invoice_serial_numbers) "
							"VALUES "
							"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
							"RETURNING id",
							(name, description, unit, cost, tax, 
							False, sellable, purchasable, min_stock, 
							reorder_qty, tax_exemptible, manufactured, 
							weight, tare, ext_name, stock, 
							self.expense_account, 
							self.inventory_account,
							self.revenue_account,
							manufacturer_number, job, 
							invoice_serial))
				self.product_id = c.fetchone()[0]
				if barcode != '':
					c.execute("UPDATE products SET barcode = %s WHERE id = %s",
													(barcode, self.product_id))
			except Exception as e:
				DB.rollback()
				self.show_message(str(e))
				return
			DB.commit()
			self.product_overview.product_id = self.product_id
			self.product_overview.append_product()
			self.product_overview.select_product()
		else:  # just save the existing product
			try:
				if barcode == '':
					barcode = self.product_id
				c.execute("UPDATE products SET (name, description, "
							"barcode, unit, cost, tax_rate_id, sellable, "
							"purchasable, min_inventory, reorder_qty, "
							"tax_exemptible, manufactured, weight, tare, "
							"ext_name, stock, manufacturer_sku, job, "
							"default_expense_account, "
							"inventory_account, revenue_account, "
							"invoice_serial_numbers) = "
							"( %s, %s, %s, %s, %s, "
							"%s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s, %s, %s, %s, %s, %s, %s, %s) "
							"WHERE id = %s",
							(name, description, barcode, unit, cost, tax, 
							sellable, purchasable, min_stock, reorder_qty, 
							tax_exemptible, manufactured, weight, tare, 
							ext_name, stock, manufacturer_number, job, 
							self.expense_account, 
							self.inventory_account,
							self.revenue_account,
							invoice_serial, self.product_id))
			except Exception as e:
				DB.rollback()
				self.show_message(str(e))
		self.save_product_terms_prices()
		DB.commit()
		c.close()
		self.window.destroy()

	def new_product (self):
		c = DB.cursor()
		c.execute("SELECT number, name FROM gl_accounts "
							"WHERE revenue_account = True "
							"ORDER BY number LIMIT 1")
		for row in c.fetchall():
			self.revenue_account = row[0]
			self.get_object('revenue_entry').set_text(row[1])
			break
		else:
			print("No revenue accounts available")
			self.show_message ("No revenue accounts available")
		c.execute("SELECT number, name FROM gl_accounts "
							"WHERE expense_account = True "
							"ORDER BY number LIMIT 1")
		for row in c.fetchall():
			self.expense_account = row[0]
			self.get_object('expense_entry').set_text(row[1])
			break
		else:
			print("No expense accounts available")
			self.show_message ("No expense accounts available")
		self.inventory_account = None
		c.execute("SELECT id FROM tax_rates WHERE standard = True ")
		default_id = c.fetchone()[0]
		self.get_object('comboboxtext4').set_active_id(str(default_id))
		c.close()
		DB.rollback()
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()


