# product_serial_numbers.py
#
# Copyright (C) 2017 - reuben
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
from dateutils import DateTimeCalendar
import psycopg2
from constants import db, ui_directory, broadcaster
import constants

UI_FILE = ui_directory + "/product_serial_numbers.ui"

class ProductSerialNumbersGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()
		self.product_store = self.get_object('product_store')
		self.contact_store = self.get_object('contact_store')
		self.handler_ids = list()
		for connection in (("products_changed", self.populate_product_store ),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		product_completion = self.get_object('add_product_completion')
		product_completion.set_match_func(self.product_match_func)
		product_completion = self.get_object('event_product_completion')
		product_completion.set_match_func(self.product_match_func)
		contact_completion = self.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		self.product_name = ''
		self.contact_name = ''
		self.serial_number = ''
		self.filtered_store = self.get_object('serial_number_treeview_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.product_id = 0
		self.populate_product_store()
		self.populate_contact_store()
		self.populate_serial_number_history()
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def search_changed (self, entry):
		'''This signal is hooked up to all search entries'''
		self.product_name = self.get_object('searchentry2').get_text().lower()
		self.contact_name = self.get_object('searchentry3').get_text().lower()
		self.serial_number = self.get_object('searchentry4').get_text().lower()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		for i in self.product_name.split():
			if i not in model[tree_iter][1].lower():
				return False
		for i in self.serial_number.split():
			if i not in model[tree_iter][2].lower():
				return False
		return True

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry3').set_text(day_text)
		self.get_object('entry4').set_text(day_text)
		
	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True
		
	def contact_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[tree_iter][1].lower():
				return False
		return True
		
	def populate_product_store (self, m=None, i=None):
		self.product_store.clear()
		self.cursor.execute("SELECT id::text, name, invoice_serial_numbers "
							"FROM products "
							"WHERE (deleted, stock, sellable) = "
							"(False, True, True) ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		
	def populate_contact_store (self, m=None, i=None):
		self.contact_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)

	def populate_serial_number_history (self):
		store = self.get_object('serial_number_treeview_store')
		store.clear()
		self.cursor.execute("SELECT "
								"sn.id, "
								"p.name, "
								"sn.serial_number, "
								"sn.date_inserted::text, "
								"format_date(sn.date_inserted), "
								"COALESCE(COUNT(snh.id)::text, ''), "
								"COALESCE(ili.invoice_id::text, ''), "
								"COALESCE(poli.purchase_order_id::text, ''), "
								"COALESCE(manufacturing_id::text, '') "
							"FROM serial_numbers AS sn "
							"JOIN products AS p ON p.id = sn.product_id "
							"LEFT JOIN serial_number_history AS snh "
								"ON snh.serial_number_id = sn.id "
							"LEFT JOIN invoice_items AS ili "
								"ON ili.id = sn.invoice_item_id "
							"LEFT JOIN purchase_order_line_items AS poli "
								"ON poli.id = purchase_order_line_item_id "
							"GROUP BY sn.id, p.name, sn.serial_number, "
								"sn.date_inserted, invoice_id, poli.id, "
								"manufacturing_id "
							"ORDER BY sn.id")
		for row in self.cursor.fetchall():
			store.append(row)

	def serial_number_treeview_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		serial_id = model[path][0]
		self.populate_serial_event_store(serial_id)

	def populate_serial_event_store (self, serial_id):
		store = self.get_object('events_store')
		store.clear()
		self.cursor.execute("SELECT "
								"snh.id, "
								"c.name, "
								"snh.date_inserted::text, "
								"format_date(snh.date_inserted), "
								"snh.description "
							"FROM serial_number_history AS snh "
							"JOIN contacts AS c ON c.id = snh.contact_id "
							"WHERE serial_number_id = %s", (serial_id,))
		for row in self.cursor.fetchall():
			store.append(row)

	def add_serial_event_clicked (self, button):
		dialog = self.get_object('event_dialog')
		response = dialog.run ()
		if response == Gtk.ResponseType.ACCEPT:
			serial_number = self.get_object('entry2').get_text()
			buf = self.get_object('textbuffer1')
			start_iter = buf.get_start_iter()
			end_iter = buf.get_end_iter()
			description = buf.get_text(start_iter, end_iter, True)
			self.cursor.execute("INSERT INTO serial_number_history "
								"(contact_id, "
								"date_inserted, description, serial_number_id) "
								"VALUES (%s, %s, %s, %s)", 
								(self.contact_id, self.date, 
								description, self.serial_id))
			self.db.commit()
			self.populate_serial_number_history ()
			self.get_object('combobox2').set_sensitive(False)
			self.get_object('combobox3').set_sensitive(False)
			self.get_object('textview1').set_sensitive(False)
			self.get_object('button4').set_sensitive(False)
			self.get_object('combobox-entry2').set_text('')
			self.get_object('combobox-entry4').set_text('')
			self.get_object('combobox-entry5').set_text('')
			self.get_object('textbuffer1').set_text('')
		dialog.hide()

	def add_serial_number_dialog_clicked (self, button):
		dialog = self.get_object('add_serial_number_dialog')
		response = dialog.run ()
		if response == Gtk.ResponseType.ACCEPT:
			self.populate_serial_number_history ()
		dialog.hide()
		self.get_object('label10').set_text('')

	def add_serial_number_clicked (self, button):
		serial_number = self.get_object('entry2').get_text()
		try:
			self.cursor.execute("INSERT INTO serial_numbers "
								"(product_id, serial_number, "
								"date_inserted) "
								"VALUES (%s, %s, %s)", 
								(self.product_id, serial_number, self.date))
			self.db.commit()
			dialog = self.get_object('add_serial_number_dialog')
			dialog.response(Gtk.ResponseType.ACCEPT)
		except psycopg2.IntegrityError as e:
			self.get_object('label10').set_text(str(e))
			self.db.rollback()

	def refresh_clicked (self, button):
		self.populate_serial_number_history ()

	def date_entry_icon_released (self, entry, icon, event):
		self.calendar.set_relative_to (entry)
		self.calendar.show()

	def event_product_match_selected(self, completion, model, iter_):
		product_id = model[iter_][0]
		self.get_object('combobox1').set_active_id(product_id)
		self.get_object('combobox4').set_active_id(product_id)

	def add_product_match_selected(self, completion, model, iter_):
		product_id = model[iter_][0]
		self.get_object('combobox1').set_active_id(product_id)
		self.get_object('combobox4').set_active_id(product_id)

	def event_product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.get_object('combobox2').set_sensitive(True)
			store = self.get_object('serial_number_store')
			store.clear()
			self.cursor.execute("SELECT id::text, serial_number "
								"FROM serial_numbers "
								"WHERE product_id = %s", (product_id,))
			for row in self.cursor.fetchall():
				store.append(row)

	def add_product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.product_id = product_id
			self.get_object('entry2').set_sensitive(True)

	def contact_match_selected (self, completion, model, iter_):
		contact_id = model[iter_][0]
		if contact_id != None:
			self.contact_id = contact_id
			self.get_object('textview1').set_sensitive(True)

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
			self.get_object('textview1').set_sensitive(True)

	def add_serial_number_changed (self, entry):
		self.get_object('button2').set_sensitive(True)

	def serial_number_match_selected (self, completion, model, iter_):
		serial_number = model[iter_][0]
		self.get_object('combobox2').set_active_id(serial_number)

	def event_serial_number_changed (self, combobox):
		serial_id = combobox.get_active_id()
		if serial_id != None:
			self.serial_id = serial_id
			self.get_object('combobox3').set_sensitive(True)

	def event_description_changed (self, entry):
		self.get_object('button4').set_sensitive(True)



		
		
