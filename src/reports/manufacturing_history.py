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
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar
import numpy as np
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
		self.manufacturing_store = self.get_object('manufacturing_jobs_store')
		self.filtered_store = self.get_object('manufacturing_jobs_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_jobs_store()
		self.populate_summary_store()
		store = self.get_object('price_level_store')
		c = DB.cursor()
		c.execute("SELECT id::text, name "
					"FROM customer_markup_percent ORDER BY name")
		for row in c .fetchall():
			store.append(row)
		c.close()
		DB.rollback()

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

	def refresh_jobs_clicked (self, button):
		self.populate_jobs_store()
		DB.rollback()

	def populate_jobs_store (self):
		c = DB.cursor()
		c.execute("SELECT "
					"m.id, "
					"m.name, "
					"p.name, "
					"qty, "
					"date_trunc('second', SUM(stop_time-start_time))::text, "
					"date_trunc('second', SUM(stop_time-start_time)/qty)::text, "
					"COUNT(DISTINCT(employee_id)), "
					"active, "
					"format_date(date_created), "
					"date_created::text "
				"FROM manufacturing_projects AS m "
				"JOIN products AS p ON p.id = m.product_id "
				"JOIN time_clock_entries AS tce "
				"ON tce.project_id = m.time_clock_projects_id "
				"GROUP BY m.id, m.name, p.name, qty "
				"ORDER BY m.id")
		for row in c.fetchall():
			self.manufacturing_store.append(row)
		c.close()

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

	def jobs_export_hub_clicked (self, button):
		treeview = self.get_object('manufacturing_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def refresh_summary_clicked (self, button):
		self.populate_summary_store()
		DB.rollback()

	def populate_summary_store (self):
		summary_store = self.get_object('summary_store')
		summary_store.clear()
		c = DB.cursor()
		c.execute(
		"SELECT p.id, "
			"p.name, "
			"p.ext_name, "
			"qty.total::int, "
			"date_trunc('second', time.total)::text, "
			"EXTRACT('EPOCH' FROM time.total)::int AS total_sort, "
			"date_trunc('second', time.total / qty.total)::text "
				"AS avg_time_per_piece, "
			"EXTRACT('EPOCH' FROM time.total / qty.total)::int AS avg_sort, "
			"date_trunc('second', minimum.piece_time)::text "
				"AS min_time_per_piece, "
			"EXTRACT('EPOCH' FROM minimum.piece_time)::int AS min_sort, "
			"date_trunc('second', maximum.piece_time)::text "
				"AS max_time_per_piece, "
			"EXTRACT('EPOCH' FROM maximum.piece_time)::int as max_sort "
			"FROM manufacturing_projects AS mp "
			"JOIN products AS p ON mp.product_id = p.id, "
			"LATERAL "
				"(SELECT SUM (tce.stop_time - tce.start_time) AS total "
				"FROM time_clock_entries AS tce "
				"WHERE tce.project_id IN "
					"(SELECT time_clock_projects_id "
					"FROM manufacturing_projects "
					"WHERE product_id = p.id) "
				") AS time,"
			"LATERAL "
				"(SELECT SUM(qty) AS total FROM manufacturing_projects "
				"WHERE product_id = p.id) AS qty, "
			"LATERAL "
				"(SELECT DISTINCT ON (product_id) "
					"(SUM(tce.stop_time - tce.start_time) / qty) "
					"AS piece_time FROM manufacturing_projects AS mp "
				"JOIN time_clock_entries AS tce "
					"ON tce.project_id = mp.time_clock_projects_id "
				"WHERE mp.product_id = p.id "
				"GROUP BY mp.id, qty, mp.product_id "
				"ORDER BY product_id, piece_time ASC, mp.id "
				") AS minimum, "
			"LATERAL "
				"(SELECT DISTINCT ON (product_id) "
					"(SUM(tce.stop_time - tce.start_time) / qty) AS piece_time "
					"FROM manufacturing_projects AS mp "
				"JOIN time_clock_entries AS tce "
					"ON tce.project_id = mp.time_clock_projects_id "
				"WHERE mp.product_id = p.id "
				"GROUP BY mp.id "
				"ORDER BY product_id, piece_time DESC, mp.id "
				") AS maximum "
			" WHERE active = False "
			"GROUP BY p.id, time.total, qty.total, "
				"minimum.piece_time, maximum.piece_time "
			"ORDER BY p.name, p.ext_name")
		for row in c.fetchall():
			summary_store.append(row)
		c.close()

	def summary_export_hub_clicked (self, button):
		treeview = self.get_object('summary_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def price_level_combo_changed (self, combo):
		price_level_id = combo.get_active_id()
		if price_level_id == None:
			return
		store = self.get_object('time_vs_profit_store')
		store.clear()
		c = DB.cursor()
		c.execute(
		"SELECT p.id, "
				"p.name, "
				"ROUND((EXTRACT(EPOCH FROM(tm.time/mp.qty))/60)::numeric, 2)::text AS minutes, "
				"(EXTRACT(EPOCH FROM(tm.time/mp.qty))/60)::int AS minutes_sort, "
				"(pmp.price - p.cost)::text AS profit, "
				"(pmp.price - p.cost)::float AS profit_sort "
			"FROM products AS p "
			"JOIN "
			"(SELECT m.product_id, SUM(m.qty) AS qty, active "
				"FROM manufacturing_projects AS m "
				"GROUP BY m.product_id, m.active) "
				"mp ON mp.product_id = p.id "
			"JOIN "
			"(SELECT mp.product_id, SUM(stop_time-start_time) AS time "
				"FROM time_clock_entries AS tce "
				"JOIN manufacturing_projects AS mp "
					"ON mp.time_clock_projects_id = tce.project_id "
				"GROUP BY mp.product_id ) tm ON tm.product_id = p.id "
			"JOIN products_markup_prices AS pmp "
				"ON pmp.product_id = p.id "
			"JOIN customer_markup_percent AS cmp "
				"ON cmp.id = pmp.markup_id AND cmp.id = %s "
			"WHERE p.manufactured = true AND mp.active = False "
			"GROUP BY p.id, mp.qty, tm.time, profit, "
			"pmp.price "
			"ORDER BY name" % (price_level_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()
		DB.rollback()
		self.get_object('time_vs_profit_button').set_sensitive(True)

	def time_vs_profit_chart_clicked (self, button):
		window = Gtk.Window()
		box = Gtk.VBox()
		window.add(box)
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure) 
		box.pack_start(canvas, True, True, 0)
		toolbar = NavigationToolbar(canvas, window)
		box.pack_start(toolbar, False, False, 0)
		figure.subplots_adjust(left=0.3, right=0.99, top=0.9, bottom=0.1)
		product_name = list()
		time = list()
		profit = list()
		price_level_text = self.get_object('price_level_entry').get_text()
		for row in reversed(self.get_object('time_vs_profit_store')):
			product_name.append (row[1])
			time.append (row[3])
			profit.append (row[5])
		width = 0.35
		y_pos = np.arange(len(time))
		time_plot = figure.add_subplot(111)
		time_plot.barh(y_pos - (width/2), time, width)
		time_plot.set_yticklabels(product_name)
		time_plot.set_yticks(y_pos)
		time_plot.set_xlabel('Assembly time (minutes)', color='b')
		for tl in time_plot.get_xticklabels():
			tl.set_color('b')
		profit_plot = time_plot.twiny()
		profit_plot.barh(y_pos + (width/2), profit, width, color='y')
		profit_plot.set_xlabel('Profit ($)', color='y')
		for tl in profit_plot.get_xticklabels():
			tl.set_color('y')
		window.set_size_request(400, 300)
		order_by = 'Name ASCENDING'
		sort_col = self.get_object('time_vs_profit_store').get_sort_column_id()
		for column in self.get_object('time_vs_profit_treeview').get_columns():
			if column.get_sort_column_id() == sort_col[0]:
				order_by = column.get_title()
				if column.get_sort_order() == Gtk.SortType.ASCENDING:
					order_by += ' ASCENDING'
				else:
					order_by += ' DESCENDING'
		title = 'Assembly time vs. profit (price level %s, order by %s)' % \
												(price_level_text, order_by)
		window.set_title(title)
		window.set_icon_name('pygtk-posting')
		window.show_all()



