# invoice_utility.py
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

import os, sys, subprocess, time, psycopg2
from time import strftime
from datetime import datetime, timedelta
from db import transactor
import printing

items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, db, store, contact, comment, date, document_type_id, document_name):
		'''store is the liststore used by the treeview, contact id, comment, date, document_type_id, document_name'''
		self.contact = contact
		self.store = store
		self.comment = comment
		self.date = date
		self.document_type_id = document_type_id
		self.document_name = document_name
		self.total = 0.00
		self.db = db
		self.cursor = self.db.cursor()
		self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",(self.contact, ))
		vendor = Item()
		items = list()
		for string in self.cursor.fetchall():
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
			item.price = '${:,.2f}'.format(i[12])
			item.ext_price = '${:,.2f}'.format(i[13])
			items.append(item)
			self.total += i[13]
		
		document = Item()
		self.cursor.execute("SELECT name FROM document_types WHERE id = %s", (document_type_id, ))
		document.type = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT * FROM document_types WHERE id = %s", (self.document_type_id))
		for row in self.cursor.fetchall():
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
		self.cursor.execute("SELECT format_date(%s)", (date_thirty,))
		payment_thirty = self.cursor.fetchone()[0]
		document.payment_due = payment_thirty

		document.number = self.document_name
		self.document_odt = self.document_name + ".odt"
		self.document_pdf = self.document_name + ".pdf"
		self.data = dict(items=items, document=document, contact = vendor, company = company)

	def view(self):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/document_template.odt", purchase_order_file , True)
		t.render(self.data) #the self.data holds all the info of the purchase_order
		subprocess.Popen("libreoffice " + purchase_order_file, shell = True)

	def print_dialog(self, window):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/document_template.odt", purchase_order_file , True)
		t.render(self.data)  #the self.data holds all the info of the purchase_order
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.Setup("/tmp/" + self.document_pdf, "document")
		p.print_dialog (window)
		
	def print_directly(self):
		from py3o.template import Template #import for every purchase order or there is an error about invalid magic header numbers
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/document_template.odt", purchase_order_file , True)
		t.render(self.data)
		subprocess.Popen("libreoffice --nologo --headless -p " + purchase_order_file, shell = True)
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		self.store = []

	def post(self, document_id):

		document = "/tmp/" + self.document_pdf		
		f = open(document,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		f.close()
		
		self.cursor.execute("UPDATE documents SET (pdf_data, pending_invoice, closed) = (%s, True, True) WHERE id = %s", (binary, document_id))
		self.db.commit()



		
