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

from gi.repository import Gtk
from datetime import datetime

UI_FILE = "src/job_sheet.ui"

class JobSheetGUI:
	def __init__(self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.handler_c_id = main.connect ("contacts_changed", self.populate_customer_store )
		self.handler_p_id = main.connect ("products_changed", self.populate_product_store )
		
		self.customer_id = 0
		self.job_id = 0
		self.job_store = self.builder.get_object('job_store')
		self.customer_store = self.builder.get_object('customer_store')
		self.populate_customer_store ()
		self.product_store = self.builder.get_object('product_store')
		self.populate_product_store()

		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		
		qty_column = self.builder.get_object ('treeviewcolumn1')
		qty_renderer = self.builder.get_object ('cellrendererspin1')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.main.disconnect(self.handler_c_id)
		self.main.disconnect(self.handler_p_id)
		self.cursor.close()

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_editing_started (self, renderer, combo, path):
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		combo_entry = combo.get_child()
		combo_entry.set_completion(product_completion)

	def product_match_selected(self, completion, model, iter_):
		product_id = model[iter_][0]
		product_name = model[iter_][1]
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.job_store[path][2] = int(product_id)
		self.job_store[path][3] = product_name
		line = self.job_store[path]
		self.save_line (line)

	def qty_edited (self, spin, path, text):
		qty = float(text)
		self.job_store[path][1] = qty
		line = self.job_store[path]
		self.save_line (line)
			
	def remark_edited(self, widget, path, text): 
		self.job_store[path][4] = text
		line = self.job_store[path]
		self.save_line (line)

	def set_sticky_text(self, widget):
		self.edited_renderer_text = widget.get_chars(0, -1)

	def job_window(self, widget):
		import job_types
		job_types.GUI(self.db)

	def product_combo_changed (self, combo, path, tree_iter):
		product_id = self.product_store.get_value (tree_iter, 0)
		product_name = self.product_store.get_value (tree_iter, 1)
		self.job_store[path][2] = int(product_id)
		self.job_store[path][3] = product_name
		line = self.job_store[path]
		self.save_line (line)

	def save_line (self, line):
		row_id = line[0]
		qty = line[1]
		product_id = line[2]
		remark = line[4]
		if row_id == 0:
			self.cursor.execute("INSERT INTO job_sheet_line_items "
								"(job_sheet_id, qty, product_id, remark) "
								"VALUES (%s, %s, %s, %s)", 
								(self.job_id, qty, product_id, remark))
		else:
			self.cursor.execute("UPDATE job_sheet_line_items "
								"SET (job_sheet_id, qty, product_id, remark) "
								"= (%s, %s, %s, %s) WHERE id = %s", 
								(self.job_id, qty, product_id, remark, row_id))
		self.db.commit()

	def contacts_window(self, widget):
		import contacts
		contacts.GUI(self.main)

	def product_window(self, column):
		import products
		products.ProductsGUI(self.main)

	def populate_product_store (self):
		self.product_store.clear()
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE (deleted, stock, sellable) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			name = row[1]
			self.product_store.append([str(product_id), name])

	def focus(self, window, void):
		if self.builder.get_object("entry1").get_text() == "":
			self.job_combobox_populate ()
		self.populate_existing_job_combobox ()

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = '{:,.1f}'.format(model.get_value(iter1, 1))
		cellrenderer.set_property("text" , qty)

	def job_combobox_populate (self):
		job_combo = self.builder.get_object('comboboxtext3')
		job = job_combo.get_active_id()
		job_combo.remove_all()
		self.cursor.execute("SELECT id, name FROM job_types")
		for i in self.cursor.fetchall():
			id_ = i[0]
			name = i[1]
			job_combo.append(str(id_), name)
		job_combo.set_active_id(job)

	def populate_existing_job_combobox (self):
		existing_job_combo = self.builder.get_object('comboboxtext2')
		existing_job = existing_job_combo.get_active_id()
		existing_job_combo.remove_all()
		self.cursor.execute("SELECT id, job_type_id, description "
							"FROM job_sheets "
							"WHERE (completed, invoiced, contact_id) "
							"= (False, False, %s)", (self.customer_id,)) 
		for i in self.cursor.fetchall():
			id_ = i[0]
			job_type_id = i[1]
			self.cursor.execute("SELECT name FROM job_types WHERE id = %s", 
																(job_type_id,))
			job_name = self.cursor.fetchone()[0]
			description = i[2]
			existing_job_combo.append(str(id_), job_name + " : " + description)
		existing_job_combo.set_active_id(existing_job)

	def delete_existing_job	(self, widget):
		job_id = widget.get_active_id()
		self.cursor.execute("DELETE FROM job_sheets WHERE id = %s", (job_id,))
		self.cursor.execute("DELETE FROM job_sheet_line_items "
							"WHERE job_sheet_id = %s", (job_id ,))
		self.db.commit()
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
		self.db.commit()

	def new_job_combo_changed(self, widget):
		if widget.get_active_id() != None: # something actually selected
			#self.save ()
			self.builder.get_object('comboboxtext2').set_active(-1)
			self.job_id = 0 # new job
			self.job_store.clear()
			self.builder.get_object('entry1').set_sensitive(True)
			self.builder.get_object('entry1').set_text("")
		else: # changed by code to nothing
			self.builder.get_object('button7').set_sensitive(False)
			self.builder.get_object('button5').set_sensitive(False)

	def existing_job_combo_changed (self, widget):
		if widget.get_active_id() != None:
			self.project_name = widget.get_active_text()
			self.builder.get_object('comboboxtext3').set_active(-1)
			self.builder.get_object('button5').set_sensitive(True)
			self.builder.get_object('button3').set_sensitive(True)
			self.builder.get_object('entry1').set_text("")
			self.builder.get_object('entry1').set_sensitive(False)
			self.job_id = widget.get_active_id()
			self.populate_job_treeview()
			self.cursor.execute("SELECT id FROM time_clock_projects "
								"WHERE (job_sheet_id, active) = (%s, True)", 
								(self.job_id,))
			for row in self.cursor.fetchall():
				self.builder.get_object('checkbutton2').set_active(True)
				break
			else:
				self.builder.get_object('checkbutton2').set_active(False)
		else:
			self.builder.get_object('button7').set_sensitive(False)
			self.builder.get_object('button5').set_sensitive(False)
			self.builder.get_object('button3').set_sensitive(False)

	def customer_combo_changed(self, widget):
		id_ = widget.get_active_id()
		if id_ != None:
			self.builder.get_object('comboboxtext2').set_sensitive(True)
			self.job_id = 0
			self.job_store.clear()
			self.customer_id = id_
			self.populate_existing_job_combobox ()	
			self.job_combobox_populate ()
			self.builder.get_object('comboboxtext3').set_active(-1)
			
	def customer_match_selected(self, completion, model, iter_):
		self.job_id = 0
		self.job_store.clear()
		self.customer_id = self.customer_store[iter_][0]
		self.job_combobox_populate ()
		self.populate_existing_job_combobox ()
		self.builder.get_object('combobox1').set_active_id(model[iter_][0])
		self.builder.get_object('comboboxtext3').set_active(-1)
		return True
		
	def description_changed(self, widget):
		self.builder.get_object('button7').set_sensitive(True)

	def job_description_entry_activated (self, entry):
		self.create_new_job()

	def create_job_clicked (self, button):
		self.create_new_job()

	def create_new_job (self):
		description = self.builder.get_object('entry1').get_text()
		time_clock_project = self.builder.get_object('checkbutton2').get_active()
		contact_name = self.builder.get_object('combobox-entry').get_text()
		job_name = self.builder.get_object('comboboxtext3').get_active_text()
		job_type_id = self.builder.get_object('comboboxtext3').get_active_id()
		job_name_description = self.builder.get_object('entry1').get_text()
		self.cursor.execute("INSERT INTO job_sheets "
							"(description, job_type_id, time_clock, "
							"date_inserted, invoiced, completed, contact_id) "
							"VALUES (%s, %s, %s, %s, %s, %s, %s) "
							"RETURNING id", 
							(description, job_type_id, time_clock_project, 
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
		self.db.commit()
		self.populate_existing_job_combobox ()
		self.builder.get_object('comboboxtext2').set_active_id(str(self.job_id))
		self.builder.get_object('button7').set_sensitive(False)

	def delete_line(self, widget):
		selection = self.builder.get_object("treeview-selection1")
		store, path = selection.get_selected_rows ()
		if path != []: # a row is selected
			job_line_id = store[path][0]
			self.cursor.execute("DELETE FROM job_sheet_line_items "
								"WHERE id = %s", (job_line_id,))
			self.db.commit()
			self.populate_job_treeview ()
			
	def new_line (self, widget):
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE deleted = False LIMIT 1")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			self.job_store.append([0, 1, product_id, product_name, ""])
		path = self.job_store.iter_n_children()
		line = self.job_store[path - 1]
		self.save_line(line)

	def post_job_clicked (self, widget):
		self.cursor.execute("UPDATE job_sheets SET (contact_id, completed) "
							"= (%s, True) WHERE id = %s", 
							(self.customer_id, self.job_id))
		self.populate_job_treeview ()
		self.cursor.execute("UPDATE time_clock_projects "
							"SET (stop_date, active) = (%s, False) "
							"WHERE job_sheet_id = %s", 
							(datetime.today(), self.job_id))
		self.job_store.clear()
		self.builder.get_object('comboboxtext2').set_active(-1)
		self.builder.get_object('comboboxtext3').set_active(-1)
		self.builder.get_object('checkbutton2').set_active(False)
		self.job_id = 0
		self.populate_customer_store ()
		self.populate_existing_job_combobox ()
		self.db.commit()

	def populate_job_treeview(self):
		treeselection = self.builder.get_object('treeview-selection1')
		model, path = treeselection.get_selected_rows ()
		self.job_store.clear()
		self.cursor.execute("SELECT id, qty, product_id, remark "
							"FROM job_sheet_line_items "
							"WHERE job_sheet_id = %s", (self.job_id ,))
		for row in self.cursor.fetchall():
			id_ = row[0]
			qty = row[1]
			product_id = row[2]
			self.cursor.execute("SELECT name FROM products WHERE id = %s", 
															(product_id,))
			product_name = self.cursor.fetchone()[0]
			remark = row[3]
			self.job_store.append([id_, qty, product_id, product_name, remark])
		if path != [] : # a row is selected
			tree_iter = model.get_iter(path)
			treeselection.select_iter(tree_iter)

	def customer_match_func (self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[tree_iter][1].lower():
				return False
		return True

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()	
		self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE (deleted, customer) = (False, True) "
							"ORDER BY name")
		for i in self.cursor.fetchall():
			serial = i[0]
			name = i[1]
			ext_name = i[2]
			self.customer_store.append([str(serial), name, ext_name])
		
		

		
