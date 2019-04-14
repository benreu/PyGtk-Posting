# statementing.py
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
import subprocess, psycopg2, re
from datetime import datetime, timedelta
import printing, main

items = list()
class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup():
	def __init__(self, store, customer_id, date, total, comment = ""):	
		self.db = main.db
		self.cursor = self.db.cursor ()
		self.customer_id = customer_id
		self.store = store
		self.comment = comment
		self.date = date	
		self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",[customer_id])
		customer = Item()
		
		for row in self.cursor.fetchall():
			customer.name = row[1]
			self.customer_id = row[0]
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
			
		items = list()
		for i in self.store:
			item = Item()
			item.description = i[1]
			item.date = i[3]
			item.amount = '${:,.2f}'.format(i[4])
			items.append(item)
		
		document = Item() 
		document.total = '${:,.2f}'.format(total)
		document.comment = self.comment
		self.cursor.execute("SELECT format_date(%s)", (date.date(),))
		date_text = self.cursor.fetchone()[0]
		document.date = date_text
		
		split_name = name.split(' ') 
		name_str = ""
		for i in split_name:
			name_str = name_str + i[0:3]
		name = name_str.lower()
		
		self.cursor.execute("INSERT INTO statements (date_inserted, "
							"customer_id, amount, printed) "
							"VALUES (%s, %s, %s, False) RETURNING id", 
							(self.date, self.customer_id, total))
		self.statement_id = self.cursor.fetchone()[0]
		text = "Sta_" + str(self.statement_id) + "_"  + name + "_" + date_text
		document.name = re.sub(" ", "_", text)
		self.document_name = document.name
		document.number = str(self.statement_id)
		self.document_number = document.number
		self.document_odt = document.name + ".odt"
		self.document_pdf = document.name + ".pdf"
		self.data = dict(items = items, statement = document, contact = customer, company = company)
		from py3o.template import Template #import for every statement or there is an error about invalid magic header numbers
		self.statement_file = "/tmp/" + self.document_odt
		t = Template(main.template_dir+"/statement_template.odt", self.statement_file , True)
		t.render(self.data) #the self.data holds all the info of the invoice
		subprocess.call(["odt2pdf", self.statement_file])

	def view (self):
		subprocess.Popen(["soffice", self.statement_file])
		self.db.rollback ()  # we are only viewing the statement, so remove the id again
		
	def print_dialog (self, window):
		p = printing.Operation(settings_file = 'statement')
		p.set_parent(window)
		p.set_file_to_print("/tmp/" + self.document_pdf)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			self.cursor.execute("UPDATE statements SET (print_date, printed) = "
								"(CURRENT_DATE, True) WHERE id = %s", 
								(self.statement_id,))
		document = "/tmp/" + self.document_pdf
		f = open(document,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		f.close()
		self.cursor.execute("UPDATE statements SET (name, pdf) = (%s, %s) "
							"WHERE id = %s", 
							(self.document_name, binary, self.statement_id))
		self.close_invoices_and_payments ()
		
	def post_as_unprinted(self):
		self.close_invoices_and_payments ()
		

	def close_invoices_and_payments (self):
		self.cursor.execute("UPDATE invoices SET statement_id = %s "
							"WHERE (canceled, active, posted) = "
							"(False, True, True) "
							"AND customer_id = %s "
							"AND statement_id IS NULL", 
							(self.statement_id, self.customer_id))
		self.cursor.execute("UPDATE payments_incoming "
							"SET (closed, statement_id) = (True, %s) "
							"WHERE statement_id IS NULL "
							"AND customer_id = %s", 
							(self.statement_id, self.customer_id))
		self.cursor.execute("UPDATE credit_memos "
							"SET statement_id = %s "
							"WHERE statement_id IS NULL "
							"AND customer_id = %s", 
							(self.statement_id, self.customer_id))
		self.db.commit()






		
		
