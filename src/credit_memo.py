# credit_memo.py
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
import subprocess, re
from dateutils import DateTimeCalendar, datetime_to_text

UI_FILE = "src/credit_memo.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class CreditMemoGUI:
	def __init__(self, main):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('credit_products_store')
		self.credit_items_store = self.builder.get_object('credit_items_store')
		self.db = main.db
		self.cursor = self.db.cursor()
		self.handler_c_id = main.connect ("contacts_changed", self.populate_customer_store )
		self.populate_customer_store ()
		
		self.date_returned_calendar = DateTimeCalendar()
		self.date_returned_calendar.connect('day-selected', self.return_day_selected )
		date_column = self.builder.get_object('label3')
		self.date_returned_calendar.set_relative_to(date_column)
		
		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect('day-selected', self.day_selected )
		self.date_calendar.set_today()
		
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		window = self.builder.get_object('window1')
		window.show_all()
		
	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def product_editing_started (self, renderer, combo, path):
		entry = combo.get_child()
		entry.set_completion(self.builder.get_object('product_completion'))
	
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def populate_customer_store (self, m=None, i=None):
		self.customer_store.clear()
		self.cursor.execute("SELECT c.id::text, c.name, c.ext_name "
							"FROM contacts AS c "
							"JOIN invoices AS i ON c.id = i.customer_id "
							"WHERE (c.deleted, c.customer, i.paid) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			customer_id = row[0]
			name = row[1]
			ext_name = row[2]
			self.customer_store.append([customer_id, name, ext_name])

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id ()
		if customer_id != None:
			self.select_customer (customer_id)

	def customer_match_selected (self, completion, model, _iter):
		customer_id = model[_iter][0]
		self.select_customer (customer_id)

	def select_customer(self, customer_id):
		self.customer_id = customer_id
		self.cursor.execute("SELECT id FROM credit_memos "
							"WHERE (customer_id, posted) = (%s, False)", 
							(customer_id,))
		for row in self.cursor.fetchall():
			self.credit_memo_id = row[0]
			self.populate_credit_memo ()
			break
		else:
			self.credit_items_store.clear()
			self.credit_memo_id = None
		self.populate_product_store ()

	def populate_credit_memo (self):
		self.credit_items_store.clear()
		self.cursor.execute("SELECT cmi.id, cmi.qty, p.id, p.name, p.ext_name, cmi.price, invoice_item_id, "
							"i.id, date_returned, cmi.tax "
							"FROM credit_memo_items AS cmi "
							"JOIN invoice_line_items AS ili ON ili.id = cmi.invoice_item_id "
							"JOIN products AS p ON p.id = ili.product_id "
							"JOIN invoices AS i ON i.id = ili.invoice_id "
							"WHERE credit_memo_id = %s", (self.credit_memo_id,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			qty = row[1]
			product_id = row[2]
			product_name = row[3]
			ext_name = row[4]
			price = row[5]
			invoice_item_id = row[6]
			invoice_id = row[7]
			date = row[8]
			tax = row[9]
			date_formatted = datetime_to_text (date)
			self.credit_items_store.append([0, 1.0, product_id, product_name, 
											ext_name, price, int(invoice_item_id), 
											invoice_id, str(date), date_formatted,
											tax, ''])

	def populate_product_store(self, m=None, i=None):
		self.product_store.clear()
		c = self.db.cursor()
		c.execute("SELECT ili.id::text, p.name, ext_name, i.id::text, i.dated_for "
					"FROM products AS p "
					"JOIN invoice_line_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE (customer_id, paid) = (%s, True) "
					"ORDER BY p.name", (self.customer_id,))
		for row in c.fetchall():
			_id_ = row[0]
			name = "%s {%s}" % (row[1], row[2])
			invoice = row[3]
			date = datetime_to_text (row[4])
			self.product_store.append([_id_, name, invoice, date])
		c.close()

	def product_combo_changed (self, combo):
		invoice_item_id = combo.get_active_id()
		if invoice_item_id != None:
			self.invoice_item_selected(invoice_item_id)

	def product_match_selected (self, completion, model, _iter):
		invoice_item_id = model[_iter_][0]
		self.invoice_item_selected(invoice_item_id)

	def invoice_item_selected (self, invoice_item_id):
		self.check_credit_memo_id()
		for row in self.credit_items_store:
			if row[5] == int(invoice_item_id):
				self.builder.get_object('treeview-selection1').select_path(row.path)
				return
		c = self.db.cursor()
		c.execute("SELECT product_id, p.name, p.ext_name, ili.price, i.id, i.dated_for, ili.tax "
					"FROM products AS p "
					"JOIN invoice_line_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE ili.id = %s ", (invoice_item_id,))
		for row in c.fetchall():
			product_id = row[0]
			product_name = row[1]
			ext_name = row[2]
			price = row[3]
			invoice = row[4]
			date = row[5]
			tax = row[6]
			date_formatted = datetime_to_text (date)
			_iter = self.credit_items_store.append([0, 1.0, product_id, product_name, 
											ext_name, price, int(invoice_item_id), 
											invoice, str(date), date_formatted,
											tax, ''])
			self.save_line(_iter)
		c.close()

	def return_day_selected (self, calendar):
		date = calendar.get_date()
		date_formatted = datetime_to_text(date)
		_iter = self.credit_items_store.get_iter(self.path)
		self.credit_items_store[_iter][8] = str(date)
		self.credit_items_store[_iter][9] = date_formatted
		self.save_line(_iter)

	def date_entry_icon_released (self, entry, icon, position):
		self.date_calendar.set_relative_to(entry)
		self.date_calendar.show_all()

	def day_selected (self, calendar):
		self.date = calendar.get_date()
		text = calendar.get_text()
		self.builder.get_object('entry1').set_text(text)

	def date_returned_editing_started (self, renderer, entry, path):
		self.path = path
		current_date = self.credit_items_store[path][8]
		self.date_returned_calendar.set_date(current_date)
		self.date_returned_calendar.show_all()
		entry.destroy()

	def save_line (self, _iter):
		row_id = self.credit_items_store[_iter][0]
		qty = self.credit_items_store[_iter][1]
		price = self.credit_items_store[_iter][5]
		invoice_item_id = self.credit_items_store[_iter][6]
		tax = self.credit_items_store[_iter][10]
		if row_id == 0:
			self.cursor.execute("INSERT INTO credit_memo_items "
							"(credit_memo_id, qty, invoice_item_id, price, date_returned, tax) "
							"VALUES (%s, %s, %s, %s, now(), %s) RETURNING id", 
							(self.credit_memo_id, qty, invoice_item_id, price, tax))
			row_id = self.cursor.fetchone()[0]
			self.credit_items_store[_iter][0] = row_id
		else:
			self.cursor.execute("UPDATE credit_memo_items SET "
							"(qty, invoice_item_id, price, tax) "
							"= (%s, %s, %s, %s) WHERE id = %s", 
							(qty, invoice_item_id, price, tax, row_id))
		self.db.commit()

	def check_credit_memo_id (self):
		if self.credit_memo_id == None:
			self.cursor.execute("INSERT INTO credit_memos "
								"(name, customer_id, date_created, total) "
								"VALUES ('', %s, now(), 0.00) RETURNING id",
								(self.customer_id,))
			self.credit_memo_id = self.cursor.fetchone()[0]


########################  py3o template to document generator

	def create_odt(self ):
		self.cursor.execute("SELECT * FROM contacts "
							"WHERE id = (%s)", (self.customer_id,))
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
		items = list()
		for i in self.credit_items_store:
			item = Item()
			item.qty = round(i[1], 1)
			product_id = i[2]
			item.product = i[3]
			ext_name = i[4]
			if ext_name != "":
				item.ext_name = " , " + i[4]
			item.price = '${:,.2f}'.format(i[5])
			item.tax = '${:,.2f}'.format(i[10])
			#item.ext_price = '${:,.2f}'.format(i[11])
			items.append(item)

		document = Item()
		date_text = datetime_to_text(self.date)
		document.date = date_text
		
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
		t = Template("./templates/credit_memo_template.odt", self.credit_memo_file , True)
		t.render(self.data) #the self.data holds all the info of the invoice

	def view_document_clicked (self, button):
		self.create_odt()
		subprocess.call(["soffice", self.credit_memo_file])






		


		