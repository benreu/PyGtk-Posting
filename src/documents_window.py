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
import subprocess, re
import documenting
from dateutils import DateTimeCalendar
from pricing import get_customer_product_price

UI_FILE = "src/documents_window.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass
		
class DocumentGUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.edited_renderer_text = 1
		self.qty_renderer_value = 1

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.handler_c_id = main.connect ("contacts_changed", self.populate_customer_store )
		self.handler_p_id = main.connect ("products_changed", self.populate_product_store )
		
		self.document_id = 0
		self.documents_store = self.builder.get_object('documents_store')
		
		self.calendar = DateTimeCalendar(self.db)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		self.treeview = self.builder.get_object('treeview2')
		self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.COPY)
		#self.treeview.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
		self.treeview.connect("drag-data-received", self.on_drag_data_received)
		self.treeview.drag_dest_set_target_list([enforce_target])
		#self.treeview.drag_dest_set_target_list(None)
		#self.treeview.drag_dest_add_text_targets()
		
		self.import_store = self.builder.get_object('import_store')
		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('product_store')
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.retailer_completion = self.builder.get_object('retailer_completion')
		self.retailer_completion.set_match_func(self.customer_match_func)

		qty_column = self.builder.get_object ('treeviewcolumn1')
		qty_renderer = self.builder.get_object ('cellrenderertext2')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)

		minimum_column = self.builder.get_object ('treeviewcolumn8')
		minimum_renderer = self.builder.get_object ('cellrenderertext9')
		minimum_column.set_cell_data_func(minimum_renderer, self.minimum_cell_func)

		maximum_column = self.builder.get_object ('treeviewcolumn9')
		maximum_renderer = self.builder.get_object ('cellrenderertext10')
		maximum_column.set_cell_data_func(maximum_renderer, self.maximum_cell_func)

		price_column = self.builder.get_object ('treeviewcolumn4')
		price_renderer = self.builder.get_object ('cellrenderertext5')
		price_column.set_cell_data_func(price_renderer, self.price_cell_func)

		s_price_column = self.builder.get_object ('treeviewcolumn13')
		s_price_renderer = self.builder.get_object ('cellrenderertext13')
		s_price_column.set_cell_data_func(s_price_renderer, self.s_price_cell_func)

		ext_price_column = self.builder.get_object ('treeviewcolumn6')
		ext_price_renderer = self.builder.get_object ('cellrenderertext7')
		ext_price_column.set_cell_data_func(ext_price_renderer, self.ext_price_cell_func)
		
		self.populate_product_store ()
		self.populate_customer_store ()
		
		self.cursor.execute("SELECT print_direct, email_when_possible FROM settings")
		print_direct, email = self.cursor.fetchone()
		self.builder.get_object('menuitem1').set_active(print_direct) #set the direct print checkbox
		self.builder.get_object('menuitem4').set_active(email) #set the email checkbox
			
		self.calculate_totals ()
		
		self.window = self.builder.get_object('window')
		self.window.show_all()


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
		self.main.disconnect(self.handler_c_id)
		self.main.disconnect(self.handler_p_id)
		self.cursor.close()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('right_click_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def focus (self, window, event):
		document_type_combo = self.builder.get_object('comboboxtext2')
		active_type_id = document_type_combo.get_active_id()
		document_type_combo.remove_all()
		self.cursor.execute("SELECT id, name FROM document_types")
		for row in self.cursor.fetchall():
			type_id = row[0]
			type_name = row[1]
			document_type_combo.append(str(type_id), type_name)
		document_type_combo.set_active_id(str(active_type_id))

	def product_window(self, column):
		import products
		products.ProductsGUI(self.db)

	def contacts_window(self, widget):
		import contacts
		contacts.GUI(self.main, True)

	def view_document_clicked(self, widget):
		comment = self.builder.get_object('entry3').get_text()
		d = documenting.Setup(self.db, self.documents_store, self.contact_id, 
								comment, self.date, self.document_type_id, 
								self.document_name) 
		d.view()

	def post_document_clicked(self, widget):
		comment = self.builder.get_object('entry3').get_text()
		d = documenting.Setup(self.db, self.documents_store,  self.contact_id, 
								comment, self.date, self.document_type_id, 
								self.document_name )
		if self.builder.get_object('menuitem1').get_active() == True:
			d.print_directly()
			#print "print_directly"
		else:
			d.print_dialog(self.window)
			#print "print dialog"
		d.post(self.document_id)	
		if self.builder.get_object('menuitem4').get_active() == True:
			self.cursor.execute("SELECT * FROM contacts "
								"WHERE id = %s", (self.contact_id, ))
			for row in self.cursor.fetchall():
				name = row[1]
				email = row[9]
				if email != "":
					email = "%s '< %s >'" % (name, email)
					d.email(email)
		self.db.commit()
		self.window.destroy()

	################## start customer
	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE (deleted, customer) = "
							"(False, True) ORDER BY 2")
		for i in self.cursor.fetchall():
			contact_id = i[0]
			name = i[1]
			self.customer_store.append([str(contact_id),name ])
		
	def customer_match_selected(self, completion, model, iter):
		self.contact_id = model[iter][0]
		self.customer_selected (self.contact_id)
		#return True

	def customer_match_func(self, completion, key, iter):
		if key in self.customer_store[iter][1].lower(): #key is the typed text (always lower case ?!) ; model[iter][1] is to match for every line in the model
			return True# it's a hit!
		return False # no match

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
		self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",(name_id,))
		for row in self.cursor.fetchall() :
			self.customer_name_default_label = row[1]
			self.builder.get_object('entry10').set_text(row[3])
			self.builder.get_object('entry11').set_text(row[2])
			self.builder.get_object('entry12').set_text(row[8])
		self.builder.get_object('button2').set_sensitive(True)
		self.builder.get_object('menuitem2').set_sensitive(True)
		job_type_combo = self.builder.get_object('comboboxtext2')
		if job_type_combo.get_active() < 0 :
			job_type_combo.set_active(0)
		self.populate_import_store ()

	################## start qty

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = '{:,.1f}'.format(model.get_value(iter1, 1))
		cellrenderer.set_property("text" , qty)

	def qty_edited(self, widget, path, text):
		self.documents_store[path][1] = round(float(text), 1)
		self.calculate_row_total(path)
		self.calculate_totals ()
		self.save_document_line (path)

	################## start minimum

	def minimum_cell_func(self, column, cellrenderer, model, iter1, data):
		minimum = '{:,.2f}'.format(model.get_value(iter1, 5))
		cellrenderer.set_property("text" , minimum)

	def minimum_edited(self, widget, path, text):
		self.documents_store[path][5] = round(float(text), 2)
		self.save_document_line (path)

	################## start maximum

	def maximum_cell_func(self, column, cellrenderer, model, iter1, data):
		maximum = '{:,.2f}'.format(model.get_value(iter1, 6))
		cellrenderer.set_property("text" , maximum)

	def maximum_edited(self, widget, path, text):
		self.documents_store[path][6] = round(float(text), 2)
		self.save_document_line (path)

	################## start freeze

	def freeze_toggled (self, cell_renderer, path):
		is_active = cell_renderer.get_active()
		self.documents_store[path][9] = not is_active
		self.save_document_line (path)
		
	################## start remark

	def remark_edited(self, widget, path, text):
		self.documents_store[path][10] = text
		self.save_document_line (path)

	################## start priority

	def priority_edited(self, widget, path, text):
		self.documents_store[path][11] = text
		self.calculate_totals ()
		self.save_document_line (path)

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
		#return True

	def retailer_match_func(self, completion, key, iter):
		if key in self.customer_store[iter][1].lower(): #key is the typed text (always lower case ?!) ; model[iter][1] is to match for every line in the model
			return True# it's a hit!
		return False # no match
	
	def retailer_changed (self, combo, path, _iter):
		retailer_id = self.customer_store[_iter][0]
		retailer_name = self.customer_store[_iter][1]
		self.documents_store[path][7] = int(retailer_id)
		self.documents_store[path][8] = retailer_name
		self.save_document_line (path)
		
	################## start price

	def s_price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = '{:,.2f}'.format(model.get_value(iter1, 13))
		cellrenderer.set_property("text" , price)

	def price_cell_func(self, column, cellrenderer, model, iter1, data):
		price = '{:,.2f}'.format(model.get_value(iter1, 12))
		cellrenderer.set_property("text" , price)

	def s_price_edited (self, widget, path, text):
		self.documents_store[path][13] = float(text)
		self.save_document_line (path)
		
	def price_edited(self, widget, path, text):	
		self.documents_store[path][12] = float(text)
		self.calculate_row_total(path)
		self.calculate_totals()
		self.save_document_line (path)

	def set_sticky_price(self, widget):
		self.price_renderer_value = widget.get_chars(0, -1)

	################## end price

	def ext_price_cell_func(self, column, cellrenderer, model, iter1, data):
		ext_price = '{:,.2f}'.format(model.get_value(iter1, 14))
		cellrenderer.set_property("text" , ext_price)
		
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
		self.cursor.execute("SELECT name, ext_name FROM products "
							"WHERE id = %s", (product_id,))
		tupl = self.cursor.fetchone()
		product_name, product_ext_name = tupl[0], tupl[1]
		self.documents_store[path][3] = product_name
		self.documents_store[path][4] = product_ext_name
		self.documents_store[path][2] = int(product_id)
		price = get_customer_product_price(self.db, self.contact_id, product_id)
		self.documents_store[path][12] = price
		self.calculate_row_total(path)
		self.calculate_totals()
		self.save_document_line (path)# auto save feature
		
	def populate_product_store (self, m=None, i=None):
		self.product_store.clear()
		self.cursor.execute("SELECT id, name, ext_name FROM products "
							"WHERE (deleted, sellable, stock) = "
							"(False, True, True) ORDER BY name ")
		for row in self.cursor.fetchall():
			_id_ = row[0]
			name = row[1]
			ext_name = row[2]
			total_name = "%s {%s}"% (name, ext_name)
			self.product_store.append([str(_id_), total_name])

	################## end product

	def calculate_row_total (self, path):
		line = self.documents_store[path]
		qty = line[1]
		price = line[12]
		ext_price = qty * price
		line[14] = ext_price
	
	def calculate_totals (self, widget = None):
		self.subtotal = 0  
		self.tax = 0
		self.total = 0 
		for item in self.documents_store:
			self.total = self.total + item[14]
		total = '${:,.2f}'.format(self.total)
		self.builder.get_object('entry8').set_text(total)

	def add_entry (self, widget):
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, sellable) = (False, True)")
		self.builder.get_object('button15').set_sensitive(True)
		for i in self.cursor.fetchall():
			product_id = i[0]
			product_name = i[1]
			price = get_customer_product_price (self.db, self.contact_id, product_id)
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

	def delete_entry (self, widget):
		selection = self.builder.get_object("treeview-selection")
		row, path = selection.get_selected_rows ()
		document_line_item_id = self.documents_store[path][0]
		self.cursor.execute("DELETE FROM document_lines WHERE id = %s",
							(document_line_item_id,))
		self.db.commit()
		self.populate_document_store ()

	def save_document_line (self, path):
		line = self.documents_store[path]
		line_id = line[0]
		qty = line[1]
		product_id = line[2]
		product_name = line[3]
		product_ext_name = line[4]
		minimum = line[5]
		maximum = line[6]
		retailer_id = line[7]
		retailer_name = line[8]
		type_1 = line[9]
		remark = line[10]
		priority = line[11]
		price = line[12]
		s_price = line[13]
		ext_price = line[14]
		if retailer_id == 0:
			retailer_id = None
		if line_id == 0:
			self.cursor.execute("INSERT INTO document_lines (document_id, qty, product_id, min, max, retailer_id, type_1, remark, priority, price, s_price, ext_price, canceled, finished) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (self.document_id, qty, product_id, minimum, maximum, retailer_id, type_1, remark, priority, price, s_price, ext_price, False, 0.00))
			line_id = self.cursor.fetchone()[0]
			line[0] = line_id
		else:
			self.cursor.execute("UPDATE document_lines SET (document_id, qty, product_id, min, max, retailer_id, type_1, remark, priority, price, s_price, ext_price) = (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) WHERE id = %s", (self.document_id, qty, product_id, minimum, maximum, retailer_id, type_1, remark, priority, price, s_price, ext_price, line_id))
		self.db.commit()
		self.calculate_totals ()

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
		self.db.commit()

	def delete_document_clicked (self, widget):
		self.cursor.execute("DELETE FROM documents WHERE id = %s", (self.document_id,))
		self.db.commit()
		self.builder.get_object('entry3').set_text('')
		self.populate_import_store ()

	def document_type_changed (self, widget):
		document_type = widget.get_active_text()
		if document_type != None:
			self.document_type = document_type
			self.document_type_id = widget.get_active_id()
			self.builder.get_object('window').set_title("New " + document_type)
			self.builder.get_object('button15').set_label("Post " + document_type)
			self.calendar.set_today()
			self.populate_import_store ()

	def document_type_clicked (self, widget):
		import settings
		settings.GUI(self.db, 'document_types')

	def new_document_clicked (self, widget):
		if self.document_type == "":
			return
		self.document_id = 0
		self.documents_store.clear()
		self.builder.get_object('label6').set_text(" Current %s : " % self.document_type)
		comment = self.builder.get_object('entry3').get_text()
		self.cursor.execute("INSERT INTO documents (contact_id, closed, invoiced, canceled, date_created, dated_for, document_type_id, pending_invoice) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (self.contact_id, False, False, False, datetime.today(), self.date, self.document_type_id, False))
		self.document_id = self.cursor.fetchone()[0]
		self.set_document_name ()
		self.db.commit()
		self.builder.get_object('button13').set_sensitive(True)
		self.builder.get_object('button14').set_sensitive(True)

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
		self.db.commit()
		self.builder.get_object('entry5').set_text(self.document_name)
		
	def populate_import_store (self):
		model, path = self.builder.get_object('treeview-selection5').get_selected_rows()
		self.import_store.clear()
		doc_count = 0
		self.cursor.execute("SELECT id, name FROM documents "
							"WHERE (document_type_id, closed, canceled, "
							"contact_id)  = "
							"(%s, False, False, %s)", 
							(self.document_type_id, self.contact_id))
		for row in self.cursor.fetchall():
			doc_count += 1
			line_id = row[0]
			line_name = row[1]
			self.import_store.append([line_id, line_name])
		self.builder.get_object('button11').set_label("Existing documents (%s)"
																	% doc_count)
		if path != []:
			self.builder.get_object('treeview-selection5').select_path(path)

	def import_window_clicked (self, widget):
		import_dialog = self.builder.get_object('import_dialog')
		self.populate_import_store ()
		result = import_dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			self.import_document ()
		import_dialog.hide()

	def import_document (self):
		selection = self.builder.get_object('treeview-selection5')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_iter = model.get_iter(path)
		self.document_id = model.get_value(tree_iter, 0)
		self.populate_document_store()
		self.builder.get_object('button13').set_sensitive(True)
		self.builder.get_object('button14').set_sensitive(True)
		self.builder.get_object('button15').set_sensitive(True)
		
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
		self.cursor.execute("SELECT dli.id, qty, p.id, p.name, ext_name, min, max, "
							"type_1, type_2, priority, remark, price, s_price, "
							"retailer_id, COALESCE(c.name, '') "
							"FROM document_lines AS dli "
							"JOIN products AS p ON dli.product_id = p.id "
							"LEFT JOIN contacts AS c ON dli.retailer_id = c.id "
							"WHERE document_id = %s ORDER BY dli.id", 
							(self.document_id, ) )
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			ext_name = row[4]
			min = row[5]
			max = row[6]
			type_1 = row[7]
			type_2 = row[8]
			priority = row[9]
			remark = row[10]
			price = row[11]
			s_price = row[12]
			retailer_id = row[13]
			retailer_name = row[14]
			ext_price = qty * price
			self.documents_store.append([row_id, qty, product_id, product_name, 
										ext_name, min, max, retailer_id,
										retailer_name, type_1, remark, priority,
										price, s_price, ext_price])
		self.calculate_totals ()

	def help_clicked (self, widget):
		subprocess.Popen("yelp ./help/invoice.page", shell = True)

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
		self.db.commit()

	def calendar_entry_icon_release (self, widget, icon, void):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def clear_retailer_entry (self, menuitem):
		selection = self.builder.get_object("treeview-selection")
		store, path = selection.get_selected_rows ()
		self.documents_store[path][7]= None
		self.documents_store[path][8] = ''
		line_id = self.documents_store[path][0]
		self.cursor.execute("UPDATE document_lines SET retailer_id = NULL "
							"WHERE id = %s", (line_id, ))
		self.db.commit()

	 #barcode entry support code *******

	def barcode_entry_activated (self, entry2):
		barcode = entry2.get_text()
		entry2.set_text('')
		self.cursor.execute("SELECT id, name, level_1_price, ext_name "
								"FROM products WHERE barcode = %s",(barcode, ))
		for i in self.cursor.fetchall():
			product_id = i[0]
			for index, row in enumerate(self.documents_store):
				if row[2] == product_id:
					row[1] += 1.0 # increase the qty by one
					self.save_document_line(index)
					treeview = self.builder.get_object('treeview2')
					c = treeview.get_column(0)
					treeview.set_cursor(index , c, False)	#set the cursor to the last appended item
					return
			product_name = i[1]
			price = i[2]
			ext_name = i[3]
			self.documents_store.append([0, 1.0, product_id, product_name, ext_name, 0.0, 100.00, int(self.contact_id), self.customer_name_default_label, False, "", "1", price, 0.00, 1])
			last = self.documents_store.iter_n_children ()-1
			#last -= 1 #iter_n_children starts at 1 ; set_cursor starts at 0 ## function merged with above line
			self.save_document_line(last)
			treeview = self.builder.get_object('treeview2')
			c = treeview.get_column(0)
			treeview.set_cursor(last , c, False)	#set the cursor to the last appended item
			return
		else:
			print ("please make a window to alert the user that the barcode does not exist!")




		
