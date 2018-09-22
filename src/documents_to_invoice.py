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
import invoice_window
from datetime import datetime
import main

UI_FILE = main.ui_directory + "/documents_to_invoice.ui"

class DocumentsToInvoiceGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.documents_store = self.builder.get_object('documents_to_invoice_store')
		self.populate_document_store ()

		self.cursor.execute("SELECT refresh_documents_price_on_import FROM settings")
		price_togglebutton = self.builder.get_object('togglebutton1')
		price_togglebutton.set_active(self.cursor.fetchone()[0])
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

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
			invoice_id = invoice_window.create_new_invoice(self.cursor, datetime.today(), customer_id)
			self.import_document_items_to_invoice(document_id, invoice_id)

	def import_document_items_to_invoice(self, document_id, invoice_id):
		self.cursor.execute("SELECT document_type_id FROM documents WHERE id = %s",(document_id,))
		if self.cursor.fetchone()[0] == 1 :#scale document import
			freeze_wt = 0
			self.cursor.execute("SELECT id,  product_id, remark, retailer_id,type_1 FROM document_lines WHERE document_id = %s", (document_id,))
			for row in self.cursor.fetchall():
				doc_line_id = row[0]
				product_id = row[1]
				remark = row[2]
				retailer_id = row[3]
				freeze = row[4]
				tabs = self.create_remark(doc_line_id,product_id,retailer_id)
				if tabs[0] == 0:
					pass 
					
				else:
					remark = remark + tabs[1]
					qty = tabs[2]
					weight = tabs[3]
					if freeze == True:
						freeze_wt = freeze_wt + weight
					self.cursor.execute("INSERT INTO invoice_items \
					(invoice_id, qty, product_id, remark,\
					canceled, imported) VALUES (%s, %s, %s, %s, \
					False, True)", (invoice_id, qty, product_id, remark))
			if freeze_wt > 0 :
				qty = freeze_wt
				self.cursor.execute("INSERT INTO invoice_items \
					(invoice_id, qty, product_id, remark,\
					canceled, imported) VALUES (%s, %s, %s, %s, \
					False, True)", (invoice_id, qty, 25, remark))
		else:#it is not a scale document therefore we do this
			#Reuben's original code block
			
			self.cursor.execute("SELECT qty, product_id, remark, price FROM document_lines WHERE document_id = %s", (document_id,))
			for row in self.cursor.fetchall():
				qty = row[0]
				product_id = row[1]
				remark = row[2]
				price = row[3]
				ext_price = qty * price
				ext_price = round(ext_price, 2)
				self.cursor.execute("INSERT INTO invoice_items (invoice_id, qty, product_id, remark, price, tax, ext_price, canceled, imported) VALUES (%s, %s, %s, %s, %s, %s, %s, False, True)", (invoice_id, qty, product_id, remark, price, 0.00, ext_price))
		self.cursor.execute("UPDATE documents SET invoiced = True WHERE id = %s", (document_id,))
		self.db.commit()
		self.populate_document_store()

	def price_togglebutton_toggled (self, togglebutton):
		toggle_state = togglebutton.get_active()
		if toggle_state is True:
			togglebutton.set_label("Refresh prices")
		else:
			togglebutton.set_label("Use document prices")
		self.cursor.execute("UPDATE settings SET refresh_documents_price_on_import = %s", (toggle_state,))
		self.db.commit()

	def create_remark(self,doc_line_id,product_id,retailer_id):
		self.cursor.execute("SELECT SUM(weight),COUNT(weight),MAX(weight),MIN(weight),ROUND(AVG(weight),2) FROM scale_label_line_items_archive WHERE document_line_item_id = %s AND deleted = False ",(doc_line_id,))
		#print self.cursor.fetchall()
		for line in self.cursor.fetchall():
			#print line
			weight = line[0]
			count = line[1]
			
			if count == 0: #if is 0 no need in wasting time doing other queries
				return count,
				
			maximum = line[2]
			minimum = line[3]
			average = line[4]
			self.cursor.execute("SELECT unit FROM products WHERE id = %s",(product_id,))
			unit = self.cursor.fetchone()[0]
			if unit == str(1):
				qty = round(count,1)
			else:
				qty = round(weight,1)
			self.cursor.execute("SELECT name FROM contacts WHERE id = %s",(retailer_id,))
			retailer = self.cursor.fetchone()[0]
			scale_remark = str(weight) +' Lb ' + str(count) + ' Pack labeled for ' + retailer + ' Max wt ' \
						+ str(maximum) + ' & Min of ' + str(minimum) + ' for ave size of ' + str(average) +' lb'
		return count,scale_remark,qty,weight


		
