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


from gi.repository import Gtk, Gdk
from decimal import Decimal
import subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/vendor_history.ui"

class VendorHistoryGUI:
	def __init__(self):

		self.search_iter = 0
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

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

		self.vendor_store = self.builder.get_object('vendor_store')
		self.cursor.execute("SELECT c.id::text, c.name "
							"FROM purchase_orders AS p "
							"JOIN contacts AS c ON c.id = p.vendor_id "
							"GROUP BY c.id, c.name "
							"ORDER BY c.name")
		for row in self.cursor.fetchall():
			self.vendor_store.append(row)
		DB.rollback()
		self.product_name = ''
		self.product_ext_name = ''
		self.remark = ''
		self.order_number = ''
		
		self.filter = self.builder.get_object ('purchase_order_items_filter')
		self.filter.set_visible_func(self.filter_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.po_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		qty = model.get_value(treeiter, 1)
		product_id = model.get_value(treeiter, 3)
		data.set_text(str(qty) + ' ' + str(product_id), -1)
		
	def row_activated(self, treeview, path, treeviewcolumn):
		file_id = self.po_store[path][0]
		self.cursor.execute("SELECT name, pdf_data FROM purchase_orders "
							"WHERE id = %s AND pdf_data IS NOT NULL", 
							(file_id,))
		for row in self.cursor.fetchall():
			file_url = "/tmp/" + row[0]
			file_data = row[1]
			with open(file_url,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_url])
		DB.rollback()

	def destroy (self, window):
		self.cursor.close()
		
	def po_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('po_menu')
			menu.popup_at_pointer()
			
	def po_item_treeview_button_release_event (self, treeview, event):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.builder.get_object('po_item_menu')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][3]
		import product_hub
		product_hub.ProductHubGUI(product_id)

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
		c = DB.cursor()
		self.po_store.clear()
		total = Decimal()
		if self.builder.get_object('checkbutton3').get_active() == True:
			c.execute("SELECT "
						"id, "
						"date_created::text, "
						"format_date(date_created), "
						"name, "
						"invoice_description, "
						"COALESCE(total, 0.00), "
						"COALESCE(total, 0.00)::text, "
						"paid, "
						"closed, "
						"'Comments:\n' || comments "
						"FROM purchase_orders "
						"WHERE canceled =  false "
						"ORDER BY date_created")
		else:
			c.execute("SELECT "
						"id, "
						"date_created::text, "
						"format_date(date_created), "
						"name, "
						"invoice_description, "
						"COALESCE(total, 0.00), "
						"COALESCE(total, 0.00)::text, "
						"paid, "
						"closed, "
						"'Comments:\n' || comments "
						"FROM purchase_orders "
						"WHERE (vendor_id, canceled) = "
						"(%s, False) ORDER BY date_created", 
						(self.vendor_id,))
		for row in c.fetchall():
			total += row[5]
			self.po_store.append(row)
		self.builder.get_object('label3').set_label(str(total))
		c.close()
		DB.rollback()

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
			self.cursor.execute("SELECT "
									"poli.id, "
									"poli.qty, "
									"poli.qty::text, "
									"product_id, "
									"p.name, "
									"p.ext_name, "
									"poli.remark, "
									"poli.price, "
									"poli.price::text, "
									"poli.ext_price, "
									"poli.ext_price::text, "
									"poli.order_number, "
									"po.id, "
									"po.date_created::text, "
									"format_date(po.date_created), "
									"c.name "
								"FROM purchase_order_line_items AS poli "
								"JOIN products AS p ON p.id = poli.product_id "
								"JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
								"JOIN contacts AS c ON c.id = po.vendor_id "
								"ORDER BY p.name ")
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
			self.cursor.execute("SELECT "
									"poli.id, "
									"poli.qty, "
									"poli.qty::text, "
									"product_id, "
									"p.name, "
									"p.ext_name, "
									"poli.remark, "
									"poli.price, "
									"poli.price::text, "
									"poli.ext_price, "
									"poli.ext_price::text, "
									"poli.order_number, "
									"po.id, "
									"po.date_created::text, "
									"format_date(po.date_created), "
									"c.name "
								"FROM purchase_order_line_items AS poli "
								"JOIN products AS p ON p.id = poli.product_id "
								"JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
								"JOIN contacts AS c ON c.id = po.vendor_id "
								"WHERE purchase_order_id IN " + args)
		for row in self.cursor.fetchall():
			store.append(row)
		DB.rollback()

	def search_entry_search_changed (self, entry):
		self.product_name = self.builder.get_object('searchentry1').get_text().lower()
		self.product_ext_name = self.builder.get_object('searchentry2').get_text().lower()
		self.remark = self.builder.get_object('searchentry3').get_text().lower()
		self.order_number = self.builder.get_object('searchentry4').get_text().lower()
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
		for text in self.order_number.split():
			if text not in model[tree_iter][11].lower():
				return False
		return True

	def view_attachment_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		po_id = model[path][0]
		self.cursor.execute("SELECT attached_pdf FROM purchase_orders "
							"WHERE id = %s AND attached_pdf IS NOT NULL", 
							(po_id,))
		for row in self.cursor.fetchall():
			file_url = "/tmp/PO %d attachment.pdf" % po_id
			file_data = row[0]
			with open(file_url,'wb') as f:
				f.write(file_data)
				subprocess.call(["xdg-open", file_url])
			break
		else:
			self.run_attach_dialog (po_id)
		DB.rollback()

	def run_attach_dialog (self, po_id):
		import pdf_attachment
		dialog = pdf_attachment.Dialog(self.window)
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			file_data = dialog.get_pdf ()
			self.cursor.execute("UPDATE purchase_orders SET attached_pdf = %s "
								"WHERE id = %s", (file_data, po_id))
			DB.commit()



