# contact_transactions.py
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


from gi.repository import Gtk, GObject, Gdk, GLib
from multiprocessing import Queue, Process
from queue import Empty
from subprocess import Popen, PIPE, STDOUT
import os, sys, time, subprocess, sane, psycopg2
import dateutils

UI_FILE = "src/reports/contact_transactions.ui"

class GUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.search_store = Gtk.ListStore(str)
		self.transaction_store = self.builder.get_object('transaction_tree_store')
		self.filter_store = Gtk.ListStore(int, str, bool)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		vendor_completion = self.builder.get_object('vendor_completion')
		vendor_completion.set_match_func(self.vendor_match_func)

		self.treeview = self.builder.get_object('treeview1')

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		#dnd = ('text/uri-list', Gtk.TargetFlags(1), 129)
		#self.treeview.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, [], Gdk.DragAction.COPY)		
		self.treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		self.treeview.connect('drag_data_get', self.on_drag_data_get)
		self.treeview.drag_source_set_target_list([dnd])
		#self.treeview.drag_source_add_text_targets()

		self.vendor_id = None
		self.customer_id = None
		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.customer_store = self.builder.get_object('customer_store')
		self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE (customer, deleted) = "
							"(True, False) ORDER BY name")
		for customer in self.cursor.fetchall():
			id_ = customer[0]
			name = customer[1]
			ext_name = customer[2]
			self.customer_store.append([str(id_) , name, ext_name])

		self.vendor_store = self.builder.get_object('vendor_store')
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE (vendor, deleted) = (True, False) "
							"ORDER BY name")
		for vendor in self.cursor.fetchall():
			id_ = vendor[0]
			name = vendor[1]
			self.vendor_store.append([str(id_) , name])
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		self.data_queue = Queue()
		self.scanner_store = self.builder.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GLib.timeout_add(100, self.populate_scanners)

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

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.transaction_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		product_id = model.get_value(treeiter, 3)
		qty = model.get_value(treeiter, 5)
		data.set_text(str(qty) + ' ' + str(product_id), -1)
		
	def row_activated(self, treeview, path, treeviewcolumn):
		file_id = self.transaction_store[path][0]
		if self.database_type == "customer":
			self.cursor.execute("SELECT name, pdf_data FROM invoices WHERE id = %s", (file_id ,))
		elif self.database_type == "vendor":
			self.cursor.execute("SELECT name, pdf_data FROM purchase_orders WHERE id = %s", (file_id,))
		for row in self.cursor.fetchall():
			file_name = row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open("/tmp/" + file_name,'wb')
			f.write(file_data)
			subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
			f.close()

	def close_transaction_window(self, window, void):
		self.window.destroy()
		return True
		
	def treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		treeiter = model.get_iter(path)
		if event.button == 3 and self.database_type == "vendor":
			self.builder.get_object('menuitem2').set_visible(True)
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			if self.transaction_store.iter_has_child(treeiter) == False:
				self.builder.get_object('menuitem1').set_visible(True)
			else:  # don't show product hub unless right clicking product
				self.builder.get_object('menuitem1').set_visible(False)
		else:
			self.builder.get_object('menuitem2').set_visible(False)
			self.builder.get_object('menuitem1').set_visible(False)

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][3]
		import product_hub
		product_hub.ProductHubGUI(self.main, product_id)
		
	def search_forward(self, widget):
		c = self.treeview.get_column(0)
		if self.builder.get_object('checkbutton1').get_active() == False :
			self.treeview.collapse_all()
		try:
			self.search_iter += 1
			row = self.search_store[self.search_iter]
		except: # tumble over to the start			
			self.search_iter = 0
			row = ["1000000"] # a number that is not valid so no row is selected
			for i in self.search_store: 
				row = self.search_store[self.search_iter]
				break # we have a valid row now
						
		path = Gtk.TreePath.new_from_string(row[0])
		self.treeview.expand_to_path(path)
		self.treeview.set_cursor(row , c, True)

	def search_backward(self, widget):
		c = self.treeview.get_column(0)		
		if self.builder.get_object('checkbutton1').get_active() == False :
			self.treeview.collapse_all()
		try:
			self.search_iter -= 1
			row = self.search_store[self.search_iter]
		except: # tumble over to the end
			self.search_iter = len(self.search_store) - 1
			row = ["1000000"] # a number that is not valid
			for i in self.search_store: 
				row = self.search_store[self.search_iter]
				break # we have a valid row now
			
		path = Gtk.TreePath.new_from_string(row[0])
		self.treeview.expand_to_path(path)
		self.treeview.set_cursor(row , c, True)

	def search_changed(self, widget): 
		search_text = widget.get_text().lower()
		self.search_store.clear()
		self.treeview.collapse_all()
		treeiter = self.transaction_store.get_iter_first()
		while treeiter != None:
			for cell in self.transaction_store[treeiter][:]:
				if search_text in str(cell).lower():
					cursor_iter = self.transaction_store.get_string_from_iter(treeiter)
					self.search_store.append([cursor_iter])
			if self.transaction_store.iter_has_child(treeiter):
				childiter = self.transaction_store.iter_children(treeiter)
				while childiter != None:
					cursor_iter = self.transaction_store.get_string_from_iter(childiter)
					for cell in self.transaction_store[childiter][:]:
						if search_text in str(cell).lower():
							self.search_store.append([cursor_iter])
					childiter = self.transaction_store.iter_next(childiter)
			treeiter = self.transaction_store.iter_next(treeiter)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_view_all_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_customer_invoices ()

	def customer_changed(self, combo):
		customer_id = combo.get_active_id()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.load_customer_invoices ()

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.load_customer_invoices ()
		
	def load_customer_invoices (self):
		self.transaction_store.clear()
		if self.builder.get_object('checkbutton4').get_active() == True:
			self.cursor.execute("SELECT id, name, date_created, total "
								"FROM invoices "
								"WHERE canceled = false "
								"ORDER BY date_created")
		else:
			if self.customer_id == None:
				return # no customer selected yet
			self.cursor.execute("SELECT id, name, date_created, total "
								"FROM invoices WHERE (customer_id, canceled) = "
								"(%s, false) ORDER BY date_created", 
								(self.customer_id,))
		self.builder.get_object('treeviewcolumn6').set_visible(False)
		self.database_type = "customer"
		self.builder.get_object('combobox-entry').set_text('')
		self.builder.get_object('checkbutton3').set_active(False)
		for invoice in self.cursor.fetchall():
			id_ = invoice[0]
			name = invoice[1]
			date = invoice[2]
			date_formatted = dateutils.datetime_to_text(date)
			remark = ''
			total = invoice[3]
			tree_item = self.transaction_store.append(None, [id_, str(date), 
															date_formatted, 0,
															name, "", remark, 
															total, ""])
			self.cursor.execute("SELECT ili.id, product_id, name, qty, remark, "
									"price "
								"FROM invoice_line_items AS ili "
								"JOIN products ON ili.product_id = products.id "
								"WHERE invoice_id = %s", (id_,))
			for line in self.cursor.fetchall():
				line_id = line[0]
				product_id = line[1]
				product_name = line[2]
				qty = line[3]
				remark = line[4]
				price = line[5]
				self.transaction_store.append(tree_item, [line_id, "", "", product_id,
												product_name, str(qty),
												remark, price, ""])
			while Gtk.events_pending():
				Gtk.main_iteration()

	def vendor_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.vendor_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def vendor_view_all_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_vendor_purchase_orders ()
		
	def vendor_changed(self, combo):
		vendor_id = combo.get_active_id ()
		if vendor_id == None:
			return
		self.vendor_id = vendor_id
		self.load_vendor_purchase_orders ()

	def vendor_match_selected (self, completion, model, iter):
		self.vendor_id = model[iter][0]
		self.load_vendor_purchase_orders ()

	def load_vendor_purchase_orders (self):
		self.transaction_store.clear()
		if self.builder.get_object('checkbutton3').get_active() == True:
			self.cursor.execute("SELECT id, name, date_created, total "
								"FROM purchase_orders "
								"WHERE canceled =  false "
								"ORDER BY date_created")
		else:
			if self.vendor_id == None:
				return # no vendor selected yet
			self.cursor.execute("SELECT id, name, date_created, total "
								"FROM purchase_orders "
								"WHERE (vendor_id, canceled) = "
								"(%s, False) ORDER BY date_created", 
								(self.vendor_id,))
		self.builder.get_object('treeviewcolumn6').set_visible(True)
		self.database_type = "vendor"
		self.builder.get_object('combobox-entry1').set_text('')
		self.builder.get_object('checkbutton4').set_active(False)
		for po in self.cursor.fetchall():
			id_ = po[0]
			name = po[1]
			date = po[2]
			date_formatted = dateutils.datetime_to_text(date)
			remark = ""
			total = po[3]
			tree_item = self.transaction_store.append(None, [id_, str(date), 
														date_formatted, 0, name, 
														"", remark, total, ""])
			self.cursor.execute("SELECT poli.id, poli.qty, remark, "
								"poli.price, product_id, name, order_number "
								"FROM purchase_order_line_items AS poli "
								"JOIN products "
								"ON products.id = poli.product_id "
								"WHERE purchase_order_id = "
								"%s", (id_,))
			for line in self.cursor.fetchall():
				line_id = line[0]
				qty = line[1]
				remark = line[2]
				price = line[3]
				product_id = line[4]
				product_name = line[5]
				order_number = line[6]
				self.transaction_store.append(tree_item, [line_id, "", "", product_id,
												product_name, str(qty), remark, 
												price, order_number])
			while Gtk.events_pending():
				Gtk.main_iteration()

	def view_attachment_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		file_id = model[path][0]
		treeiter = model.get_iter (path)
		if self.transaction_store.iter_has_child(treeiter):
			self.cursor.execute("SELECT attached_pdf FROM purchase_orders "
								"WHERE id = %s", (file_id,))
			for row in self.cursor.fetchall():
				file_name = "/tmp/Attachment.pdf"
				file_data = row[0]
				if file_data == None:
					self.run_attach_dialog ()
					return
				f = open(file_name,'wb')
				f.write(file_data)
				subprocess.call("xdg-open %s" % file_name, shell = True)
				f.close()

	def run_attach_dialog (self):
		dialog = self.builder.get_object('no_attachment_dialog')
		self.builder.get_object('button8').set_sensitive (False)
		self.spinner = self.builder.get_object('spinner1')
		self.spinner.stop ()
		self.spinner.set_visible (False)
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
		self.spinner.start()
		self.spinner.set_visible(True)
		self.result_buffer = self.builder.get_object('pdf_opt_result_buffer')
		self.result_buffer.set_text('', -1)
		self.sw = self.builder.get_object('scrolledwindow2')
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
		selection = self.builder.get_object("treeview-selection1")
		model, path = selection.get_selected_rows()
		po_id = model[path][0]
		f = open("/tmp/opt.pdf",'rb')
		file_data = f.read ()
		binary = psycopg2.Binary (file_data)
		f.close()
		self.cursor.execute("UPDATE purchase_orders SET attached_pdf = %s "
							"WHERE id = %s", (binary, po_id))
		self.db.commit()


		


