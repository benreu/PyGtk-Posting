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
from main import ui_directory, db, broadcaster

items = list()

UI_FILE = ui_directory + "/purchase_order_window.ui"

def add_expense_to_po (po_id, product_id, expense_amount ):
	cursor = db.cursor ()
	cursor.execute("INSERT INTO purchase_order_line_items "
					"(purchase_order_id, product_id, qty, remark, price, "
					"ext_price, canceled, expense_account) "
					"VALUES (%s, %s, 1, '', %s, %s, False, "
						"(SELECT default_expense_account "
						"FROM products WHERE id = %s))", 
					(po_id, product_id, expense_amount, expense_amount, 
					product_id))
	db.commit ()
	cursor.close()

class Item(object):#this is used by py3o library see their example for more info
	pass
	
class PurchaseOrderGUI(Gtk.Builder):
<<<<<<< HEAD
	def __init__(self, edit_po_id = None ):
		
=======
	def __init__(self, main, edit_po_id = None ):

>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473
		self.purchase_order_id = None
		self.vendor_id = 0
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1

		self.focusing = False
		self.menu_visible = False

		self.order_number_completion = self.get_object ('order_number_completion')
		self.order_number_store = self.get_object ('order_number_store')
		self.revenue_account_store = self.get_object ('revenue_account_store')
		self.expense_account_store = self.get_object ('expense_account_store')
		self.p_o_store = self.get_object('purchase_order_store')
		self.vendor_store = self.get_object('vendor_store')
		self.barcodes_not_found_store = self.get_object('barcodes_not_found_store')
		vendor_completion = self.get_object('vendor_completion')
		vendor_completion.set_match_func(self.vendor_match_func)

		self.db = db
		self.cursor = db.cursor()
		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_vendor_store ), 
						   ("products_changed", self.populate_product_store )):
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
		
		self.populate_vendor_store ()
		if edit_po_id != None:
			self.cursor.execute("SELECT name, vendor_id FROM purchase_orders "
								"WHERE id = %s", (edit_po_id,))
			for row in self.cursor.fetchall():
				po_name = row[0]
				self.vendor_id = row[1]
			self.get_object('combobox1').set_active_id(str(self.vendor_id))
			self.get_object('button2').set_sensitive(True)
			self.get_object('button3').set_sensitive(True)
			self.get_object('menuitem5').set_sensitive(True)
			self.get_object('menuitem2').set_sensitive(True)
			self.purchase_order_id = int(edit_po_id)
			self.products_from_existing_po ()

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

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.unlock_po()
		self.cursor.close()

	def on_drag_data_received(self,widget,drag_context,x,y,data,info,time):
		list_ = data.get_text().split(' ')
		if len(list_) != 2:
			raise Exception("invalid drag data received")
			return
		if self.vendor_id == 0:
			return
		qty, product_id = list_[0], list_[1]
		_iter = self.p_o_store.append([0, '1', int(product_id), '', 
										True, '', '', '', '0', 
										'0', True, 
										int(self.vendor_id), '', 
										self.purchase_order_id, False])
		self.save_product(_iter, product_id)

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
			cursor = self.db.cursor()
			cursor.execute("SELECT "
								"qty, "
								"name, "
								"order_number, "
								"price, "
								"ext_price "
							"FROM purchase_order_line_items AS poli "
							"JOIN products ON poli.product_id = products.id "
							"WHERE (purchase_order_id, hold) = (%s, False) "
							"ORDER BY poli.id", 
							(self.purchase_order_id,))
			for row in cursor.fetchall():
				exportfile.writerow(row)
			cursor.close()

	def help_clicked (self, widget):
		subprocess.Popen(["yelp", main.help_dir + "/purchase_order.page"])

	def view_all_toggled (self, checkbutton):
		self.products_from_existing_po ()

	def hold_togglebutton_toggled (self, togglebutton, path):
		cursor = db.cursor()
		row_id = self.p_o_store[path][0]
		try:
			cursor.execute("UPDATE purchase_order_line_items "
							"SET hold = NOT "
								"(SELECT hold FROM purchase_order_line_items "
								"WHERE id = %s FOR UPDATE NOWAIT) "
							"WHERE id = %s RETURNING hold", (row_id, row_id))
		except psycopg2.OperationalError as e:
			db.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			return False
		for row in cursor.fetchall():
			active = row[0]
			self.p_o_store[path][14] = active
		db.commit()
		self.calculate_totals ()
		cursor.close()

	def products_from_existing_po (self):
		cursor = self.db.cursor()
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
							"FROM purchase_order_line_items AS poli "
							"JOIN products ON products.id = poli.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poli.purchase_order_id "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poli.product_id, po.vendor_id) "
							"WHERE (po.canceled, po.closed, po.paid) = "
							"(False, False, False) ORDER BY poli.id")
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
							"FROM purchase_order_line_items AS poli "
							"JOIN products ON products.id = poli.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poli.purchase_order_id "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poli.product_id, po.vendor_id) "
							"WHERE purchase_order_id = %s ORDER BY poli.id", 
							(self.purchase_order_id, ) )
		for row in cursor.fetchall():
			self.p_o_store.append(row)
		self.calculate_totals ()
		cursor.close()

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
		if self.purchase_order_id != None:
			self.products_from_existing_po ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3 and self.menu_visible == False:
			menu = self.get_object('right_click_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			self.menu_visible = True
		else:
			self.menu_visible = False

	def product_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def update_line_item_vendor (self, _iter, vendor_id):
		row_id = self.p_o_store[_iter][0]
		self.cursor.execute("SELECT id FROM purchase_orders "
							"WHERE vendor_id = (%s) "
							"AND (paid, closed, canceled) = "
							"(False, False, False)", (vendor_id, ))
		for row in self.cursor.fetchall() : # check for active PO
			purchase_order_id = row[0]
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
		self.p_o_store[_iter][13] = purchase_order_id
		db.commit()
		
	def products_activated (self, column):
		import products
		products.ProductsGUI()

	def populate_vendor_store (self, m=None, i=None):
		self.populating = True
		name_combo = self.get_object('combobox1')
		active_customer = name_combo.get_active() 
		self.vendor_store.clear()
		cursor = self.db.cursor()
		cursor.execute("SELECT "
							"id::text, "
							"name, "
							"COALESCE((SELECT name FROM purchase_orders "
							"WHERE (closed, canceled) = (False, False) "
							"AND vendor_id = c_outer.id), 'No PO')"
						"FROM contacts AS c_outer "
						"WHERE (deleted, vendor) "
						"= (False, True) ORDER BY name")
		for row in cursor.fetchall():
			self.vendor_store.append(row)
		cursor.close()
		self.populating = False

	def contacts_window(self, widget):
		import contacts
		c = contacts.GUI()
		c.get_object('radiobutton2').set_active(True)
	
	def vendor_match_func(self, completion, key, iter):
		if key in self.vendor_store[iter][1].lower(): 
			return True# it's a hit!
		return False # no match

	def view_purchase_order(self, widget):
		comment = self.get_object('entry2').get_text()
<<<<<<< HEAD
		purchase_order = purchase_ordering.Setup(db, 
=======
		purchase_order = purchase_ordering.Setup(self.db, 
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473
													self.vendor_id, 
													comment, 
													self.datetime, 
													self.purchase_order_id)
		purchase_order.view()

	def post_and_process(self, widget):
		self.post_purchase_order ()	
		import unprocessed_po
		unprocessed_po.GUI ()

	def post_purchase_order(self, widget = None):
		cursor = db.cursor()
		cursor.execute("SELECT "
							"pg_try_advisory_lock(id) "
						"FROM purchase_orders "
						"WHERE id = %s ", (self.purchase_order_id, ))
		for row in cursor.fetchall():
			if row[0] == False:
				self.show_message("Somebody else is still accessing this PO")
				return
		comment = self.get_object('entry2').get_text()
<<<<<<< HEAD
		purchase_order = purchase_ordering.Setup(db,  
=======
		purchase_order = purchase_ordering.Setup(self.db,  
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473
													self.vendor_id, 
													comment, 
													self.datetime, 
													self.purchase_order_id)
		if self.get_object('menuitem1').get_active() == True:
			result = purchase_order.print_directly()
		else:
			result = purchase_order.print_dialog(self.window)
		purchase_order.post(self.purchase_order_id, self.vendor_id,
												self.datetime)
		old_purchase_id = self.purchase_order_id
		self.purchase_order_id = None
		self.check_po_id ()
		cursor.execute ("UPDATE purchase_order_line_items "
							"SET (purchase_order_id, hold) = (%s, False) "
							"WHERE (purchase_order_id, hold) = "
							"(%s, True) RETURNING id", 
							(self.purchase_order_id, old_purchase_id))
		if cursor.fetchone() == None: #no products held
			db.rollback()
			self.window.destroy ()
		else:								#new po created; show it
			db.commit()
			self.products_from_existing_po ()
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
									"id, "
									"date_created, "
									"format_date(date_created), "
									"pg_try_advisory_lock_shared(id) AS lock "
								"FROM purchase_orders "
								"WHERE vendor_id = %s "
								"AND (paid, closed, canceled) = "
								"(False, False, False)) s "
								"WHERE lock = True", (vendor_id, ))
			for row in self.cursor.fetchall() : # check for active PO
				self.purchase_order_id = row[0]
				self.datetime = row[1]
				self.get_object('entry1').set_text(row[2])
				self.products_from_existing_po ()
				break
			else:
				self.cursor.execute("SELECT "
									"CURRENT_DATE, "
									"format_date(CURRENT_DATE) ")
				for row in self.cursor.fetchall() : 
					self.purchase_order_id = None
					self.datetime = row[0]
					self.get_object('entry1').set_text(row[1])
			self.calculate_totals ()

	def editing_canceled (self, cellrenderer):
<<<<<<< HEAD
		"all widgets need to connect to this function to release row locks"
		"removing row locks is as simple as doing a rollback or commit"
		"all rows need to be locked whenever a widget is opened to "
		"edit an invoice row"
		db.rollback() #remove row lock by rolling back
=======
		"all item widgets need to connect to this function to release row locks"
		"removing row locks is as simple as doing a rollback or commit;"
		"every time a widget is opened to edit an invoice row,"
		"a lock needs to be acquired to block other concurrent users"
		self.db.rollback() #remove row lock by rolling back
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473

	################## start qty

	def qty_editing_started (self, cellrenderer, celleditable, path):
		row_id = self.p_o_store[path][0]
		cursor = db.cursor()
		try:
			cursor.execute("SELECT qty::text FROM purchase_order_line_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			db.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			celleditable.destroy()
			return False
		for row in cursor.fetchall():
			celleditable.set_text(row[0])
		cursor.close()

	def qty_edited(self, widget, path, text):
		cursor = self.db.cursor()
		_iter = self.p_o_store.get_iter (path)
		self.check_po_item_id (_iter)
		line_id = self.p_o_store[_iter][0]
		try:
			cursor.execute("UPDATE purchase_order_line_items "
								"SET (qty, ext_price) = (%s, %s * price) "
								"WHERE id = %s "
								"RETURNING qty::text, ext_price::text", 
								(text, text, line_id))
		except psycopg2.DataError as e:
			self.show_message (str(e))
			self.db.rollback()
			return
		for row in cursor.fetchall():
			qty = row[0]
			ext_price = row[1]
			self.p_o_store[_iter][1] = qty
			self.p_o_store[_iter][9] = ext_price
		self.db.commit()
		self.calculate_totals ()

	################## start order number

	def order_number_editing_started (self, renderer, entry, path):
		row_id = self.p_o_store[path][0]
		cursor = db.cursor()
		try:
			cursor.execute("SELECT order_number FROM purchase_order_line_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			db.rollback()
			cursor.close()
			error = str(e) + "Somebody else is editing this row"
			self.show_message (error)
			entry.destroy()
			return False
		for row in cursor.fetchall():
			entry.set_text(row[0])
		cursor.close()
		entry.set_completion(self.order_number_completion)
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
		self.cursor.execute("UPDATE purchase_order_line_items "
							"SET order_number = %s WHERE id = %s",
							(order_number, row_id))
		self.db.commit()

	def order_number_match_selected (self, completion, store, _iter):
		product_id = store[_iter][0]
		_iter = self.p_o_store.get_iter(self.path)
		self.save_product (_iter, product_id)

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
		cursor = self.db.cursor()
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
		
	################## start remark

	def remark_edited(self, widget, path, text):
		_iter = self.p_o_store.get_iter(path)
		self.p_o_store[_iter][7] = text
		row_id = self.p_o_store[_iter][0] 
		cursor = self.db.cursor()
		cursor.execute("UPDATE purchase_order_line_items SET remark = %s "
							"WHERE id = %s", (text, row_id))
		cursor.close()
		self.db.commit()
		
	def remark_editing_started (self, cellrenderer, entry, path):
		row_id = self.p_o_store[path][0]
		cursor = db.cursor()
		try:
			cursor.execute("SELECT remark FROM purchase_order_line_items "
							"WHERE id = %s FOR UPDATE NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			db.rollback()
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
		product_id = self.product_store[iter_][0]
		_iter = self.p_o_store.get_iter(path)
		self.save_product (_iter, int(product_id))

	def product_renderer_editing_started (self, renderer, combo, path):
		combo.connect('remove-widget', self.product_widget_removed, path)
		entry = combo.get_child()
		row_id = self.p_o_store[path][0]
		cursor = db.cursor()
		try:
			cursor.execute("SELECT p.name "
							"FROM purchase_order_line_items AS poi "
							"JOIN products AS p ON p.id = poi.product_id "
							"WHERE poi.id = %s "
							"FOR UPDATE OF poi NOWAIT", (row_id,))
		except psycopg2.OperationalError as e:
			db.rollback()
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
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE expense_account = True ORDER BY name")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.expense_account_store.append([str(account_number), account_name])
		self.cursor.execute("SELECT number, name FROM gl_accounts "
							"WHERE revenue_account = True ORDER BY name")
		for row in self.cursor.fetchall():
			account_number = row[0]
			account_name = row[1]
			self.revenue_account_store.append([str(account_number), account_name])

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

	def product_widget_removed (self, combo, path):
		if self.p_o_store[path][4] == True:
			return
		_iter = self.p_o_store.get_iter(path)
		entry = combo.get_child()
		product_text = entry.get_text()
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
			import products
			product_id = products.add_non_stock_product(
												self.vendor_id, product_name,
												product_number, expense_account,
												revenue_account)
			self.p_o_store[_iter][2] = product_id
			self.save_product (_iter, product_id)
			self.calculate_totals ()
		self.get_object ('entry3').set_text('')
		self.get_object ('button1').set_sensitive(False)
	
	def product_edited (self, cellrenderertext, text, path):
		"Posting does not allow product names to be edited directly"
		db.rollback () # remove row lock, see editing_canceled

	def save_product (self, _iter, product_id):
		if self.check_for_duplicate_products (product_id, _iter) == True:
			db.rollback() # remove row lock, see editing_canceled
			return # duplicate product, skip the rest of the code
		self.save_product_without_duplicate_check (_iter, product_id)

	def save_product_without_duplicate_check(self, _iter, product_id):
		cursor = self.db.cursor()
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
						"(UPDATE purchase_order_line_items "
						"SET "
							"(product_id, "
							"price, "
							"ext_price, "
							"order_number"
							") " 
						"= "
							"(%s, "
							"(SELECT cost FROM p_info), "
							"qty * (SELECT cost FROM p_info), "
							"(SELECT vendor_sku FROM p_info)"
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
						(self.vendor_id, product_id, product_id, row_id))
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
		self.db.commit()
		self.calculate_totals ()

	def product_match_string(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_match_selected(self, completion, model, iter_):
		product_id = model[iter_][0]
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
				dialog = self.get_object('duplicate_product_dialog')
				result = dialog.run()
				if result == Gtk.ResponseType.ACCEPT :
					row_id = row[0]
					qty = qty_spinbutton.get_text()
					self.cursor.execute("UPDATE purchase_order_line_items "
										"SET qty = %s WHERE id = %s", 
										(qty, row_id))
					self.db.commit()
					self.calculate_totals ()
					self.delete_entry_activated ()
				elif result == Gtk.ResponseType.REJECT:
					self.save_product_without_duplicate_check(_iter, product_id)
				dialog.hide()
				return True
		return False

	def check_po_item_id (self, _iter):
		line = self.p_o_store[_iter]
<<<<<<< HEAD
		if line[2] == 0:
			db.rollback()
			return # no valid product yet
=======
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473
		row_id = line[0]
		if row_id != 0:
			return # we have a valid id
		cursor = self.db.cursor()
		qty = line[1]
		product_id = line[2]
		order_number = line[3]
		remark = line[7]
		price = line[8]
		ext_price = line[9]
		line[10] = False
		purchase_order_id = line[13]
		cursor.execute("INSERT INTO purchase_order_line_items "
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
<<<<<<< HEAD
		db.commit()
		#if a default expense account is available, use it
		self.cursor.execute("SELECT default_expense_account FROM products WHERE id = %s", (product_id,))
		for row in self.cursor.fetchall():
			expense_account = row[0]
			break
		else: 
			expense_account = None
		if row_id == 0:
			self.cursor.execute("INSERT INTO purchase_order_line_items "
								"(purchase_order_id, qty, product_id, remark, "
								"price, ext_price, canceled, expense_account, "
								"order_number) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id", (purchase_order_id, qty, 
								product_id, remark, price, ext_price, False, 
								expense_account, order_number))
			row_id = self.cursor.fetchone()[0]
			line[0] = row_id
		else:
			self.cursor.execute("UPDATE purchase_order_line_items "
								"SET (purchase_order_id, qty, product_id, "
								"remark, price, ext_price, expense_account, "
								"order_number) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s) "
								"WHERE id = %s", (purchase_order_id, qty, 
								product_id, remark, price, ext_price, 
								expense_account, order_number,  row_id))
		db.commit()
=======
		self.db.commit()
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473
		self.calculate_totals ()

	def calculate_totals(self):
		cursor = self.db.cursor()
		cursor.execute("SELECT COALESCE(SUM(ext_price), 0.0)::money "
						"FROM purchase_order_line_items "
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
			self.purchase_order_id = self.cursor.fetchone()[0]

	def new_entry_clicked (self, button):
		self.add_entry ()

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
			iter_ = self.p_o_store.append([0, '1', product_id, 
										"Select order number", 
										False, "Select a stock item" , "", "", 
										'1', '1', True, int(self.vendor_id),
										'', self.purchase_order_id, False])
			self.check_po_item_id (iter_)
			treeview = self.get_object('treeview2')
			c = treeview.get_column(0)
			path = self.p_o_store.get_path(iter_)
			treeview.set_cursor(path, c, True)
<<<<<<< HEAD
		db.commit()
		self.p_o_store.append([0, Decimal(1.0), 0, "Select order number", 
								False, "Select a stock item" , "", "", 
								Decimal(1), Decimal(1), True, int(self.vendor_id),
								'', self.purchase_order_id, False])

	def select_new_entry (self):
		treeview = self.builder.get_object('treeview2')
		for index, row in enumerate(self.p_o_store):
			if row[10] == True:
				c = treeview.get_column(0)
				treeview.set_cursor(index , c, True)
				break
=======
		self.db.commit()
>>>>>>> 4d5dc48fbda038090742b7a0a8a70063f684b473

	def delete_entry_activated (self, menuitem = None):
		selection = self.get_object("treeview-selection")
		model, path = selection.get_selected_rows ()
		if path != []:
			line_id = model[path][0]
			self.cursor.execute("DELETE FROM purchase_order_line_items "
								"WHERE id = %s", (line_id,))
			db.commit()
			self.products_from_existing_po ()

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
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass

	def window_key_event(self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'F1':
			self.help_clicked (None)
		if keyname == 'F2':
			self.add_entry()
		if keyname == 'F3':
			self.delete_entry_activated ()

	def barcode_entry_key_released (self, entry, event):
		if event.get_state() & Gdk.ModifierType.SHIFT_MASK: #shift held down
			barcode = entry.get_text()
			if barcode == "":
				return # blank barcode
			self.cursor.execute("SELECT id FROM products "
								"WHERE barcode = %s", (barcode,))
			for row in self.cursor.fetchall():
				product_id = row[0]
				break
			else:
				return
			keyname = Gdk.keyval_name(event.keyval)
			if keyname == 'Return' or keyname == "KP_Enter": # enter key(s)
				for index, row in enumerate(self.p_o_store):
					if row[2] == product_id:
						row[1] -= 1
						self.save_purchase_order_line (index)
						break

	def barcode_entry_activated (self, entry):
		barcode = entry.get_text()
		entry.select_region(0,-1)
		if barcode == "":
			return # blank barcode
		self.cursor.execute("SELECT id FROM products "
							"WHERE barcode = %s", (barcode,))
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
			self.get_object('entry10').grab_focus()
			barcode_error_dialog = self.get_object('barcode_error_dialog')
			barcode_error_dialog.run()
			barcode_error_dialog.hide()
			return
		for index, row in enumerate(self.p_o_store):
			if row[2] == product_id:
				row[1] += 1
				self.save_purchase_order_line (index)
				break
			continue
		else:
			self.p_o_store.append([0, 1, 0, '', True, '', 
											'', '', 0.00, 0.00, False, 
											int(self.vendor_id), '', 
											self.purchase_order_id, False])
			path = self.p_o_store.iter_n_children ()
			path -= 1 #iter_n_children starts at 1 ; path starts at 0
			_iter = self.p_o_store.get_iter(path)
			self.save_product (_iter, product_id)

	def calendar_day_selected (self, calendar):
		self.datetime = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry1').set_text(day_text)

	def calendar_entry_icon_release (self, widget, icon, void):
		self.calendar.set_relative_to (widget)
		self.calendar.show()

	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()

