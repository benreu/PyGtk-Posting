# payment_receipt.py
#
# Copyright (C) 2017 - reuben
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
import subprocess, psycopg2
import printing
import main

UI_FILE = main.ui_directory + "/payment_receipt.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class PaymentReceiptGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor ()

		self.customer_store = self.builder.get_object('customer_store')
		self.payment_store = self.builder.get_object('payment_store')

		self.populate_customer_store ()
		completion = self.builder.get_object('customer_completion')
		completion.set_match_func(self.customer_match_func)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def populate_customer_store (self):
		self.customer_store.clear()
		self.cursor.execute ("SELECT contacts.id, contacts.name, ext_name "
							"FROM payments_incoming "
							"JOIN contacts "
							"ON contacts.id = payments_incoming.customer_id "
							"GROUP BY contacts.id, contacts.name, ext_name "
							"ORDER BY contacts.name, contacts.ext_name")
		for row in self.cursor.fetchall():
			c_id = row[0]
			c_name = row[1]
			c_co = row[2]
			self.customer_store.append([str(c_id), c_name, c_co])

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id()
		if customer_id != None:
			self.builder.get_object('checkbutton1').set_active(False)
			self.populate_payment_store ()

	def payment_type_edited (self, renderer, path, text):
		self.payment_store[path][7] = text

	def customer_match_selected (self, completion, model, iter_):
		customer_id = model[iter_][0]
		self.builder.get_object('combobox1').set_active_id(customer_id)

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False# no match
		return True# it's a hit!

	def view_all_toggled (self, togglebutton):
		self.populate_payment_store()

	def populate_payment_store (self):
		self.payment_store.clear()
		customer_id = self.builder.get_object('combobox1').get_active_id()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
									"p.id, "
									"date_inserted::text, "
									"format_date(date_inserted), "
									"c.id, "
									"c.name, "
									"amount, "
									"payment_info(p.id), "
									"COALESCE(invoices.id, 0), "
									"COALESCE(invoices.name, '') "
								"FROM payments_incoming AS p "
								"JOIN contacts AS c ON c.id = p.customer_id "
								"LEFT JOIN invoices ON invoices.payments_incoming_id = p.id "
								"ORDER BY c.name")
		else:
			self.cursor.execute("SELECT "
									"p.id, "
									"date_inserted::text, "
									"format_date(date_inserted), "
									"c.id, "
									"c.name, "
									"amount, "
									"payment_info(p.id), "
									"COALESCE(invoices.id, 0), "
									"COALESCE(invoices.name, '') "
								"FROM payments_incoming AS p "
								"JOIN contacts AS c ON c.id = p.customer_id "
								"LEFT JOIN invoices ON invoices.payments_incoming_id = p.id "
								"WHERE c.id = %s ORDER BY c.name", 
								(customer_id,))
		for row in self.cursor.fetchall():
			self.payment_store.append(row)

	def view_payment_receipt_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("SELECT payment_receipt_pdf FROM payments_incoming "
							"WHERE id = %s", (row_id,))
		for row in self.cursor.fetchall():
			file_name = "/tmp/Payment_receipt.pdf"
			file_data = row[0]
			if file_data == None:
				return
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.call("xdg-open %s" % file_name, shell = True)
			f.close()

	def generate_payment_receipt (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		line = model[path]
		self.create_payment_receipt (line)
		subprocess.Popen ("soffice " + self.receipt_file, shell = True)
		

	def post_payment_receipt_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		line = model[path]
		self.create_payment_receipt(line)
		subprocess.call("odt2pdf /tmp/" + self.document_odt, shell = True)
		document = "/tmp/" + self.document_pdf
		f = open(document,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		f.close()
		self.cursor.execute("UPDATE payments_incoming "
							"SET payment_receipt_pdf = %s WHERE id = %s", 
							(binary, self.payment_id))
		self.db.commit()
		p = printing.PrintDialog("/tmp/" + self.document_pdf)
		p.run_print_dialog(self.window)

	def create_payment_receipt(self, line):
		self.payment_id = line[0]
		payment = Item()
		payment.date = line[2]
		payment.amount = '${:,.2f}'.format(line[5])
		payment.text = line[6]
		payment.type = line[7]
		payment.invoice_number = line[8]
		payment.invoice_name = line[9]
		contact_id = line[3]
		self.cursor.execute("SELECT * FROM contacts "
							"WHERE id = (%s)", [contact_id])
		customer = Item()
		for row in self.cursor.fetchall():
			self.customer_id = row[0]
			customer.name = row[1]
			name = row[1]
			customer.ext_name = row[2]
			customer.street = row[3]
			customer.city = row[4]
			customer.state = row[5]
			customer.zip = row[6]
			customer.fax = row[7]
			customer.phone = row[8]
			customer.email = row[9]
			customer.label = row[10]
			customer.tax_exempt = row[11]
			customer.tax_exempt_number = row[12]
		company = Item()
		self.cursor.execute("SELECT * FROM company_info")
		for row in self.cursor.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
			company.tax_number = row[11]

		document_name = "payment_receipt"
		self.document_name = document_name
		self.document_odt = document_name + ".odt"
		self.document_pdf = document_name + ".pdf"
		data = dict(payment = payment, contact = customer, company = company)
		from py3o.template import Template 
		self.receipt_file = "/tmp/" + self.document_odt
		t = Template("./templates/payment_receipt_template.odt", self.receipt_file , True)
		t.render(data) #the data holds all the info of the invoice


	

		
