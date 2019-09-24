# manufacturing_reports.py
#
# Copyright (C) 2019 - reuben
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
import numpy as np
import constants

UI_FILE = constants.ui_directory + "/reports/manufacturing_reports.ui"

class ManufacturingReportsGUI (Gtk.Builder):
	figure = None
	def __init__ (self):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		store = self.get_object('price_level_store')
		c = constants.db.cursor()
		c.execute("SELECT id::text, name "
					"FROM customer_markup_percent ORDER BY name")
		for row in c .fetchall():
			store.append(row)
		price_level_id = self.get_object('price_level_combo').set_active(0)
		c.close()
		window = self.get_object('window')
		window.show_all()

	def profit_to_time_chart_clicked (self, button):
		window = Gtk.Window()
		scrolled_window = Gtk.ScrolledWindow()
		window.add(scrolled_window)
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure) 
		scrolled_window.add(canvas)
		figure.subplots_adjust(left=0.3, right=0.99, top=0.9, bottom=0.1)
		c = constants.db.cursor()
		product_name = list()
		time = list()
		profit = list()
		order_by = self.get_object('sort_by_combo').get_active_id()
		price_level_id = self.get_object('price_level_combo').get_active_id()
		price_level_text = self.get_object('price_level_entry').get_text()
		c.execute("SELECT p.name, "
						"ROUND((EXTRACT(EPOCH FROM(tm.time/mp.qty))/60)::numeric, 2) AS minutes, "
						"(pmp.price - p.cost) AS profit "
					"FROM products AS p "
					"JOIN "
					"(SELECT m.product_id, SUM(m.qty) AS qty "
						"FROM manufacturing_projects AS m "
						"GROUP BY m.product_id) mp ON mp.product_id = p.id "
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
					"WHERE p.manufactured = true "
					"GROUP BY p.id, mp.qty, tm.time, profit "
					"ORDER BY %s" % (price_level_id, order_by))
		for row in c.fetchall():
			product_name.append (row[0])
			time.append (row[1])
			profit.append (row[2])
		c.close()
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
		title = 'Assembly time vs. profit (price level %s, order by %s)' % \
												(price_level_text, order_by)
		window.set_title(title)
		window.set_icon_name('pygtk-posting')
		window.show_all()
		


