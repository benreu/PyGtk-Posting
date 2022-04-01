# job_sheet.py
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

import psycopg2
from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
import subprocess
from invoice_window import create_new_invoice 
from constants import ui_directory, DB, broadcaster, template_dir
import printing

UI_FILE = ui_directory + "/job_sheet.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass
	
class JobSheetGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_customer_store ), 
						   ("products_changed", self.populate_product_store )):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		enforce_target = Gtk.TargetEntry.new('text/plain', 
												Gtk.TargetFlags(1),
												129)
		treeview = self.get_object('treeview1')
		treeview.drag_dest_set(Gtk.DestDefaults.ALL, 
								[enforce_target], 
								Gdk.DragAction.COPY)
		treeview.connect("drag-data-received", self.on_drag_data_received)
		treeview.drag_dest_set_target_list([enforce_target])
		
		self.customer_id = 0
		self.job_id = 0
		self.job_store = self.get_object('job_store')
		self.customer_store = self.get_object('customer_store')
		self.populate_customer_store ()
		self.product_store = self.get_object('product_store')
		self.job_type_store = self.get_object('job_type_store')
		self.populate_product_store()

		customer_completion = self.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		
		qty_column = self.get_object ('treeviewcolumn1')
		qty_renderer = self.get_object ('cellrendererspin1')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
		list_ = data.get_text().split(' ')
		if len(list_) != 2:
			raise Exception("invalid drag data received")
			return
		if self.job_id == 0:
			return
		qty, product_id = list_[0], list_[1]
		self.cursor.execute("SELECT 0, %s::float, id, name, '' FROM products "
							"WHERE id = %s", (qty, product_id))
		for row in self.cursor.fetchall():
			iter_ = self.job_store.append(row)
		self.cursor.execute("INSERT INTO job_sheet_items "
							"(job_sheet_id, qty, product_id) "
							"VALUES (%s, %s, %s) RETURNING id, qty", 
							(self.job_id, qty, product_id))
		for row in self.cursor.fetchall():
			self.job_store[iter_][0] = row[0] #set the line id
			self.job_store[iter_][1] = row[1] #set the formatted qty
		path = self.job_store.get_path(iter_)
		treeview = self.get_object('treeview1')
		column = treeview.get_column(0)
		treeview.set_cursor(path, column, False)
		DB.commit()
		
	def destroy (self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_editing_started (self, renderer, combo, path):
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		combo_entry = combo.get_child()
		combo_entry.set_completion(product_completion)

	def product_match_selected(self, completion, model, iter_):
		product_id = model[iter_][0]
		product_name = model[iter_][1]
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.product_selected(path, product_id, product_name)

	def product_combo_changed (self, combo, path, tree_iter):
		product_id = self.product_store.get_value (tree_iter, 0)
		product_name = self.product_store.get_value (tree_iter, 1)
		self.product_selected(path, product_id, product_name)

	def product_selected (self, path, product_id, product_name):
		iter_ = self.job_store.get_iter(path)
		self.job_store[iter_][2] = int(product_id)
		self.job_store[iter_][3] = product_name
		line_id = self.job_store[iter_][0]
		self.cursor.execute("UPDATE job_sheet_items "
							"SET product_id = %s WHERE id = %s", 
							(product_id, line_id))
		DB.commit()
		# retrieve path again after all sorting has happened for the updates
		path = self.job_store.get_path(iter_)
		treeview = self.get_object('treeview1')
		c = treeview.get_column(2)
		GLib.idle_add(treeview.set_cursor, path, c, True)

	def qty_edited (self, spin, path, text):
		iter_ = self.job_store.get_iter(path) 
		line_id = self.job_store[iter_][0]
		self.cursor.execute("UPDATE job_sheet_items "
							"SET qty = %s WHERE id = %s; "
							"SELECT qty FROM job_sheet_items "
							"WHERE id = %s", 
							(text, line_id, line_id))
		DB.commit()
		self.job_store[iter_][1] = self.cursor.fetchone()[0]
		
	def remark_edited(self, widget, path, text):
		iter_ = self.job_store.get_iter(path) 
		line_id = self.job_store[iter_][0]
		self.job_store[iter_][4] = text
		self.cursor.execute("UPDATE job_sheet_items "
							"SET remark = %s WHERE id = %s", 
							(text, line_id))
		DB.commit()

	def job_window(self, widget):
		import job_types
		job_types.GUI()

	def contacts_window (self, widget):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()

	def product_window_activated (self, menuitem):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def generate_serial_number_clicked (self, button):
		c = DB.cursor()
		c.execute("UPDATE job_types "
					"SET current_serial_number = (current_serial_number + 1) "
					"WHERE id = %s RETURNING current_serial_number::text",
					(self.job_type_id,))
		serial_number = c.fetchone()[0]
		self.get_object('entry1').set_text(serial_number)
		button.set_sensitive(False)
		self.print_serial_number(serial_number)
		DB.commit()

	def print_serial_number(self, serial_number):
		document = Item()
		document.serial_number = serial_number
		data = dict(label = document)
		from py3o.template import Template
		sn_file = "/tmp/job_serial.odt"
		t = Template(template_dir+"/job_serial_template.odt", sn_file, True)
		t.render(data)
		subprocess.Popen(["soffice", sn_file])

	def populate_product_store (self, m=None):
		self.product_store.clear()
		self.cursor.execute("SELECT id::text, "
							"name || ' {' || ext_name || '}' FROM products "
							"WHERE (deleted, stock, sellable) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		DB.rollback()

	def focus(self, window, void):
		if self.get_object("entry1").get_text() == "":
			self.job_combobox_populate ()
		self.populate_existing_job_combobox ()

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = '{:,.1f}'.format(model.get_value(iter1, 1))
		cellrenderer.set_property("text" , qty)

	def job_combobox_populate (self):
		job_combo = self.get_object('job_type_combo')
		job = job_combo.get_active_id()
		model = job_combo.get_model()
		model.clear()
		self.cursor.execute("SELECT id::text, name "
							"FROM job_types ORDER BY name")
		for row in self.cursor.fetchall():
			model.append(row)
		job_combo.set_active_id(job)
		DB.rollback()

	def populate_existing_job_combobox (self):
		existing_job_combo = self.get_object('comboboxtext2')
		existing_job = existing_job_combo.get_active_id()
		existing_job_combo.remove_all()
		self.cursor.execute("SELECT js.id::text, "
							"jt.name || ' : ' || js.description "
							"FROM job_sheets AS js "
							"JOIN job_types AS jt ON jt.id = js.job_type_id "
							"WHERE (completed, invoiced, contact_id) "
							"= (False, False, %s)", (self.customer_id,)) 
		for row in self.cursor.fetchall():
			existing_job_combo.append(row[0], row[1])
		existing_job_combo.set_active_id(existing_job)
		DB.rollback()

	def delete_existing_job	(self, widget):
		job_id = widget.get_active_id()
		try:
			self.cursor.execute("DELETE FROM job_sheets WHERE id = %s", 
															(job_id,))
		except psycopg2.IntegrityError as e:
			DB.rollback()
			self.show_message(str(e))
			return
		DB.commit()
		self.populate_existing_job_combobox ()
		self.job_store.clear()

	def time_clock_available_toggled(self, widget):
		if widget.has_focus() == False:
			return # changed by code
		if self.job_id == 0:
			return # no active project
		available = widget.get_active()
		self.cursor.execute("UPDATE job_sheets "
							"SET time_clock = %s WHERE id = %s", 
							(available, self.job_id))
		if available == True:
			self.cursor.execute("INSERT INTO time_clock_projects "
								"(name, start_date, active, permanent, "
								"job_sheet_id) "
								"VALUES (%s, %s, True, False, %s)", 
								(self.project_name, datetime.today(), 
								self.job_id))
		else:
			self.cursor.execute("UPDATE time_clock_projects "
								"SET (active, stop_date) = (%s, %s) "
								"WHERE job_sheet_id = %s", 
								(available, datetime.today(), self.job_id))
		DB.commit()

	def new_job_combo_changed(self, combo):
		id_ = combo.get_active_id()
		if id_ != None: # something actually selected
			self.get_object('comboboxtext2').set_active(-1)
			self.job_id = 0 # new job
			self.job_store.clear()
			self.job_type_id = id_
			self.get_object('entry1').set_sensitive(True)
			self.get_object('entry1').set_text("")
			self.get_object('button8').set_sensitive(True)
		else: # changed by code to nothing
			self.get_object('button7').set_sensitive(False)
			self.get_object('button5').set_sensitive(False)
			self.get_object('button8').set_sensitive(False)

	def existing_job_combo_changed (self, widget):
		if widget.get_active_id() != None:
			self.project_name = widget.get_active_text()
			self.get_object('job_type_combo').set_active(-1)
			self.get_object('button5').set_sensitive(True)
			self.get_object('button3').set_sensitive(True)
			self.get_object('entry1').set_text("")
			self.get_object('entry1').set_sensitive(False)
			self.job_id = widget.get_active_id()
			self.populate_job_treeview()
			self.cursor.execute("SELECT id FROM time_clock_projects "
								"WHERE (job_sheet_id, active) = (%s, True)", 
								(self.job_id,))
			for row in self.cursor.fetchall():
				self.get_object('checkbutton2').set_active(True)
				break
			else:
				self.get_object('checkbutton2').set_active(False)
		else:
			self.get_object('button7').set_sensitive(False)
			self.get_object('button5').set_sensitive(False)
			self.get_object('button3').set_sensitive(False)
		DB.rollback()

	def customer_combo_changed(self, widget):
		id_ = widget.get_active_id()
		if id_ != None:
			self.get_object('job_type_combo').set_sensitive(True)
			self.get_object('comboboxtext2').set_sensitive(True)
			self.job_id = 0
			self.job_store.clear()
			self.customer_id = id_
			self.populate_existing_job_combobox ()	
			self.job_combobox_populate ()
			self.get_object('job_type_combo').set_active(-1)
			
	def customer_match_selected(self, completion, model, iter_):
		self.job_id = 0
		self.job_store.clear()
		self.customer_id = self.customer_store[iter_][0]
		self.job_combobox_populate ()
		self.populate_existing_job_combobox ()
		self.get_object('combobox1').set_active_id(model[iter_][0])
		self.get_object('job_type_combo').set_active(-1)
		return True
		
	def description_changed(self, widget):
		self.get_object('button7').set_sensitive(True)

	def job_description_entry_activated (self, entry):
		self.create_new_job()

	def create_job_clicked (self, button):
		self.create_new_job()

	def create_new_job (self):
		description = self.get_object('entry1').get_text()
		time_clock_project = self.get_object('checkbutton2').get_active()
		contact_name = self.get_object('combobox-entry').get_text()
		iter_ = self.get_object('job_type_combo').get_active_iter()
		job_name = self.job_type_store[iter_][1]
		job_name_description = self.get_object('entry1').get_text()
		self.cursor.execute("INSERT INTO job_sheets "
							"(description, job_type_id, time_clock, "
							"date_inserted, invoiced, completed, contact_id) "
							"VALUES (%s, %s, %s, %s, %s, %s, %s) "
							"RETURNING id", 
							(description, self.job_type_id, time_clock_project, 
							datetime.today(), False, False, 
							self.customer_id))
		self.job_id = self.cursor.fetchone()[0]
		self.project_name = job_name + " : " + job_name_description
		if time_clock_project == True:
			self.cursor.execute("INSERT INTO time_clock_projects "
								"(name, start_date, active, permanent, "
								"job_sheet_id) "
								"VALUES (%s, %s, True, False, %s)", 
								(self.project_name, datetime.today(), 
								self.job_id))
		DB.commit()
		self.populate_existing_job_combobox ()
		self.get_object('comboboxtext2').set_active_id(str(self.job_id))
		self.get_object('button7').set_sensitive(False)

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def delete_item (self, widget = None):
		selection = self.get_object("treeview-selection1")
		store, path = selection.get_selected_rows ()
		if path != []: # a row is selected
			job_line_id = store[path][0]
			self.cursor.execute("DELETE FROM job_sheet_items "
								"WHERE id = %s", (job_line_id,))
			DB.commit()
			self.populate_job_treeview ()
			
	def new_line (self, widget = None):
		self.cursor.execute("INSERT INTO job_sheet_items "
							"(job_sheet_id, qty, product_id) "
							"VALUES (%s, 1, (SELECT id FROM products "
								"WHERE deleted = False LIMIT 1)) "
							"RETURNING job_sheet_items.id ",
							(self.job_id,))
		line_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT jsi.id, qty, p.id, p.name, remark "
							"FROM job_sheet_items AS jsi "
							"JOIN products AS p ON p.id = jsi.product_id "
							"WHERE jsi.id = %s", 
							(line_id,))
		for row in self.cursor.fetchall():
			iter_ = self.job_store.append(row)
		DB.commit()
		path = self.job_store.get_path(iter_)
		treeview = self.get_object('treeview1')
		column = treeview.get_column(0)
		treeview.set_cursor(path, column, True)

	def post_job_to_invoice_clicked (self, widget):
		c = DB.cursor()
		c.execute("SELECT i.id, i.name, c.name FROM invoices AS i "
					"JOIN contacts AS c ON c.id = i.customer_id "
					"WHERE (i.posted, i.canceled, i.active, i.customer_id) = "
					"(False, False, True, %s) "
					"LIMIT 1", (self.customer_id,))
		for row in c.fetchall():
			invoice_id = row[0]
			invoice_name = row[1]
			customer_name = row[2]
			message = "Invoice '%s' already exists for customer '%s'.\n"\
						"Do you want to append the items?" \
						% (invoice_name, customer_name)
			action = self.show_invoice_exists_message (message) 
			if action == 2:
				break # append the items
			else:
				return # cancel posting to invoice altogether
		else: # create new invoice
			invoice_id = create_new_invoice (datetime.today(), self.customer_id)
		c.execute("INSERT INTO invoice_items "
						"(qty, product_id, remark, invoice_id) "
					"SELECT qty, product_id, remark, %s "
					"FROM job_sheet_items AS jsi "
						"WHERE jsi.job_sheet_id = %s; "
					"UPDATE job_sheets SET (invoiced, completed) "
						"= (True, True) WHERE id = %s; "
					"UPDATE time_clock_projects "
					"SET (stop_date, active) = (%s, False) "
					"WHERE job_sheet_id = %s", 
					(invoice_id, self.job_id, self.job_id, 
					datetime.today(), self.job_id))
		DB.commit()
		self.job_store.clear()
		self.get_object('comboboxtext2').set_active(-1)
		self.get_object('job_type_combo').set_active(-1)
		self.get_object('checkbutton2').set_active(False)
		self.job_id = 0
		self.populate_customer_store ()
		self.populate_existing_job_combobox ()

	def populate_job_treeview(self):
		treeselection = self.get_object('treeview-selection1')
		model, path = treeselection.get_selected_rows ()
		self.job_store.clear()
		self.cursor.execute("SELECT jsi.id, qty, p.id, p.name, remark "
							"FROM job_sheet_items AS jsi "
							"JOIN products AS p ON p.id = jsi.product_id "
							"WHERE job_sheet_id = %s", (self.job_id ,))
		for row in self.cursor.fetchall():
			self.job_store.append(row)
		if path != [] : # a row is selected
			tree_iter = model.get_iter(path)
			treeselection.select_iter(tree_iter)
		DB.rollback()

	def customer_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[tree_iter][1].lower():
				return False
		return True

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()	
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE (deleted, customer) = (False, True) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)
		DB.rollback()

	def window_key_release_event_ (self, window, event):
		keyname = Gdk.keyval_name(event.keyval)
		if keyname == 'F1':
			pass # self.help_clicked ()
		elif keyname == 'F2':
			self.new_line ()
		elif keyname == 'F3':
			self.delete_line ()

	def treeview_key_release_event (self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
				path = tmodel.get_path(titer)
				next_column = columns[0]
			GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)

	def show_invoice_exists_message (self, message):
		dialog = Gtk.Dialog(	"", 
								self.window,
								0)
		dialog.add_button("Cancel", 1)
		dialog.add_button("Append items", 2)
		label = Gtk.Label(label = message)
		box = dialog.get_content_area()
		box.add(label)
		label.show()
		response = dialog.run()
		dialog.destroy()
		return response

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



