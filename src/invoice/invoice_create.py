# invoice_create.py
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

from gi.repository import GLib, Gtk
import os, subprocess, time, psycopg2, re
import uno, unohelper
from com.sun.star.connection import NoConnectException
from com.sun.star.uno import RuntimeException
from com.sun.star.util import XCloseListener
from time import strftime
from datetime import datetime, timedelta
from multiprocessing import Process
from db import transactor
import printing
from constants import DB, template_dir

class Item(object):#this is used by py3o library see their example for more info
	pass

class Setup(XCloseListener, unohelper.Base):
	def __init__(self, store, contact_id, comment, date,
											invoice_id, parent, 
											doc_type = "Invoice"):
		self.contact_id = contact_id
		self.store = store
		self.comment = comment
		self.date = date
		self.invoice_id = invoice_id
		self.doc_type = doc_type

		self.parent = parent
		self.invoice_doc = None
		self.get_office_socket_connection()
		self.create_odt ()

	def create_odt (self):
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"c.name, "
								"c.ext_name, "
								"c.address, "
								"c.city, "
								"c.state, "
								"c.zip, "
								"c.fax, "
								"c.phone, "
								"c.email, "
								"c.label, "
								"c.tax_number, "
								"i.name "
								"FROM contacts AS c "
								"JOIN invoices AS i ON i.customer_id = c.id "
							"WHERE i.id = (%s)",[self.invoice_id])
		customer = Item()
		for row in cursor.fetchall():
			customer.name = row[0]
			customer.ext_name = row[1]
			customer.street = row[2]
			customer.city = row[3]
			customer.state = row[4]
			customer.zip = row[5]
			customer.fax = row[6]
			customer.phone = row[7]
			customer.email = row[8]
			customer.label = row[9]
			customer.tax_exempt_number = row[10]
			invoice_name = row[11]
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
		for i in self.store:
			item = Item()
			item.qty = i[1] 
			product_id = i[2]
			item.product = i[3]
			ext_name = i[4]
			if ext_name != "":
				item.ext_name = " , " + i[4]
			remark = i[5]
			if remark != "":
				item.remark = " : " + i[5]
			item.price = i[6] 
			item.tax_letter = i[11]
			item.tax = i[7] 
			item.ext_price = i[8] 
			items.append(item)
	
		terms = Item()
		cursor.execute("SELECT plus_date, text1, text2, text3, text4 "
							"FROM contacts "
							"JOIN terms_and_discounts "
							"ON contacts.terms_and_discounts_id = "
							"terms_and_discounts.id WHERE contacts.id = %s", 
							(self.contact_id,))
		for row in cursor.fetchall():
			plus_date = row[0]
			terms.plus_date = plus_date
			terms.text1 = row[1]
			terms.text2 = row[2]
			terms.text3 = row[3]
			terms.text4 = row[4]
			
		document = Item()
		cursor.execute("WITH _subtotal AS "
							"(SELECT SUM(ext_price) AS ep FROM invoice_items "
							"WHERE invoice_id = %s "
							"), "
						"_tax AS "
							"(SELECT SUM(tax) FROM invoice_items "
							"WHERE invoice_id = %s "
							") "
						"UPDATE invoices SET (subtotal, tax, total) = "
							"((SELECT * FROM _subtotal), "
							"(SELECT * FROM _tax), "
							"(SELECT * FROM _subtotal) + (SELECT * FROM _tax )"
						") WHERE id = %s "
						"RETURNING subtotal::money, "
							"tax::money, "
							"total::money", 
						(self.invoice_id, self.invoice_id, self.invoice_id))
		for row in cursor.fetchall():
			subtotal = row[0]
			tax = row[1]
			total = row[2]
		document.subtotal = subtotal
		document.tax = tax
		document.total = total
		document.comment = self.comment
		document.document_status = ''
		
		date_plus_thirty = self.date + timedelta(days=plus_date)
		cursor.execute("SELECT format_date(%s), format_date(%s)", 
							(date_plus_thirty, self.date))
		for row in cursor.fetchall():
			payment_due_text = row[0]
			date_text = row[1]
		if self.doc_type == "Invoice":
			document.payment_due = payment_due_text
		else: # document is not an invoice
			terms.plus_date = ''
			terms.text1 = ''
			terms.text2 = ''
			terms.text3 = ''
			terms.text4 = ''
			
		document.date = date_text
		document.name = invoice_name
		document.number = str(self.invoice_id)
		document.type = self.doc_type

		self.document_name = document.name
		self.document_odt = document.name + ".odt"
		self.document_pdf = document.name + ".pdf"
		self.lock_file = '/tmp/.~lock.' + self.document_odt + '#'
		data = dict(items = items, 
					document = document, 
					contact = customer, 
					terms = terms, 
					company = company)
		from py3o.template import Template #import for every invoice
		self.invoice_file = "/tmp/" + self.document_odt
		t = Template(template_dir+"/invoice_template.odt", self.invoice_file , True)
		t.render(data) #the data holds all the info of the invoice
		cursor.close()

	def save (self):
		try:
			self.invoice_doc.save()
		except Exception as e:
			print (e, 'in invoice_create, document no longer exists')

	def view(self):
		if self.invoice_doc:
			try:
				self.invoice_doc.close(True)
			except RuntimeException as e:
				print (e, 'a user closed the document, probably')
				self.get_office_socket_connection ()
		try:
			document = "file:///tmp/" + self.document_odt
			self.invoice_doc = self.desktop.loadComponentFromURL(document, 
																	'_blank', 
																	0, 
																	())
		except NoConnectException:
			self.get_office_socket_connection ()

	def get_office_socket_connection (self):
		subprocess.Popen(["soffice",
							"--accept=socket,"
							"host=localhost,"
							"port=2002;"
							"urp;",
							"--nologo",
							"--nodefault"])	
		localContext = uno.getComponentContext()
		resolver = localContext.ServiceManager.createInstanceWithContext(
										'com.sun.star.bridge.UnoUrlResolver', 
										localContext )
		connection_url = 	('uno:socket,'
							'host=localhost,'
							'port=2002;'
							'urp;'
							'StarOffice.ServiceManager')
		result = False
		while result == False:
			try:
				smgr = resolver.resolve( connection_url )
				result = True
			except NoConnectException:
				subprocess.Popen(["soffice",
									"--accept=socket,"
									"host=localhost,"
									"port=2002;"
									"urp;",
									"--nologo",
									"--nodefault"])
				time.sleep(1)
		remoteContext = smgr.getPropertyValue( 'DefaultContext' )
		self.desktop = smgr.createInstanceWithContext( 'com.sun.star.frame.Desktop', 
																remoteContext)

	def print_dialog(self, window):
		subprocess.call("odt2pdf " + self.invoice_file, shell = True)
		p = printing.Operation(settings_file = "invoice")
		p.set_parent(window)
		p.set_file_to_print("/tmp/" + self.document_pdf)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			cursor = DB.cursor()
			cursor.execute("UPDATE invoices SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.invoice_id,))
			cursor.close()
		return result
				
	def print_directly(self, window):
		subprocess.call("odt2pdf " + self.invoice_file, shell = True)
		p = printing.Operation(settings_file = "invoice")
		p.set_parent(window)
		p.set_file_to_print("/tmp/" + self.document_pdf)
		result = p.print_directly()
		cursor = DB.cursor()
		if result == Gtk.PrintOperationResult.APPLY:
			cursor.execute("UPDATE invoices SET date_printed = "
								"CURRENT_DATE WHERE id = %s", 
								(self.invoice_id,))
		cursor.close()

	def email (self, email_address):
		document = "/tmp/" + self.document_pdf
		subprocess.Popen(["xdg-email",
							"--subject", "Invoice",
							"--attach", document,
							email_address])

	def post(self):
		document = "/tmp/" + self.document_pdf
		f = open(document,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		f.close()
		cursor = DB.cursor()
		cursor.execute("UPDATE invoices SET(name, "
							"pdf_data, posted, amount_due, dated_for) "
							"= (%s, %s, %s, total, %s) "
							"WHERE id = %s RETURNING gl_entries_id, total", 
							(self.document_name, binary, True, self.date, 
							self.invoice_id))
		for row in cursor.fetchall():
			gl_entries_id = row[0]
			total = row[1]
		transactor.post_invoice_receivables(total, self.date, 
											self.invoice_id, gl_entries_id)
		cursor.execute("SELECT accrual_based FROM settings")
		if cursor.fetchone()[0] == True:
			transactor.post_invoice_accounts (self.date, self.invoice_id)
		cursor.close()
		
		

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Setup,'com.sun.star.util.XClosedListener',())


