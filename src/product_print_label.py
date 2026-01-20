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


from gi.repository import Gtk, GLib
import subprocess, os, glob
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
		self.populate_printers()
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
		self.cursor.execute("SELECT id::text, name, ext_name, barcode "
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

	def populate_system_labels(self):
		store = self.get_object('printer_template_store')
		store.clear()
		for path in glob.glob('./templates/product*.odt'):
			name = path.replace('./templates/', '')
			store.append(["odt", name])
			
	def populate_zebra_labels(self):
		store = self.get_object('printer_template_store')
		store.clear()
		for path in glob.glob('./templates/Zebra/*'):
			name = path.replace('./templates/', '')
			store.append(["zpl", name])

	def populate_printers(self):
		store = self.get_object('printer_store')
		store.clear()
		store.append(['0', 'System', 'None', 0])
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, host, port "
						"FROM settings.zebra_printers")
		for row in cursor.fetchall():
			store.append(row)
		
	def completion_match_selected (self, entrycompletion, model, tree_iter):
		self.product_id = model[tree_iter][0]
		barcode = model[tree_iter][3]
		self.get_object('barcode_entry').set_text(barcode)
		self.load_product()

	def barcode_entry_focus_in_event (self, entry, event):
		GLib.idle_add(entry.select_region, 0, -1)

	def barcode_entry_activated (self, entry):
		product_id = entry.get_text()
		if self.get_object('product_combo').set_active_id(product_id):
			if self.get_object('print_label_checkbutton').get_active():
				self.print_label()
		entry.select_region(0, -1)

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id != None:
			model = combobox.get_model()
			iter_ = combobox.get_active_iter()
			barcode = model[iter_][3]
			self.get_object('barcode_entry').set_text(barcode)
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
		if self.get_object('print_label_checkbutton').get_active():
			self.print_label()
		DB.rollback()

	def printer_combo_changed (self, combobox):
		printer_id = combobox.get_active_id()
		if printer_id == None:
			return
		if printer_id == '0':
			self.populate_system_labels()
		else:
			self.populate_zebra_labels()

	def printer_template_combo_changed (self, combobox):
		if combobox.get_active_iter() == None:
			self.get_object('print_label_checkbutton').set_sensitive(False)
			self.get_object('print_label_checkbutton').set_active(False)
		else:
			self.get_object('print_label_checkbutton').set_sensitive(True)

	def print_label (self):
		print("print")
		product_name = self.get_object('product_name_entry').get_text()
		barcode = self.get_object('barcode_entry').get_text()
		printer_id = self.get_object('printer_combo').get_active_id()
		if printer_id == None:
			return
		template_id = self.get_object('template_combo').get_active_id()
		if template_id == None:
			return
		template_iter = self.get_object('template_combo').get_active_iter()
		model = self.get_object('printer_template_store')
		template = model[template_iter][1]
		try:
			template_dir = os.path.join( os.getcwd() , "templates")
			abs_file_path = os.path.join(template_dir, template)
		except Exception as e:
			print(e)
			self.show_message(str(e))
			return
		if template_id == 'zpl':
			self.zebra_print_label(barcode, product_name, 1, abs_file_path)
		elif template_id == 'odt':
			label_file = self.system_print_label(barcode, product_name, 1, abs_file_path)
			
	def zebra_print_label (self, barcode, product_name, label_qty, template_file):
		printer_iter = self.get_object('printer_combo').get_active_iter()
		model = self.get_object('printer_store')
		host = model[printer_iter][2]
		port = model[printer_iter][3]
		try:
			with open(template_file) as template:
				template_str = template.read()
		except Exception as e:
			print (e)
			return
		import socket
		mysocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			mysocket.connect((host, port))
		except OSError as e:
			print(e)
			self.show_message(str(e))
			return
		for i in range(label_qty):
			barcode_str = template_str % (barcode, product_name) 
			mysocket.send(bytes(barcode_str, 'utf-8'))#using bytes 
		mysocket.close () #closing connection

	def system_print_label (self, barcode, product_name, template):
		label_file = self.generate_label()
		subprocess.call(["soffice", "--headless", "-p", label_file])

	def print_label_clicked (self, button):
		self.print_label()

	def view_label_clicked (self, button):
		label_file = self.generate_label()
		subprocess.Popen(["soffice", label_file])

	def generate_label (self):
		product_name = self.get_object('product_name_entry').get_text()
		barcode = self.get_object('barcode_entry').get_text()
		label = Item()
		label.code128 = barcode_generator.makeCode128(str(barcode))
		label.barcode = barcode
		label.name = product_name
		label.aisle = self.get_object('entry5').get_text()
		label.cart = self.get_object('entry6').get_text()
		label.rack = self.get_object('entry7').get_text()
		label.shelf = self.get_object('entry8').get_text()
		label.cabinet = self.get_object('entry9').get_text()
		label.drawer = self.get_object('entry10').get_text()
		label.bin = self.get_object('entry11').get_text()
		price = pricing.product_retail_price (self.product_id)
		label.price = '${:,.2f}'.format(price)
		head, template_name = os.path.split(template)
		from py3o.template import Template
		label_file = os.path.join("/tmp", template_name)
		t = Template(template, label_file)
		data = dict(label = label)
		t.render(data)
		return label_file

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



