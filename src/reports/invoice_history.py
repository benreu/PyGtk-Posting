# invoice_history.py
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


from gi.repository import Gtk, Gdk
from decimal import Decimal
import subprocess
from constants import ui_directory, DB, broadcaster, is_admin

UI_FILE = ui_directory + "/reports/invoice_history.ui"

class InvoiceHistoryGUI(Gtk.Builder):
	exists = True
	def __init__(self):

		self.search_iter = 0
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.search_store = Gtk.ListStore(str)
		self.invoice_store = self.get_object('invoice_store')
		customer_completion = self.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		treeview = self.get_object('treeview2')

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		treeview.connect('drag_data_get', self.on_drag_data_get)
		treeview.drag_source_set_target_list([dnd])

		self.customer_id = 0

		self.customer_store = self.get_object('customer_store')
		self.cursor.execute("SELECT c.id::text, c.name, c.ext_name "
							"FROM contacts AS c "
							"JOIN invoices ON invoices.customer_id = c.id "
							"WHERE deleted = False "
							"GROUP BY c.id, c.name ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)
		DB.rollback()
		if is_admin == True:
			self.get_object('treeview2').set_tooltip_column(0)
		
		self.product_name = ''
		self.product_ext_name = ''
		self.remark = ''
		
		self.filter = self.get_object ('invoice_items_filter')
		self.filter.set_visible_func(self.filter_func)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.exists = False
		self.cursor.close()

	def present(self):
		self.window.present()

	def select_all_invoices_toggled (self, checkbutton):
		if checkbutton.get_active():
			self.get_object('treeview-selection1').select_all()
		else:
			self.get_object('treeview-selection1').unselect_all()

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.invoice_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		qty = model.get_value(treeiter, 1)
		product_id = model.get_value(treeiter, 3)
		data.set_text(str(qty) + ' ' + str(product_id), -1)
		
	def row_activated(self, treeview, path, treeviewcolumn):
		file_id = self.invoice_store[path][0]
		self.cursor.execute("SELECT name, pdf_data FROM invoices "
							"WHERE id = %s", (file_id,))
		for row in self.cursor.fetchall():
			file_name = row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open("/tmp/" + file_name,'wb')
			f.write(file_data)
			subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
			f.close()
		DB.rollback()
		
	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('invoice_menu')
			menu.popup_at_pointer()
			
	def invoice_item_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('invoice_item_menu')
			menu.popup_at_pointer()

	def invoice_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][11]
		import invoice_hub
		invoice_hub.InvoiceHubGUI(invoice_id)

	def view_invoice_pdf_activated (self, menuitem):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][11]
		self.cursor.execute("SELECT name, pdf_data FROM invoices "
							"WHERE id = %s", (invoice_id,))
		for row in self.cursor.fetchall():
			file_name = row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open("/tmp/" + file_name,'wb')
			f.write(file_data)
			subprocess.call(["xdg-open", "/tmp/%s" % file_name])
			f.close()
		DB.rollback()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][3]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def customer_view_all_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_customer_invoices ()
		if active == True:
			self.get_object('checkbutton1').set_active(False)
			self.get_object('select_all_checkbutton').set_active(False)
		
	def customer_changed(self, combo):
		customer_id = combo.get_active_id ()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.get_object('checkbutton1').set_active(False)
		self.get_object('checkbutton3').set_active(False)
		self.get_object('select_all_checkbutton').set_active(False)
		self.load_customer_invoices ()

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.get_object('checkbutton1').set_active(False)
		self.get_object('checkbutton3').set_active(False)
		self.get_object('select_all_checkbutton').set_active(False)
		self.load_customer_invoices ()

	def load_customer_invoices (self):
		invoice_treeview = self.get_object('treeview1')
		model = invoice_treeview.get_model()
		invoice_treeview.set_model(None)
		model.clear()
		total = Decimal()
		if self.get_object('checkbutton3').get_active() == True:
			self.cursor.execute("SELECT "
									"i.id, "
									"dated_for::text, "
									"format_date(dated_for), "
									"i.name, "
									"c.name, "
									"'Comments: ' || comments, "
									"COALESCE(total, 0.00), "
									"COALESCE(total, 0.00)::text, "
									"date_created::text, "
									"format_date(date_created), "
									"date_printed::text, "
									"format_date(date_printed)"
								"FROM invoices AS i "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE canceled =  false "
								"ORDER BY dated_for")
		else:
			self.cursor.execute("SELECT "
									"i.id, "
									"dated_for::text, "
									"format_date(dated_for), "
									"i.name, "
									"c.name, "
									"'Comments: ' || comments, "
									"COALESCE(total, 0.00), "
									"COALESCE(total, 0.00)::text, "
									"date_created::text, "
									"format_date(date_created), "
									"date_printed::text, "
									"format_date(date_printed)"
								"FROM invoices AS i "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE (customer_id, canceled) = "
								"(%s, False) ORDER BY dated_for", 
								(self.customer_id,))
		for row in self.cursor.fetchall():
			total += row[6]
			model.append(row)
		invoice_treeview.set_model(model)
		self.get_object('label3').set_label(str(total))
		DB.rollback()

	def invoice_row_changed (self, selection):
		self.get_object('checkbutton1').set_active(False)
		self.load_invoice_items ()

	def all_products_togglebutton_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_invoice_items (load_all = active)
		if active == True:
			self.get_object('checkbutton3').set_active(False)

	def select_all_activated (self, menuitem):
		self.get_object('treeview-selection1').select_all()

	def load_invoice_items (self, load_all = False):
		store = self.get_object('invoice_items_store')
		store.clear()
		if load_all == True:
			self.cursor.execute("SELECT "
									"ili.id, "
									"ili.qty,  "
									"ili.qty::text,  "
									"ili.product_id, "
									"p.name, "
									"p.ext_name, "
									"ili.remark, "
									"ili.price, "
									"ili.price::text, "
									"ili.ext_price, "
									"ili.ext_price::text, "
									"ili.invoice_id, "
									"i.dated_for::text, "
									"format_date(i.dated_for), "
									"c.name "
								"FROM invoice_items AS ili "
								"JOIN products AS p ON p.id = ili.product_id "
								"JOIN invoices AS i ON i.id = ili.invoice_id "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"ORDER BY ili.sort, ili.id")
		else:
			selection = self.get_object('treeview-selection1')
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
			self.cursor.execute("SELECT "
									"ili.id, "
									"ili.qty,  "
									"ili.qty::text,  "
									"ili.product_id, "
									"p.name, "
									"p.ext_name, "
									"ili.remark, "
									"ili.price, "
									"ili.price::text, "
									"ili.ext_price, "
									"ili.ext_price::text, "
									"ili.invoice_id, "
									"i.dated_for::text, "
									"format_date(i.dated_for), "
									"c.name "
								"FROM invoice_items AS ili "
								"JOIN products AS p ON p.id = ili.product_id "
								"JOIN invoices AS i ON i.id = ili.invoice_id "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE invoice_id IN %s "
								"ORDER BY ili.sort, ili.id" % args)
		for row in self.cursor.fetchall():
			store.append(row)
		DB.rollback()

	def search_entry_search_changed (self, entry):
		self.product_name = self.get_object('searchentry1').get_text().lower()
		self.product_ext_name = self.get_object('searchentry2').get_text().lower()
		self.remark = self.get_object('searchentry3').get_text().lower()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.product_name.split():
			if text not in model[tree_iter][4].lower():
				return False
		for text in self.product_ext_name.split():
			if text not in model[tree_iter][5].lower():
				return False
		for text in self.remark.split():
			if text not in model[tree_iter][6].lower():
				return False
		return True





