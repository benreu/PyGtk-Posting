# purchase_order_window.py
#
# Copyright (C) 2016 reuben 
# 
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
import subprocess, re, os, psycopg2
from dateutils import DateTimeCalendar
import purchase_ordering
from constants import ui_directory, DB, broadcaster, help_dir

items = list()

UI_FILE = ui_directory + "/purchase_order_window.ui"

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

def add_expense_to_po (po_id, product_id, expense_amount ):
	cursor = DB.cursor ()
	cursor.execute("INSERT INTO purchase_order_items "
					"(purchase_order_id, product_id, qty, remark, price, "
					"ext_price, canceled, expense_account) "
					"VALUES (%s, %s, 1, '', %s, %s, False, "
						"(SELECT default_expense_account "
						"FROM products WHERE id = %s))", 
					(po_id, product_id, expense_amount, expense_amount, 
					product_id))
	DB.commit ()
	cursor.close()

class Item(object):#this is used by py3o library see their example for more info
	pass
	
class PurchaseOrderGUI(Gtk.Builder):
	def __init__(self, edit_po_id = None ):
		
		self.purchase_order_id = None
		self.vendor_id = 0
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1

		self.focusing = False

		self.order_number_completion = self.get_object ('order_number_completion')
		self.order_number_store = self.get_object ('order_number_store')
		self.revenue_account_store = self.get_object ('revenue_account_store')
		self.expense_account_store = self.get_object ('expense_account_store')
		self.p_o_store = self.get_object('purchase_order_store')
		self.vendor_store = self.get_object('vendor_store')
		self.barcodes_not_found_store = self.get_object('barcodes_not_found_store')
		vendor_completion = self.get_object('vendor_completion')
		vendor_completion.set_match_func(self.vendor_match_func)
		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_vendor_store ), 
						   ("products_changed", self.populate_product_store ), 
						   ("purchase_orders_changed", self.show_reload_infobar )):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		
		self.product_store = self.get_object('product_store')
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_string )
		self.populate_product_store ()

		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.treeview = self.get_object('treeview2')
		self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		self.treeview.drag_dest_set_target_list([enforce_target])
		
		column = self.get_object ('line_number_column')
		renderer = self.get_object ('line_number_renderer')
		column.set_cell_data_func(renderer, self.line_number_cell_func)
		
		self.populate_vendor_store ()
		if edit_po_id != None:
			self.cursor.execute("SELECT name, vendor_id FROM purchase_orders "
								"WHERE id = %s", (edit_po_id,))
			for row in self.cursor.fetchall():
				po_name = row[0]
				self.vendor_id = row[1]
				self.get_object('combobox1').set_active_id(str(self.vendor_id))
				self.get_object('po_name_entry').set_text(po_name)
				self.get_object('po_number_entry').set_text(str(edit_po_id))
				self.get_object('button2').set_sensitive(True)
				self.get_object('button3').set_sensitive(True)
				self.get_object('menuitem5').set_sensitive(True)
				self.get_object('menuitem2').set_sensitive(True)
				self.purchase_order_id = int(edit_po_id)
				self.populate_purchase_order_items ()

		self.cursor.execute("SELECT print_direct FROM settings")
		self.get_object('menuitem1').set_active(self.cursor.fetchone()[0]) #set the direct print checkbox
		
		self.window = self.get_object('window')
		self.window.show_all()
		
		GLib.idle_add(self.load_settings)

	def load_settings (self):
		self.cursor.execute("SELECT column_id, visible "
							"FROM settings.po_columns")
		for row in self.cursor.fetchall():
			column_id = row[0]
			visible = row[1]
			self.get_object(column_id).set_visible(visible)
		DB.rollback()

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.unlock_po()
		self.cursor.close()

	def widget_focus_in_event (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)

	def on_drag_data_received(self,widget,drag_context,x,y,data,info,time):
		list_ = data.get_text().split(' ')
		if len(list_) != 2:
			raise Exception("invalid drag data received")
			return
		if self.vendor_id == 0:
			return
		self.check_po_id()
		qty, product_id = list_[0], list_[1]
		cursor = DB.cursor()
		cursor.execute("SELECT COALESCE(vpn.vendor_sku, ''), p.name "
						"FROM products AS p "
						"LEFT JOIN vendor_product_numbers AS vpn "
						"ON p.id = vpn.product_id AND vendor_id = %s "
						"WHERE p.id = %s",
						(self.vendor_id, product_id))
		for row in cursor.fetchall():
			order_number = row[0]
			name = row[1]
		_iter = self.p_o_store.append([0, '1', int(product_id), order_number, 
										True, name, '', '', '0', 
										'0', True, 
										int(self.vendor_id), '', 
										self.purchase_order_id, False])
		self.check_po_item_id(_iter)
		cursor.close()

	def export_to_csv_activated (self, menuitem):
		import csv 
		vendor_name = self.get_object('combobox-entry').get_text()
		dialog = self.get_object ('filechooserdialog1')
		uri = os.path.expanduser('~')
		dialog.set_current_folder_uri("file://" + uri)
		dialog.set_current_name(vendor_name + ".csv")
		response = dialog.run()
		dialog.hide()
		if response != Gtk.ResponseType.ACCEPT:
			return
		selected_file = dialog.get_filename()
		with open(selected_file, 'w') as csvfile:
			exportfile = csv.writer(		csvfile, 
											delimiter=',',
											quotechar='|', 
											quoting=csv.QUOTE_MINIMAL)
			cursor = DB.cursor()
			cursor.execute("SELECT "
								"qty, "
								"name, "
								"order_number, "
								"price, "
								"ext_price "
							"FROM purchase_order_items AS poli "
							"JOIN products ON poli.product_id = products.id "
							"WHERE (purchase_order_id, hold) = (%s, False) "
							"ORDER BY poli.sort, poli.id", 
							(self.purchase_order_id,))
			for row in cursor.fetchall():
				exportfile.writerow(row)
			cursor.close()
		DB.rollback()

	def line_number_cell_func(self, column, cellrenderer, model, iter1, data):
		line = int(model.get_path(iter1)[0]) + 1
		cellrenderer.set_property("text" , str(line))

	def help_clicked (self, widget):
		subprocess.Popen(["yelp", help_dir + "/purchase_order.page"])

	def view_all_toggled (self, checkbutton):
		self.populate_purchase_order_items ()

	def hold_togglebutton_toggled (self, togglebutton, path):
		cursor = DB.cursor()
		row_id = self.p_o_store[path][0]
		try:
			cursor.execute("UPDATE purchase_order_items "
							"SET hold = NOT "
								"(SELECT hold FROM purchase_order_items "
								"WHERE id = %s FOR UPDATE NOWAIT) "
							"WHERE id = %s RETURNING hold", (row_id, row_id))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			return False
		for row in cursor.fetchall():
			active = row[0]
			self.p_o_store[path][14] = active
		DB.commit()
		self.calculate_totals ()
		cursor.close()

	def populate_purchase_order_items (self):
		cursor = DB.cursor()
		self.p_o_store.clear()
		if self.get_object ('checkbutton1').get_active() == True:
			self.get_object('treeviewcolumn11').set_visible(True)
			cursor.execute("SELECT "
								"poli.id, "
								"poli.qty::text, "
								"poli.product_id, "
								"COALESCE(order_number, vendor_sku, 'No sku'), "
								"products.stock, "
								"products.name, "
								"products.ext_name, "
								"poli.remark, "
								"poli.price::text, "
								"(poli.qty * poli.price)::text, "
								"False, "
								"po.vendor_id, "
								"c.name, "
								"po.id, "
								"poli.hold "
							"FROM purchase_order_items AS poli "
							"JOIN products ON products.id = poli.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poli.purchase_order_id "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poli.product_id, po.vendor_id) "
							"WHERE (po.canceled, po.closed, po.paid) = "
							"(False, False, False) "
							"ORDER BY poli.sort, poli.id")
		else:
			self.get_object('treeviewcolumn11').set_visible(False)
			cursor.execute("SELECT "
								"poli.id, "
								"poli.qty::text, "
								"poli.product_id, "
								"COALESCE(order_number, vendor_sku, 'No sku'), "
								"products.stock, "
								"products.name, "
								"products.ext_name, "
								"poli.remark, "
								"poli.price::text, "
								"(poli.qty * poli.price)::text, "
								"False, "
								"po.vendor_id, "
								"c.name, "
								"po.id, "
								"poli.hold "
							"FROM purchase_order_items AS poli "
							"JOIN products ON products.id = poli.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poli.purchase_order_id "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poli.product_id, po.vendor_id) "
							"WHERE purchase_order_id = %s "
							"ORDER BY poli.sort, poli.id", 
							(self.purchase_order_id, ) )
		for row in cursor.fetchall():
			self.p_o_store.append(row)
		self.calculate_totals ()
		cursor.close()
		DB.rollback()

	def populate_product_store (self, m=None, i=None):
		self.product_store.clear()
		self.cursor.execute("SELECT id::text, name ||'{' || ext_name ||'}' "
							"FROM products "
							"WHERE (deleted, purchasable, stock) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		self.order_number_store.clear()
		self.cursor.execute("SELECT product_id, vendor_sku "
							"FROM vendor_product_numbers "
							"WHERE vendor_id = %s", (self.vendor_id,))
		for row in self.cursor.fetchall():
			self.order_number_store.append(row)
		DB.rollback()

	def line_items_treeview_vendor_changed (self, combo, path, iter_):
		vendor_id = self.vendor_store[iter_][0]
		vendor_name = self.vendor_store[iter_][1]
		_iter = self.p_o_store.get_iter(path)
		product_id = self.p_o_store[_iter][2]
		self.p_o_store[_iter][11] = int(vendor_id)
		self.p_o_store[_iter][12] = vendor_name
		self.update_line_item_vendor (_iter, vendor_id)
		self.save_product (_iter, product_id)

	def focus (self, widget, event): 
		self.focusing = True
		self.populate_product_store ()
		self.populate_vendor_store ()
		self.focusing = False

	def vendor_combo_populate_popup (self, entry, menu):
		separator = Gtk.SeparatorMenuItem ()
		separator.show ()
		menu.prepend(separator)
		contact_hub_menu = Gtk.MenuItem.new_with_label("Contact hub")
		contact_hub_menu.connect("activate", self.contact_hub_clicked)
		contact_hub_menu.show()
		menu.prepend(contact_hub_menu)

	def contact_hub_clicked (self, menuitem):
		if self.vendor_id != 0:
			import contact_hub
			contact_hub.ContactHubGUI(self.vendor_id)

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('p_o_item_menu')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(product_id)

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

	def save_row_ordering (self):
		for row_count, row in enumerate (self.p_o_store):
			row_id = row[0]
			self.cursor.execute("UPDATE purchase_order_items "
								"SET sort = %s WHERE id = %s", 
								(row_count, row_id))
		DB.commit()

	def update_line_item_vendor (self, _iter, vendor_id):
		row_id = self.p_o_store[_iter][0]
		self.cursor.execute("SELECT po.id, c.name FROM purchase_orders AS po "
							"JOIN contacts AS c ON c.id = vendor_id "
							"WHERE vendor_id = %s "
							"AND (paid, closed, canceled) = "
							"(False, False, False)", (vendor_id, ))
		for row in self.cursor.fetchall() : # check for active PO
			purchase_order_id = row[0]
			vendor_name = row[1]
			break
		else:
			self.cursor.execute("SELECT name FROM contacts WHERE id = %s", 
								(vendor_id,))
			vendor_name = self.cursor.fetchone()[0]
			self.cursor.execute("INSERT INTO purchase_orders "
								"( vendor_id, closed, paid, canceled, "
								"received, date_created) "
								"VALUES (%s, %s, %s, %s, %s, CURRENT_DATE) "
								"RETURNING id, date_created", 
								(vendor_id, False, False, False, False))
			for row in self.cursor.fetchall():
				purchase_order_id = row[0]
				date = row[1]
			name_str = ""
			for i in vendor_name.split(' '):
				name_str = name_str + i[0:3]
			name = name_str.lower()
			po_date = re.sub("-", "_", str(date))
			document_name = "PO_" + str(purchase_order_id) + "_"  + name + "_" + po_date
			self.cursor.execute("UPDATE purchase_orders "
								"SET name = %s WHERE id = %s", 
								(document_name, purchase_order_id))
		self.p_o_store[_iter][11] = int(vendor_id)
		self.p_o_store[_iter][12] = vendor_name
		self.p_o_store[_iter][13] = purchase_order_id
		self.cursor.execute("UPDATE purchase_order_items "
							"SET purchase_order_id = %s "
							"WHERE id = %s", (purchase_order_id, row_id))
		DB.commit()
		
	def products_activated (self, column):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def populate_vendor_store (self, m=None, i=None):
		self.populating = True
		name_combo = self.get_object('combobox1')
		active_customer = name_combo.get_active() 
		self.vendor_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT "
							"id::text, "
							"name, "
								"COALESCE((SELECT name FROM purchase_orders "
								"WHERE (closed, canceled) = (False, False) "
								"AND vendor_id = c_outer.id LIMIT 1), 'No PO')"
						"FROM contacts AS c_outer "
						"WHERE (deleted, vendor) "
						"= (False, True) ORDER BY name")
		for row in cursor.fetchall():
			self.vendor_store.append(row)
		cursor.close()
		DB.rollback()
		self.populating = False

	def contacts_window(self, widget):
		import contacts_overview
		c = contacts_overview.ContactsOverviewGUI ()
		c.get_object('radiobutton2').set_active(True)
	
	def vendor_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.vendor_store[iter][1].lower(): 
				return False
		return True

	def view_purchase_order(self, widget):
		comment = self.get_object('entry2').get_text()
		purchase_order = purchase_ordering.Setup( self.vendor_id, 
													comment, 
													self.datetime, 
													self.purchase_order_id)
		purchase_order.view()

	def post_and_process(self, widget):
		self.post_purchase_order ()	
		import unprocessed_po
		unprocessed_po.GUI ()

	def post_purchase_order(self, widget = None):
		cursor = DB.cursor()
		cursor.execute("SELECT "
							"pg_try_advisory_lock(id) "
						"FROM purchase_orders "
						"WHERE id = %s ", (self.purchase_order_id, ))
		for row in cursor.fetchall():
			if row[0] == False:
				self.show_message("Somebody else is still accessing this PO")
				return
		comment = self.get_object('entry2').get_text()
		purchase_order = purchase_ordering.Setup(self.vendor_id, 
													comment, 
													self.datetime, 
													self.purchase_order_id)
		if self.get_object('menuitem1').get_active() == True:
			result = purchase_order.print_directly()
		else:
			result = purchase_order.print_dialog(self.window)
		purchase_order.post(self.purchase_order_id, self.vendor_id,
												self.datetime)
		hold = False
		for row in self.p_o_store:
			if row[14] == True:
				hold = True
				break
		if hold == True: # create new po and show it
			old_purchase_id = self.purchase_order_id
			self.purchase_order_id = None
			self.check_po_id ()
			cursor.execute ("UPDATE purchase_order_items "
							"SET (purchase_order_id, hold) = (%s, False) "
							"WHERE (purchase_order_id, hold) = "
							"(%s, True) RETURNING id", 
							(self.purchase_order_id, old_purchase_id))
			DB.commit()
			self.populate_purchase_order_items ()
		else: #no products held
			DB.commit()
			self.window.destroy ()
		cursor.close()

	def vendor_match_selected(self, completion, model, iter):
		vendor_id = model[iter][0]
		self.select_vendor (vendor_id)

	def vendor_combobox_changed(self, widget, toggle_button = None):
		if self.focusing == True:
			return
		vendor_id = widget.get_active_id()
		if vendor_id != None:
			self.select_vendor(vendor_id)

	def unlock_po (self):
		if self.purchase_order_id:
			self.cursor.execute("SELECT "
									"pg_advisory_unlock_shared(id) "
								"FROM purchase_orders "
								"WHERE id = %s ", 
								(self.purchase_order_id, ))
		DB.commit()
		
	def select_vendor (self, vendor_id):
		self.p_o_store.clear()
		self.get_object ('checkbutton1').set_active(False)
		if vendor_id != None and self.populating == False:
			self.unlock_po()
			self.vendor_id = vendor_id
			self.get_object('button2').set_sensitive(True)
			self.get_object('button3').set_sensitive(True)
			self.get_object('menuitem5').set_sensitive(True)
			self.get_object('menuitem2').set_sensitive(True)
			self.cursor.execute("SELECT * FROM "
								"(SELECT "
									"po.id, "
									"po.date_created, "
									"format_date(po.date_created), "
									"c.phone, "
									"po.name, "
									"pg_try_advisory_lock_shared(po.id) AS lock "
								"FROM purchase_orders AS po "
								"JOIN contacts AS c ON c.id = po.vendor_id "
								"WHERE vendor_id = %s "
								"AND (paid, closed, canceled) = "
								"(False, False, False)) s "
								"WHERE lock = True", (vendor_id, ))
			for row in self.cursor.fetchall() : # check for active PO
				self.purchase_order_id = row[0]
				self.datetime = row[1]
				self.get_object('entry1').set_text(row[2])
				self.get_object('entry8').set_text(row[3])
				self.get_object('po_name_entry').set_text(row[4])
				self.get_object('po_number_entry').set_text(str(row[0]))
				self.populate_purchase_order_items ()
				break
			else:
				self.cursor.execute("SELECT "
									"CURRENT_DATE, "
									"format_date(CURRENT_DATE), "
									"phone "
									"FROM contacts WHERE id = %s", 
									(vendor_id,))
				for row in self.cursor.fetchall() : 
					self.purchase_order_id = None
					self.datetime = row[0]
					self.get_object('entry1').set_text(row[1])
					self.get_object('entry8').set_text(row[2])
					self.get_object('po_name_entry').set_text('')
					self.get_object('po_number_entry').set_text('')
			self.calculate_totals ()
		DB.rollback()

	def editing_canceled (self, cellrenderer):
		"all widgets need to connect to this function to release row locks"
		"removing row locks is as simple as doing a rollback or commit"
		"all rows need to be locked whenever a widget is opened to "
		"edit an invoice row"
		DB.rollback() #remove row lock by rolling back
		#cellrenderer.hide_on_delete()
		return True

	################## start qty

	def qty_editing_started (self, cellrenderer, celleditable, path):
		row_id = self.p_o_store[path][0]
		cursor = DB.cursor()
		try:
			cursor.execute("SELECT qty::text FROM purchase_order_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			celleditable.destroy()
			return False
		for row in cursor.fetchall():
			celleditable.set_text(row[0])
		cursor.close()

	def qty_edited(self, widget, path, text):
		cursor = DB.cursor()
		_iter = self.p_o_store.get_iter (path)
		self.check_po_item_id (_iter)
		line_id = self.p_o_store[_iter][0]
		try:
			cursor.execute("UPDATE purchase_order_items "
								"SET (qty, ext_price) = (%s, %s * price) "
								"WHERE id = %s "
								"RETURNING qty::text, ext_price::text", 
								(text, text, line_id))
		except psycopg2.DataError as e:
			self.show_message (str(e))
			DB.rollback()
			return
		for row in cursor.fetchall():
			qty = row[0]
			ext_price = row[1]
			self.p_o_store[_iter][1] = qty
			self.p_o_store[_iter][9] = ext_price
		DB.commit()
		self.calculate_totals ()

	################## start order number

	def order_number_editing_started (self, renderer, entry, path):
		row_id = self.p_o_store[path][0]
		cursor = DB.cursor()
		try:
			cursor.execute("SELECT order_number FROM purchase_order_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			entry.destroy()
			return False
		for row in cursor.fetchall():
			entry.set_text(row[0])
		cursor.close()
		entry.set_completion(self.order_number_completion)
		entry.connect('icon-release', self.order_number_icon_released)
		entry.connect('key-release-event', self.order_number_entry_changed)
		self.path = path

	def order_number_edited(self, widget, path, text):
		order_number = text
		row_id = self.p_o_store[path][0]
		product_id = self.p_o_store[path][2]
		if product_id == 0:
			self.show_message ("Please select a product first.\n"
								"Alternatively, you can type in a "
								"partial order number\nand select an "
								"order number from the popup.")
			return
		if order_number != self.p_o_store[path][3]:
			self.show_temporary_permanent_dialog(order_number, product_id)
		else:
			return # order number not updated
		self.p_o_store[path][3] = order_number
		self.cursor.execute("UPDATE purchase_order_items "
							"SET order_number = %s WHERE id = %s",
							(order_number, row_id))
		DB.commit()

	def order_number_match_selected (self, completion, store, _iter):
		product_id = store[_iter][0]
		_iter = self.p_o_store.get_iter(self.path)
		self.save_product (_iter, product_id)

	def order_number_no_match (self, entrycompletion):
		pos = Gtk.EntryIconPosition.SECONDARY
		entry = entrycompletion.get_entry()
		entry.set_icon_from_icon_name(pos, 'gtk-justify-fill')

	def order_number_icon_released (self, entry, entryiconposition, event):
		order_number = entry.get_text()
		self.extended_order_number_search(order_number)

	def extended_order_number_search (self, order_number):
		store = self.get_object('order_number_extended_store')
		store.clear()
		results = False
		c = DB.cursor()
		c.execute("SELECT p.id, name, ext_name, barcode, poi.order_number "
					"FROM products AS p "
					"JOIN purchase_order_items AS poi ON poi.product_id = p.id "
					"WHERE poi.order_number ILIKE %s "
					"GROUP BY poi.order_number, p.id", ('%' + order_number + '%',))
		for row in c.fetchall():
			store.append(row)
			results = True
		if results:
			window = self.get_object('extended_order_number_window')
			window.show_all()
			window.present()
		else:
			dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.INFO,
										buttons = Gtk.ButtonsType.CLOSE,
										text = "Extended search found no results",
										transient_for = self.window)
			dialog.run()
			dialog.destroy()

	def order_number_entry_changed (self, entry, event):
		state = event.get_state()
		if state & Gdk.ModifierType.CONTROL_MASK:
			if Gdk.keyval_name(event.keyval) == "Return":
				order_number = entry.get_text()
				self.extended_order_number_search(order_number)

	def extended_order_number_row_activated (self, treeview, path, treeviewcolumn):
		model = treeview.get_model()
		product_id = model[path][0]
		selection = self.get_object('treeview-selection')
		model, path_list = selection.get_selected_rows()
		path = path_list[0].to_string()
		_iter = self.p_o_store.get_iter(path)
		self.save_product (_iter, product_id)
		self.get_object('extended_order_number_window').hide()

	def extended_order_number_window_delete (self, window, event):
		window.hide()
		return True

	def show_temporary_permanent_dialog (self, order_number, product_id):
		if self.get_object('checkbutton2').get_active() == True:
			if self.order_number_response == 1:
				self.update_vendor_order_number (order_number, product_id)
			return # user selected to always have the same action
		dialog = self.get_object('temp_permanent_dialog')
		self.order_number_response = dialog.run()
		dialog.hide()
		if self.order_number_response == 1:
			self.update_vendor_order_number (order_number, product_id)

	def update_vendor_order_number (self, order_number, product_id):
		if self.vendor_id == 0:
			return
		cursor = DB.cursor()
		cursor.execute("INSERT INTO vendor_product_numbers AS vpn "
							"(vendor_sku, "
							"vendor_id, "
							"product_id) "
						"VALUES (%s, %s, %s) "
						"ON CONFLICT (vendor_id, product_id) "
						"DO UPDATE SET "
						"vendor_sku = %s "
						"WHERE (vpn.vendor_id, vpn.product_id) = (%s, %s)", 
						(order_number, self.vendor_id, product_id, 
						order_number, self.vendor_id, product_id))
		cursor.close()
		DB.commit()
		
	################## start remark

	def remark_edited(self, widget, path, text):
		_iter = self.p_o_store.get_iter(path)
		self.p_o_store[_iter][7] = text
		row_id = self.p_o_store[_iter][0] 
		cursor = DB.cursor()
		cursor.execute("UPDATE purchase_order_items SET remark = %s "
							"WHERE id = %s", (text, row_id))
		cursor.close()
		DB.commit()
		
	def remark_editing_started (self, cellrenderer, entry, path):
		row_id = self.p_o_store[path][0]
		cursor = DB.cursor()
		try:
			cursor.execute("SELECT remark FROM purchase_order_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			entry.destroy()
			return False
		for row in cursor.fetchall():
			entry.set_text(row[0])
		cursor.close()

	################## end remark

	def product_renderer_changed (self, widget, path, iter_):
		product_id = int(self.product_store[iter_][0])
		_iter = self.p_o_store.get_iter(path)
		self.save_product (_iter, product_id)

	def product_renderer_editing_started (self, renderer, combo, path):
		entry = combo.get_child()
		row_id = self.p_o_store[path][0]
		cursor = DB.cursor()
		try:
			cursor.execute("SELECT p.name "
							"FROM purchase_order_items AS poi "
							"JOIN products AS p ON p.id = poi.product_id "
							"WHERE poi.id = %s "
							"FOR UPDATE OF poi NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			DB.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			combo.destroy()
			return False
		for row in cursor.fetchall():
			entry.set_text(row[0])
		completion = self.get_object("product_completion")
		entry.set_completion(completion)

	def populate_account_store (self):
		self.expense_account_store.clear()
		self.revenue_account_store.clear()
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE expense_account = True ORDER BY name")
		for row in self.cursor.fetchall():
			self.expense_account_store.append(row)
		self.cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE revenue_account = True ORDER BY name")
		for row in self.cursor.fetchall():
			self.revenue_account_store.append(row)
		DB.rollback()

	def create_product_widgets_changed (self, widget):
		self.get_object ('button1').set_sensitive(False)
		product_name = self.get_object ('entry4').get_text() 
		if product_name == '':
			return # no product name
		else:
			self.cursor.execute("SELECT id FROM products "
								"WHERE name = %s", (product_name,))
			for row in self.cursor.fetchall():
				self.get_object('label15').set_visible(True)
				break
			else:
				self.get_object('label15').set_visible(False)
		order_number = self.get_object ('entry3').get_text()
		if order_number == '':
			return # no order number
		else:
			self.cursor.execute("SELECT name FROM vendor_product_numbers "
								"JOIN products "
								"ON products.id = "
								"vendor_product_numbers.product_id "
								"WHERE (vendor_sku, vendor_id) = "
								"(%s, %s)", (order_number, self.vendor_id))
			for row in self.cursor.fetchall():
				product_name = row[0]
				self.get_object('label13').set_text(product_name)
				self.get_object('box8').set_visible(True)
				break
			else:
				self.get_object('box8').set_visible(False)
		if self.get_object ('combobox2').get_active_id() == None:
			return # no expense account
		if self.get_object ('combobox3').get_active_id() == None:
			return # no income account
		self.get_object ('button1').set_sensitive(True)
		DB.rollback()

	def product_renderer_edited (self, cellrenderertext, path, product_text):
		_iter = self.p_o_store.get_iter(path)
		self.populate_account_store ()
		self.get_object ('entry4').set_text(product_text)
		dialog = self.get_object ('non_stock_product_dialog')
		result = dialog.run ()
		self.get_object('box8').set_visible(False)
		self.get_object('label15').set_visible(False)
		dialog.hide ()
		product_name = self.get_object ('entry4').get_text()
		product_number = self.get_object ('entry3').get_text()
		expense_account = self.get_object ('combobox2').get_active_id()
		revenue_account = self.get_object ('combobox3').get_active_id()
		if result == Gtk.ResponseType.ACCEPT:
			product_id = add_non_stock_product(	self.vendor_id, product_name,
												product_number, expense_account,
												revenue_account)
			self.p_o_store[_iter][2] = product_id
			self.save_product (_iter, product_id)
			self.calculate_totals ()
		self.get_object ('entry3').set_text('')
		self.get_object ('button1').set_sensitive(False)

	def save_product (self, _iter, product_id):
		if self.check_for_duplicate_products (product_id, _iter) == True:
			DB.rollback() # remove row lock, see editing_canceled
			return # duplicate product, skip the rest of the code
		self.save_product_without_duplicate_check (_iter, product_id)
		# retrieve path again after all sorting has happened for the updates
		path = self.p_o_store.get_path(_iter)
		treeview = self.get_object('treeview2')
		c = treeview.get_column(5)
		treeview.set_cursor(path, c, True)

	def save_product_without_duplicate_check(self, _iter, product_id):
		cursor = DB.cursor()
		row_id = self.p_o_store[_iter][0]
		vendor_id = self.p_o_store[_iter][11]
		self.p_o_store[_iter][2] = int(product_id)
		cursor.execute("WITH p_info AS "
							"(SELECT "
								"name, "
								"cost, "
								"ext_name, "
								"stock, "
								"COALESCE(vendor_sku, '') AS vendor_sku "
							"FROM products AS p "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON vpn.product_id = p.id AND vendor_id = %s"
							"WHERE p.id = %s), "
						"poi_update AS "
						"(UPDATE purchase_order_items "
						"SET "
							"(product_id, "
							"price, "
							"ext_price, "
							"order_number, "
							"expense_account "
							") " 
						"= "
							"(%s, "
							"(SELECT cost FROM p_info), "
							"qty * (SELECT cost FROM p_info), "
							"(SELECT vendor_sku FROM p_info), "
							"(SELECT default_expense_account "
								"FROM products WHERE id = %s)"
							") "
						"WHERE id = %s RETURNING ext_price"
						") "
						"SELECT "
							"name, "
							"cost::text, "
							"(SELECT ext_price FROM poi_update)::text, "
							"ext_name, "
							"stock, "
							"vendor_sku "
						"FROM p_info", 
						(self.vendor_id, product_id, 
						product_id, product_id, row_id))
		for row in cursor.fetchall():
			name = row[0]
			price = row[1]
			ext_price = row[2]
			ext_name = row[3]
			stock = row[4]
			order_number = row[5]
			self.p_o_store[_iter][3] = order_number
			self.p_o_store[_iter][4] = stock
			self.p_o_store[_iter][5] = name
			self.p_o_store[_iter][6] = ext_name
			self.p_o_store[_iter][8] = price
			self.p_o_store[_iter][9] = ext_price
		cursor.close()
		DB.commit()
		self.calculate_totals ()

	def product_match_string(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_match_selected(self, completion, model, iter_):
		product_id = int(model[iter_][0])
		product_name = model[iter_][1]
		selection = self.get_object('treeview-selection')
		model, path_list = selection.get_selected_rows()
		path = path_list[0].to_string()
		_iter = self.p_o_store.get_iter(path)
		self.save_product (_iter, product_id)

	def check_for_duplicate_products(self, product_id, _iter ):
		path = self.p_o_store.get_path (_iter)
		for row in self.p_o_store:
			if row.path == path:
				continue # continue with the rest of the liststore
			if product_id == row[2]: # the liststore has duplicates
				product_name = row[5]
				self.get_object('label5').set_label(product_name)
				qty = row[1]
				qty_spinbutton = self.get_object('spinbutton1')
				qty_spinbutton.set_value(int(qty))
				self.duplicate_product_id = product_id
				self.duplicate_product_primary_row = row
				window = self.get_object('duplicate_product_window')
				window.show_all()
				return True
		return False

	def duplicate_product_cancel_clicked (self, button):
		self.get_object('duplicate_product_window').hide()

	def duplicate_product_update_qty_clicked (self, button):
		selection = self.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		qty_spinbutton = self.get_object('spinbutton1')
		qty = qty_spinbutton.get_text()
		self.duplicate_product_primary_row[1] = qty
		row_id = self.duplicate_product_primary_row[0]
		self.cursor.execute("UPDATE purchase_order_items "
							"SET qty = %s WHERE id = %s", 
							(qty, row_id))
		DB.commit()
		self.calculate_totals ()
		self.get_object('duplicate_product_window').hide()

	def duplicate_product_add_again_clicked (self, button):
		selection = self.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		_iter = model.get_iter(path)
		self.save_product_without_duplicate_check(_iter, self.duplicate_product_id)
		self.get_object('duplicate_product_window').hide()

	def check_po_item_id (self, _iter):
		line = self.p_o_store[_iter]
		row_id = line[0]
		if row_id != 0:
			return # we have a valid id
		cursor = DB.cursor()
		qty = line[1]
		product_id = line[2]
		order_number = line[3]
		remark = line[7]
		price = line[8]
		ext_price = line[9]
		line[10] = False
		purchase_order_id = line[13]
		cursor.execute("INSERT INTO purchase_order_items "
							"(purchase_order_id, "
							"qty, "
							"product_id, "
							"remark, "
							"price, "
							"ext_price, "
							"canceled, "
							"expense_account, "
							"order_number) "
						"VALUES "
							"(%s, "
							"%s, "
							"%s, "
							"%s, "
							"%s, "
							"%s, "
							"%s, "
							"(SELECT default_expense_account "
								"FROM products WHERE id = %s), "
							"%s) "
						"RETURNING id", 
							(purchase_order_id, 
							qty, 
							product_id, 
							remark, 
							price, 
							ext_price, 
							False, 
							product_id, 
							order_number))
		row_id = cursor.fetchone()[0]
		line[0] = row_id
		cursor.close()
		DB.commit()
		self.calculate_totals ()

	def calculate_totals(self):
		cursor = DB.cursor()
		cursor.execute("SELECT COALESCE(SUM(ext_price), 0.0)::money "
						"FROM purchase_order_items "
						"WHERE purchase_order_id = %s", 
						(self.purchase_order_id,))
		for row in cursor.fetchall():
			total = row[0]
			self.get_object('entry5').set_text(total)
		rows = len(self.p_o_store)
		self.get_object('rows_entry').set_text(str(rows))

	def check_po_id (self):
		if self.purchase_order_id == None:
			comment = self.get_object('entry2').get_text()
			self.cursor.execute("INSERT INTO purchase_orders "
									"(name, "
									"vendor_id, "
									"closed, "
									"paid, "
									"canceled, "
									"received, "
									"date_created) "
								"VALUES "
									"(%s, %s, False, False, False, False, %s) "
								"RETURNING id", 
									("", self.vendor_id, self.datetime ))
			po_id = self.cursor.fetchone()[0]
			self.purchase_order_id = po_id
			self.get_object('po_name_entry').set_text('')
			self.get_object('po_number_entry').set_text(str(po_id))

	def new_entry_clicked (self, button):
		_iter = self.add_entry ()
		treeview = self.get_object('treeview2')
		c = treeview.get_column(1)
		path = self.p_o_store.get_path(_iter)
		treeview.set_cursor(path, c, True)

	def add_entry (self):
		self.check_po_id ()
		self.cursor.execute("SELECT id, name "
							"FROM products "
							"WHERE (deleted, purchasable, stock) = "
									"(False, True, True) "
							"ORDER BY id, name "
							"LIMIT 1")
		for i in self.cursor.fetchall():
			product_id = i[0]
			product_name = i[1]
			_iter = self.p_o_store.append([0, '1', product_id, 
										"Select order number", 
										False, "Select a stock item" , "", "", 
										'1', '1', True, int(self.vendor_id),
										'', self.purchase_order_id, False])
			self.check_po_item_id (_iter)
		DB.commit()
		return _iter

	def delete_item_activated (self, menuitem = None):
		selection = self.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path != []:
			line_id = model[path][0]
			self.cursor.execute("DELETE FROM purchase_order_items "
								"WHERE id = %s", (line_id,))
			DB.commit()
			self.populate_purchase_order_items ()

	def key_tree_tab(self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		## only visible columns!!
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
					next_column = columns[1]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass

	def window_key_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if event.get_state() & Gdk.ModifierType.CONTROL_MASK: #Ctrl held down
			if keyname == "h":
				self.product_hub_activated (None)
			elif keyname == "Down":
				self.move_down_activated (None)
			elif keyname == "Up":
				self.move_up_activated (None)
		elif keyname == 'F1':
			self.help_clicked (None)
		elif keyname == 'F2':
			self.add_entry()
		elif keyname == 'F3':
			self.delete_entry_activated ()

	def barcode_entry_key_released (self, entry, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname != 'Return' and keyname != "KP_Enter": # enter key(s)
			if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
				# process keypresses with CTRL held down
				entry.delete_selection()
				position = entry.get_position()
				number = re.sub("[^0-9]", "", keyname)
				entry.insert_text(number, position)
				entry.set_position(position + 1)
			return
		barcode = entry.get_text()
		if barcode == "":
			return # blank barcode
		self.cursor.execute("SELECT id FROM products "
							"WHERE barcode = %s", (barcode,))
		for row in self.cursor.fetchall():
			product_id = row[0]
			break
		else:
			self.process_missing_barcode (barcode)
			return
		if event.get_state() & Gdk.ModifierType.SHIFT_MASK: #shift held down
			entry.select_region(0,-1)
			for index, row in enumerate(self.p_o_store):
				if row[2] == product_id:
					row[1] -= 1
					self.save_purchase_order_line (index)
					break
		elif event.get_state() & Gdk.ModifierType.CONTROL_MASK: #ctrl held down
			entry.select_region(0,-1)
			selection = self.get_object('treeview-selection')
			model, path = selection.get_selected_rows()
			if path == []:
				return
			_iter = self.p_o_store.get_iter(path)
			self.save_product (_iter, product_id)
		else:
			entry.select_region(0,-1)
			self.add_product (product_id)

	def process_missing_barcode (self, barcode):
		for row in self.barcodes_not_found_store:
			if row[2] == barcode:
				row[1] += 1
				break
			continue
		else:
			self.barcodes_not_found_store.append([0, 1, barcode])
		self.get_object('entry10').grab_focus()
		barcode_error_dialog = self.get_object('barcode_error_dialog')
		barcode_error_dialog.run()
		barcode_error_dialog.hide()

	def add_product (self, product_id):
		for index, row in enumerate(self.p_o_store):
			if row[2] == product_id:
				row[1] += 1
				self.save_purchase_order_line (index)
				break
			continue
		else:
			_iter = self.add_entry ()
			self.save_product (_iter, product_id)

	def calendar_day_selected (self, calendar):
		self.datetime = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry1').set_text(day_text)

	def calendar_entry_icon_release (self, widget, icon, void):
		self.calendar.set_relative_to (widget)
		self.calendar.show()

	def po_name_icon_release (self, entry, entryiconposition, event):
		po_name = entry.get_text()
		self.cursor.execute("UPDATE purchase_orders SET name = %s "
							"WHERE id = %s", (po_name, self.purchase_order_id))
		DB.commit()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

	def show_reload_infobar (self, broadcaster, po_id):
		if po_id == self.purchase_order_id:
			infobar = self.get_object('po_changed_infobar')
			infobar.set_revealed(True)

	def info_bar_close (self, infobar):
		infobar.set_revealed(False)

	def info_bar_response (self, infobar, response):
		if response == Gtk.ResponseType.APPLY:
			self.populate_purchase_order_items ()
		infobar.set_revealed(False)

