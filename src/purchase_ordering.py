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

from gi.repository import Gtk
import subprocess, re
from datetime import timedelta
from decimal import Decimal
from db import transactor
from dateutils import datetime_to_text
import printing


items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, db, store, contact, comment, datetime, purchase_order_id):	
		'''store is the liststore used by the treeview, contact id, comment, datetime'''
		self.contact = contact
		self.store = store
		self.comment = comment
		self.datetime = datetime
		self.total = Decimal()
		self.purchase_order_id = purchase_order_id
		self.db = db
		self.cursor = db.cursor()
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
		for row in self.store:
			if row[14] == False:
				self.total += row[9]
				item = Item()
				item.qty = row[1]
				item.order_number = row[3]
				item.product_name = row[5]
				item.product_ext_name = row[6]
				item.remark = row[7]
				item.price = '${:,.2f}'.format(row[8])
				item.ext_price = '${:,.2f}'.format(row[9])
				items.append(item)
		
		document = Item()
		document.total = '${:,.2f}'.format(self.total)
		document.comment = self.comment
		document.date = self.datetime

		date_plus_thirty = datetime + timedelta(days=30)
		payment_due_text = datetime_to_text(date_plus_thirty)
		document.payment_due = payment_due_text
		date_text = datetime_to_text(datetime)
		document.date = date_text
		
		split_name = name.split(' ')
		name_str = ""
		for i in split_name:
			name_str += i[0:3]
		name = name_str.lower()
		po_name_date = re.sub(" ", "_", str(self.datetime))
		document.number = "PO_" + str(purchase_order_id) + "_"  + name + "_" + po_name_date[0:10]

		self.document_name = document.number
		self.document_odt = document.number + ".odt"
		self.document_pdf = document.number + ".pdf"
		self.data = dict(items=items, document=document, contact = vendor, company = company)

	def view(self):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data) #the self.data holds all the info of the purchase_order
		subprocess.Popen("libreoffice " + purchase_order_file, shell = True)

	def print_dialog(self, window):
		from py3o.template import Template
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data)  #the self.data holds all the info of the purchase_order
		#subprocess.call("libreoffice --nologo -p " + purchase_order_file, shell = True)
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.PrintDialog("/tmp/" + self.document_pdf)
		result = p.run_print_dialog(window)
		if result == Gtk.PrintOperationResult.APPLY:
			self.cursor.execute("UPDATE purchase_orders SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.purchase_order_id,))
		
	def print_directly(self):
		from py3o.template import Template
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template("./templates/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data)
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.PrintDialog("/tmp/" + self.document_pdf)
		p.print_direct(window)
		self.store = []

	def post(self, purchase_order_id, vendor_id, datetime):
		document = "/tmp/" + self.document_pdf
		f = open(document,'rb')
		dat = f.read()
		f.close()
		self.cursor.execute("UPDATE purchase_orders SET (pdf_data, closed, "
							"invoiced, name, date_created) "
							"= (%s, True, False, %s, %s) WHERE id = %s", 
							(dat, self.document_name, datetime, 
							purchase_order_id))
		transactor.post_purchase_order (self.db, self.total, purchase_order_id)
		self.db.commit()


		
		

		
