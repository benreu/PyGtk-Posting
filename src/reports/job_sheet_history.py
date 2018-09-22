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
import main

UI_FILE = main.ui_directory + "/reports/job_sheet_history.ui"

class JobSheetHistoryGUI:
	def __init__(self, db):

		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()
		self.customer_text = ''
		self.ext_name = ''
		self.job_text = ''
		self.description_text = ''
		
		self.job_sheet_store = self.builder.get_object('job_store')
		self.job_sort_store = self.builder.get_object('job_sort')
		self.job_sheet_line_item_store = self.builder.get_object('job_line_item_store')
		self.job_filter = self.builder.get_object('job_filter')
		self.job_filter.set_visible_func(self.filter_func)

		qty_column = self.builder.get_object ('treeviewcolumn5')
		qty_renderer = self.builder.get_object ('cellrenderertext5')
		qty_column.set_cell_data_func(qty_renderer, self.qty_cell_func)

		self.populate_job_sheet_treeview ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def qty_cell_func(self, column, cellrenderer, model, iter1, data):
		qty = model.get_value(iter1, 1)
		cellrenderer.set_property("text" , '{:,.1f}'.format(qty))

	def filter_func(self, model, tree_iter, r):
		for text in self.customer_text.split():
			if text not in model[tree_iter][1].lower():
				return False
		for text in self.ext_name.split():
			if text not in model[tree_iter][2].lower():
				return False
		for text in self.job_text.split():
			if text not in model[tree_iter][5].lower():
				return False
		for text in self.description_text.split():
			if text not in model[tree_iter][6].lower():
				return False
		return True

	def search_changed (self, entry):
		"activated by any of the search entries changing"
		self.customer_text = self.builder.get_object("searchentry1").get_text()
		self.ext_name = self.builder.get_object("searchentry4").get_text()
		self.job_text = self.builder.get_object("searchentry2").get_text()
		self.description_text = self.builder.get_object("searchentry3").get_text()
		self.job_filter.refilter()

	def remark_edited(self, widget, path, text):
		_id_ = self.job_sheet_line_item_store[path][0]
		self.job_sheet_line_item_store[path][3] = text
		self.cursor.execute("UPDATE job_sheet_line_items "
							"SET remark = %s WHERE id = %s", (text, _id_))
		self.db.commit()

	def focus (self, window, event):
		return
		tree_selection = self.builder.get_object('treeview-selection1')
		model, path = tree_selection.get_selected_rows()
		self.populate_job_sheet_treeview()
		if path == []:
			return
		self.builder.get_object('treeview1').scroll_to_cell(path)
		tree_selection.select_path(path)
		job_sheet_id = model[path][0]
		self.populate_job_sheet_line_item_treeview(job_sheet_id)

	def populate_job_sheet_treeview (self):
		self.job_sheet_store.clear()
		self.job_sheet_line_item_store.clear()
		self.cursor.execute("SELECT "
								"js.id, "
								"c.name, "
								"c.ext_name, "
								"date_inserted::text, "
								"format_date(date_inserted), "
								"jt.name, "
								"description "
							"FROM job_sheets AS js "
							"JOIN contacts AS c ON c.id = contact_id "
							"JOIN job_types AS jt ON jt.id = job_type_id")
		for row in self.cursor.fetchall():
			self.job_sheet_store.append(row)
			while Gtk.events_pending():
				Gtk.main_iteration()

	def job_sheet_treeview_activate(self, treeview, path, treeviewcolumn):
		job_sheet_id = self.job_sort_store[path][0]
		self.populate_job_sheet_line_item_treeview(job_sheet_id)

	def populate_job_sheet_line_item_treeview (self, job_sheet_id):
		self.job_sheet_line_item_store.clear()
		self.cursor.execute("SELECT jsli.id, qty, p.name, remark "
							"FROM job_sheet_line_items AS jsli "
							"JOIN products AS p ON p.id = "
							"jsli.product_id "
							"WHERE job_sheet_id = %s ORDER BY id",
							(job_sheet_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_name = row[2]
			remark = row[3]
			self.job_sheet_line_item_store.append([row_id, qty, 
													product_name, 
													remark])







