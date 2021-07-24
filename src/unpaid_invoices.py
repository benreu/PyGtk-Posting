# Copyright (C) 2016 reuben 
# 
# unpaid_invoices is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# unpaid_invoices is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
from db import transactor
from dateutils import DateTimeCalendar
import subprocess, decimal

from constants import ui_directory, DB
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/unpaid_invoices.ui"

class GUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.store = self.get_object('unpaid_invoice_store')
		self.window = self.get_object('window')
		self.set_window_layout_from_settings()
		self.window.show_all()

		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect("day-selected", self.date_selected)

	def set_window_layout_from_settings(self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'sort_column'")
		sort_column = c.fetchone()[0]
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'sort_type'")
		sort_type = Gtk.SortType(c.fetchone()[0])
		store = self.get_object('unpaid_invoice_store')
		store.set_sort_column_id(sort_column, sort_type)
		c.execute("SELECT widget_id, value FROM unpaid_invoices WHERE "
					"widget_id IN ('number_column', "
									"'invoice_column', "
									"'customer_column', "
									"'date_column', "
									"'amount_column')")
		for row in c.fetchall():
			column = self.get_object(row[0])
			width = row[1]
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('window_height', ?)", (height,))
		tuple_ = self.get_object('unpaid_invoice_store').get_sort_column_id()
		sort_column = tuple_[0]
		if sort_column == None:
			sort_column = 0
			sort_type = 0
		else:
			sort_type = tuple_[1].numerator
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('sort_column', ?)", (sort_column,))
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('sort_type', ?)", (sort_type,))
		for column in ['number_column', 
						'invoice_column', 
						'customer_column', 
						'date_column', 
						'amount_column']:
			try:
				width = self.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def present (self):
		self.window.present()

	def window_delete_event (self, window, event):
		window.hide()
		return True
	
	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def contact_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][2]
		import contact_hub
		contact_hub.ContactHubGUI(customer_id)

	def invoice_chart_clicked (self, button):
		window = Gtk.Window()
		box = Gtk.VBox()
		window.add (box)
		from matplotlib.figure import Figure
		from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
		from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure)  # a Gtk.DrawingArea
		canvas.set_size_request(900, 600)
		box.pack_start(canvas, True, True, 0)
		toolbar = NavigationToolbar(canvas, window)
		box.pack_start(toolbar, False, False, 0)
		plot = figure.add_subplot(111)
		labels = list()
		fractions = list()
		unpaid = 0
		cursor = DB.cursor()
		cursor.execute("SELECT SUM(amount_due), c.name FROM invoices "
							"JOIN contacts AS c ON c.id = invoices.customer_id "
							"WHERE (canceled, paid, posted) = "
							"(False, False, True) GROUP BY customer_id, c.name "
							"ORDER BY c.name")
		for row in cursor.fetchall():
			customer_total = row[0]
			customer_name = row[1]
			fractions.append(customer_total)
			labels.append(customer_name)
			unpaid += 1
		if unpaid == 0:
			labels.append("None")
			fractions.append(1.00)
		cursor.close()
		plot.pie (fractions, labels=labels, autopct='%1.f%%', radius=0.9)
		window.set_title ('Unpaid invoices pie chart')
		window.set_icon_name ('pygtk-posting')
		window.show_all()
		DB.rollback()

	def unpaid_chart_window_delete_event (self, window, event):
		window.hide()
		return True

	def date_entry_icon_released (self, entry, icon, position):
		self.date_calendar.set_relative_to(entry)
		self.date_calendar.show_all()

	def date_selected (self, calendar):
		self.date = calendar.get_date()
		button = self.get_object('button6')
		button.set_sensitive(True)
		button.set_label("Yes, cancel invoice")
		entry = self.get_object('entry1')
		entry.set_text(calendar.get_text())
		
	def cancel_dialog (self, widget):		
		button = self.get_object('button6')
		button.set_sensitive(False)
		button.set_label("No date selected")
		cancel_dialog = self.get_object('dialog1')
		message = "Do you want to cancel %s ?\nThis is not reversible!" % self.invoice_name
		self.get_object('label1').set_label(message)
		response = cancel_dialog.run()
		cancel_dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			transactor.cancel_invoice(self.date, self.invoice_id)
			self.cursor.execute("UPDATE invoices SET canceled = True "
								"WHERE id = %s"
								"; "
								"UPDATE serial_numbers "
								"SET invoice_item_id = NULL "
								"WHERE invoice_item_id IN "
								"(SELECT id FROM invoice_items "
								"WHERE invoice_id = %s)", 
								(self.invoice_id, self.invoice_id))
			DB.commit()
			self.populate_unpaid_invoices ()
		
		
	def view_invoice(self, widget):
		treeselection = self.get_object('treeview-selection')
		model, path = treeselection.get_selected_rows ()
		if path != []:
			tree_iter = model.get_iter(path)
			invoice_id = model.get_value(tree_iter, 0)
			self.cursor.execute("SELECT name, pdf_data FROM invoices "
								"WHERE id = %s", (invoice_id ,))
			for cell in self.cursor.fetchall():
				file_name = cell[0] + ".pdf"
				file_data = cell[1]
				f = open("/tmp/" + file_name,'wb')
				f.write(file_data)		
				subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
				f.close()
			DB.rollback()

	def focus(self, window, event):
		self.populate_unpaid_invoices()

	def populate_unpaid_invoices(self):
		unpaid_invoice_amount = decimal.Decimal()
		treeview_selection = self.get_object('treeview-selection')
		model, path = treeview_selection.get_selected_rows()
		model.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"i.id, "
						"i.name, "
						"c.id, "
						"c.name, "
						"format_date(dated_for), "
						"dated_for::text, "
						"amount_due::text, "
						"amount_due::float "
					"FROM invoices AS i "
					"JOIN contacts AS c ON i.customer_id = c.id "
					"WHERE (canceled, paid, posted) = "
					"(False, False, True) "
					"ORDER BY i.id")
		tupl = c.fetchall()
		for row in tupl:
			model.append(row)
			unpaid_invoice_amount += decimal.Decimal(row[6])
		if path != [] and tupl != []:
			treeview_selection.select_path(path)
			self.get_object('treeview1').scroll_to_cell(path)
		c.execute("SELECT "
					"COALESCE(i.amount_due - (pi.amount + cm.amount), 0.00)::money "
					"FROM (SELECT SUM(amount_due) AS amount_due FROM invoices "
					"WHERE (posted, canceled, active) = (True, False, True)) i, "
					"(SELECT SUM(amount) AS amount FROM payments_incoming "
					"WHERE misc_income = False) pi, "
					"(SELECT SUM(amount_owed) AS amount FROM credit_memos "
					"WHERE posted = True) cm ")
		unpaid = c.fetchone()[0]
		self.get_object('AR_balance_label').set_label(unpaid)
		l = '${:,.2f}'.format(unpaid_invoice_amount)
		self.get_object('unpaid_invoices_label').set_label(l)
		c.close()
		DB.rollback()

	def row_activated(self, treeview, path, treeviewcolumn):
		treeiter = self.store.get_iter(path)
		self.invoice_id = self.store.get_value(treeiter, 0)
		self.invoice_name = self.store.get_value(treeiter, 1)
		self.contact_id = self.store.get_value(treeiter, 2)
		self.get_object('button1').set_sensitive(True)
		self.get_object('button2').set_sensitive(True)
		self.get_object('button4').set_sensitive(True)

	def payment_window (self, widget):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][2]
		import customer_payment
		customer_payment.GUI(customer_id)

	def new_statement (self, widget):
		new_statement.GUI()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

