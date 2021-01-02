# product_print_label.py
#
# Copyright (C) 2020 - reuben
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


from gi.repository import Gtk
import subprocess
from constants import DB, ui_directory, template_dir, broadcaster
import barcode_generator, pricing

UI_FILE = ui_directory + "/product_print_label.ui"

class Item(object):
	pass

class ProductPrintLabelGUI (Gtk.Builder):
	def __init__(self, product_id = None):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.product_id = product_id
		self.product_store = self.get_object('product_store')
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.populate_stores ()
		if product_id != None: # triggers load_product
			self.get_object('product_combo').set_active_id(str(product_id)) 
		self.window = self.get_object('window')
		self.window.show_all()

	def destroy (self, widget, event):
		self.cursor.close()
	
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_stores (self):
		self.cursor.execute("SELECT id::text, name, ext_name "
							"FROM products WHERE deleted = False "
							"ORDER BY name, ext_name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		store = self.get_object('location_store')
		self.cursor.execute("SELECT id::text, name FROM locations "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			store.append(row)
		self.get_object('location_combo').set_active(0) # triggers load_product
		DB.rollback()
		
	def completion_match_selected (self, entrycompletion, model, titer):
		self.product_id = model[titer][0]
		self.load_product()

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.load_product()

	def location_combo_changed (self, combobox):
		location_id = combobox.get_active_id()
		if location_id != None and self.product_id != None:
			self.load_product ()

	def load_product (self):
		location_id = self.get_object('location_combo').get_active_id()
		self.cursor.execute("SELECT aisle, rack, cart, shelf, cabinet, "
						"drawer, bin FROM product_location "
						"WHERE (product_id, location_id) = (%s, %s) ",
						(self.product_id, location_id))
		for row in self.cursor.fetchall():
			self.get_object('entry5').set_text(row[0])
			self.get_object('entry6').set_text(row[1])
			self.get_object('entry7').set_text(row[2])
			self.get_object('entry8').set_text(row[3])
			self.get_object('entry9').set_text(row[4])
			self.get_object('entry10').set_text(row[5])
			self.get_object('entry11').set_text(row[6])
		DB.rollback()

	def print_label_clicked (self, button):
		self.generate_label()
		subprocess.Popen(["soffice", "-p", self.label_file])
		self.window.destroy()

	def view_label_clicked (self, button):
		self.generate_label()
		subprocess.Popen(["soffice", self.label_file])

	def generate_label (self):
		label = Item()
		label.aisle = self.get_object('entry5').get_text()
		label.cart = self.get_object('entry6').get_text()
		label.rack = self.get_object('entry7').get_text()
		label.shelf = self.get_object('entry8').get_text()
		label.cabinet = self.get_object('entry9').get_text()
		label.drawer = self.get_object('entry10').get_text()
		label.bin = self.get_object('entry11').get_text()
		self.cursor.execute("SELECT name, description, barcode FROM products "
							"WHERE id = (%s)",[self.product_id])
		for row in self.cursor.fetchall():
			label.name= row[0]
			label.description = row[1]
			label.code128 = barcode_generator.makeCode128(row[2])
			label.barcode = row[2]
		price = pricing.product_retail_price (self.product_id)
		label.price = '${:,.2f}'.format(price)
		data = dict(label = label)
		from py3o.template import Template
		self.label_file = "/tmp/product_label.odt"
		t = Template(template_dir+"/product_label_template.odt", 
													self.label_file )
		t.render(data)
		DB.rollback()




