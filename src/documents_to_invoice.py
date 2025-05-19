# documents_to_invoice.py
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


from gi.repository import Gtk
import psycopg2
import invoice_window
from datetime import datetime
from constants import ui_directory, DB

UI_FILE = ui_directory + "/documents_to_invoice.ui"

class DocumentsToInvoiceGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.cursor.execute("SELECT refresh_documents_price_on_import FROM settings")
		price_togglebutton = self.builder.get_object('togglebutton1')
		price_togglebutton.set_active(self.cursor.fetchone()[0])

		self.documents_store = self.builder.get_object('documents_to_invoice_store')
		self.populate_document_store ()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def focus(self, window, event):
		self.populate_document_store ()

	def populate_document_store(self):
		self.documents_store.clear()
		self.cursor.execute("SELECT "
								"d.id, "
								"contact_id, "
								"c.name, "
								"d.name, "
								"date_created::text, "
								"format_date(date_created) "
							"FROM documents AS d "
							"JOIN contacts AS c ON c.id = d.contact_id "
							"WHERE (canceled, invoiced, pending_invoice) = "
							"(False, False, True)")
		for row in self.cursor.fetchall():
			self.documents_store.append(row)
		DB.rollback()

	def import_to_invoice_clicked(self, button):
		model, path = self.builder.get_object('treeview-selection1').get_selected_rows()
		document_id = model[path][0]
		customer_id = model[path][1]
		customer_name = model[path][2]
		self.cursor.execute("SELECT id FROM invoices WHERE (customer_id, posted) = (%s, False)", (customer_id,))
		for row in self.cursor.fetchall():
			invoice_id = row[0]
			self.builder.get_object('label1').set_label("There is an unposted invoice for %s.\n\
Do you want to append the document items?" % customer_name) 
			invoice_exists_dialog = self.builder.get_object('dialog1')
			result = invoice_exists_dialog.run()
			if result == Gtk.ResponseType.ACCEPT:
				self.import_document_items_to_invoice(document_id, invoice_id)
			invoice_exists_dialog.hide()
			break
		else:
			invoice_id = invoice_window.create_new_invoice(datetime.today(), customer_id)
			self.import_document_items_to_invoice(document_id, invoice_id)

	def import_document_items_to_invoice(self, document_id, invoice_id):
		self.cursor.execute("SELECT document_type_id "
							"FROM documents WHERE id = %s",(document_id,))
		self.cursor.execute("SELECT qty, product_id, remark, price FROM document_items WHERE document_id = %s", (document_id,))
		for row in self.cursor.fetchall():
			qty = row[0]
			product_id = row[1]
			remark = row[2]
			price = row[3]
			ext_price = qty * price
			ext_price = round(ext_price, 2)
			self.cursor.execute("INSERT INTO invoice_items (invoice_id, qty, product_id, remark, price, tax, ext_price, canceled, imported) VALUES (%s, %s, %s, %s, %s, %s, %s, False, True)", (invoice_id, qty, product_id, remark, price, 0.00, ext_price))
		self.cursor.execute("UPDATE documents SET invoiced = True WHERE id = %s", (document_id,))
		DB.commit()
		self.populate_document_store()

	def price_togglebutton_toggled (self, togglebutton):
		toggle_state = togglebutton.get_active()
		if toggle_state is True:
			togglebutton.set_label("Refresh prices")
		else:
			togglebutton.set_label("Use document prices")
		self.cursor.execute("UPDATE settings SET refresh_documents_price_on_import = %s", (toggle_state,))
		DB.commit()



