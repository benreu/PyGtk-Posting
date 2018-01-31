# customer_history.py
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
from decimal import Decimal
import subprocess
import dateutils

UI_FILE = "src/reports/customer_history.ui"

class CustomerHistoryGUI:
	def __init__(self, main):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.search_store = Gtk.ListStore(str)
		self.invoice_store = self.builder.get_object('invoice_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		treeview = self.builder.get_object('treeview2')

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		treeview.connect('drag_data_get', self.on_drag_data_get)
		treeview.drag_source_set_target_list([dnd])

		self.customer_id = 0
		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.customer_store = self.builder.get_object('customer_store')
		self.cursor.execute("SELECT c.id, c.name FROM contacts AS c "
							"JOIN invoices ON invoices.customer_id = c.id "
							"WHERE (customer, deleted) = (True, False) "
							"GROUP BY c.id, c.name ORDER BY name")
		for customer in self.cursor.fetchall():
			id_ = customer[0]
			name = customer[1]
			self.customer_store.append([str(id_) , name])

		amount_column = self.builder.get_object ('treeviewcolumn5')
		amount_renderer = self.builder.get_object ('cellrenderertext5')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)

		
		self.product_name = ''
		self.product_ext_name = ''
		self.remark = ''
		self.order_number = ''
		
		self.filter = self.builder.get_object ('invoice_items_filter')
		self.filter.set_visible_func(self.filter_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def amount_cell_func(self, column, cellrenderer, model, iter1, data):
		price = '{:,.2f}'.format(model.get_value(iter1, 6))
		cellrenderer.set_property("text" , price)

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.invoice_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		product_id = model.get_value(treeiter, 3)
		qty = model.get_value(treeiter, 5)
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

	def close_transaction_window(self, window, void):
		self.window.destroy()
		return True
		
	def invoice_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('invoice_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			
	def invoice_item_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('invoice_item_menu')
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
			self.builder.get_object('checkbutton1').set_active(False)
		
	def customer_changed(self, combo):
		customer_id = combo.get_active_id ()
		if customer_id == None:
			return
		self.customer_id = customer_id
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('checkbutton3').set_active(False)
		self.load_customer_invoices ()

	def customer_match_selected (self, completion, model, iter):
		self.customer_id = model[iter][0]
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('checkbutton3').set_active(False)
		self.load_customer_invoices ()

	def load_customer_invoices (self):
		self.invoice_store.clear()
		total = Decimal()
		if self.builder.get_object('checkbutton3').get_active() == True:
			self.cursor.execute("SELECT i.id, dated_for, i.name, c.name, "
								"comments, COALESCE(total, 0.00) "
								"FROM invoices AS i "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE canceled =  false "
								"ORDER BY dated_for")
		else:
			self.cursor.execute("SELECT i.id, dated_for, i.name, c.name, "
								"comments, COALESCE(total, 0.00) "
								"FROM invoices AS i "
								"JOIN contacts AS c ON c.id = i.customer_id "
								"WHERE (customer_id, canceled) = "
								"(%s, False) ORDER BY dated_for", 
								(self.customer_id,))
		for row in self.cursor.fetchall():
			id_ = row[0]
			date = row[1]
			date_formatted = dateutils.datetime_to_text(date)
			i_name = row[2]
			c_name = row[3]
			remark = "Comments: " + row[4]
			amount = row[5]
			total += amount
			self.invoice_store.append([id_, str(date), date_formatted, i_name, 
													c_name, remark, amount])
		self.builder.get_object('label3').set_label(str(total))

	def invoice_row_changed (self, selection):
		self.builder.get_object('checkbutton1').set_active(False)
		self.load_invoice_items ()

	def all_products_togglebutton_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_invoice_items (load_all = active)
		if active == True:
			self.builder.get_object('checkbutton3').set_active(False)

	def load_invoice_items (self, load_all = False):
		store = self.builder.get_object('invoice_items_store')
		store.clear()
		if load_all == True:			
			self.cursor.execute("SELECT ili.id, ili.qty,  "
								"product_id, name, ext_name, ili.price, "
								"ili.ext_price, remark "
								"FROM invoice_line_items AS ili "
								"JOIN products "
								"ON products.id = ili.product_id "
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
			self.cursor.execute("SELECT ili.id, ili.qty,  "
								"product_id, name, ext_name, ili.price, "
								"ili.ext_price, remark "
								"FROM invoice_line_items AS ili "
								"JOIN products "
								"ON products.id = ili.product_id "
								"WHERE invoice_id IN " + args)
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			ext_name = row[4]
			price = row[5]
			ext_price = row[6]
			remark = row[7]
			store.append([float(qty), product_id,
											product_name, ext_name, remark, 
											price, ext_price])
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


		


