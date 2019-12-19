# credit_memo_template.py
#
# Copyright (C) 2018 - reuben
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
import re, subprocess
from db import transactor
import printing
from constants import DB, template_dir

class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup :
	def __init__ (self, credit_items_store, credit_memo_id, customer_id):

		self.credit_items_store = credit_items_store
		self.credit_memo_id = credit_memo_id
		self.customer_id = customer_id
		self.create_odt ()
		
	def create_odt(self ):
		cursor = DB.cursor()
		cursor.execute("SELECT * FROM contacts "
							"WHERE id = (%s)", (self.customer_id,))
		customer = Item()
		for row in cursor.fetchall():
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
		items = list()
		for i in self.credit_items_store:
			item = Item()
			item.qty = i[1]
			product_id = i[2]
			item.product = i[3]
			ext_name = i[4]
			if ext_name != "":
				item.ext_name = " , " + i[4]
			item.price = i[5]
			item.ext_price = i[6]
			item.tax = i[7]
			items.append(item)

		document = Item()
		cursor.execute("SELECT "
								"format_date(dated_for), "
								"(-total)::money, "
								"(-tax)::money, "
								"(-amount_owed)::money "
							"FROM credit_memos WHERE id = %s ", 
							(self.credit_memo_id,))
		for row in cursor.fetchall():
			date_text = row[0]
			subtotal = row[1]
			tax = row[2]
			total = row[3]
		document.date = date_text
		document.subtotal = subtotal
		document.tax = tax
		document.total = total
		
		split_name = name.split(' ')
		name_str = ""
		for i in split_name:
			name_str += i[0:3]
		name = name_str.lower()

		invoice_date = re.sub(" ", "_", date_text)
		document.name = "CreMem" + "_" + str(self.credit_memo_id) + "_"\
												+ name + "_" + invoice_date
		document.number = str(self.credit_memo_id)

		self.document_name = document.name
		self.document_odt = document.name + ".odt"
		self.document_pdf = document.name + ".pdf"
		self.lock_file = '/tmp/.~lock.' + self.document_odt + '#'
		self.data = dict(items = items, document = document, contact = customer, company = company)
		from py3o.template import Template
		self.credit_memo_file = "/tmp/" + self.document_odt
		t = Template(template_dir+"/credit_memo_template.odt", self.credit_memo_file , True)
		t.render(self.data) #the self.data holds all the info of the invoice
		cursor.close()

	def view_odt (self):
		subprocess.Popen(["soffice", self.credit_memo_file])

	def print_pdf (self, window):
		cursor = DB.cursor()
		subprocess.call(["odt2pdf", self.credit_memo_file])
		p = printing.Operation(settings_file = "credit_memo")
		p.set_parent(window)
		p.set_file_to_print ("/tmp/" + self.document_pdf)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			cursor.execute("UPDATE credit_memos SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.credit_memo_id,))
		cursor.close()
		return result

	def post (self):
		cursor = DB.cursor()
		transactor.post_credit_memo (self.credit_memo_id)
		with open("/tmp/" + self.document_pdf, 'rb') as fp:
			data = fp.read()
		cursor.execute("UPDATE credit_memos "
							"SET (pdf_data, posted) = "
							"(%s, True) "
							"WHERE id = %s", 
							(data, self.credit_memo_id))
		cursor.close()





