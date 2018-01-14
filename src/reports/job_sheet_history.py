# job_sheet_history.py
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
from dateutils import datetime_to_text

UI_FILE = "src/reports/job_sheet_history.ui"

class JobSheetHistoryGUI:
	def __init__(self, db):

		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.customer_id = None
		self.job_sheet_treeview = self.builder.get_object('treeview1')
		
		self.customer_store = self.builder.get_object('customer_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.job_sheet_store = self.builder.get_object('job_store')
		self.job_sheet_line_item_store = self.builder.get_object('liststore2')
		self.search_store = Gtk.ListStore(str)
		
		self.populate_customers()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def search_changed(self, widget):
		search_text = widget.get_text()	
		self.search_store.clear()
		treeiter = self.job_sheet_store.get_iter_first()
		while treeiter != None:
			for cell in self.job_sheet_store[treeiter][:]:
				if search_text in str(cell):
					cursor_iter = self.job_sheet_store.get_string_from_iter(treeiter)
					self.search_store.append([cursor_iter])
			treeiter = self.job_sheet_store.iter_next(treeiter)

	def search_forward(self, widget):
		c = self.job_sheet_treeview.get_column(0)
		try:
			self.search_iter += 1
			row = self.search_store[self.search_iter]
		except: # tumble over to the start
			self.search_iter = 0
			row = ["1000000"] # a number that is not valid so no row is selected
			for i in self.search_store: 
				row = self.search_store[self.search_iter]
				break # we have a valid row now
		path = Gtk.TreePath.new_from_string(row[0])
		self.job_sheet_treeview.expand_to_path(path)
		self.job_sheet_treeview.set_cursor(row , c, True)

	def search_backward(self, widget):
		c = self.job_sheet_treeview.get_column(0)
		try:
			self.search_iter -= 1
			row = self.search_store[self.search_iter]
		except: # tumble over to the end
			self.search_iter = len(self.search_store) - 1
			row = ["1000000"] # a number that is not valid
			for i in self.search_store: 
				row = self.search_store[self.search_iter]
				break # we have a valid row now
		path = Gtk.TreePath.new_from_string(row[0])
		self.job_sheet_treeview.expand_to_path(path)
		self.job_sheet_treeview.set_cursor(row , c, True)

	def remark_edited(self, widget, path, text):
		_id_ = self.job_sheet_line_item_store[path][0]
		self.job_sheet_line_item_store[path][3] = text
		self.cursor.execute("UPDATE job_sheet_line_items "
							"SET remark = %s WHERE id = %s", (text, _id_))
		self.db.commit()

	def focus (self, window, event):
		tree_selection = self.builder.get_object('treeview-selection1')
		model, path = tree_selection.get_selected_rows()
		self.populate_job_sheet_treeview()
		if path == []:
			return
		self.builder.get_object('treeview1').scroll_to_cell(path)
		tree_selection.select_path(path)
		job_sheet_id = model[path][0]
		self.populate_job_sheet_line_item_treeview(job_sheet_id)

	def customer_changed (self, widget):
		customer_id = widget.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			self.populate_job_sheet_treeview()

	def customer_match_selected (self, completion, model, iter_):
		self.customer_id = model[iter_][0]
		self.populate_job_sheet_treeview()

	def populate_job_sheet_treeview (self):
		self.job_sheet_store.clear()
		self.job_sheet_line_item_store.clear()
		view_checkbutton = self.builder.get_object('checkbutton1')
		if view_checkbutton.get_active() == True:
			self.cursor.execute("SELECT id, contact_id, job_type_id, "
								"date_inserted, description FROM job_sheets")
		elif self.customer_id != None:
			self.cursor.execute("SELECT id, contact_id, job_type_id, "
								"date_inserted, description "
								"FROM job_sheets WHERE contact_id = %s", 
								(self.customer_id,))
		else:
			return #no active customer and 'view all' not on
		for row in self.cursor.fetchall():
			row_id = row[0]
			contact_id = row[1]
			job_type_id = row[2]
			self.cursor.execute("SELECT name FROM job_types "
								"WHERE id = %s", (job_type_id,))
			job_type_name = self.cursor.fetchone()[0]
			date = row[3]
			date_text = datetime_to_text(date)
			description = row[4]
			self.cursor.execute("SELECT name, c_o FROM contacts "
								"WHERE id = %s", (contact_id,))
			contact_name = self.cursor.fetchone()[0]
			self.job_sheet_store.append([row_id, contact_name, str(date), 
										date_text, job_type_name, description])

	def job_sheet_treeview_activate(self, treeview, path, treeviewcolumn):
		job_sheet_id = self.job_sheet_store[path][0]
		self.populate_job_sheet_line_item_treeview(job_sheet_id)

	def populate_job_sheet_line_item_treeview (self, job_sheet_id):
		self.job_sheet_line_item_store.clear()
		self.cursor.execute("SELECT jsli.id, qty, p.name, remark "
							"FROM job_sheet_line_items AS jsli "
							"JOIN products AS p ON p.id = "
							"jsli.product_id "
							"WHERE job_sheet_id = %s", (job_sheet_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_name = row[2]
			remark = row[3]
			self.job_sheet_line_item_store.append([row_id, qty, 
													product_name, 
													remark])
		
	def populate_customers (self):		
		self.cursor.execute("SELECT contacts.id, contacts.name, contacts.c_o "
							"FROM job_sheets "
							"JOIN contacts "
							"ON contacts.id = job_sheets.contact_id "
							"GROUP BY contacts.id "
							"ORDER BY contacts.name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			customer_name = row[1]
			customer_co = row[2]
			self.customer_store.append([str(customer_id), 
										customer_name, 
										customer_co])

	def view_button_toggled (self, widget):
		if widget.get_active() == False:
			widget.set_label("View all")
		else:
			widget.set_label("View selected")
		self.populate_job_sheet_treeview()

	def customer_match_func(self, completion, key, _iter):
		for text in key.split():
			if text not in self.customer_store[_iter][1].lower():
				return False
		return True







