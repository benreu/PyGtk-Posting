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
from datetime import datetime
from decimal import Decimal
from db import transactor
from dateutils import datetime_to_text
import subprocess

UI_FILE = "src/unpaid_invoices.ui"
Figure = None

class GUI:
	def __init__(self, main):
		Figure = None

		self.parent = main
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
		self.db = main.db
		self.cursor = self.db.cursor()

		self.store = self.builder.get_object('unpaid_invoice_store')
		self.window = self.builder.get_object('window')
		self.window.show_all()
		main.unpaid_invoices_window = self.window
		
		self.cursor.execute("SELECT accrual_based FROM settings")
		if self.cursor.fetchone()[0] == False:
			self.builder.get_object('button2').set_visible(False)
			self.builder.get_object('button3').set_visible(True)
		else:
			self.builder.get_object('button3').set_visible(False)
			self.builder.get_object('button2').set_visible(True)
		
		amount_column = self.builder.get_object ('treeviewcolumn3')
		amount_renderer = self.builder.get_object ('cellrenderertext3')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)
		
		self.cursor.execute("SELECT accrual_based FROM settings")
		if self.cursor.fetchone()[0] == True:
			self.builder.get_object('button3').set_visible(False)

	def present (self):
		self.window.present()

	def amount_cell_func(self, column, cellrenderer, model, iter1, data):
		amount = model.get_value(iter1, 6)
		cellrenderer.set_property("text" , str(amount))

	def destroy(self, window):
		self.parent.unpaid_invoices_window = None
		self.cursor.close()

	def invoice_chart_clicked (self, button):
		global Figure
		if Figure == None:
			from matplotlib.figure import Figure
			from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
			from matplotlib.pyplot import pie
			self.figure = Figure(figsize=(4, 4), dpi=100)
			canvas = FigureCanvas(self.figure)  # a Gtk.DrawingArea
			canvas.set_size_request(800, 500)
			overlay = self.builder.get_object('overlay1')
			overlay.add (canvas)
		a = self.figure.add_subplot(111)
		labels = list()
		fractions = list()
		unpaid = 0
		self.cursor.execute("SELECT SUM(amount_due), c.name FROM invoices "
							"JOIN contacts AS c ON c.id = invoices.customer_id "
							"WHERE (canceled, paid, posted) = "
							"(False, False, True) GROUP BY customer_id, c.name "
							"ORDER BY SUM(amount_due)")
		for row in self.cursor.fetchall():
			customer_total = row[0]
			customer_name = row[1]
			fractions.append(customer_total)
			labels.append(customer_name)
			unpaid += 1
		if unpaid == 0:
			labels.append("None")
			fractions.append(1.00)
		a.pie(fractions, labels=labels, autopct='%1.f%%', radius=0.7)
		window = self.builder.get_object('window1')
		window.show_all()

	def unpaid_chart_window_delete_event (self, window, event):
		window.hide()
		return True

	def cancel_dialog (self, widget):
		cancel_dialog = self.builder.get_object('dialog1')
		message = "Do you want to cancel %s ?\nThis is not reversible!" % self.invoice_name
		self.builder.get_object('label1').set_label(message)
		response = cancel_dialog.run()
		cancel_dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			print ("cancel invoice is disabled until further work is done on accounts")
			return
			self.cursor.execute("UPDATE invoices SET canceled = True "
								"WHERE id = %s RETURNING total, tax", 
								[self.invoice_id])
			transactor.cancel_invoice(self.db, datetime.today(), self.invoice_id)
			self.db.commit()
			self.treeview_populate ()
		
	def view_invoice(self, widget):
		treeselection = self.builder.get_object('treeview-selection')
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

	def focus(self, d , f):
		self.treeview_populate()

	def edit_invoice(self, widget):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		invoice_id = model[path][0]
		contact_id = model[path][2]
		import invoice_window
		invoice_window.InvoiceGUI(self.parent, invoice_id, contact_id)

	def treeview_populate(self):
		treeview_selection = self.builder.get_object('treeview-selection')
		model, path = treeview_selection.get_selected_rows()
		model.clear()
		total = Decimal()
		self.cursor.execute("SELECT i.id, i.name, amount_due, c.name, c.id, "
							"dated_for FROM invoices AS i "
							"JOIN contacts AS c ON i.customer_id = c.id "
							"WHERE (canceled, paid, posted) = "
							"(False, False, True) "
							"ORDER BY i.id")
		tupl = self.cursor.fetchall()
		for row in tupl:
			invoice_id = row[0]
			invoice_name = row[1]
			invoice = row[2]
			total += invoice
			customer_name = row[3]
			customer_id = row[4]
			date = row[5]
			date_formatted = datetime_to_text(date)
			model.append([invoice_id, invoice_name, customer_id, 
								customer_name, str(date), date_formatted, 
								invoice ])
		if path != [] and tupl != []:
			treeview_selection.select_path(path)
			self.builder.get_object('treeview1').scroll_to_cell(path)
		self.builder.get_object('label3').set_label('Total: ${:,.2f}'.format (total))

	def row_activated(self, treeview, path, treeviewcolumn):
		treeiter = self.store.get_iter(path)
		self.invoice_id = self.store.get_value(treeiter, 0)
		self.invoice_name = self.store.get_value(treeiter, 1)
		self.contact_id = self.store.get_value(treeiter, 2)
		self.builder.get_object('button1').set_sensitive(True)
		self.builder.get_object('button2').set_sensitive(True)
		self.builder.get_object('button3').set_sensitive(True)
		self.builder.get_object('button4').set_sensitive(True)

	def payment_window (self, widget):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][2]
		import customer_payment
		customer_payment.GUI(self.db, customer_id)

	def new_statement (self, widget):
		new_statement.GUI(self.db)

