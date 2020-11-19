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

from gi.repository import Gtk, GLib
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

		c = DB.cursor()
		self.product_store = self.get_object('product_store')
		c.execute("SELECT id::text, name, ext_name "
					"FROM products WHERE deleted = False "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.product_store.append(row)
		c.close()
		DB.rollback()
		self.get_object('product_combo').set_active(0)

		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)

		window = self.get_object('window')
		window.show_all()

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id != None:
			self.product_id = product_id

	def product_match_selected (self, entrycompletion, treemodel, treeiter):
		self.get_object('product_combo').set_active_id(treemodel[treeiter][0])

	def product_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter][1].lower():
				return False
		return True

	def focus_in (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)

	def revenue_chart_clicked (self, button):
		date_field = self.get_object('invoice_group_by_combo').get_active_id()
		title = "Invoice amounts by %s" % date_field
		amounts = list()
		dates = list()
		c = DB.cursor()
		c.execute("WITH cte AS "
						"(SELECT SUM(amount_due) AS amount, "
							"date_trunc(%s, dated_for) AS date_group "
						"FROM invoices "
						"WHERE canceled = False AND dated_for IS NOT NULL "
						"GROUP BY date_group ORDER BY date_group) "
					"SELECT amount, date_group::date FROM cte", (date_field,))
		tupl = c.fetchall()
		c.close()
		DB.rollback()
		self.create_window_using_tuple (tupl, title)

	def products_sold_clicked (self, button):
		name = self.get_object('product_name_entry').get_text()
		date_field = self.get_object('product_group_by_combo').get_active_id()
		title = "'%s' qty by %s" % (name, date_field)
		c = DB.cursor()
		c.execute("WITH cte AS "
						"(SELECT SUM(qty) AS amount, "
							"date_trunc(%s, dated_for) AS date_group "
						"FROM invoice_items AS ii "
						"JOIN invoices AS i ON i.id = ii.invoice_id "
						"WHERE (ii.canceled, i.canceled) = (False, False) "
						"AND dated_for IS NOT NULL "
						"AND ii.product_id = %s "
						"GROUP BY date_group ORDER BY date_group) "
					"SELECT amount, date_group::date FROM cte", 
					(date_field, self.product_id))
		tupl = c.fetchall()
		c.close()
		DB.rollback()
		self.create_window_using_tuple (tupl, title)

	def products_purchased_clicked (self, button):
		name = self.get_object('product_name_entry').get_text()
		date_field = self.get_object('product_group_by_combo').get_active_id()
		title = "'%s' qty by %s" % (name, date_field)
		c = DB.cursor()
		c.execute("WITH cte AS "
						"(SELECT SUM(qty) AS amount, "
							"date_trunc(%s, date_created) AS date_group "
						"FROM purchase_order_items AS poli "
						"JOIN purchase_orders AS po "
							"ON po.id = poli.purchase_order_id "
						"WHERE (poli.canceled, po.canceled) = (False, False) "
						"AND poli.product_id = %s "
						"GROUP BY date_group ORDER BY date_group) "
					"SELECT amount, date_group::date FROM cte", 
					(date_field, self.product_id))
		tupl = c.fetchall()
		c.close()
		DB.rollback()
		self.create_window_using_tuple (tupl, title)

	def create_window_using_tuple (self, tupl, title):
		window = Gtk.Window()
		box = Gtk.VBox()
		window.add(box)
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure) 
		box.pack_start(canvas, True, True, 0)
		toolbar = NavigationToolbar(canvas, window)
		box.pack_start(toolbar, False, False, 0)
		subplot = figure.add_subplot(111)
		amounts = list()
		dates = list()
		for row in tupl:
			amounts.append(row[0])
			dates.append(row[1])
		subplot.bar(dates, amounts, width = 10)
		subplot.set_xticks(dates)
		subplot.set_xticklabels(dates)
		for index, data in enumerate(amounts):
			subplot.text(x=dates[index], y=data, s=f"{data}", ha='center')
		figure.autofmt_xdate()
		subplot.set_title(title)
		window.set_size_request(400, 300)
		window.set_title(title)
		window.set_icon_name('pygtk-posting')
		window.show_all()





