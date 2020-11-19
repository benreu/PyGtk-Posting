# product_history.py
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


from gi.repository import Gtk
from decimal import Decimal
import subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/product_history.ui"

class ProductHistoryGUI (Gtk.Builder):
	def __init__(self):

		self.search_iter = 0
		
		Gtk.Builder.__init__ (self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		self.invoice_history = None

		self.product_store = self.get_object('product_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM products "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		DB.rollback()
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.cursor.close()

	def notebook_create_window (self, notebook, widget, x, y):
		window = Gtk.Window()
		new_notebook = Gtk.Notebook()
		window.add(new_notebook)
		new_notebook.set_group_name('posting')
		new_notebook.connect('page-removed', self.notebook_page_removed, window)
		window.connect('destroy', self.sub_window_destroyed, new_notebook, notebook)
		window.set_transient_for(self.window)
		window.set_destroy_with_parent(True)
		window.set_size_request(400, 400)
		window.set_title('Product History')
		window.set_icon_name('pygtk-posting')
		window.move(x, y)
		window.show_all()
		return new_notebook

	def notebook_page_removed (self, notebook, child, page, window):
		#destroy the window after the notebook is empty
		if notebook.get_n_pages() == 0:
			window.destroy()

	def sub_window_destroyed (self, window, notebook, dest_notebook):
		# detach the notebook pages in reverse sequence to avoid index errors
		for page_num in reversed(range(notebook.get_n_pages())):
			widget = notebook.get_nth_page(page_num)
			tab_label = notebook.get_tab_label(widget)
			notebook.detach_tab(widget)
			dest_notebook.append_page(widget, tab_label)
			dest_notebook.set_tab_detachable(widget, True)
			dest_notebook.set_tab_reorderable(widget, True)
			dest_notebook.child_set_property(widget, 'tab-expand', True)

	def export_hub_clicked (self, button):
		tab_num = self.get_object('notebook1').get_current_page()
		scrolled_window = self.get_object('notebook1').get_nth_page(tab_num)
		treeview = scrolled_window.get_child()
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def invoice_row_activated (self, treeview, treepath, treeviewcolumn):
		model = treeview.get_model()
		file_id = model[treepath][0]
		self.cursor.execute("SELECT name, pdf_data FROM invoices "
							"WHERE id = %s AND pdf_data IS NOT NULL", 
							(file_id ,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/" + row[0]
			file_data = row[1]
			with open(file_name,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_name])
		DB.rollback()

	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('invoice_menu')
			menu.popup_at_pointer()

	def invoice_history_activated (self, menuitem):
		selection = self.get_object('treeview-selection4')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][0]
		contact_id = model[path][8]
		if not self.invoice_history or self.invoice_history.exists == False:
			from reports import invoice_history as ih
			self.invoice_history = ih.InvoiceHistoryGUI()
		combo = self.invoice_history.get_object('combobox1')
		combo.set_active_id(contact_id)
		store = self.invoice_history.get_object('invoice_store')
		selection = self.invoice_history.get_object('treeview-selection1')
		selection.unselect_all()
		for row in store:
			if row[0] == invoice_id:
				selection.select_iter(row.iter)
				break
		self.invoice_history.present()

	def p_o_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('p_o_menu')
			menu.popup_at_pointer()

	def view_p_o_attachment_activated (self, menuitem):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		p_o_id = model[path][0]
		self.cursor.execute("SELECT name, attached_pdf FROM purchase_orders "
							"WHERE id = %s AND attached_pdf IS NOT NULL", 
							(p_o_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/" + row[0]
			file_data = row[1]
			with open(file_name,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_name])
			break
		else:
			self.show_message("No attachment for this Purchase Order")
		DB.rollback()

	def product_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter][1].lower():
				return False# no match
		return True# it's a hit!
		
	def product_changed(self, combo):
		product_id = combo.get_active_id ()
		if product_id == None:
			return
		self.product_id = product_id
		self.populate_product_stores ()

	def product_match_selected (self, completion, model, iter):
		self.product_id = model[iter][0]
		self.populate_product_stores ()

	def refresh_clicked (self, button):
		self.populate_product_stores ()

	def populate_product_stores (self):
		self.get_object('refresh_button').set_sensitive(True)
		self.get_object('report_hub_button').set_sensitive(True)
		self.populate_product_invoices ()
		self.populate_purchase_orders ()
		self.populate_warranty_store ()
		self.populate_manufacturing_store ()
		DB.rollback()

	def populate_warranty_store (self):
		warranty_store = self.get_object('warranty_store')
		warranty_store.clear()
		count = 0
		self.cursor.execute("SELECT "
								"snh.id, "
								"p.name, "
								"sn.serial_number, "
								"snh.date_inserted::text, "
								"format_date(snh.date_inserted), "
								"snh.description, "
								"c.name "
							"FROM serial_number_history AS snh "
							"JOIN serial_numbers AS sn "
							"ON sn.id = snh.serial_number_id "
							"JOIN products AS p ON p.id = sn.product_id "
							"JOIN contacts AS c ON c.id = snh.contact_id "
							"WHERE sn.product_id = %s"
							"ORDER by snh.date_inserted", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			warranty_store.append(row)
		if count == 0:
			self.get_object('label8').set_label('Warranty')
		else:
			label = "<span weight='bold'>Warranty (%s)</span>" % count
			self.get_object('label8').set_markup(label)

	def populate_purchase_orders (self):
		po_store = self.get_object('po_store')
		po_store.clear()
		count = 0
		qty = Decimal()
		self.cursor.execute("SELECT "
								"po.id, "
								"date_created::text, "
								"format_date(date_created), "
								"contacts.name, "
								"qty, "
								"price, "
								"price::text, "
								"order_number "
							"FROM purchase_orders AS po "
							"JOIN purchase_order_items AS poli "
							"ON poli.purchase_order_id = po.id "
							"JOIN contacts ON contacts.id = po.vendor_id "
							"WHERE product_id = %s ORDER by date_created", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			qty += row[4]
			po_store.append(row)
		if count == 0:
			self.get_object('label4').set_label('Purchase Orders')
		else:
			label = "<span weight='bold'>Purchase Orders (%s) [%s]</span>" \
														% (count, qty)
			self.get_object('label4').set_markup(label)

	def populate_product_invoices (self):
		invoice_store = self.get_object('invoice_store')
		invoice_store.clear()
		count = 0
		qty = Decimal()
		self.cursor.execute("SELECT "
								"i.id, "
								"dated_for::text, "
								"format_date(dated_for), "
								"i.name, "
								"'Comments: ' || comments, "
								"qty, "
								"qty::text, "
								"price, "
								"price::text, "
								"c.id::text, "
								"c.name "
							"FROM invoices AS i "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"JOIN invoice_items AS ii ON ii.invoice_id = i.id "
							"WHERE (product_id, i.canceled) = "
							"(%s, False) ORDER BY dated_for", 
							(self.product_id,))
		for row in self.cursor.fetchall():
			count += 1
			qty += row[5]
			invoice_store.append(row)
		if count == 0:
			self.get_object('label2').set_label('Invoices')
		else:
			label = "<span weight='bold'>Invoices (%s) [%s]</span>" \
												% (count, qty)
			self.get_object('label2').set_markup(label)

	def populate_manufacturing_store (self):
		store = self.get_object('manufacturing_store')
		store.clear()
		count = 0
		qty = Decimal()
		self.cursor.execute("SELECT "
								"mp.id, "
								"mp.name, "
								"qty, "
								"SUM(stop_time - start_time)::text, "
								"COUNT(DISTINCT(employee_id)), "
								"date_created::text, "
								"format_date(date_created) "
							"FROM manufacturing_projects AS mp "
							"JOIN time_clock_projects AS tcp "
								"ON tcp.id = mp.time_clock_projects_id "
							"JOIN time_clock_entries AS tce "
								"ON tce.project_id = tcp.id "
							"WHERE product_id = %s "
							"GROUP BY mp.id, mp.name, qty "
							"ORDER BY date_created", (self.product_id,))
		for row in self.cursor.fetchall():
			store.append(row) 
			count+= 1
			qty += row[2]
		if count == 0:
			self.get_object('label3').set_label('Manufacturing')
		else:
			label = "<span weight='bold'>Manufacturing (%s) [%s]</span>" \
													% (count, qty)
			self.get_object('label3').set_markup(label)
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



			
