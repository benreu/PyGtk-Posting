# manufacturing_history.py
#
# Copyright (C) 2018 - reuben
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/manufacturing_history.ui"

class ManufacturingHistoryGUI(Gtk.Builder):
	def __init__(self):
		
		self.product_text = ''
		self.name_text = ''
		
		Gtk.Builder.__init__ (self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.manufacturing_store = self.get_object('manufacturing_history_store')
		self.filtered_store = self.get_object('manufacturing_history_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_manufacturing_store()

	def destroy (self, widget):
		self.cursor.close()

	def manufacturing_history_row_activated (self, treeview, path, column):
		store = treeview.get_model()
		manufacturing_id = store[path][0]
		serial_number_store = self.get_object('serial_number_store')
		serial_number_store.clear()
		self.cursor.execute("SELECT sn.id, serial_number, COALESCE(c.name, '') "
							"FROM serial_numbers AS sn "
							"LEFT JOIN invoice_items AS ili "
							"ON ili.id = sn.invoice_item_id "
							"LEFT JOIN invoices AS i ON i.id = ili.invoice_id "
							"LEFT JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE manufacturing_id = %s", (manufacturing_id,))
		for row in self.cursor.fetchall():
			serial_number_store.append(row)
		DB.rollback()

	def populate_manufacturing_store (self):
		c = DB.cursor()
		c.execute("SELECT "
					"m.id, "
					"m.name, "
					"p.name, "
					"qty, "
					"date_trunc('second', SUM(stop_time-start_time))::text, "
					"date_trunc('second', SUM(stop_time-start_time)/qty)::text, "
					"COUNT(DISTINCT(employee_id)), "
					"active "
				"FROM manufacturing_projects AS m "
				"JOIN products AS p ON p.id = m.product_id "
				"JOIN time_clock_entries AS tce "
				"ON tce.project_id = m.time_clock_projects_id "
				"GROUP BY m.id, m.name, p.name, qty "
				"ORDER BY m.id")
		for row in c.fetchall():
			self.manufacturing_store.append(row)
		c.close()
		DB.rollback()

	def filter_changed (self, entry):
		entry = self.get_object('searchentry1')
		self.product_text = entry.get_text().lower()
		entry = self.get_object('searchentry2')
		self.name_text = entry.get_text().lower()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		if self.name_text not in model[tree_iter][1].lower():
			return False
		if self.product_text not in model[tree_iter][2].lower():
			return False
		return True

	def export_to_pdf_clicked (self, button):
		treeview = self.get_object('manufacturing_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def reports_clicked (self, button):
		from reports import manufacturing_reports
		manufacturing_reports.ManufacturingReportsGUI()




