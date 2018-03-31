# jobs_to_invoice.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
import os, sys
from datetime import datetime
import invoice_window
from pricing import get_customer_product_price

#Comment the first line and uncomment the second before installing
#or making the tarball (alternatively, use project variables)
UI_FILE = "src/jobs_to_invoice.ui"
#UI_FILE = "/usr/local/share/pygtk_accounting/ui/pygtk_accounting.ui"


class GUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.jobs_store = self.builder.get_object('jobs_to_invoice_store')
		self.customer_store = self.builder.get_object('customer_store')
		#self.populate_job_store ()
		self.populate_customer_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def post_jobs_to_invoice_clicked(self, widget = None):
		model, path = self.builder.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		job_sheet_id = model[path][0]
		customer_id = self.builder.get_object('combobox1').get_active_id()
		self.cursor.execute ("SELECT name FROM contacts WHERE id = %s", (customer_id,))
		customer_name = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT id FROM invoices WHERE (customer_id, posted) = (%s, False)", (customer_id,))
		for row in self.cursor.fetchall():
			invoice_id = row[0]
			self.builder.get_object('label2').set_label("There is an unposted invoice for %s.\n\
Do you want to append the Job Sheet items?" % customer_name) 
			invoice_exists_dialog = self.builder.get_object('dialog1')
			result = invoice_exists_dialog.run()
			if result == Gtk.ResponseType.ACCEPT:
				self.import_job_sheet_items_to_invoice(job_sheet_id, 
													invoice_id, customer_id)
			invoice_exists_dialog.hide()
			break
		else:
			invoice_id = invoice_window.create_new_invoice(self.cursor, datetime.today(), customer_id)
			self.import_job_sheet_items_to_invoice(job_sheet_id, invoice_id, 
													customer_id)

	def import_job_sheet_items_to_invoice(self, job_sheet_id, 
											invoice_id, customer_id):
		self.cursor.execute("SELECT qty, product_id, remark FROM job_sheet_line_items WHERE job_sheet_id = %s", (job_sheet_id,))
		for row in self.cursor.fetchall():
			qty = row[0]
			product_id = row[1]
			remark = row[2]
			price = get_customer_product_price (self.db, 
												customer_id, product_id)
			ext_price = float(qty) * price
			ext_price = round(ext_price, 2)
			self.cursor.execute("INSERT INTO invoice_items (invoice_id, qty, product_id, remark, price, tax, ext_price, canceled, imported) VALUES (%s, %s, %s, %s, %s, %s, %s, False, True)", (invoice_id, qty, product_id, remark, price, 0.00, ext_price))
		self.cursor.execute("UPDATE job_sheets SET invoiced = True WHERE id = %s", (job_sheet_id,))
		self.db.commit()
		self.populate_customer_store()

	def focus (self, widget, event):
		self.populate_customer_store()

	def edit_as_job_sheet_clicked (self, button):
		model, path = self.builder.get_object('treeview-selection1').get_selected_rows()
		job_sheet_id = model[path][0]
		self.cursor.execute ("UPDATE job_sheets SET completed = False WHERE id = %s", (job_sheet_id,))
		self.db.commit ()
		self.populate_customer_store ()

	def row_activate(self, treeview, path, treeviewcolumn):
		if self.jobs_store[path][0] != 0:
			self.builder.get_object("button1").set_sensitive(True)
			self.builder.get_object("button2").set_sensitive(True)
		else:
			self.builder.get_object("button2").set_sensitive(False)
			self.builder.get_object("button1").set_sensitive(False)

	def populate_customer_store (self):
		customer_combo = self.builder.get_object('combobox1')
		active = customer_combo.get_active()
		self.customer_store.clear()
		self.cursor.execute("SELECT contact_id FROM job_sheets WHERE (invoiced, completed) = (False, True) GROUP BY contact_id")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			self.cursor.execute("SELECT name FROM contacts WHERE id = %s", (contact_id,))
			contact_name = self.cursor.fetchone()[0]
			self.customer_store.append([str(contact_id), contact_name])
		customer_combo.set_active(active)

	def customer_combo_changed(self, combo):
		self.jobs_store.clear()
		customer_id = combo.get_active_id()
		self.cursor.execute("SELECT id, job_type_id, description FROM job_sheets WHERE (invoiced, completed, contact_id) = (False, True, %s)", (customer_id,))
		for row in self.cursor.fetchall():
			job_id = row[0]
			job_type_id = row[1]
			description = row[2]
			self.cursor.execute("SELECT name FROM job_types WHERE id = %s", (job_type_id,))
			job_name = self.cursor.fetchone()[0]
			job = self.jobs_store.append(None,[job_id, job_name, description, "", "", ""])
			self.cursor.execute("SELECT id, qty, product_id, remark FROM job_sheet_line_items WHERE job_sheet_id = %s", (job_id,))
			for row in self.cursor.fetchall():
				line_id = row[0]
				qty = row[1]
				product_id = row[2]
				remark = row[3]
				self.cursor.execute("SELECT name FROM products WHERE id = %s", (product_id,))
				product_name = self.cursor.fetchone()[0]
				self.jobs_store.append(job,[0, "", "", str(qty), product_name, remark])
	
		



		