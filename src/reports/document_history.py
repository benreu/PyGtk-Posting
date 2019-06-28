# document_history.py
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
from constants import ui_directory, db, broadcaster, is_admin

UI_FILE = ui_directory + "/reports/document_history.ui"

class DocumentHistoryGUI(Gtk.Builder):
	exists = True
	def __init__(self):

		self.search_iter = 0
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.search_store = Gtk.ListStore(str)
		self.document_store = self.get_object('document_store')
		customer_completion = self.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		treeview = self.get_object('treeview2')

		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.COPY)
		treeview.connect('drag_data_get', self.on_drag_data_get)
		treeview.drag_source_set_target_list([dnd])

		self.contact_id = 0
		self.db = db
		self.cursor = self.db.cursor()

		self.customer_store = self.get_object('customer_store')
		self.cursor.execute("SELECT "
								"c.id::text, "
								"c.name, "
								"c.ext_name "
							"FROM contacts AS c "
							"JOIN documents ON documents.contact_id = c.id "
							"WHERE (customer, deleted) = (True, False) "
							"GROUP BY c.id, c.name ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)
		
		if is_admin == True:
			self.get_object('treeview2').set_tooltip_column(0)
		
		self.product_name = ''
		self.product_ext_name = ''
		self.remark = ''
		
		self.filter = self.get_object ('document_items_filter')
		self.filter.set_visible_func(self.filter_func)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def present(self):
		self.window.present()

	def select_all_documents_toggled (self, checkbutton):
		if checkbutton.get_active():
			self.get_object('treeview-selection1').select_all()
		else:
			self.get_object('treeview-selection1').unselect_all()

	def on_drag_data_get(self, widget, drag_context, data, info, time):
		model, path = widget.get_selection().get_selected_rows()
		treeiter = model.get_iter(path)
		if self.document_store.iter_has_child(treeiter) == True:
			return # not an individual line item
		product_id = model.get_value(treeiter, 3)
		qty = model.get_value(treeiter, 5)
		data.set_text(str(qty) + ' ' + str(product_id), -1)
		
	def row_activated(self, treeview, path, treeviewcolumn):
		file_id = self.document_store[path][0]
		self.cursor.execute("SELECT name FROM documents "
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

	def close_transaction_window(self, window, event):
		self.exists = False
		self.cursor.close()
		
	def document_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('document_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()
			
	def document_item_treeview_button_release_event (self, treeview, event):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		if event.button == 3:
			menu = self.get_object('document_item_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def view_document_activated (self, menuitem):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		document_id = model[path][8]
		self.cursor.execute("SELECT name FROM documents "
							"WHERE id = %s", (document_id,))
		for row in self.cursor.fetchall():
			file_name = row[0]
			if file_name == None:
				return
			file_data = row[1]
			f = open("/tmp/" + file_name,'wb')
			f.write(file_data)
			subprocess.call(["xdg-open", "/tmp/%s" % file_name])
			f.close()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
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
		self.load_customer_documents ()
		if active == True:
			self.get_object('checkbutton1').set_active(False)
			self.get_object('all_invoice_checkbutton').set_active(False)
		
	def customer_changed(self, combo):
		contact_id = combo.get_active_id ()
		if contact_id == None:
			return
		self.contact_id = contact_id
		self.get_object('checkbutton1').set_active(False)
		self.get_object('all_customer_checkbutton').set_active(False)
		self.get_object('all_invoice_checkbutton').set_active(False)
		self.load_customer_documents ()

	def customer_match_selected (self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.get_object('checkbutton1').set_active(False)
		self.get_object('all_customer_checkbutton').set_active(False)
		self.get_object('all_invoice_checkbutton').set_active(False)
		self.load_customer_documents ()

	def load_customer_documents (self):
		document_treeview = self.get_object('treeview1')
		model = document_treeview.get_model()
		document_treeview.set_model(None)
		model.clear()
		total = Decimal()
		if self.get_object('all_customer_checkbutton').get_active() == True:
			self.cursor.execute("SELECT "
									"d.id, "
									"dated_for::text, "
									"format_date(dated_for), "
									"d.name, "
									"c.name, "
									"'Comments: ' || comments, "
									"COALESCE(total, 0.00), "
									"date_printed::text, "
									"format_date(date_printed), "
									"pending_invoice "
								"FROM documents AS d "
								"JOIN contacts AS c ON c.id = d.contact_id "
								"WHERE canceled =  false "
								"ORDER BY dated_for")
		else:
			self.cursor.execute("SELECT "
									"d.id, "
									"dated_for::text, "
									"format_date(dated_for), "
									"d.name, "
									"c.name, "
									"'Comments: ' || comments, "
									"COALESCE(total, 0.00), "
									"date_printed::text, "
									"format_date(date_printed), "
									"pending_invoice "
								"FROM documents AS d "
								"JOIN contacts AS c ON c.id = d.contact_id "
								"WHERE (contact_id, canceled) = "
								"(%s, False) ORDER BY dated_for", 
								(self.contact_id,))
		for row in self.cursor.fetchall():
			total += row[6]
			model.append(row)
		document_treeview.set_model(model)
		self.get_object('label3').set_label(str(total))

	def document_row_changed (self, selection):
		self.get_object('checkbutton1').set_active(False)
		self.load_document_items ()

	def all_products_togglebutton_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.load_document_items (load_all = active)
		if active == True:
			self.get_object('all_customer_checkbutton').set_active(False)

	def select_all_activated (self, menuitem):
		self.get_object('treeview-selection1').select_all()

	def load_document_items (self, load_all = False):
		store = self.get_object('document_items_store')
		store.clear()
		if load_all == True:
			self.cursor.execute("SELECT "
									"ili.id, "
									"ili.qty::float,  "
									"ili.product_id, "
									"p.name, "
									"p.ext_name, "
									"ili.remark, "
									"ili.price, "
									"ili.ext_price, "
									"ili.document_id, "
									"d.dated_for::text, "
									"format_date(d.dated_for), "
									"c.name "
								"FROM document_items AS ili "
								"JOIN products AS p ON p.id = ili.product_id "
								"JOIN documents AS d ON d.id = ili.document_id "
								"JOIN contacts AS c ON c.id = d.contact_id "
								"ORDER BY p.name ")
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
									"ili.qty::float,  "
									"ili.product_id, "
									"p.name, "
									"p.ext_name, "
									"ili.remark, "
									"ili.price, "
									"ili.ext_price, "
									"ili.document_id, "
									"d.dated_for::text, "
									"format_date(d.dated_for), "
									"c.name "
								"FROM document_items AS ili "
								"JOIN products AS p ON p.id = ili.product_id "
								"JOIN documents AS d ON d.id = ili.document_id "
								"JOIN contacts AS c ON c.id = d.contact_id "
								"WHERE document_id IN " + args)
		for row in self.cursor.fetchall():
			store.append(row)

	def search_entry_search_changed (self, entry):
		self.product_name = self.get_object('searchentry1').get_text().lower()
		self.product_ext_name = self.get_object('searchentry2').get_text().lower()
		self.remark = self.get_object('searchentry3').get_text().lower()
		self.filter.refilter()

	def filter_func(self, model, tree_iter, r):
		for text in self.product_name.split():
			if text not in model[tree_iter][3].lower():
				return False
		for text in self.product_ext_name.split():
			if text not in model[tree_iter][4].lower():
				return False
		for text in self.remark.split():
			if text not in model[tree_iter][5].lower():
				return False
		return True


		


