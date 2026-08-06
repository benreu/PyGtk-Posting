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
import printing
from db_connection import DB
from constants import template_dir


items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, contact, comment, datetime, purchase_order_id):
		self.vendor_id = contact
		self.comment = comment
		self.datetime = datetime
		self.purchase_order_id = purchase_order_id
		
		cursor = DB.cursor()
		cursor.execute("SELECT "
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
		for row in cursor.fetchall():
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
		cursor.execute("SELECT "
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
		for row in cursor.fetchall():
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
		cursor.execute("SELECT "
								"poi.qty, "
								"poi.remark, "
								"COALESCE(order_number, vendor_sku, 'No sku'), "
								"products.name, "
								"products.ext_name "
							"FROM purchase_order_items AS poi "
							"JOIN products ON products.id = poi.product_id "
							"JOIN purchase_orders AS po "
							"ON po.id = poi.purchase_order_id "
							"LEFT JOIN vendor_product_numbers AS vpn "
							"ON (vpn.vendor_id, vpn.product_id) "
							"= (poi.product_id, po.vendor_id) "
							"WHERE (purchase_order_id, hold) = (%s, False) "
							"ORDER BY poi.id",
							(self.purchase_order_id, ) )
		for row in cursor.fetchall():
			item = Item()
			item.qty = row[0]
			if row[1] != '':
				item.remark = " : " + row[1]
			item.order_number = row[2]
			item.product_name = row[3]
			item.product_ext_name = row[4]
			items.append(item)

		document = Item()
		document.comment = self.comment
		document.date = self.datetime

		cursor.execute("SELECT format_date(%s)", (datetime,))
		document.date = cursor.fetchone()[0]
		
		split_name = name.split(' ')
		name_str = ""
		for i in split_name:
			name_str += i[0:3]
		name = name_str.lower()
		po_name_date = re.sub(" ", "_", str(self.datetime))
		document.number = "PO_" + str(purchase_order_id) + "_"  + name + "_" + po_name_date[0:10]
		document.po_number = str(purchase_order_id)

		self.document_name = document.number
		self.document_pdf = document.number + ".pdf"
		self.purchase_order_pdf = "/tmp/" + self.document_pdf

		from jinja2 import Environment, FileSystemLoader
		import weasyprint

		env = Environment(loader=FileSystemLoader(template_dir))
		template = env.get_template('purchase_order_template.html')
		html = template.render(items=items, document=document,
							contact=vendor, company=company)
		weasyprint.HTML(string=html).write_pdf(self.purchase_order_pdf)
		cursor.close()

	def view(self):
		subprocess.Popen(["xdg-open", self.purchase_order_pdf])

	def print_dialog(self, window):
		p = printing.Operation(settings_file = 'purchase_order')
		p.set_parent(window)
		p.set_file_to_print(self.purchase_order_pdf)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			cursor = DB.cursor()
			cursor.execute("UPDATE purchase_orders SET date_printed = "
								"CURRENT_DATE WHERE id = %s",
								(self.purchase_order_id,))
			cursor.close()
		return result

	def print_directly(self, window):
		p = printing.Operation(settings_file = 'purchase_order')
		p.set_parent(window)
		p.set_file_to_print(self.purchase_order_pdf)
		result = p.print_directly()
		if result == Gtk.PrintOperationResult.APPLY:
			cursor = DB.cursor()
			cursor.execute("UPDATE purchase_orders SET date_printed = "
								"CURRENT_DATE WHERE id = %s",
								(self.purchase_order_id,))
			cursor.close()
		return result

	def post(self, purchase_order_id, vendor_id, datetime):
		document = self.purchase_order_pdf
		f = open(document,'rb')
		dat = f.read()
		f.close()
		cursor = DB.cursor()
		cursor.execute("UPDATE purchase_orders "
								"SET (pdf_data, "
									"closed, "
									"invoiced, "
									"name, "
									"date_created, "
									"comments) "
								"= (%s, "
									"True, "
									"False, "
									"%s, "
									"%s, "
									"%s) "
								"WHERE id = %s", 
							(dat, 
							self.document_name, 
							datetime,
							self.comment, 
							purchase_order_id))
		DB.commit()
		cursor.close()






