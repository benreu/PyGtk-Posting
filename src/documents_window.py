#documents.py
#
# Copyright (C) 2016 reuben 
# 
# documents is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# documents is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, Gdk, GLib
from datetime import datetime, timedelta
import subprocess, re, psycopg2
import documenting
from dateutils import DateTimeCalendar
from pricing import get_customer_product_price
from constants import ui_directory, DB, broadcaster, help_dir

UI_FILE = ui_directory + "/documents_window.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass
		
class DocumentGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1
		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_customer_store ), 
						   ("products_changed", self.populate_product_store )):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		
		self.document_id = 0
		self.documents_store = self.builder.get_object('documents_store')
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.treeview = self.builder.get_object('treeview2')
		self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		self.treeview.connect("drag-data-received", self.on_drag_data_received)
		self.treeview.drag_dest_set_target_list([enforce_target])
		
		self.existing_store = self.builder.get_object('existing_store')
		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('product_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.retailer_completion = self.builder.get_object('retailer_completion')
		self.retailer_completion.set_match_func(self.customer_match_func)
		
		self.populate_product_store ()
		self.populate_customer_store ()
			
		self.calculate_totals ()
		self.load_settings()
		
		self.window = self.builder.get_object('window')
		self.window.show_all()

	def load_settings (self):
		self.cursor.execute("SELECT column_id, column_name, visible "
							"FROM settings.document_columns")
		for row in self.cursor.fetchall():
			column_id = row[0]
			column_name = row[1]
			visible = row[2]
			tree_column = self.builder.get_object(column_id)
			tree_column.set_title(column_name)
			tree_column.set_visible(visible)
		self.cursor.execute("SELECT print_direct, email_when_possible FROM settings")
		print_direct, email = self.cursor.fetchone()
		self.builder.get_object('menuitem1').set_active(print_direct) #set the direct print checkbox
		self.builder.get_object('menuitem4').set_active(email) #set the email checkbox
		DB.rollback()

	def drag_finish(self, wid, context, x, y, time):
		print (wid, context, x, y, time)

	def on_drag_motion(self, wid, context, x, y, time):
		#print wid
		#l.set_text('\n'.join([str(t) for t in context.targets]))
		#context.drag_status(gtk.gdk.ACTION_COPY, time)
		#print context.list_targets()
		# Returning True which means "I accept this data".
		#print "movement"
		#return False
		pass

	def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
		_list_ = data.get_text().split(' ')
		if len(_list_) != 2:
			return
		table, _id_ = _list_[0], _list_[1]
		self.cursor.execute("SELECT product, remark, price FROM %s WHERE id = %s" % (table, _id_))
		for row in self.cursor.fetchall():
			product = row[0]
			remark = row[1]
			price = row[2]
		print ("please implement me") #FIXME

	def destroy(self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('right_click_menu')
			menu.popup_at_pointer()

	def focus (self, window, event):
		document_type_combo = self.builder.get_object('comboboxtext2')
		active_type_id = document_type_combo.get_active_id()
		document_type_combo.remove_all()
		self.cursor.execute("SELECT id::text, name FROM document_types")
		for row in self.cursor.fetchall():
			type_id = row[0]
			type_name = row[1]
			document_type_combo.append(str(type_id), type_name)
		document_type_combo.set_active_id(str(active_type_id))

	def product_window(self, column):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def contacts_window(self, widget):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()

	def view_document_clicked(self, widget):
		comment = self.builder.get_object('entry3').get_text()
		d = documenting.Setup(self.documents_store, self.contact_id, 
								comment, self.date, self.document_type_id, 
								self.document_name) 
		d.view()

	def post_document_clicked(self, widget):
		comment = self.builder.get_object('entry3').get_text()
		d = documenting.Setup( self.documents_store,  self.contact_id, 
								comment, self.date, self.document_type_id, 
								self.document_name )
		if self.builder.get_object('menuitem1').get_active() == True:
			d.print_directly()
		else:
			d.print_dialog(self.window)
		d.post(self.document_id)	
		if self.builder.get_object('menuitem4').get_active() == True:
			self.cursor.execute("SELECT name, email FROM contacts "
								"WHERE id = %s", (self.contact_id, ))
			for row in self.cursor.fetchall():
				name = row[0]
				email = row[1]
				if email != "":
					email = "%s '< %s >'" % (name, email)
					d.email(email)
		DB.commit()
		self.window.destroy()

	################## start customer
	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		self.cursor.execute("SELECT id::text, name FROM contacts "
							"WHERE (deleted, customer) = "
							"(False, True) ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)
		DB.rollback()
		
	def customer_match_selected(self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.customer_selected (self.contact_id)

	def customer_match_func(self, completion, key, iter):
		for text in key.split():
			if text not in self.customer_store[iter][1].lower(): 
				return False 
		return True

	def customer_combobox_changed(self, widget, toggle_button=None): #updates the customer
		contact_id = widget.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
			self.customer_selected (self.contact_id)
			self.calculate_totals ()

	def customer_selected(self, name_id):
		self.builder.get_object('comboboxtext2').set_sensitive(True)
		self.builder.get_object('button4').set_sensitive(True)
		self.builder.get_object('button11').set_sensitive(True)
		self.builder.get_object('button12').set_sensitive(True)
		self.cursor.execute("SELECT "
								"name, "
								"ext_name, "
								"address, "
								"phone "
							"FROM contacts "
							"WHERE id = %s",(name_id,))
		for row in self.cursor.fetchall() :
			self.customer_name_default_label = row[0]
			self.builder.get_object('entry11').set_text(row[1])
			self.builder.get_object('entry10').set_text(row[2])
			self.builder.get_object('entry12').set_text(row[3])
		self.builder.get_object('button2').set_sensitive(True)
		self.builder.get_object('menuitem2').set_sensitive(True)
		job_type_combo = self.builder.get_object('comboboxtext2')
		if job_type_combo.get_active() < 0 :
			job_type_combo.set_active(0)
		self.populate_existing_store ()

	################## start qty

	def qty_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		try:
			self.cursor.execute("UPDATE document_items "
								"SET (qty, ext_price) = "
								"(%s, (%s * price)) "
								"WHERE id = %s "
								"RETURNING qty::text, ext_price::text", 
								(text, text, row_id))
			for row in self.cursor.fetchall():
				self.documents_store[path][1] = row[0]
				self.documents_store[path][14] = row[1]
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_message (e)
			return False
		DB.commit()
		self.calculate_totals ()

	################## start minimum

	def minimum_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		try:
			self.cursor.execute("UPDATE document_items SET min = %s "
									"WHERE id = %s "
									"RETURNING min::text", (text, row_id))
			DB.commit()
			for row in self.cursor.fetchall():
				minimum = row[0]
				self.documents_store[path][5] = minimum
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_message (e)
			return False

	################## start maximum

	def maximum_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		try:
			self.cursor.execute("UPDATE document_items SET max = %s "
									"WHERE id = %s "
									"RETURNING max::text", (text, row_id))
			DB.commit()
			for row in self.cursor.fetchall():
				maximum = row[0]
				self.documents_store[path][6] = maximum
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_message (e)
			return False

	################## start freeze

	def freeze_toggled (self, cell_renderer, path):
		row_id = self.documents_store[path][0]
		self.cursor.execute("UPDATE document_items SET type_1 = NOT "
								"(SELECT type_1 FROM document_items "
									"WHERE id = %s) "
								"WHERE id = %s "
								"RETURNING type_1", (row_id, row_id))
		DB.commit()
		for row in self.cursor.fetchall():
			freeze = row[0]
			self.documents_store[path][9] = freeze
		
	################## start remark

	def remark_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		self.cursor.execute("UPDATE document_items SET remark = %s "
								"WHERE id = %s "
								"RETURNING remark", (text, row_id))
		DB.commit()
		for row in self.cursor.fetchall():
			remark = row[0]
			self.documents_store[path][10] = remark

	################## start priority

	def priority_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		self.cursor.execute("UPDATE document_items SET priority = %s "
								"WHERE id = %s "
								"RETURNING priority", (text, row_id))
		DB.commit()
		for row in self.cursor.fetchall():
			priority = row[0]
			self.documents_store[path][11] = priority

	################## start retailer

	def retailer_editing_started (self, renderer, combo, path):
		entry = combo.get_child()
		entry.set_completion (self.retailer_completion)

	def retailer_match_selected(self, completion, model, iter):
		retailer_id = model[iter][0]
		retailer_name = model[iter][1]
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		self.documents_store[path][7] = int(retailer_id)
		self.documents_store[path][8] = retailer_name
		self.save_document_line (path)

	def retailer_match_func(self, completion, key, iter):
		for text in key.split():
			if text not in self.customer_store[iter][1].lower(): 
				return False 
		return True
	
	def retailer_changed (self, combo, path, _iter):
		retailer_id = self.customer_store[_iter][0]
		retailer_name = self.customer_store[_iter][1]
		self.documents_store[path][7] = int(retailer_id)
		self.documents_store[path][8] = retailer_name
		self.save_document_line (path)
		
	################## start price

	def s_price_edited (self, widget, path, text):
		row_id = self.documents_store[path][0]
		try:
			self.cursor.execute("UPDATE document_items "
								"SET s_price = %s "
								"WHERE id = %s "
								"RETURNING s_price::text", 
								(text, row_id))
			for row in self.cursor.fetchall():
				self.documents_store[path][13] = row[0]
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_message (e)
			return False
		DB.commit()
		
	def price_edited(self, widget, path, text):
		row_id = self.documents_store[path][0]
		try:
			self.cursor.execute("UPDATE document_items "
								"SET (price, ext_price) = "
								"(%s, (qty * %s)) "
								"WHERE id = %s "
								"RETURNING price::text, ext_price::text", 
								(text, text, row_id))
			for row in self.cursor.fetchall():
				self.documents_store[path][12] = row[0]
				self.documents_store[path][14] = row[1]
		except psycopg2.DataError as e:
			DB.rollback()
			self.show_message (e)
			return False
		DB.commit()
		self.calculate_totals ()
		
	################## start product
	
	def product_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_renderer_editing_started (self, renderer, combo, path):
		completion = self.builder.get_object('product_completion')
		entry = combo.get_child()
		entry.set_completion(completion)
		
	def product_match_selected (self, completion, model, iter_):
		product_id = self.product_store[iter_][0]
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows ()
		self.product_selected (product_id, path)
		
	def product_renderer_changed (self, widget, path, iter_):
		product_id = self.product_store[iter_][0]
		self.product_selected(product_id, path)

	def product_selected (self, product_id, path):
		if int(product_id) == self.documents_store[path][2]:
			return # product did not change
		iter_ = self.documents_store.get_iter(path)
		row_id = self.documents_store[iter_][0]
		self.cursor.execute("UPDATE document_items "
							"SET product_id = %s WHERE id = %s;"
							"SELECT name, ext_name FROM products "
							"WHERE id = %s", (product_id, row_id, product_id))
		tupl = self.cursor.fetchone()
		DB.commit()
		product_name, product_ext_name = tupl[0], tupl[1]
		self.documents_store[iter_][2] = int(product_id)
		self.documents_store[iter_][3] = product_name
		self.documents_store[iter_][4] = product_ext_name
		price = get_customer_product_price(self.contact_id, product_id)
		self.documents_store[iter_][12] = str(price)
		self.calculate_totals()
		# retrieve path again after all sorting has happened for the updates
		path = self.documents_store.get_path(iter_)
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(3)
		treeview.set_cursor(path, c, True)
		
	def populate_product_store (self, m=None, i=None):
		self.product_store.clear()
		self.cursor.execute("SELECT "
								"id::text, "
								"name ||' {' || ext_name ||'}' FROM products "
							"WHERE (deleted, sellable, stock) = "
							"(False, True, True) ORDER BY name ")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		DB.rollback()

	################## end product
	
	def calculate_totals (self, widget = None):
		self.cursor.execute("SELECT "
								"COALESCE(SUM(ext_price), 0.00)::text "
							"FROM document_items WHERE document_id = %s", 
							(self.document_id,))
		for row in self.cursor.fetchall():
			self.total = row[0]
		self.builder.get_object('entry8').set_text(self.total)
		DB.rollback()

	def add_entry (self, widget):
		c = DB.cursor()
		c.execute("INSERT INTO document_items " 
						"(document_id, product_id, retailer_id) "
					"VALUES "
						"(%s, "
						"(SELECT id FROM products "
							"WHERE (deleted, sellable, stock) = "
									"(False, True, True) LIMIT 1), "
						"%s) "
					"RETURNING "
						"id ", 
					(self.document_id, self.contact_id))
		row_id = c.fetchone()[0]
		c.execute("SELECT "
						"di.id, "
						"qty::text, "
						"p.id, "
						"p.name, "
						"p.ext_name, "
						"min::text, "
						"max::text, "
						"retailer_id, "
						"COALESCE(c.name, ''), "
						"type_1, "
						"remark, "
						"priority, "
						"price::text, "
						"s_price::text, "
						"ext_price::text "
					"FROM document_items AS di "
					"JOIN products AS p ON di.product_id = p.id "
					"LEFT JOIN contacts AS c ON di.retailer_id = c.id "
					"WHERE di.id = %s",
					(row_id,))
		self.builder.get_object('button15').set_sensitive(True)
		DB.commit()
		for row in c.fetchall():
			iter_ = self.documents_store.append(row)
			treeview = self.builder.get_object('treeview2')
			c = treeview.get_column(0)
			path = self.documents_store.get_path(iter_)
			treeview.set_cursor(path , c, True)#set the cursor to the last appended item
			return
			row_id = row[0]
			product_id = row[1]
			product_name = i[1]
			price = get_customer_product_price (self.contact_id, product_id)
			self.documents_store.append([0, 1.0, product_id, product_name, "", 
										0.0, 100.00, int(self.contact_id), 
										self.customer_name_default_label, 
										False, "", "1", price, 0.00, 1])
			last = self.documents_store.iter_n_children ()
			last -= 1 #iter_n_children starts at 1 ; set_cursor starts at 0
			treeview = self.builder.get_object('treeview2')
			c = treeview.get_column(0)
			treeview.set_cursor(last , c, True)	#set the cursor to the last appended item
			break
		c.close()

	def delete_entry (self, widget):
		selection = self.builder.get_object("treeview-selection")
		row, path = selection.get_selected_rows ()
		if path == []:
			return
		document_line_item_id = self.documents_store[path][0]
		self.cursor.execute("DELETE FROM document_items WHERE id = %s",
							(document_line_item_id,))
		DB.commit()
		self.populate_document_store ()

	def key_tree_tab (self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		## only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab" or keyname=="Esc":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass

	def document_name_changed (self, widget):
		if self.document_id == 0:
			return
		document_name = widget.get_text()
		if " " in document_name:
			document_name = re.sub(" ", "", document_name)
			widget.set_text(document_name)
			return
		self.cursor.execute("UPDATE documents SET name = %s "
							"WHERE id = %s", (document_name, self.document_id))
		DB.commit()

	def delete_document_clicked (self, widget):
		self.cursor.execute("DELETE FROM documents WHERE id = %s", (self.document_id,))
		DB.commit()
		self.builder.get_object('entry3').set_text('')
		self.populate_existing_store ()

	def document_type_changed (self, widget):
		document_type = widget.get_active_text()
		if document_type != None:
			self.document_type = document_type
			self.document_type_id = widget.get_active_id()
			self.builder.get_object('window').set_title("New " + document_type)
			self.builder.get_object('button15').set_label("Post " + document_type)
			self.calendar.set_today()
			self.populate_existing_store ()

	def document_type_clicked (self, widget):
		import settings
		settings.GUI('document_types')

	def new_document_clicked (self, widget):
		if self.document_type == "":
			return
		self.document_id = 0
		self.documents_store.clear()
		self.builder.get_object('label6').set_text(" Current %s : " % self.document_type)
		comment = self.builder.get_object('entry3').get_text()
		self.cursor.execute("INSERT INTO documents "
								"(contact_id, "
								"closed, "
								"invoiced, "
								"canceled, "
								"date_created, "
								"dated_for, "
								"document_type_id, "
								"pending_invoice) "
							"VALUES "
							"(%s, %s, %s, %s, %s, %s, %s, %s) "
							"RETURNING id", 
							(self.contact_id, False, False, False, datetime.today(), self.date, self.document_type_id, False))
		self.document_id = self.cursor.fetchone()[0]
		self.set_document_name ()
		DB.commit()
		self.builder.get_object('button13').set_sensitive(True)
		self.builder.get_object('button14').set_sensitive(True)
		self.builder.get_object('import_from_history').set_sensitive(True)

	def set_document_name (self):
		type_text = self.document_type[0:3]
		contact_name = self.builder.get_object('combobox-entry5').get_text() 
		split_name = contact_name.split(' ')
		name_str = ""
		for i in split_name:
			name_str = name_str + i[0:3]
		name = name_str.lower()
		self.cursor.execute("SELECT format_date(%s)", (self.date,))
		date = self.cursor.fetchone()[0]
		date = re.sub (" ", "_", date)
		self.document_name = type_text + "_" + str(self.document_id) + "_" + name + "_" + date
		self.cursor.execute("UPDATE documents SET name = %s WHERE id = %s", (self.document_name, self.document_id))
		DB.commit()
		self.builder.get_object('entry5').set_text(self.document_name)
		
	def populate_existing_store (self):
		model, path = self.builder.get_object('treeview-selection5').get_selected_rows()
		self.existing_store.clear()
		doc_count = 0
		self.cursor.execute("SELECT id, name FROM documents "
							"WHERE "
								"(document_type_id, closed, "
								"canceled, contact_id) "
							"= "
								"(%s, False, False, %s) ORDER BY id", 
							(self.document_type_id, self.contact_id))
		for row in self.cursor.fetchall():
			doc_count += 1
			self.existing_store.append(row)
		self.builder.get_object('button11').set_label("Existing documents (%s)"
																	% doc_count)
		if path != []:
			self.builder.get_object('treeview-selection5').select_path(path)
		DB.rollback()

	def existing_documents_clicked (self, widget):
		existing_dialog = self.builder.get_object('existing_dialog')
		self.populate_existing_store ()
		result = existing_dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			self.existing_document ()
		existing_dialog.hide()

	def existing_document (self):
		selection = self.builder.get_object('treeview-selection5')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.document_id = model[path][0]
		self.populate_document_store()
		self.builder.get_object('button13').set_sensitive(True)
		self.builder.get_object('button14').set_sensitive(True)
		self.builder.get_object('button15').set_sensitive(True)
		self.builder.get_object('import_from_history').set_sensitive(True)
		
	def populate_document_store (self):
		self.documents_store.clear()
		self.cursor.execute("SELECT "
								"name, "
								"dated_for, "
								"format_date(dated_for) "
							"FROM documents WHERE id = %s", 
							(self.document_id,))
		for row in self.cursor.fetchall():
			self.document_name = row[0]
			self.date = row[1]
			self.builder.get_object('entry1').set_text(row[2])
		self.builder.get_object('entry5').set_text(self.document_name)
		self.cursor.execute("SELECT "
								"di.id, "
								"qty::text, "
								"p.id, "
								"p.name, "
								"p.ext_name, "
								"min::text, "
								"max::text, "
								"retailer_id, "
								"COALESCE(c.name, ''), "
								"type_1, "
								"remark, "
								"priority, "
								"price::text, "
								"s_price::text, "
								"ext_price::text "
							"FROM document_items AS di "
							"JOIN products AS p ON di.product_id = p.id "
							"LEFT JOIN contacts AS c ON di.retailer_id = c.id "
							"WHERE document_id = %s ORDER BY di.id", 
							(self.document_id, ) )
		for row in self.cursor.fetchall():
			self.documents_store.append(row)
		self.calculate_totals ()
		DB.rollback()

	def import_items_from_history_activated (self, menuitem):
		button = Gtk.Button(label = 'Import items from document history')
		button.show()
		from reports import document_history
		dh = document_history.DocumentHistoryGUI()
		dh.window.set_transient_for (self.window)
		dh.get_object("box1").pack_start(button, False, False, 10)
		dh.get_object("all_customer_checkbutton").set_active(True)
		dh.get_object("box3").set_visible(False)
		selection = dh.get_object("treeview-selection1")
		selection.set_mode(Gtk.SelectionMode.SINGLE)
		selection.select_path(0)
		button.connect("clicked", self.import_items_from_history, dh)

	def import_items_from_history(self, button, dh):
		model, path = dh.get_object("treeview-selection1").get_selected_rows()
		if path == []:
			return
		old_id = model[path][0]
		self.cursor.execute("INSERT INTO document_items "
								"(qty, "
								"document_id, "
								"product_id, "
								"min, "
								"max, "
								"retailer_id, "
								"type_1, "
								"remark, "
								"priority, "
								"price, "
								"s_price, "
								"ext_price) "
							"(SELECT "
								"qty, "
								"%s, "
								"product_id, "
								"min, "
								"max, "
								"%s, "
								"type_1, "
								"remark, "
								"priority, "
								"price, "
								"s_price, "
								"ext_price "
							"FROM document_items WHERE document_id = %s)", 
							(self.document_id, self.contact_id, old_id))
		DB.commit()
		self.populate_document_store ()
		dh.window.destroy()

	def help_clicked (self, widget):
		subprocess.Popen(["yelp", help_dir + "/document.page"])

	def window_key_event (self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'F1':
			self.help_clicked(None)
		if keyname == 'F2':
			self.add_entry(None)
		if keyname == 'F3':
			self.delete_entry(None)

	def calendar_day_selected (self, calendar):
		day_text = calendar.get_text()
		self.date = calendar.get_date()
		self.builder.get_object('entry1').set_text(day_text)
		self.cursor.execute("UPDATE documents SET dated_for = %s "
							"WHERE id = %s", (self.date, self.document_id))
		self.set_document_name ()
		DB.commit()

	def calendar_entry_icon_release (self, widget, icon, void):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def clear_retailer_entry (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		store, path = selection.get_selected_rows ()
		self.documents_store[path][7]= None
		self.documents_store[path][8] = ''
		line_id = self.documents_store[path][0]
		self.cursor.execute("UPDATE document_items SET retailer_id = NULL "
							"WHERE id = %s", (line_id, ))
		DB.commit()

	 #barcode entry support code *******

	def barcode_entry_activated (self, entry2):
		barcode = entry2.get_text()
		entry2.set_text('')
		self.cursor.execute("SELECT id, name, 1.00, ext_name "
								"FROM products WHERE barcode = %s",(barcode, ))
		for i in self.cursor.fetchall():
			product_id = i[0]
			for index, row in enumerate(self.documents_store):
				if row[2] == product_id:
					row[1] += 1.0 # increase the qty by one
					treeview = self.builder.get_object('treeview2')
					c = treeview.get_column(0)
					treeview.set_cursor(index , c, False)	#set the cursor to the last appended item
					return
			product_name = i[1]
			price = i[2]
			ext_name = i[3]
			self.documents_store.append([0, 1.0, product_id, product_name, ext_name, 0.0, 100.00, int(self.contact_id), self.customer_name_default_label, False, "", "1", price, 0.00, 1]) #FIXME
			last = self.documents_store.iter_n_children() - 1
			treeview = self.builder.get_object('treeview2')
			c = treeview.get_column(0)
			treeview.set_cursor(last , c, False)	#set the cursor to the last appended item
			return
		else:
			raise Exception ("please make a window to alert the user that the barcode does not exist!")
		DB.rollback()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



