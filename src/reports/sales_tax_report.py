# sales_tax_report.py
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

from gi.repository import Gtk, GdkPixbuf, Gdk
from datetime import datetime, date, timedelta
from dateutils import DateTimeCalendar
import main

UI_FILE = main.ui_directory + "/reports/sales_tax_report.ui"

class SalesTaxReportGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = main.db
		self.cursor = self.db.cursor()
		self.tax_store = self.builder.get_object('tax_store')

		self.end_datetime = None

		start_entry = self.builder.get_object('entry1')
		end_entry = self.builder.get_object('entry2')

		self.start_calendar = DateTimeCalendar()
		self.start_calendar.set_relative_to(start_entry)
		self.end_calendar = DateTimeCalendar()
		self.end_calendar.set_relative_to(end_entry)

		self.start_calendar.connect('day-selected', self.start_date_selected)
		self.end_calendar.connect('day-selected', self.end_date_selected)

		self.start_calendar.set_date(datetime.today() - timedelta(days = 365))
		self.end_calendar.set_today ()

		tax_column = self.builder.get_object('treeviewcolumn2')
		tax_renderer = self.builder.get_object('cellrenderertext2')
		tax_column.set_cell_data_func(tax_renderer, self.tax_cell_func )

		total_column = self.builder.get_object('treeviewcolumn3')
		total_renderer = self.builder.get_object('cellrenderertext3')
		total_column.set_cell_data_func(total_renderer, self.total_cell_func )
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_tax_treeview(self):
		self.tax_store.clear()
		self.cursor.execute("SELECT SUM(i.ext_price), SUM(i.tax), "
							"tax_rates.name "
							"FROM invoice_items AS i "
							"JOIN tax_rates ON i.tax_rate_id = tax_rates.id "
							"JOIN invoices ON invoices.id = i.invoice_id "
							"WHERE (invoices.canceled, invoices.posted) "
							"= (False, True) "
							"AND date_created >= %s "
							"AND date_created <= %s "
							"GROUP BY tax_rates.name", 
							(self.start_datetime, self.end_datetime))
		for row in self.cursor.fetchall():
			sale_amount = row[0]
			tax_amount = row[1]
			tax_rate_name = row[2]
			self.tax_store.append([tax_rate_name, float(tax_amount), 
									float(sale_amount)])
		self.cursor.execute("SELECT "
								"COALESCE(SUM(i.ext_price), 0.00), "
								"COALESCE(SUM(i.tax), 0.00) "
							"FROM invoice_items AS i "
							"JOIN invoices ON invoices.id = i.invoice_id "
							"WHERE (invoices.canceled, invoices.posted) "
							"= (False, True) "
							"AND date_created >= %s "
							"AND date_created <= %s", 
							(self.start_datetime, self.end_datetime))
		for row in self.cursor.fetchall():
			sale_total = '${:,.2f}'.format(row[0])
			tax_total = '${:,.2f}'.format(row[1])
			self.builder.get_object('label4').set_label(tax_total)
			self.builder.get_object('label6').set_label(sale_total)
				
	def tax_cell_func(self, column, cellrenderer, model, iter1, data):
		tax = '${:,.2f}'.format(model.get_value(iter1, 1))
		cellrenderer.set_property("text" , tax)	

	def total_cell_func(self, column, cellrenderer, model, iter1, data):
		total = '${:,.2f}'.format(model.get_value(iter1, 2))
		cellrenderer.set_property("text" , total)

	def start_date_selected(self, calendar):
		self.start_datetime = calendar.get_datetime()
		day_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(day_text)
		if self.end_datetime != None: #end date not available before start date
			self.populate_tax_treeview ()

	def end_date_selected (self, calendar):
		self.end_datetime = calendar.get_datetime()
		day_text = calendar.get_text()
		self.builder.get_object('entry2').set_text(day_text)
		self.populate_tax_treeview ()

	def start_icon_clicked (self, entry, icon, event):
		self.start_calendar.show()

	def end_icon_clicked (self, entry, icon, event):
		self.end_calendar.show()







		
