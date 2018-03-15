# vendor_history.py
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
from decimal import Decimal
import os, subprocess, sane, psycopg2
import dateutils

UI_FILE = "src/reports/vendor_history.ui"

class VendorHistoryGUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.search_store = Gtk.ListStore(str)
		self.po_store = self.builder.get_object('purchase_order_store')
		vendor_completion = self.builder.get_object('vendor_completion')
		vendor_completion.set_match_func(self.vendor_match_func)

		treeview = self.builder.get_object('treeview2')

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		treeview.connect('drag_data_get', self.on_drag_data_get)
		treeview.drag_source_set_target_list([dnd])

		self.vendor_id = 0
		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.vendor_store = self.builder.get_object('vendor_store')
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE (vendor, deleted) = (True, False) "
							"ORDER BY name")
		for vendor in self.cursor.fetchall():
			id_ = vendor[0]
			name = vendor[1]
			self.vendor_store.append([str(id_) , name])

		column = self.builder.get_object ('treeviewcolumn12')
		renderer = self.builder.get_object ('cellrenderertext14')
		column.set_cell_data_func(renderer, self.amount_cell_func, 6)

		column = self.builder.get_object ('treeviewcolumn5')
		renderer = self.builder.get_object ('cellrenderertext5')
		column.set_cell_data_func(renderer, self.amount_cell_func, 5)

		self.cursor.execute("SELECT qty_prec, price_prec FROM settings.purchase_order")
		for row in self.cursor.fetchall():
			qty_prec = row[0]
			price_prec = row[1]
			
		column = self.builder.get_object ('treeviewcolumn7')
		renderer = self.builder.get_object ('cellrenderertext8')
		column.set_cell_data_func(renderer, self.qty_cell_func, qty_prec)

		column = self.builder.get_object ('treeviewcolumn11')
		renderer = self.builder.get_object ('cellrenderertext13')
		column.set_cell_data_func(renderer, self.price_cell_func, price_prec)
		
		self.product_name = ''
		self.product_ext_name = ''
		self.remark = ''
		self.order_number = ''
		
		self.filter = self.builder.get_object ('purchase_order_items_filter')
		self.filter.set_visible_func(self.filter_func)
		
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

	def price_cell_func(self, treecolumn, cellrenderer, model, iter1, prec):
		price = '{:.{prec}f}'.format(model.get_value(iter1, 5), prec=prec)
		cellrenderer.set_property("text" , price)

	def qty_cell_func(self, treecolumn, cellrenderer, model, iter1, prec):
		qty = '{:.{prec}f}'.format(model.get_value(iter1, 0), prec=prec)
		cellrenderer.set_property("text" , qty)

	def amount_cell_func(self, treecolumn, cellrenderer, model, iter1, column):
		amount = '{:,.2f}'.format(model.get_value(iter1, column))
		cellrenderer.set_property("text" , amount)

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.po_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		qty = model.get_value(treeiter, 0)
		product_id = model.get_value(treeiter, 1)
		data.set_text(str(qty) + ' ' + str(product_id), -1)
		
	def row_activated(self, treeview, path, treeviewcolumn):
		file_id = self.po_store[path][0]
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
		
	def po_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('po_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			
	def po_item_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('po_item_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		import product_hub
		product_hub.ProductHubGUI(self.main, product_id)

	def vendor_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.vendor_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def vendor_view_all_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_vendor_purchase_orders ()
		if active == True:
			self.builder.get_object('checkbutton1').set_active(False)
		
	def vendor_changed(self, combo):
		vendor_id = combo.get_active_id ()
		if vendor_id == None:
			return
		self.vendor_id = vendor_id
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('checkbutton3').set_active(False)
		self.load_vendor_purchase_orders ()

	def vendor_match_selected (self, completion, model, iter):
		self.vendor_id = model[iter][0]
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('checkbutton3').set_active(False)
		self.load_vendor_purchase_orders ()

	def load_vendor_purchase_orders (self):
		self.po_store.clear()
		total = Decimal()
		if self.builder.get_object('checkbutton3').get_active() == True:
			self.cursor.execute("SELECT id, date_created, name, "
								"COALESCE(total, 0.00) "
								"FROM purchase_orders "
								"WHERE canceled =  false "
								"ORDER BY date_created")
		else:
			self.cursor.execute("SELECT id, date_created, name, "
								"COALESCE(total, 0.00) "
								"FROM purchase_orders "
								"WHERE (vendor_id, canceled) = "
								"(%s, False) ORDER BY date_created", 
								(self.vendor_id,))
		for po in self.cursor.fetchall():
			id_ = po[0]
			date = po[1]
			date_formatted = dateutils.datetime_to_text(date)
			name = po[2]
			remark = ""
			amount = po[3]
			total += amount
			self.po_store.append([id_, str(date), date_formatted, name, 
														remark, amount])
		self.builder.get_object('label3').set_label(str(total))

	def invoice_row_changed (self, selection):
		self.builder.get_object('checkbutton1').set_active(False)
		self.load_purchase_order_items ()

	def all_products_togglebutton_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_purchase_order_items (load_all = active)
		if active == True:
			self.builder.get_object('checkbutton3').set_active(False)

	def load_purchase_order_items (self, load_all = False):
		store = self.builder.get_object('purchase_order_items_store')
		store.clear()
		if load_all == True:			
			self.cursor.execute("SELECT poli.id, poli.qty,  "
								"product_id, name, ext_name, poli.price, "
								"poli.ext_price, remark, order_number "
								"FROM purchase_order_line_items AS poli "
								"JOIN products "
								"ON products.id = poli.product_id "
								"ORDER BY name ")
		else:
			selection = self.builder.get_object('treeview-selection1')
			model, paths = selection.get_selected_rows ()
			id_list = []
			for path in paths:
				id_list.append(model[path][0])
			rows = len(id_list)
			if rows == 0:
				return						 #nothing selected
			elif rows > 1:
				args = str(tuple(id_list))
			else:				# single variables do not work in tuple > SQL
				args = "(%s)" % id_list[0] 
			self.cursor.execute("SELECT poli.id, poli.qty,  "
								"product_id, name, ext_name, poli.price, "
								"poli.ext_price, remark, order_number "
								"FROM purchase_order_line_items AS poli "
								"JOIN products "
								"ON products.id = poli.product_id "
								"WHERE purchase_order_id IN " + args)
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			ext_name = row[4]
			price = row[5]
			ext_price = row[6]
			remark = row[7]
			order_number = row[8]
			store.append([float(qty), product_id,
											product_name, ext_name, remark, 
											price, ext_price, order_number])
			while Gtk.events_pending():
				Gtk.main_iteration()

	def search_entry_search_changed (self, entry):
		self.product_name = self.builder.get_object('searchentry1').get_text().lower()
		self.product_ext_name = self.builder.get_object('searchentry2').get_text().lower()
		self.remark = self.builder.get_object('searchentry3').get_text().lower()
		self.order_number = self.builder.get_object('searchentry4').get_text().lower()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.product_name.split():
			if text not in model[tree_iter][2].lower():
				return False
		for text in self.product_ext_name.split():
			if text not in model[tree_iter][3].lower():
				return False
		for text in self.remark.split():
			if text not in model[tree_iter][4].lower():
				return False
		for text in self.order_number.split():
			if text not in model[tree_iter][7].lower():
				return False
		return True

	def view_attachment_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		file_id = model[path][0]
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
		device_address = self.builder.get_object("combobox").get_active_id()
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


		


