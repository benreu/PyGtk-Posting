# products.py
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
import subprocess
import spell_check

UI_FILE = "src/products.ui"

def add_non_stock_product (db, vendor_id, product_name, product_number,
							expense_account, revenue_account):
	
	cursor = db.cursor()
	cursor.execute("SELECT id FROM tax_rates WHERE standard = True")
	default_tax_rate = cursor.fetchone()[0]
	cursor.execute("INSERT INTO products (name, description, unit, cost, "
					"level_1_price, level_2_price, level_3_price, "
					"level_4_price, tax_rate_id, deleted, sellable, "
					"purchasable, min_inventory, reorder_qty, tax_exemptible, "
					"manufactured, weight, tare, ext_name, stock, "
					"inventory_enabled, default_expense_account, "
					"revenue_account) "
					"VALUES (%s, '', 1, 1.00, 1.40, 1.30, 1.20, 1.10, "
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
	db.commit()
	cursor.close()
	return product_id

class Item(object):#this is used by py3o library see their example for more info
	pass

class ProductsGUI:
	def __init__(self, main, product_id = None, product_location_tab = False, 
					manufactured = False):

		self.previous_keyname = None
		self.ascending = False
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.repopulated = False
		self.populating = True
		self.handler_id = main.connect("products_changed", self.populate_product_store)
		self.builder.get_object('combobox1').set_model(main.product_expense_acc)
		self.builder.get_object('combobox2').set_model(main.product_revenue_acc)
		self.builder.get_object('combobox3').set_model(main.product_inventory_acc)

		textview = self.builder.get_object('textview1')
		spell_check.add_checker_to_widget (textview)

		self.exists = True
		self.pane = self.builder.get_object('paned1')

		self.filter_list = ""
		self.treeview = self.builder.get_object('treeview2')
		self.product_store = self.builder.get_object('product_store')
		self.filtered_product_store = self.builder.get_object('filtered_product_store')
		self.filtered_product_store.set_visible_func(self.filter_func)
		
		self.product_id = 0
		self.new_product()
		
		self.populate_product_store()
		self.populate_terms_listbox()
		self.populate_account_combos ()
		self.set_price_listbox_to_default ()
		
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		self.treeview.connect('drag_data_get', self.on_drag_data_get)
		self.treeview.drag_source_set_target_list([dnd])

		if product_location_tab == True:
			self.builder.get_object('notebook1').set_current_page(1)
		if manufactured == True:
			self.builder.get_object('radiobutton3').set_active(True)
		
		window = self.builder.get_object('window')
		window.show_all()
		if product_id != None:
			self.product_id = product_id
			self.select_product()

	def destroy(self, window):
		self.main.disconnect(self.handler_id)
		self.cursor.close()
		self.exists = False

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		product_id = model[path][0]
		string = '1 ' + str(product_id) 
		data.set_text(string, -1)

	def location_clicked (self, button):
		import locations
		locations.LocationsGUI(self.db)

	def help_button_activated (self, menuitem):
		subprocess.Popen("yelp ./help/products.page", shell = True)

	def print_label(self, widget):
		location_id = self.builder.get_object('comboboxtext6').get_active_id()
		label = Item()
		self.cursor.execute("SELECT aisle, cart, rack, shelf, cabinet, drawer, "
							"bin FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)", 
							(self.product_id, location_id))
		for row in self.cursor.fetchall():
			label.aisle = row[0]
			label.cart = row[1]
			label.rack = row[2]
			label.shelf = row[3]
			label.cabinet = row[4]
			label.drawer = row[5]
			label.bin = row[6]
			break
		else:
			label.aisle = ''
			label.cart = ''
			label.rack = ''
			label.shelf = ''
			label.cabinet = ''
			label.drawer = ''
			label.bin = ''
		self.cursor.execute("SELECT name, description, barcode FROM products "
							"WHERE id = (%s)",[self.product_id])
		for row in self.cursor.fetchall():
			label.name= row[0]
			label.description = row[1]
			barcode = row[2]
		self.cursor.execute("SELECT id FROM terms_and_discounts "
							"WHERE standard = True")
		default_term_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT price FROM products_terms_prices "
							"WHERE (product_id, term_id) = (%s, %s)", 
							(self.product_id, default_term_id))
		for row in self.cursor.fetchall():
			label.price = '${:,.2f}'.format(row[0])
			break
		else:
			cost = self.builder.get_object('spinbutton1').get_value()
			self.cursor.execute("SELECT markup_percent "
								"FROM terms_and_discounts WHERE id = %s", 
								(term_id,))
			markup = float(self.cursor.fetchone()[0])
			margin = (markup / 100) * cost
			label.price = '${:,.2f}'.format(margin + cost)
		import barcode_generator
		bc = barcode_generator.Code128()
		bc.createImage(barcode, 20)
		data = dict(label = label)
		from py3o.template import Template
		label_file = "/tmp/product_label.odt"
		t = Template("templates/product_label_template.odt", label_file )
		t.set_image_path('staticimage.logo', '/tmp/product_barcode.png')
		t.render(data) #the self.data holds all the info
		subprocess.Popen("soffice " + label_file, shell = True)

	def product_column_sorted(self, treeview_column):
		if self.ascending == True:
			treeview_column.set_sort_order(Gtk.SortType.ASCENDING )
			self.product_store.set_sort_column_id (1, Gtk.SortType.ASCENDING )
		else:
			treeview_column.set_sort_order(Gtk.SortType.DESCENDING )
			self.product_store.set_sort_column_id (1, Gtk.SortType.DESCENDING )
		self.ascending = not self.ascending

	def vendor_combo_changed(self, widget = None):
		if self.product_id == 0: 
			return
		self.populating = True
		vendor_id = self.builder.get_object('comboboxtext2').get_active_id()
		if vendor_id != None :
			self.builder.get_object('label16').set_label('$0.00')
			sku_entry = self.builder.get_object('entry4')
			barcode_entry = self.builder.get_object('entry3')
			qty_entry = self.builder.get_object('spinbutton2')
			price_entry = self.builder.get_object('spinbutton3')
			self.cursor.execute("SELECT id, vendor_sku, vendor_barcode, qty, "
								"price "
								"FROM vendor_product_numbers "
								"WHERE (vendor_id, product_id) = (%s, %s) "
								"LIMIT 1", 
								(vendor_id, self.product_id))
			for row in self.cursor.fetchall():
				self.sku_id = row[0]
				sku_entry.set_text(row[1])
				barcode_entry.set_text(row[2])
				qty_entry.set_value(int(row[3]))
				price_entry.set_value(float(row[4]))
				self.calculate_piece_cost ()
				break
			else:  # vendor sku is not in the database
				sku_entry.set_text("")
				barcode_entry.set_text("")
				qty_entry.set_text('0')
				price_entry.set_text('0')
				self.sku_id = 0 # new vendor sku
		self.populating = False

	def vendor_sku_changed(self, entry = None):
		if self.populating == True:
			return
		self.update_vendor_product_info ()

	def vendor_barcode_changed(self, entry = None):
		if self.populating == True:
			return
		self.update_vendor_product_info ()

	def vendor_qty_changed (self, spinbutton):
		self.calculate_piece_cost ()
		if self.populating == True:
			return
		self.update_vendor_product_info ()

	def vendor_price_changed (self, spinbutton):
		self.calculate_piece_cost ()
		if self.populating == True:
			return
		self.update_vendor_product_info ()

	def cost_sell_ratio_changed (self, spinbutton):
		self.calculate_piece_cost ()
		if self.populating == True:
			return
		self.update_vendor_product_info ()

	def calculate_piece_cost (self):
		qty = self.builder.get_object('spinbutton2').get_value()
		price = self.builder.get_object('spinbutton3').get_value()
		ratio = self.builder.get_object('spinbutton4').get_value()
		if price == 0.00 or qty == 0 or ratio == 0.00:
			piece_cost = 0.00
		else:
			piece_cost = round(price / qty, 6)
			piece_cost = piece_cost / ratio
		string = '${:,.6f}'.format(piece_cost)
		self.builder.get_object('label16').set_label(string)

	def apply_individual_cost_clicked (self, button):
		qty = self.builder.get_object('spinbutton2').get_value()
		price = self.builder.get_object('spinbutton3').get_value()
		ratio = self.builder.get_object('spinbutton4').get_value()
		piece_cost = round(price / qty, 6)
		piece_cost = piece_cost / ratio
		self.builder.get_object('spinbutton1').set_value(piece_cost)

	def update_vendor_product_info (self):
		if self.product_id == 0: 
			return # we cannot save vendor info if the product does not exist
		vendor_id = self.builder.get_object('comboboxtext2').get_active_id()
		vendor_sku = self.builder.get_object('entry4').get_text()
		vendor_barcode = self.builder.get_object('entry3').get_text()
		vendor_qty = self.builder.get_object('spinbutton2').get_text()
		vendor_price = self.builder.get_object('spinbutton3').get_text()
		if vendor_sku == '' and vendor_barcode == '' and vendor_qty == '0'\
											and float(vendor_price) == 0.00:
			self.cursor.execute("DELETE FROM vendor_product_numbers "
								"WHERE (vendor_id, product_id) = (%s, %s)",
								(vendor_id, self.product_id))
								# delete any blank vendor info
			return #do not save, no vendor info
		if self.sku_id == 0:
			self.cursor.execute("INSERT INTO vendor_product_numbers "
								"(vendor_sku, vendor_id, vendor_barcode, "
								"product_id, qty, price) "
								"VALUES (%s, %s, %s, %s, %s, %s) "
								"RETURNING id", (vendor_sku, vendor_id, 
								vendor_barcode, self.product_id, vendor_qty, 
								vendor_price))
			self.sku_id = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE vendor_product_numbers SET "
								"(vendor_sku, vendor_id, vendor_barcode, "
								"qty, price) = "
								"(%s, %s, %s, %s, %s) WHERE id = %s", 
								(vendor_sku, vendor_id, vendor_barcode, 
								vendor_qty, vendor_price, self.sku_id))
		self.db.commit()

	def focus_in_populate_comboboxes(self, widget, event):
		#self.populate_product_store ()
		self.populate_account_combos ()

	def populate_account_combos(self):
		tax_combobox = self.builder.get_object('comboboxtext4')
		current_tax = tax_combobox.get_active_id()
		tax_combobox.remove_all()
		self.cursor.execute("SELECT id, name FROM tax_rates ORDER BY name")
		for item in self.cursor.fetchall():
			tax_combobox.append(str(item[0]),item[1])
		if current_tax != None:
			tax_combobox.set_active_id(current_tax)
		vendor_combobox = self.builder.get_object('comboboxtext2')
		current_vendor = vendor_combobox.get_active_id()
		vendor_combobox.remove_all()
		self.cursor.execute("SELECT id, name FROM contacts "	
							"WHERE (deleted, vendor) = (False, True) "
							"ORDER BY name")
		for item in self.cursor.fetchall():
			vendor_combobox.append(str(item[0]),item[1])
		vendor_combobox.set_active_id(current_vendor)
		location_combo = self.builder.get_object('comboboxtext6')
		active_location = location_combo.get_active()
		location_combo.remove_all()
		self.cursor.execute("SELECT id, name FROM locations ORDER BY name")
		for row in self.cursor.fetchall():
			location_id = row[0]
			location_name = row[1]
			location_combo.append(str(location_id), location_name)
		if active_location  == -1:
			active_location = 0
		location_combo.set_active(active_location)
		
	def unit_combobox_changed(self, widget):
		self.builder.get_object('comboboxtext1').get_active_text()

	def contacts_window(self, widget):
		import contacts
		contacts.GUI(self.main)

	def tax_window(self, widget):
		import tax_rates
		tax_rates.TaxRateGUI(self.db)

	def filter_func(self, model, tree_iter, r):
		for text in self.filter_list:
			if text not in model[tree_iter][1].lower():
				return False
		return True

	def search_changed(self, search_entry):
		self.populating = True
		filter_text = search_entry.get_text()
		self.filter_list = filter_text.split(" ")
		self.filtered_product_store.refilter()
		self.populating = False

	def purchasable_checkbutton_clicked(self, widget):
		if widget.get_active() == True:
			self.builder.get_object('checkbutton3').set_active(False)

	def manufactured_checkbutton_clicked(self, widget):
		if widget.get_active() == True:
			self.builder.get_object('checkbutton5').set_active(False)

	def sellable_checkbutton_clicked (self, checkbutton):
		pass

	def populate_terms_listbox (self):
		listbox = self.builder.get_object('listbox2')
		cost_spinbutton = self.builder.get_object('spinbutton1')
		cost = cost_spinbutton.get_text()
		self.cursor.execute("SELECT id, name, markup_percent "
							"FROM terms_and_discounts ORDER BY name")
		for row in self.cursor.fetchall():
			terms_id = row[0]
			terms_name = row[1]
			terms_markup = row[2]
			terms_id_label = Gtk.Label(str(terms_id), xalign=0)
			terms_id_label.set_visible(False)
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

	def cost_changed (self, cost_spin, markup_spin, sell_spin, terms_id):
		cost = self.builder.get_object('spinbutton1').get_value()
		markup_percent = markup_spin.get_value()
		markup = cost * (markup_percent / 100)
		selling_price = cost + markup
		sell_adjustment = sell_spin.get_adjustment()
		sell_adjustment.set_lower(cost)
		sell_spin.set_value(selling_price)
		#sell_spin.emit('value-changed')
		#print (terms_id, 'cost_changed')
		#self.cursor.execute("UPDATE products SET cost = %s "
		#					"WHERE id = %s", (cost, self.product_id))
		#self.db.commit()

	def sell_changed (self, sell_spin, markup_spin, term_id):
		cost = self.builder.get_object('spinbutton1').get_value()
		sell_price = sell_spin.get_value ()
		margin = sell_price - cost
		markup = (margin / cost) * 100
		markup_spin.set_value(markup)
		if self.product_id == 0 or self.populating == True:
			return
		#print ('update price', self.product_id, sell_price, term_id)
		self.cursor.execute("UPDATE products_terms_prices SET price = %s "
							"WHERE (product_id, term_id) = (%s, %s) "
							"RETURNING id", 
							(sell_price, self.product_id, term_id))
		for row in self.cursor.fetchall():
			break
		else:
			self.cursor.execute("INSERT INTO products_terms_prices "
								"(product_id, term_id, price) "
								"VALUES (%s, %s, %s)", 
								(self.product_id, term_id, sell_price))
		self.db.commit()

	def markup_changed(self, markup_spin, sell_spin, terms_id):
		cost = self.builder.get_object('spinbutton1').get_value()
		markup = markup_spin.get_value()
		margin = (markup / 100) * cost
		sell_price = margin + cost
		sell_spin.set_value(sell_price)

	def set_price_listbox_to_default (self):
		cost = self.builder.get_object('spinbutton1').get_value()
		listbox = self.builder.get_object('listbox2')
		for list_box_row in listbox:
			if list_box_row.get_index() == 0:
				continue # skip the header
			box = list_box_row.get_child()
			widget_list = box.get_children()
			terms_id_label = widget_list[0]
			#terms_id_label.set_visible(False)
			terms_id = terms_id_label.get_label()
			markup_spin = widget_list[2]
			sell_spin = widget_list[3]
			sell_adjustment = sell_spin.get_adjustment()
			sell_adjustment.set_lower(cost)
			self.cursor.execute("SELECT markup_percent "
								"FROM terms_and_discounts WHERE id = %s", 
								(terms_id,))
			markup = float(self.cursor.fetchone()[0])
			markup_spin.set_value(markup)
			margin = (markup / 100) * cost
			sell_price = margin + cost
			sell_spin.set_value(sell_price)

	def load_product_terms_prices (self):
		cost = self.builder.get_object('spinbutton1').get_value()
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
			self.cursor.execute("SELECT price FROM products_terms_prices "
								"WHERE (product_id, term_id) = (%s, %s)", 
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
									"FROM terms_and_discounts WHERE id = %s", 
									(terms_id,))
				markup = float(self.cursor.fetchone()[0])
				markup_spin.set_value(markup)
				margin = (markup / 100) * cost
				sell_price = margin + cost
				sell_spin.set_value(sell_price)
			
	def populate_product_store (self, widget = None, d=None):
		if self.repopulated == True: #block auto-repopulating if we just saved and repopulated
			self.repopulated = False
			return
		self.populating = True
		self.product_store.clear()
		if self.builder.get_object('radiobutton1').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE (deleted, sellable) = (False, True) "
								"OR id = %s ORDER BY name", (self.product_id,))
		elif self.builder.get_object('radiobutton2').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE (deleted, purchasable) = (False, True) "
								"OR id = %s ORDER BY name", (self.product_id,))
		elif self.builder.get_object('radiobutton3').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE (deleted, manufactured) = (False, True) "
								"OR id = %s ORDER BY name", (self.product_id,))
		elif self.builder.get_object('radiobutton4').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE (deleted, kit) = (False, True) "
								"OR id = %s ORDER BY name", (self.product_id,))
		elif self.builder.get_object('radiobutton5').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE (deleted, stock) = (False, False) "
								"OR id = %s ORDER BY name", (self.product_id,))
		elif self.builder.get_object('radiobutton7').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE deleted = True "
								"ORDER BY name")
		else:
			self.cursor.execute("SELECT id, name, ext_name FROM products "
								"WHERE deleted = False "
								"ORDER BY name")
		for row in self.cursor.fetchall():
			serial_number = row[0]
			name = str(row[1])
			ext_name = row[2]
			self.product_store.append([serial_number, name, ext_name])
		self.path = 0
		self.populating = False
		for row in self.filtered_product_store:
			if row[0] == self.product_id: # select the product we had selected before repopulating
				treeview_selection = self.builder.get_object('treeview-selection')
				treeview_selection.select_path(self.path)
				self.treeview.scroll_to_cell(self.path)
				return
			self.path += 1

	def product_treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		import product_hub
		product_hub.ProductHubGUI(self.main, self.product_id)

	def duplicate_product_activated (self, menuitem):
		self.product_id = 0
		self.builder.get_object('entry2').set_text('')
		self.save ()

	def inventory_history_clicked (self, widget):
		from inventory import inventory_history
		inventory_history.InventoryHistoryGUI(self.db, self.product_id)

	def adjust_inventory_clicked (self, button):
		from inventory import inventory_adjustment
		inventory_adjustment.InventoryAdjustmentGUI(self.db, self.product_id)

	def location_entry_changed(self, widget):
		self.builder.get_object('checkbutton1').set_active(True)

	def window_key_press_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == "F12":
			self.builder.get_object('notebook1').next_page()
		elif keyname == "F11":
			self.builder.get_object('notebook1').prev_page()
		if self.previous_keyname == "Control_L":
			if keyname == "q":
				self.builder.get_object('window').destroy()
		self.previous_keyname = keyname

	def product_treeview_cursor_changed (self, treeview):
		if self.populating == True:
			return
		path = treeview.get_cursor().path
		if path == None:
			return
		self.product_id = self.filtered_product_store[path][0]
		self.select_product()

	def product_exemptible_toggled(self, widget):
		if widget.get_active() == True:
			widget.set_label("Tax exemptible")
		else:
			widget.set_label("Not exemptible")

	def location_changed(self, combo):
		self.location_id = combo.get_active_id()
		self.cursor.execute("SELECT * FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)", 
							(self.product_id, self.location_id))
		for row in self.cursor.fetchall():
			self.builder.get_object('entry5').set_text(row[2])
			self.builder.get_object('entry6').set_text(row[3])
			self.builder.get_object('entry7').set_text(row[4])
			self.builder.get_object('entry8').set_text(row[5])
			self.builder.get_object('entry9').set_text(row[6])
			self.builder.get_object('entry11').set_text(row[9])
			self.builder.get_object('entry12').set_text(row[10])
			self.builder.get_object('checkbutton1').set_active(row[7])
			break
		else:
			self.builder.get_object('entry5').set_text('')
			self.builder.get_object('entry6').set_text('')
			self.builder.get_object('entry7').set_text('')
			self.builder.get_object('entry8').set_text('')
			self.builder.get_object('entry9').set_text('')
			self.builder.get_object('entry11').set_text('')
			self.builder.get_object('entry12').set_text('')
			self.builder.get_object('checkbutton1').set_active(False)
		
	def select_product (self):
		self.cursor.execute("SELECT name, description, barcode, unit, "
							"cost, tax_rate_id, sellable, purchasable, "
							"min_inventory, reorder_qty, tax_exemptible, "
							"manufactured, weight, tare, ext_name, "
								"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = default_expense_account), ''), "
								"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = products.revenue_account), ''), "
								"COALESCE ((SELECT name FROM gl_accounts "
								"WHERE number = products.inventory_account), ''), "
							"manufacturer_sku, job, invoice_serial_numbers "
							"FROM products WHERE id = (%s)", (self.product_id,))
		for row in self.cursor.fetchall():
			self.builder.get_object('entry1').set_text(row[0])
			self.builder.get_object("textbuffer1").set_text(row[1])
			self.builder.get_object('entry2').set_text(row[2])
			self.builder.get_object('comboboxtext1').set_active_id(str(row[3]))
			self.product_cost = row[4]
			self.builder.get_object('comboboxtext4').set_active_id(str(row[5]))
			self.builder.get_object('checkbutton4').set_active(row[6])
			self.builder.get_object('checkbutton5').set_active(row[7])
			self.builder.get_object('spinbutton10').set_text(str(row[8]))
			self.builder.get_object('spinbutton11').set_text(str(row[9]))
			self.builder.get_object('checkbutton2').set_active(row[10])
			self.builder.get_object('checkbutton3').set_active(row[11])
			self.builder.get_object('spinbutton13').set_text(str(row[12]))
			self.builder.get_object('spinbutton14').set_text(str(row[13]))
			self.builder.get_object('entry10').set_text(row[14])
			expense_account_name = row[15] #set active id does not work with treestore
			self.builder.get_object('combobox-entry').set_text(expense_account_name)
			revenue_account_name = row[16]
			self.builder.get_object('combobox-entry1').set_text(revenue_account_name)
			inventory_account_name = row[17]
			self.builder.get_object('combobox-entry4').set_text(inventory_account_name)
			self.builder.get_object('entry13').set_text(row[18])
			self.builder.get_object('checkbutton6').set_active(row[19])
			self.builder.get_object('checkbutton7').set_active(row[20])
		
		vendor_combo = self.builder.get_object('comboboxtext2')
		if vendor_combo.get_active() == -1:
			vendor_combo.set_active(0)

		location_id = self.builder.get_object('comboboxtext6').get_active_id()
		self.cursor.execute("SELECT * FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)", 
							(self.product_id, location_id))
		for row in self.cursor.fetchall():
			self.builder.get_object('entry5').set_text(row[2])
			self.builder.get_object('entry6').set_text(row[3])
			self.builder.get_object('entry7').set_text(row[4])
			self.builder.get_object('entry8').set_text(row[5])
			self.builder.get_object('entry9').set_text(row[6])
			self.builder.get_object('entry11').set_text(row[9])
			self.builder.get_object('entry12').set_text(row[10])
			self.builder.get_object('checkbutton1').set_active(row[7])
			break
		else:
			self.builder.get_object('entry5').set_text('')
			self.builder.get_object('entry6').set_text('')
			self.builder.get_object('entry7').set_text('')
			self.builder.get_object('entry8').set_text('')
			self.builder.get_object('entry9').set_text('')
			self.builder.get_object('entry11').set_text('')
			self.builder.get_object('entry12').set_text('')
			self.builder.get_object('checkbutton1').set_active(False)
		self.populating = True
		#explicitly keep the prices from updating (which also saves invalid prices)
		self.builder.get_object('spinbutton1').set_value(self.product_cost)
		self.populating = False
		#now update the prices
		self.load_product_terms_prices ()
		GLib.timeout_add(10, self.vendor_combo_changed )

	def default_expense_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None or self.product_id == 0:
			return
		self.cursor.execute("UPDATE products SET default_expense_account = %s "
							"WHERE id = %s", (account_number, self.product_id))
		self.db.commit()

	def revenue_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None or self.product_id == 0:
			return
		self.cursor.execute("UPDATE products SET revenue_account = %s "
							"WHERE id = %s", (account_number, self.product_id))
		self.db.commit()

	def inventory_account_combo_changed (self, combo):
		account_number = combo.get_active_id()
		if account_number == None or self.product_id == 0:
			return
		self.cursor.execute("UPDATE products SET inventory_account = %s "
							"WHERE id = %s", (account_number, self.product_id))
		self.db.commit()

	def save(self, button = None):
		name = self.builder.get_object('entry1').get_text()
		ext_name = self.builder.get_object('entry10').get_text()
		barcode = self.builder.get_object('entry2').get_text()
		unit = self.builder.get_object('comboboxtext1').get_active_id()
		cost = self.builder.get_object('spinbutton1').get_text()
		tax = self.builder.get_object('comboboxtext4').get_active_id()
		tax_exemptible = self.builder.get_object('checkbutton2').get_active()
		
		description_buffer = self.builder.get_object("textbuffer1")
		start = description_buffer.get_start_iter()
		end = description_buffer.get_end_iter()
		description = description_buffer.get_text(start,end,True)
		
		sellable = self.builder.get_object('checkbutton4').get_active()
		purchasable = self.builder.get_object('checkbutton5').get_active()
		manufactured = self.builder.get_object('checkbutton3').get_active()
		job = self.builder.get_object('checkbutton6').get_active()
		invoice_serial = self.builder.get_object('checkbutton7').get_active()

		min_stock = self.builder.get_object('spinbutton10').get_text()
		reorder_qty = self.builder.get_object('spinbutton11').get_text()

		weight = self.builder.get_object('spinbutton13').get_text()
		weight = float(weight)
		tare = self.builder.get_object('spinbutton14').get_text()
		tare = float(tare)
		manufacturer_number = self.builder.get_object('entry13').get_text()

		rack = self.builder.get_object('entry5').get_text()
		cart = self.builder.get_object('entry6').get_text()
		shelf = self.builder.get_object('entry7').get_text()
		cabinet = self.builder.get_object('entry8').get_text()
		drawer = self.builder.get_object('entry9').get_text()
		aisle = self.builder.get_object('entry11').get_text()
		_bin_ = self.builder.get_object('entry12').get_text()
		locator_visible = self.builder.get_object('checkbutton1').get_active()
		location_id = self.builder.get_object('comboboxtext6').get_active_id()
		
		if self.product_id == 0:
			self.cursor.execute("INSERT INTO products (name, description, "
								"barcode, unit, cost, tax_rate_id, deleted, "
								"sellable, purchasable, min_inventory, "
								"reorder_qty, tax_exemptible, manufactured, "
								"weight, tare, ext_name, stock, revenue_account, "
								"manufacturer_sku, job, invoice_serial_numbers) "
								"VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id",
								(name, description, barcode, unit, cost, tax, 
								False, sellable, purchasable, min_stock, 
								reorder_qty, tax_exemptible, manufactured, 
								weight, tare, ext_name, True, self.new_revenue_account,
								manufacturer_number, job, 
								invoice_serial))
			self.product_id = self.cursor.fetchone()[0]
			if barcode == '':
				barcode = self.product_id
				self.cursor.execute("UPDATE products SET barcode = %s "
									"WHERE id = %s",(barcode, self.product_id))
			self.vendor_sku_changed ()
			self.vendor_barcode_changed()
		else:
			if barcode == '':
				barcode = self.product_id
			self.cursor.execute("UPDATE products SET (name, description, "
								"barcode, unit, cost, tax_rate_id, sellable, "
								"purchasable, min_inventory, reorder_qty, "
								"tax_exemptible, manufactured, weight, tare, "
								"ext_name, stock, manufacturer_sku, job, "
								"invoice_serial_numbers) = "
								"( %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"WHERE id = %s",
								(name, description, barcode, unit, cost, tax, 
								sellable, purchasable, min_stock, reorder_qty, 
								tax_exemptible, manufactured, weight, tare, 
								ext_name, True, manufacturer_number, job, 
								invoice_serial, self.product_id))
			
		self.cursor.execute("SELECT id FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)", 
							(self.product_id, location_id))
		for row in self.cursor.fetchall():
			row_id = row[0]
			self.cursor.execute("UPDATE product_location "
								"SET (aisle, rack, cart, shelf, cabinet, "
								"drawer, bin, locator_visible) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s)"
								"WHERE id = %s", 
								(aisle, rack, cart, shelf, cabinet, drawer, 
								_bin_, locator_visible, row_id))
			break
		else:
			self.cursor.execute("INSERT INTO product_location "
								"(product_id, location_id, aisle, rack, cart, "
								"shelf, cabinet, drawer, bin, locator_visible) "
								"VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
								(self.product_id, location_id, aisle, rack, 
								cart, shelf, cabinet, drawer, _bin_, 
								locator_visible))
		self.builder.get_object('spinbutton1').emit("value-changed")
		self.db.commit()
		self.populate_product_store ()
		self.repopulated = True
		self.update_vendor_product_info ()
		

	def delete_product_activated (self, widget):
		try:
			self.cursor.execute("DELETE FROM products WHERE id = %s ", 
								(self.product_id,))
		except Exception as e:
			print (e)
			self.db.rollback()
			self.cursor.execute("UPDATE products SET deleted = TRUE "
								"WHERE id = %s ", (self.product_id,))
		self.db.commit()
		self.populate_product_store ()

	def new_clicked (self, button):
		self.new_product()

	def new_product (self):
		product_name_entry = self.builder.get_object('entry1')
		product_name_entry.set_text("New product")
		product_name_entry.select_region(0,-1)
		product_name_entry.grab_focus()
		self.product_id = 0 # tell the rest of the program we are creating a new product
		self.sku_id = 0 # new vendor sku
		self.builder.get_object('entry10').set_text("")
		self.builder.get_object('entry2').set_text("")
		self.builder.get_object("textbuffer1").set_text("")
		self.builder.get_object('comboboxtext1').set_active_id("1")
		self.builder.get_object('spinbutton1').set_value(1.00)
		self.builder.get_object('checkbutton4').set_active(True)
		self.builder.get_object('checkbutton5').set_active(True)
		self.builder.get_object('checkbutton3').set_active(False)
		self.builder.get_object('spinbutton10').set_value(0)
		self.builder.get_object('spinbutton11').set_value(0)
		self.builder.get_object('entry3').set_text("")
		self.builder.get_object('entry4').set_text("")
		self.builder.get_object('entry5').set_text("")
		self.builder.get_object('entry6').set_text("")
		self.builder.get_object('entry7').set_text("")
		self.builder.get_object('entry8').set_text("")
		self.builder.get_object('entry9').set_text("")
		self.builder.get_object('entry13').set_text("")
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('checkbutton2').set_active(True)
		
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE revenue_account = True "
							"ORDER BY number LIMIT 1")
		for row in self.cursor.fetchall():
			self.new_revenue_account = row[0]
			self.builder.get_object('combobox-entry1').set_text(row[1])
			break
		else:
			raise Exception("No revenue accounts available")
		self.cursor.execute("SELECT id FROM tax_rates WHERE standard = True ")
		default_id = self.cursor.fetchone()[0]
		self.builder.get_object('comboboxtext4').set_active_id(str(default_id))

		self.set_price_listbox_to_default ()
		
		
		


