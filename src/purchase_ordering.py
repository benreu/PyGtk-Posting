# purchase_ordering.py
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
import subprocess, re
from datetime import timedelta
from decimal import Decimal
from db import transactor
import printing, main


items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, db, contact, comment, datetime, purchase_order_id):
		self.vendor_id = contact
		self.comment = comment
		self.datetime = datetime
		self.total = Decimal()
		self.purchase_order_id = purchase_order_id
		self.db = db
		self.cursor = db.cursor()
		self.cursor.execute("SELECT "
								"name, "
								"ext_name, "
								"address, "
								"city, "
								"state, "
								"zip, "
								"fax, "
								"phone, "
								"email, "
								"label, "
								"tax_number "
							"FROM contacts WHERE id = %s",
							(contact, ))
		vendor = Item()
		items = list()
		for row in self.cursor.fetchall():
			vendor.name = (row[0])
			name = (row[0])
			vendor.ext_name = (row[1])
			vendor.address = (row[2])
			vendor.city = (row[3])
			vendor.state = (row[4])
			vendor.zip = (row[5])
			vendor.fax = (row[6])
			vendor.phone = (row[7])
			vendor.email = (row[8])
			vendor.label = (row[9])
			vendor.tax_exempt_number = (row[10])
		company = Item()
		self.cursor.execute("SELECT "
							"name, "
							"street, "
							"city, "
							"state, "
							"zip, "
							"country, "
							"phone, "
							"fax, "
							"email, "
							"website, "
							"tax_number "
							"FROM company_info")
		for row in self.cursor.fetchall():
			company.name = row[0]
			company.street = row[1]
			company.city = row[2]
			company.state = row[3]
			company.zip = row[4]
			company.country = row[5]
			company.phone = row[6]
			company.fax = row[7]
			company.email = row[8]
			company.website = row[9]
			company.tax_number = row[10]
		self.cursor.execute("SELECT "
								"poi.qty, "
								"poi.remark, "
								"poi.price::money, "
								"poi.qty*poi.price::money, "
								"COALESCE(order_number, vendor_sku, 'No sku'), "
								"products.name, "
								"products.ext_name, "
								"poi.qty*poi.price "
							"FROM purchase_order_line_items AS poi "
							"JOIN products ON products.id = poi.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poi.purchase_order_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poi.product_id, po.vendor_id) "
							"WHERE (purchase_order_id, hold) = (%s, False) "
							"ORDER BY poi.id", 
							(self.purchase_order_id, ) )
		for row in self.cursor.fetchall():
			item = Item()
			item.qty = row[0]
			if row[1] != '':
				item.remark = " : " + row[1]
			item.price = row[2]
			item.ext_price = row[3]
			item.order_number = row[4]
			item.product_name = row[5]
			item.product_ext_name = row[6]
			items.append(item)
			self.total += row[7]
		
		document = Item()
		document.total = '${:,.2f}'.format(self.total)
		document.comment = self.comment
		document.date = self.datetime

		date_thirty = datetime + timedelta(days=30)
		self.cursor.execute("SELECT format_date(%s), format_date(%s)", 
											(date_thirty, datetime))
		for row in self.cursor.fetchall():
			payment_due_text = row[0]
			date_text = row[1]
		document.payment_due = payment_due_text
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
		self.data = dict(items=items, document=document,
							contact=vendor, company=company)

	def view(self):
		from py3o.template import Template 
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(main.template_dir+"/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data) #the self.data holds all the info of the purchase_order
		subprocess.Popen("libreoffice " + purchase_order_file, shell = True)

	def print_dialog(self, window):
		from py3o.template import Template
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(main.template_dir+"/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data)  #the self.data holds all the info of the purchase_order
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.Operation(settings_file = 'purchase_order')
		p.set_parent(window)
		p.set_file_to_print("/tmp/" + self.document_pdf)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			self.cursor.execute("UPDATE purchase_orders SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.purchase_order_id,))
		return result
		
	def print_directly(self):
		from py3o.template import Template
		purchase_order_file = "/tmp/" + self.document_odt
		t = Template(main.template_dir+"/purchase_order_template.odt", purchase_order_file , True)
		t.render(self.data)
		subprocess.call("odt2pdf " + purchase_order_file, shell = True)
		p = printing.Operation(settings_file = 'purchase_order')
		p.set_parent(window)
		p.set_file_to_print("/tmp/" + self.document_pdf)
		result = p.print_direct()
		if result == Gtk.PrintOperationResult.APPLY:
			self.cursor.execute("UPDATE purchase_orders SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.purchase_order_id,))
		return result

	def post(self, purchase_order_id, vendor_id, datetime):
		document = "/tmp/" + self.document_pdf
		f = open(document,'rb')
		dat = f.read()
		f.close()
		self.cursor.execute("UPDATE purchase_orders "
								"SET (pdf_data, "
									"closed, "
									"invoiced, "
									"name, "
									"date_created) "
								"= (%s, "
									"True, "
									"False, "
									"%s, "
									"%s) "
								"WHERE id = %s", 
							(dat, 
							self.document_name, 
							datetime, 
							purchase_order_id))
		self.db.commit()






