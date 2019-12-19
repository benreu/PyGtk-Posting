# charts.py
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
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar
from constants import DB, ui_directory

UI_FILE = ui_directory + "/reports/charts.ui"

class ChartsGUI (Gtk.Builder):
	def __init__ (self):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		window = self.get_object('window')
		window.show_all()

	def revenue_chart_clicked (self, button):
		window = Gtk.Window()
		box = Gtk.VBox()
		window.add(box)
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure) 
		box.pack_start(canvas, True, True, 0)
		toolbar = NavigationToolbar(canvas, window)
		box.pack_start(toolbar, False, False, 0)
		date_field = self.get_object('invoice_group_by_combo').get_active_id()
		amount = list()
		month = list()
		c = DB.cursor()
		c.execute("WITH cte AS "
						"(SELECT SUM(amount_due) AS amount, "
							"date_trunc(%s, dated_for) AS date_group "
						"FROM invoices "
						"WHERE canceled = False AND dated_for IS NOT NULL "
						"GROUP BY date_group ORDER BY date_group) "
					"SELECT amount, date_group::date FROM cte", (date_field,))
		for row in c.fetchall():
			amount.append(row[0])
			month.append(row[1])
		c.close()
		subplot = figure.add_subplot(111)
		subplot.plot(month, amount)
		for tick in subplot.get_xticklabels():
			tick.set_rotation(45)
		figure.autofmt_xdate()
		window.set_size_request(400, 300)
		window.set_title('Invoice amount by %s' % date_field)
		window.set_icon_name('pygtk-posting')
		window.show_all()
		DB.rollback()





