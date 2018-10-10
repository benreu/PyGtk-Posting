# receive_orders.py
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

from gi.repository import Gtk, GLib
import subprocess
from inventory import inventorying
import locations, barcode_generator
from pricing import product_retail_price
import main

UI_FILE = main.ui_directory + "/receive_orders.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class ReceiveOrdersGUI:
	def __init__(self, db):

		self.db = db
		self.cursor = db.cursor()
		self.previous_keyname = None
		self.ascending = False
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.purchase_order_store = self.builder.get_object('purchase_order_store')
		self.receive_order_store = self.builder.get_object('receive_order_store')
		self.location_store = self.builder.get_object('location_store')

		self.populate_purchase_order_combo()
		self.populate_location_combo()

		window = self.builder.get_object('window1')
		window.show_all()

		
	def populate_purchase_order_combo(self):
		self.purchase_order_store.clear()
		self.cursor.execute("SELECT id::text, name FROM purchase_orders "
							"WHERE (canceled, invoiced, closed, received) = "
							"(False, True, True, False) ")	
		for row in self.cursor.fetchall():
			self.purchase_order_store.append(row)

	def purchase_order_combo_changed(self, combo):
		self.receive_order_store.clear()
		po_id = combo.get_active_id()
		self.cursor.execute("SELECT pli.id, qty, product_id, remark, received, "
							"name, ext_name, cost "
							"FROM purchase_order_line_items AS pli "
							"JOIN products ON products.id = pli.product_id "
							"AND expense = False "
							"WHERE purchase_order_id = %s ORDER BY id", (po_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			remark = row[3]
			received = row[4]
			product_name = row[5]
			product_ext_name = row[6]
			cost = row[7]
			sell_price = product_retail_price (self.db, product_id)
			self.receive_order_store.append([row_id, int(qty), product_id, 
											product_name, product_ext_name, 
											remark, received, cost, sell_price])
		self.check_if_all_products_received()
		
	def focus_in (self, window, event):
		self.populate_location_combo()

	def populate_location_combo (self):
		location_combo = self.builder.get_object('combobox2')
		active_id = location_combo.get_active_id()
		self.location_store.clear()
		self.cursor.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in self.cursor.fetchall():
			self.location_store.append(row)
		if active_id == None :
			location_combo.set_active(0)
		else:
			location_combo.set_active_id(active_id)

	def receive_treeview_activated (self, treeview, path, treeview_column):
		qty = self.receive_order_store[path][6]
		ordered = self.receive_order_store[path][1]
		receive_spinbutton = self.builder.get_object('spinbutton1')
		receive_spinbutton.set_value(qty)
		receive_spinbutton.set_range(0, ordered)

	def location_clicked (self, widget):
		locations.LocationsGUI(self.db)

	def close_purchase_order_clicked (self, button):
		po_combo = self.builder.get_object('combobox1')
		po_id = po_combo.get_active_id ()
		self.cursor.execute("UPDATE purchase_orders SET "
							"received = True WHERE id = %s", (po_id,))
		location_id = self.builder.get_object('combobox2').get_active_id()
		inventorying.receive(self.db, po_id, location_id)
		self.db.commit()
		self.populate_purchase_order_combo()

	def check_if_all_products_received (self):
		for row in self.receive_order_store:
			if row[1] != row[6]:
				self.builder.get_object('button3').set_sensitive(False)
				return
		self.builder.get_object('button3').set_sensitive(True)

	def receive_all_products_clicked(self, button):
		for row in self.receive_order_store:
			received = row[6]
			ordered = row[1]
			difference = ordered - received
			row_id = row[0]
			product_id = row[2]
			for i in range(difference):
				GLib.timeout_add(100, self.print_label, product_id)
			row[6] = ordered
			self.cursor.execute("UPDATE purchase_order_line_items "
								"SET received = %s WHERE id = %s", 
								(ordered, row_id))
			self.db.commit()
		self.builder.get_object('button3').set_sensitive(True)

	def received_spinbutton_changed (self, spinbutton):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			spinbutton.set_text('0')
			return
		previous_qty = self.receive_order_store[path][6]
		qty = spinbutton.get_value()
		difference = int(qty-previous_qty)
		row_id = self.receive_order_store[path][0]
		product_id = self.receive_order_store[path][2]
		for i in range(difference):	
			GLib.timeout_add(10, self.print_label, product_id)
		self.receive_order_store[path][6] = qty
		self.cursor.execute("UPDATE purchase_order_line_items "
							"SET received = %s WHERE id = %s", (qty, row_id))
		self.db.commit()
		self.check_if_all_products_received()

	def print_label(self, product_id):
		if self.builder.get_object('checkbutton1').get_active() == False:
			return
		location_id = self.builder.get_object('combobox2').get_active_id()
		label = Item()
		price = product_retail_price (self.db, product_id)
		label.price = '${:,.2f}'.format(price)
		self.cursor.execute("SELECT aisle, cart, rack, shelf, cabinet, drawer, "
							"bin FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)", 
							(product_id, location_id))
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
		self.cursor.execute("SELECT name, description, barcode "
							"FROM products WHERE id = (%s)",(product_id,))
		for row in self.cursor.fetchall():
			label.name = row[0]
			label.description = row[1]
			label.code128 = barcode_generator.makeCode128(row[2])
			label.barcode = row[2]
			data = dict(label = label)
			from py3o.template import Template
			label_file = "/tmp/product_label.odt"
			t = Template(main.template_dir+"/product_label_template.odt", label_file )
			t.render(data) #the self.data holds all the info
			subprocess.call("soffice -p --headless " + label_file, shell = True)







		
