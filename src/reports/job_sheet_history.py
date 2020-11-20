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
from constants import ui_directory, DB, is_admin

UI_FILE = ui_directory + "/reports/job_sheet_history.ui"

class JobSheetHistoryGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.customer_text = ''
		self.ext_name = ''
		self.job_text = ''
		self.description_text = ''
		
		self.job_sheet_store = self.get_object('job_store')
		self.job_sort_store = self.get_object('job_sort')
		self.job_sheet_line_item_store = self.get_object('job_line_item_store')
		self.job_filter = self.get_object('job_filter')
		self.job_filter.set_visible_func(self.filter_func)

		self.populate_job_sheet_treeview ()
		if is_admin == True:
			self.get_object ('treeview1').set_tooltip_column(0)
			self.get_object ('treeview2').set_tooltip_column(0)
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

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
		self.customer_text = self.get_object("searchentry1").get_text()
		self.ext_name = self.get_object("searchentry4").get_text()
		self.job_text = self.get_object("searchentry2").get_text()
		self.description_text = self.get_object("searchentry3").get_text()
		self.job_filter.refilter()

	def remark_edited(self, widget, path, text):
		_id_ = self.job_sheet_line_item_store[path][0]
		self.job_sheet_line_item_store[path][3] = text
		self.cursor.execute("UPDATE job_sheet_items "
							"SET remark = %s WHERE id = %s", (text, _id_))
		DB.commit()

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
		DB.rollback()

	def job_sheet_treeview_activate(self, treeview, path, treeviewcolumn):
		job_sheet_id = self.job_sort_store[path][0]
		self.populate_job_sheet_line_item_treeview(job_sheet_id)

	def populate_job_sheet_line_item_treeview (self, job_sheet_id):
		self.job_sheet_line_item_store.clear()
		self.cursor.execute("SELECT jsi.id, qty, qty::text, p.name, remark "
							"FROM job_sheet_items AS jsi "
							"JOIN products AS p ON p.id = "
							"jsi.product_id "
							"WHERE job_sheet_id = %s ORDER BY id",
							(job_sheet_id,))
		for row in self.cursor.fetchall():
			self.job_sheet_line_item_store.append(row)
		DB.rollback()

	def refresh_clicked (self, button):
		self.populate_job_sheet_treeview()





