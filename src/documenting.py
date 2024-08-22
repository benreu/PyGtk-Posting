# invoice_utility.py
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

import os, sys, subprocess, time, psycopg2
from time import strftime
from decimal import Decimal
from datetime import datetime, timedelta
import printing
from constants import DB, template_dir

items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, store, contact, comment, date, document_type_id, document_name):
		'''store is the liststore used by the treeview, contact id, comment, date, document_type_id, document_name'''
		self.contact = contact
		self.store = store
		self.comment = comment
		self.date = date
		self.document_type_id = document_type_id
		self.document_name = document_name
		self.total = Decimal()
		cursor = DB.cursor()
		cursor.execute("SELECT * FROM contacts WHERE id = (%s)",(self.contact,))
		vendor = Item()
		items = list()
		for string in cursor.fetchall():
			vendor.name = (string[1])
			self.vendor_id = (string[0])
			name = (string[1])
			vendor.ext_name = (string[2])
			vendor.address = (string[3])
			vendor.city = (string[4])
			vendor.state = (string[5])
			vendor.zip = (string[6])
			vendor.fax = (string[7])
			vendor.phone = (string[8])
			vendor.email = (string[9])
			vendor.label = (string[10])
			vendor.tax_exempt = (string[11])
			vendor.tax_exempt_number = (string[12])
		company = Item()
		cursor.execute("SELECT * FROM company_info")
		for row in cursor.fetchall():
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
		for i in self.store:
			item = Item()
			item.qty = i[1]
			item.product = i[3]
			item.ext_name = i[4]
			item.minimum = i[5]
			item.maximum = i[6]
			item.retailer = i[8]
			item.remark = i[10]
			item.priority = i[11]
			item.price = i[12]
			item.s_price = i[13]
			item.ext_price = i[14]
			items.append(item)
			self.total += Decimal(i[14])
		
		document = Item()
		cursor.execute("SELECT name FROM document_types WHERE id = %s", (document_type_id, ))
		document.type = cursor.fetchone()[0]
		cursor.execute("SELECT * FROM document_types WHERE id = %s", (self.document_type_id))
		for row in cursor.fetchall():
			document.text1 = row[2]
			document.text2 = row[3]
			document.text3 = row[4]
			document.text4 = row[5]
			document.text5 = row[6]
			document.text6 = row[7]
			document.text7 = row[8]
			document.text8 = row[9]
			document.text9 = row[10]
			document.text10 = row[11]
			document.text11 = row[12]
			document.text12 = row[13]
		document.total = '${:,.2f}'.format(self.total)
		document.comment = self.comment
		document.date = self.date
		
		date_thirty = date + timedelta(days=30)
		cursor.execute("SELECT format_date(%s)", (date_thirty,))
		payment_thirty = cursor.fetchone()[0]
		document.payment_due = payment_thirty

		document.number = self.document_name
		self.document_odt = self.document_name + ".odt"
		self.document_pdf = self.document_name + ".pdf"
		self.data = dict(items=items, document=document, contact = vendor, company = company)
		cursor.close()

	def view(self):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(template_dir+"/document_template.odt", purchase_order_file , True)
		t.render(self.data) #the self.data holds all the info of the purchase_order
		subprocess.Popen("libreoffice " + purchase_order_file, shell = True)

	def print_dialog(self, window):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(template_dir+"/document_template.odt", purchase_order_file , True)
		t.render(self.data)  #the self.data holds all the info of the purchase_order
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.Operation(settings_file = "document")
		p.set_parent(window)
		p.set_file_to_print ("/tmp/" + self.document_pdf)
		p.print_dialog ()
		
	def print_directly(self):
		from py3o.template import Template #import for every purchase order or there is an error about invalid magic header numbers
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(template_dir+"/document_template.odt", purchase_order_file , True)
		t.render(self.data)
		subprocess.Popen("libreoffice --nologo --headless -p " + purchase_order_file, shell = True)
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		self.store = []

	def post(self, document_id):
		cursor = DB.cursor()
		document = "/tmp/" + self.document_pdf		
		f = open(document,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		f.close()
		cursor.execute("UPDATE documents SET "
						"(pdf_data, pending_invoice, closed) = "
						"(%s, True, True) WHERE id = %s", (binary, document_id))
		DB.commit()
		cursor.close()



		
