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
from db.transactor import mark_purchase_order_received
import locations, barcode_generator
from pricing import product_retail_price
from db_connection import DB
from constants import ui_directory, template_dir

UI_FILE = ui_directory + "/receive_orders.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class ReceiveOrdersGUI:
	def __init__(self):

		self.previous_keyname = None
		self.populating = False
		self.receive_line = None # the line the spinbutton counts, or None
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

	def destroy (self, widget):
		pass

	def populate_purchase_order_combo(self):
		self.builder.get_object('button3').set_sensitive(False)
		self.purchase_order_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name FROM purchase_orders "
							"WHERE (canceled, invoiced, closed, received) = "
							"(False, True, True, False) ")
		for row in cursor.fetchall():
			self.purchase_order_store.append(row)
		cursor.close()
		DB.rollback()

	def purchase_order_combo_changed(self, combo):
		self.receive_order_store.clear()
		po_id = combo.get_active_id()
		cursor = DB.cursor()
		cursor.execute("SELECT pli.id, qty::int, product_id, "
							"remark, received, "
							"name, ext_name, cost "
							"FROM purchase_order_items AS pli "
							"JOIN products ON products.id = pli.product_id "
							"AND expense = False "
							"WHERE purchase_order_id = %s "
							"ORDER BY id", (po_id,))
		for row in cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			remark = row[3]
			received = row[4]
			product_name = row[5]
			product_ext_name = row[6]
			cost = row[7]
			sell_price = product_retail_price (product_id)
			self.receive_order_store.append([row_id, qty, product_id, 
											product_name, product_ext_name, 
											remark, received, cost, sell_price])
		cursor.close()
		self.check_if_all_products_received()
		DB.rollback()
	
	def reload_clicked (self, button):
		self.populate_purchase_order_combo()
	
	def focus_in (self, window, event):
		self.populate_location_combo()

	def populate_location_combo (self):
		location_combo = self.builder.get_object('combobox2')
		active_id = location_combo.get_active_id()
		self.location_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in cursor.fetchall():
			self.location_store.append(row)
		cursor.close()
		if active_id == None :
			location_combo.set_active(0)
		else:
			location_combo.set_active_id(active_id)

	def receive_selection_changed (self, selection):
		'''the spinbutton counts the line that is highlighted, so it is loaded
		from the selection and not from an activation: a click activates a row
		in this treeview, but arrow keys only move the selection, and the count
		has to follow either way. The range goes in before the value, or the
		line loaded before this one clamps its count, and the handler writes
		that number back to a line nobody touched'''
		model, path = selection.get_selected_rows()
		spinbutton = self.builder.get_object('spinbutton1')
		self.populating = True # loading a line must not count it in again
		if path == []:
			self.receive_line = None
			spinbutton.set_range(0, 0)
			spinbutton.set_value(0)
		else:
			self.receive_line = path
			spinbutton.set_range(0, self.receive_order_store[path][1])
			spinbutton.set_value(self.receive_order_store[path][6])
		self.populating = False

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('receive_order_item_menu')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def location_clicked (self, widget):
		locations.LocationsGUI()

	def close_purchase_order_clicked (self, button):
		'''posts what has been counted in. The order is marked received only
		once all of it has arrived; short of that it stays on the list above, so
		the rest of the shipment can be counted in and posted when it comes'''
		po_combo = self.builder.get_object('combobox1')
		po_id = po_combo.get_active_id ()
		cursor = DB.cursor()
		#a line this window listed and nobody counted has arrived in the
		#quantity it shows, which is none. Leaving the count NULL would receive
		#it in full, the reading receive () takes of a line it was never shown
		cursor.execute("UPDATE purchase_order_items AS poli SET received = 0 "
						"FROM products AS p "
						"WHERE p.id = poli.product_id "
						"AND poli.received IS NULL "
						"AND (poli.purchase_order_id, p.expense) = (%s, False)",
						(po_id,))
		cursor.close()
		location_id = self.builder.get_object('combobox2').get_active_id()
		inventorying.receive(po_id, location_id)
		mark_purchase_order_received (po_id)
		DB.commit()
		self.populate_purchase_order_combo()

	def check_if_all_products_received (self):
		'''the button posts whatever has been counted in, so what it is called
		is what changes here, not whether it works. The store holds only the
		lines this window lists, which is all the label needs: a line it does
		not show is one nobody can count here, and mark_purchase_order_received
		weighs those up for itself when it decides to close the order'''
		button = self.builder.get_object('button3')
		po_id = self.builder.get_object('combobox1').get_active_id()
		button.set_sensitive(po_id != None)
		for row in self.receive_order_store:
			if row[1] != row[6]:
				button.set_label("Post Partial Receipt")
				return
		button.set_label("Close Purchase Order")

	def receive_all_products_clicked(self, button):
		cursor = DB.cursor()
		for row in self.receive_order_store:
			received = row[6]
			ordered = row[1]
			difference = ordered - received
			row_id = row[0]
			product_id = row[2]
			for i in range(difference):
				GLib.timeout_add(100, self.print_label, product_id)
			row[6] = ordered
			cursor.execute("UPDATE purchase_order_items "
								"SET received = %s WHERE id = %s",
								(ordered, row_id))
			DB.commit()
		cursor.close()
		#the count the spinbutton was loaded with has just changed under it
		selection = self.builder.get_object('treeview-selection1')
		self.receive_selection_changed (selection)
		self.check_if_all_products_received()

	def received_spinbutton_changed (self, spinbutton):
		if self.populating == True:
			return
		path = self.receive_line
		if path == None: # no line is highlighted, so there is none to count
			return
		previous_qty = self.receive_order_store[path][6]
		qty = spinbutton.get_value_as_int()
		row_id = self.receive_order_store[path][0]
		product_id = self.receive_order_store[path][2]
		for i in range(qty - previous_qty):
			GLib.timeout_add(10, self.print_label, product_id)
		self.receive_order_store[path][6] = qty
		cursor = DB.cursor()
		cursor.execute("UPDATE purchase_order_items "
							"SET received = %s WHERE id = %s", (qty, row_id))
		cursor.close()
		DB.commit()
		self.check_if_all_products_received()

	def print_label(self, product_id):
		if self.builder.get_object('checkbutton1').get_active() == False:
			return
		location_id = self.builder.get_object('combobox2').get_active_id()
		label = Item()
		price = product_retail_price (product_id)
		label.price = '${:,.2f}'.format(price)
		cursor = DB.cursor()
		cursor.execute("SELECT aisle, cart, rack, shelf, cabinet, drawer, "
							"bin FROM product_location "
							"WHERE (product_id, location_id) = (%s, %s)",
							(product_id, location_id))
		for row in cursor.fetchall():
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
		cursor.execute("SELECT name, description, barcode "
							"FROM products WHERE id = (%s)",(product_id,))
		for row in cursor.fetchall():
			label.name = row[0]
			label.description = row[1]
			label.code128 = barcode_generator.makeCode128(row[2])
			label.barcode = row[2]
			data = dict(label = label)
			from py3o.template import Template
			label_file = "/tmp/product_label.odt"
			t = Template(template_dir+"/product_label_template.odt", label_file )
			t.render(data) #the self.data holds all the info
			subprocess.call("soffice -p --headless " + label_file, shell = True)
		cursor.close()
		DB.rollback()







		
