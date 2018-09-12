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
import subprocess, re, psycopg2
from dateutils import DateTimeCalendar

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

		self.window = self.builder.get_object('window1')
		self.window.show_all()
		
	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def product_renderer_changed (self, combo, path, tree_iter):
		invoice_item_id = self.product_store[tree_iter][0]
		product_name = self.product_store[tree_iter][1]
		_iter= self.credit_items_store.get_iter (path)
		self.credit_items_store[_iter][6] = int(invoice_item_id)
		self.credit_items_store[_iter][3] = product_name
		self.save_line(_iter)

	def product_editing_started (self, renderer, combo, path):
		entry = combo.get_child()
		entry.set_completion(self.builder.get_object('product_completion'))
	
	def price_edited (self, cellrenderer, path, text):
		row_id = self.credit_items_store[path][0]
		try:
			self.cursor.execute("UPDATE credit_memo_items "
								"SET (price, ext_price) = (%s, qty*%s) "
								"WHERE id = %s "
								"RETURNING price::text, ext_price::text", 
								(text, text, row_id))
			self.db.commit()
		except psycopg2.DataError as e:
			self.show_message(str(e))
			self.db.rollback()
			return
		for row in self.cursor.fetchall():
			price = row[0]
			ext_price = row[1]
		self.credit_items_store[path][5] = price
		self.credit_items_store[path][6] = ext_price

	def qty_edited (self, cellrenderertext, path, text):
		row_id = self.credit_items_store[path][0]
		try:
			self.cursor.execute("UPDATE credit_memo_items "
								"SET (qty, ext_price) = (%s, %s*price) "
								"WHERE id = %s "
								"RETURNING qty::text, ext_price::text", 
								(text, text, row_id))
			self.db.commit()
		except psycopg2.DataError as e:
			self.show_message(str(e))
			self.db.rollback()
			return
		for row in self.cursor.fetchall():
			qty = row[0]
			ext_price = row[1]
		self.credit_items_store[path][1] = qty
		self.credit_items_store[path][6] = ext_price

	def tax_edited (self, cellrenderertext, path, text):
		row_id = self.credit_items_store[path][0]
		try:
			self.cursor.execute("UPDATE credit_memo_items "
								"SET tax = %s "
								"WHERE id = %s "
								"RETURNING tax::text", 
								(text, row_id))
			self.db.commit()
		except psycopg2.DataError as e:
			self.show_message(str(e))
			self.db.rollback()
			return
		for row in self.cursor.fetchall():
			tax = row[0]
		self.credit_items_store[path][7] = tax

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
							"(False, True, True) "
							"GROUP BY c.id, c.name, c.ext_name "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)

	def customer_combo_changed (self, combo):
		customer_id = combo.get_active_id ()
		if customer_id != None:
			self.select_customer (customer_id)

	def customer_match_selected (self, completion, model, _iter):
		customer_id = model[_iter][0]
		self.select_customer (customer_id)

	def select_customer(self, customer_id):
		self.customer_id = customer_id
		self.cursor.execute("SELECT "
								"address, COALESCE(cm.id, NULL) "
							"FROM contacts AS c "
							"LEFT JOIN credit_memos AS cm "
							"ON cm.customer_id = c.id "
							"WHERE c.id = %s", 
							(customer_id,))
		for row in self.cursor.fetchall():
			address = row[0]
			self.credit_memo_id = row[1]
			self.builder.get_object('address_entry').set_text(address)
		self.populate_credit_memo ()
		if self.populate_product_store ():
			self.builder.get_object('menuitem2').set_sensitive(True)
			self.builder.get_object('button1').set_sensitive(True)
			self.builder.get_object('button2').set_sensitive(True)
		else:
			self.show_message ("There are no returnable "
								"products for this customer!\n"
								"You will not be able to create a credit memo.")

	def populate_credit_memo (self):
		c = self.db.cursor()
		self.credit_items_store.clear()
		c.execute("SELECT "
						"cmi.id, "
						"cmi.qty::text, "
						"p.id, "
						"p.name, "
						"p.ext_name, "
						"cmi.price::text, "
						"cmi.ext_price::text, "
						"cmi.tax::text, "
						"cmi.invoice_item_id, "
						"ili.invoice_id, "
						"date_returned::text, "
						"format_date(date_returned)," 
						"COALESCE(sn.serial_number, '') "
					"FROM credit_memo_items AS cmi "
					"JOIN invoice_items AS ili ON ili.id = cmi.invoice_item_id "
					"JOIN products AS p ON p.id = ili.product_id "
					"LEFT JOIN serial_number_history AS snh ON snh.credit_memo_item_id = cmi.id "
					"LEFT JOIN serial_numbers AS sn ON sn.id = snh.serial_number_id "
					"WHERE credit_memo_id = %s", (self.credit_memo_id,))
		for row in c.fetchall():
			self.credit_items_store.append(row)
		c.close()

	def populate_product_store(self, m=None, i=None):
		self.product_store.clear()
		c = self.db.cursor()
		c.execute("SELECT ili.id::text, p.name || '  {' || ext_name || '}', "
					"i.id::text, format_date(i.dated_for) "
					"FROM products AS p "
					"JOIN invoice_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE (customer_id, paid) = (%s, True) "
					"ORDER BY p.name", (self.customer_id,))
		for row in c.fetchall():
			self.product_store.append(row)
			continue
		else:        # this customer has bought no products yet
			c.close()
			return False
		c.close()

	def product_combo_changed (self, combo):
		invoice_item_id = combo.get_active_id()
		if invoice_item_id != None:
			self.invoice_item_selected(invoice_item_id)

	def product_match_selected (self, completion, model, _iter_):
		invoice_item_id = model[_iter_][0]
		self.invoice_item_selected(invoice_item_id)

	def invoice_item_selected (self, invoice_item_id):
		self.check_credit_memo_id()
		c = self.db.cursor()
		c.execute("SELECT "
					"0, "
					"1.0, "
					"product_id, "
					"p.name, "
					"p.ext_name, "
					"ili.price, "
					"ili.id, "
					"i.id, "
					"i.dated_for::text, "
					"format_date(i.dated_for), "
					"ili.tax::float, "
					"'' "
					"FROM products AS p "
					"JOIN invoice_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE ili.id = %s ", (invoice_item_id,))
		for row in c.fetchall():
			_iter = self.credit_items_store.append(row)
			self.save_line(_iter)
		c.close()

	def apply_serial_number_activated (self, menuitem):
		pass

	def treeview_cursor_changed (self, treeview):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][2]
		store = self.builder.get_object('serial_number_store')
		store.clear()
		self.cursor.execute("SELECT ii.id, sn.serial_number "
							"FROM serial_numbers AS sn "
							"JOIN invoice_items AS ii ON ii.id = sn.invoice_item_id "
							"JOIN invoices AS i ON i.id = ii.invoice_id "
							"WHERE (i.customer_id, ii.product_id) = (%s, %s)", 
							(self.customer_id, product_id))
		for row in self.cursor.fetchall():
			store.append(row)
	
	def serial_number_changed (self, combo, path, tree_iter):
		model = self.builder.get_object('serial_number_store')
		invoice_item_id = model[tree_iter][0]
		serial_number = model[tree_iter][1]
		self.credit_items_store[path][6] = invoice_item_id
		self.credit_items_store[path][11] = serial_number

	def return_day_selected (self, calendar):
		date = calendar.get_date()
		_iter = self.credit_items_store.get_iter(self.path)
		self.credit_items_store[_iter][8] = str(date)
		#self.credit_items_store[_iter][9] = date_formatted
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
		c = self.db.cursor()
		row_id = self.credit_items_store[_iter][0]
		qty = self.credit_items_store[_iter][1]
		price = self.credit_items_store[_iter][5]
		invoice_item_id = self.credit_items_store[_iter][6]
		tax = self.credit_items_store[_iter][10]
		if row_id == 0:
			row_id = c.fetchone()[0]
			self.credit_items_store[_iter][0] = row_id
		else:
			c.execute("UPDATE credit_memo_items SET "
							"(qty, invoice_item_id, price, tax) "
							"= (%s, %s, %s, %s) WHERE id = %s", 
							(qty, invoice_item_id, price, tax, row_id))
		self.db.commit()
		c.close()

	def new_item_clicked (self, button):
		c = self.db.cursor()
		self.check_credit_memo_id()
		invoice_item_id = self.product_store[0][0]
		c.execute("INSERT INTO credit_memo_items "
					"(credit_memo_id, qty, invoice_item_id, "
						"price, date_returned, tax) "
					"VALUES (%s, 1, %s, 1.00, now(), "
						"(SELECT tax FROM invoice_items WHERE id = %s)"
					") RETURNING id", 
					(self.credit_memo_id, invoice_item_id, invoice_item_id))
		
		self.credit_items_store.append([0,1,0,'','','1.00',0,0,'','',0.00,'']) 

	def check_credit_memo_id (self):
		if self.credit_memo_id == None:
			self.cursor.execute("INSERT INTO credit_memos "
								"(name, customer_id, date_created, total) "
								"VALUES ('', %s, now(), 0.00) RETURNING id",
								(self.customer_id,))
			self.credit_memo_id = self.cursor.fetchone()[0]

	def post_credit_memo_clicked (self, button):
		c = self.db.cursor()
		c.execute("WITH cancel AS"
					"(SELECT ii.product_id, serial_number "
					"FROM credit_memo_items AS cmi "
					"JOIN invoice_items AS ii ON ii.id = cmi.invoice_item_id "
					"JOIN "
					")", ())
		c.close()
	
	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()
		
		
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
		'''self.cursor.execute("SELECT qty, p.name, p.ext_name, price, ii.tax "
							"FROM credit_memo_items AS cmi "
							"JOIN invoice_items AS ii "
								"ON ii.id = cmi.invoice_item_id "
							"JOIN products AS p ON p.id = ii.product_id")'''
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
		self.cursor.execute("SELECT format_date(%s)", (self.date,))
		date_text = self.cursor.fetchone()[0] 
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

	def view_document_activated (self, button):
		self.create_odt()
		subprocess.Popen(["soffice", self.credit_memo_file])









		