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

from gi.repository import Gtk, Gdk, GLib
import psycopg2
from dateutils import DateTimeCalendar
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/credit_memo.ui"

class CreditMemoGUI:
	credit_memo_template = None
	def __init__(self):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.customer_store = self.builder.get_object('customer_store')
		self.product_store = self.builder.get_object('credit_products_store')
		self.credit_items_store = self.builder.get_object('credit_items_store')
		self.handler_ids = list()
		for connection in (("contacts_changed", self.populate_customer_store),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.populate_customer_store ()
		
		self.date_returned_calendar = DateTimeCalendar()
		self.date_returned_calendar.connect('day-selected', self.return_day_selected )
		date_column = self.builder.get_object('label3')
		self.date_returned_calendar.set_relative_to(date_column)
		
		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect('day-selected', self.day_selected )
		
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def window_destroy (self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()
		
	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def product_match_selected (self, completion, model, _iter_):
		invoice_item_id = model[_iter_][0]
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		self.update_product_row (path, invoice_item_id)

	def product_renderer_changed (self, combo, path, tree_iter):
		invoice_item_id = self.product_store[tree_iter][0]
		self.update_product_row (path, invoice_item_id)

	def update_product_row (self, path, invoice_item_id):
		c = DB.cursor()
		iter_ = self.credit_items_store.get_iter (path)
		self.check_row_id (iter_)
		row_id = self.credit_items_store[iter_][0]
		c.execute(	"WITH tax_cte AS "
						"(SELECT tr.rate / 100 AS rate, price "
						"FROM invoice_items AS ii "
						"JOIN tax_rates AS tr ON tr.id = ii.tax_rate_id "
						"WHERE ii.id = %s"
						") "
					"UPDATE credit_memo_items AS cmi "
					"SET (invoice_item_id, "
						"price, "
						"ext_price, "
						"tax"
						") "
					"= "
						"(%s, "
						"(SELECT price FROM tax_cte), "
						"qty * (SELECT price FROM tax_cte), "
						"qty * (SELECT price FROM tax_cte) * (SELECT rate FROM tax_cte)"
						") "
					"WHERE id = %s; " #new sql; this updates values
					"SELECT "
						"p.id, "
						"p.name, "
						"p.ext_name, "
						"ii.price::text, "
						"cmi.ext_price::text, "
						"cmi.tax::text, "
						"cmi.invoice_item_id, "
						"ii.invoice_id "
					"FROM credit_memo_items AS cmi "
					"JOIN invoice_items AS ii ON ii.id = cmi.invoice_item_id "
					"JOIN products AS p ON p.id = ii.product_id "
					"WHERE cmi.id = %s", 
					(invoice_item_id, invoice_item_id, row_id, row_id))
		for row in c.fetchall():
			self.credit_items_store[iter_][2] = row[0]
			self.credit_items_store[iter_][3] = row[1]
			self.credit_items_store[iter_][4] = row[2]
			self.credit_items_store[iter_][5] = row[3]
			self.credit_items_store[iter_][6] = row[4]
			self.credit_items_store[iter_][7] = row[5]
			self.credit_items_store[iter_][8] = row[6]
			self.credit_items_store[iter_][9] = row[7]
		self.calculate_totals ()

	def product_editing_started (self, renderer, combo, path):
		renderer_invoice = Gtk.CellRendererText()
		combo.pack_start(renderer_invoice, True)
		combo.add_attribute(renderer_invoice, "text", 2)
		renderer_date = Gtk.CellRendererText()
		combo.pack_start(renderer_date, True)
		combo.add_attribute(renderer_date, "text", 3)
		entry = combo.get_child()
		entry.set_completion(self.builder.get_object('product_completion'))
	
	def price_edited (self, cellrenderer, path, text):
		c = DB.cursor()
		iter_ = self.credit_items_store.get_iter(path)
		self.check_row_id (iter_)
		row_id = self.credit_items_store[iter_][0]
		invoice_item_id = self.credit_items_store[iter_][8]
		try:
			c.execute(	"WITH tax_cte AS "
							"(SELECT tr.rate / 100 AS rate "
							"FROM invoice_items AS ii "
							"JOIN tax_rates AS tr ON tr.id = ii.tax_rate_id "
							"WHERE ii.id = %s"
							") "
						"UPDATE credit_memo_items "
							"SET "
								"(price, "
								"ext_price, "
								"tax) "
							"= "
								"(%s, "
								"qty*%s, "
								"qty*%s*(SELECT rate FROM tax_cte)) "
							"WHERE id = %s "
							"RETURNING price::text, ext_price::text, tax::text", 
							(invoice_item_id, text, text, text, row_id))
		except psycopg2.DataError as e:
			self.show_message(str(e))
			DB.rollback()
			return
		for row in c.fetchall():
			price = row[0]
			ext_price = row[1]
			tax = row[2]
		self.credit_items_store[iter_][5] = price
		self.credit_items_store[iter_][6] = ext_price
		self.credit_items_store[iter_][7] = tax
		c.close ()
		self.calculate_totals ()

	def qty_edited (self, cellrenderertext, path, text):
		c = DB.cursor()
		iter_ = self.credit_items_store.get_iter(path)
		self.check_row_id (iter_)
		row_id = self.credit_items_store[iter_][0]
		invoice_item_id = self.credit_items_store[iter_][8]
		try:
			c.execute(	"WITH tax_cte AS "
							"(SELECT tr.rate / 100 AS rate "
							"FROM invoice_items AS ii "
							"JOIN tax_rates AS tr ON tr.id = ii.tax_rate_id "
							"WHERE ii.id = %s"
							") "
						"UPDATE credit_memo_items "
						"SET "
							"(qty, "
							"ext_price, "
							"tax) "
						"= "
							"(%s, "
							"%s*price, "
							"%s*price*(SELECT rate FROM tax_cte)) "
						"WHERE id = %s "
						"RETURNING qty::text, ext_price::text", 
						(invoice_item_id, text, text, text, row_id))
		except psycopg2.DataError as e:
			self.show_message(str(e))
			DB.rollback()
			return
		for row in c.fetchall():
			qty = row[0]
			ext_price = row[1]
		self.credit_items_store[iter_][1] = qty
		self.credit_items_store[iter_][6] = ext_price
		c.close()
		self.calculate_totals ()

	def tax_edited (self, cellrendererspin, path, text):
		iter_ = self.credit_items_store.get_iter(path)
		self.check_row_id (iter_)
		row_id = self.credit_items_store[iter_][0]
		try:
			self.cursor.execute("UPDATE credit_memo_items "
								"SET tax = %s "
								"WHERE id = %s "
								"RETURNING tax::text", 
								(text, row_id))
		except psycopg2.DataError as e:
			self.show_message(str(e))
			DB.rollback()
			return
		for row in self.cursor.fetchall():
			tax = row[0]
		self.credit_items_store[iter_][7] = tax
		self.calculate_totals ()

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def calculate_totals (self ):
		c = DB.cursor()
		c.execute(	"WITH cte AS "
						"(SELECT "
							"SUM(ext_price) AS subtotal, "
							"SUM(tax) AS tax, "
							"SUM(tax + ext_price) AS total "
						"FROM credit_memo_items WHERE "
							"(credit_memo_id, deleted) = (%s, False) "
						")"
					"UPDATE credit_memos "
					"SET "
						"(total, "
						"tax, "
						"amount_owed) "
					"= "
						"((SELECT subtotal FROM cte),"
						"(SELECT tax FROM cte),"
						"(SELECT total FROM cte)"
						")"
					"WHERE id = %s "
					"RETURNING "
						"total::money, "
						"tax::money, "
						"amount_owed::money", 
						(self.credit_memo_id, self.credit_memo_id))
		for row in c.fetchall():
			subtotal = row[0]
			tax = row[1]
			total = row[2]
			self.builder.get_object('subtotal_entry').set_text(subtotal)
			self.builder.get_object('tax_entry').set_text(tax)
			self.builder.get_object('total_entry').set_text(total)
		c.close()
		DB.commit()
		self.credit_memo_template = None # credit memo changed, force regenerate

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

	def select_customer (self, customer_id):
		self.customer_id = customer_id
		self.cursor.execute("SELECT "
								"address, "
								"COALESCE(cm.id, NULL), "
								"COALESCE(-total, -0.00)::money, "
								"COALESCE(-tax, -0.00)::money, "
								"COALESCE(-amount_owed, -0.00)::money, "
								"COALESCE(dated_for, now()), "
								"COALESCE(comments, '') "
							"FROM contacts AS c "
							"LEFT JOIN credit_memos AS cm "
							"ON cm.customer_id = c.id AND cm.posted = False "
							"WHERE c.id = %s", 
							(customer_id,))
		for row in self.cursor.fetchall():
			address = row[0]
			self.credit_memo_id = row[1]
			subtotal = row[2]
			tax = row[3]
			total = row[4]
			self.date = row[5] 
			comments = row[6]
			self.builder.get_object('address_entry').set_text(address)
			self.builder.get_object('subtotal_entry').set_text(subtotal)
			self.builder.get_object('tax_entry').set_text(tax)
			self.builder.get_object('total_entry').set_text(total)
			self.date_calendar.set_date (self.date)
			self.builder.get_object('comments_buffer').set_text(comments)
		self.populate_credit_memo ()
		self.populate_product_store ()
		self.builder.get_object('menuitem2').set_sensitive(True)
		self.builder.get_object('button1').set_sensitive(True)
		self.builder.get_object('button2').set_sensitive(True)
		self.builder.get_object('comments_textview').set_sensitive(True)

	def populate_credit_memo (self):
		c = DB.cursor()
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
						"format_date(date_returned) " 
					"FROM credit_memo_items AS cmi "
					"JOIN invoice_items AS ili ON ili.id = cmi.invoice_item_id "
					"JOIN products AS p ON p.id = ili.product_id "
					"WHERE (credit_memo_id, cmi.deleted) = (%s, False) "
					"ORDER BY cmi.id", 
					(self.credit_memo_id,))
		for row in c.fetchall():
			self.credit_items_store.append(row)
		c.close()

	def populate_product_store(self, m=None, i=None):
		self.product_store.clear()
		c = DB.cursor()
		c.execute("SELECT ili.id::text, p.name || '  {' || ext_name || '}', "
					"i.id::text, format_date(i.dated_for) "
					"FROM products AS p "
					"JOIN invoice_items AS ili ON ili.product_id = p.id "
					"JOIN invoices AS i ON ili.invoice_id = i.id "
					"WHERE (customer_id, posted) = (%s, True) "
					"ORDER BY p.name", (self.customer_id,))
		for row in c.fetchall():
			self.product_store.append(row)
		c.close()

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
		row_id = self.credit_items_store[_iter][0]
		self.cursor.execute("UPDATE credit_memo_items "
							"SET date_returned = %s "
							"WHERE id = %s "
							"RETURNING date_returned::text, "
								"format_date (date_returned)", 
							(date, row_id))
		for row in self.cursor.fetchall():
			date = row[0]
			date_formatted = row[1]
			self.credit_items_store[_iter][10] = str(date)
			self.credit_items_store[_iter][11] = date_formatted

	def date_entry_icon_released (self, entry, icon, position):
		self.date_calendar.set_relative_to(entry)
		self.date_calendar.show_all()

	def day_selected (self, calendar):
		self.date = calendar.get_date()
		text = calendar.get_text()
		self.builder.get_object('entry1').set_text(text)
		if self.credit_memo_id:
			self.cursor.execute("UPDATE credit_memos "
								"SET dated_for = %s "
								"WHERE id = %s", 
								(self.date, self.credit_memo_id))
			DB.commit()

	def date_returned_editing_started (self, renderer, entry, path):
		self.path = path
		current_date = self.credit_items_store[path][10]
		self.date_returned_calendar.set_date(current_date)
		GLib.idle_add(self.date_returned_calendar.show_all)
		entry.destroy()

	def check_row_id (self, _iter):
		c = DB.cursor()
		row_id = self.credit_items_store[_iter][0]
		qty = self.credit_items_store[_iter][1]
		price = self.credit_items_store[_iter][5]
		tax = self.credit_items_store[_iter][7]
		invoice_item_id = self.credit_items_store[_iter][8]
		if row_id == 0:
			c.execute(	"INSERT INTO credit_memo_items "
							"(qty, "
							"invoice_item_id, "
							"price, "
							"tax, "
							"date_returned, "
							"credit_memo_id) "
						"VALUES "
							"(%s, %s, %s, %s, %s, %s) RETURNING id", 
						(qty, 
						invoice_item_id, 
						price, 
						tax, 
						self.date, 
						self.credit_memo_id))
			row_id = c.fetchone()[0]
			self.credit_items_store[_iter][0] = row_id
		DB.commit()
		c.close()

	def new_item_clicked (self, button):
		c = DB.cursor()
		self.check_credit_memo_id()
		invoice_item_id = self.product_store[0][0]
		c.execute("SELECT "
						"0, "
						"1.0::text, "
						"p.id, "
						"p.name, "
						"p.ext_name, "
						"price::text, "
						"price::text, "
						"ROUND(1.0 * price * tr.rate/100, 2)::text, "
						"ii.id, "
						"ii.invoice_id, "
						"CURRENT_DATE::text, "
						"format_date(CURRENT_DATE) " 
					"FROM invoice_items AS ii "
					"JOIN products AS p ON p.id = ii.product_id "
					"JOIN tax_rates AS tr ON tr.id = ii.tax_rate_id "
					"WHERE ii.id = %s LIMIT 1", 
					(invoice_item_id,))
		for row in c.fetchall():
			iter_ = self.credit_items_store.append(row)
			treeview = self.builder.get_object('treeview1')
			column = treeview.get_column(0)
			path = self.credit_items_store.get_path(iter_)
			treeview.set_cursor(path, column, True)
	
	def delete_item_clicked (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return 
		row_id = model[path][0]
		self.cursor.execute("UPDATE credit_memo_items "
							"SET deleted = True "
							"WHERE id = %s", (row_id,))
		DB.commit()
		self.populate_credit_memo ()
		
	def treeview_key_release_event (self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab" or keyname=="Esc":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.idle_add(treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass 

	def check_credit_memo_id (self):
		if self.credit_memo_id == None:
			self.cursor.execute("INSERT INTO credit_memos "
								"(name, customer_id, date_created, dated_for, total) "
								"VALUES ('Credit Memo', %s, now(), %s, 0.00) "
								"RETURNING id", (self.customer_id, self.date))
			self.credit_memo_id = self.cursor.fetchone()[0]
			DB.commit()

	def post_credit_memo_clicked (self, button):
		import credit_memo_template as cmt
		self.credit_memo_template = cmt.Setup(
												self.credit_items_store,
												self.credit_memo_id,
												self.customer_id)
		self.credit_memo_template.print_pdf(self.window)
		self.credit_memo_template.post()
		DB.commit()
		self.window.destroy()

	def view_document_activated (self, button):
		if not self.credit_memo_template:
			import credit_memo_template as cmt
			self.credit_memo_template = cmt.Setup(
													self.credit_items_store,
													self.credit_memo_id,
													self.customer_id)
		self.credit_memo_template.view_odt()
	
	def comments_buffer_changed (self, textbuffer):
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		notes = textbuffer.get_text(start, end, True)
		self.cursor.execute("UPDATE credit_memos SET comments = %s "
							"WHERE id = %s", 
							(notes,  self.credit_memo_id))
		DB.commit()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()






		
