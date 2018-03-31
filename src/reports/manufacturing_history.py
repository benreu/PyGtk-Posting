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

UI_FILE = "src/reports/manufacturing_history.ui"

class ManufacturingHistoryGUI:
	def __init__(self, main):

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		
		self.product_text = ''
		self.name_text = ''
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.manufacturing_store = self.builder.get_object('manufacturing_history_store')
		self.filtered_store = self.builder.get_object('manufacturing_history_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_manufacturing_store()

	def manufacturing_history_row_activated (self, treeview, path, column):
		store = treeview.get_model()
		manufacturing_id = store[path][0]
		serial_number_store = self.builder.get_object('serial_number_store')
		serial_number_store.clear()
		self.cursor.execute("SELECT sn.id, serial_number, COALESCE(c.name, '') "
							"FROM serial_numbers AS sn "
							"LEFT JOIN invoice_items AS ili "
							"ON ili.id = sn.invoice_line_item_id "
							"LEFT JOIN invoices AS i ON i.id = ili.invoice_id "
							"LEFT JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE manufacturing_id = %s", (manufacturing_id,))
		for row in self.cursor.fetchall():
			serial_id = row[0]
			serial_number = row[1]
			customer_name = row[2]
			serial_number_store.append([serial_id, serial_number, customer_name])

	def populate_manufacturing_store (self):
		self.cursor.execute("SELECT m.id, m.name, p.name, qty, "
								"ROUND( "
									"(SUM(stop_time::numeric) - "
									"SUM(start_time::numeric)) / 3600"
									", 2)::text, "
								"COUNT(DISTINCT(employee_id)) "
								"FROM manufacturing_projects AS m "
								"JOIN products AS p ON p.id = m.product_id "
								"JOIN time_clock_entries AS tce "
								"ON tce.project_id = m.time_clock_projects_id "
								"GROUP BY m.id, m.name, p.name, qty "
								"ORDER BY m.id")
		for row in self.cursor.fetchall():
			manufacturing_id = row[0]
			manufacturing_name = row[1]
			product_name = row[2]
			qty = row[3]
			time = row[4]
			employee_count = row[5]
			self.manufacturing_store.append([manufacturing_id, 
											manufacturing_name,
											product_name,
											qty,
											time,
											employee_count])

	def filter_changed (self, entry):
		entry = self.builder.get_object('searchentry1')
		self.product_text = entry.get_text().lower()
		entry = self.builder.get_object('searchentry2')
		self.name_text = entry.get_text().lower()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		if self.name_text not in model[tree_iter][1].lower():
			return False
		if self.product_text not in model[tree_iter][2].lower():
			return False
		return True



		