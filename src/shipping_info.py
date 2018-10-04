# shipping_info.py
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
import main

UI_FILE = main.ui_directory + "/shipping_info.ui"

class ShippingInfoGUI:
	def __init__ (self, main_class):

		self.db = main_class.db
		self.cursor = self.db.cursor()
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.customer_store = self.builder.get_object('customer_store')
		self.invoice_store = self.builder.get_object('invoice_store')
		self.cursor.execute("SELECT "
								"c.id::text, c.name, c.ext_name "
							"FROM invoices AS i "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE i.canceled = False "
							"GROUP BY c.id, c.name, c.ext_name")
		for row in self.cursor.fetchall():
			self.customer_store.append(row)
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		
		self.window = self.builder.get_object('window')
		self.window.show_all()

	def help_clicked (self, button):
		print ('please add help to shipping info')

	def customer_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter_][1].lower():
				return False
		return True

	def customer_changed (self, combobox):
		customer_id = combobox.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			self.populate_invoices()
			self.populate_shipping_history ()

	def customer_match_selected (self, entrycompletion, treemodel, treeiter):
		self.customer_id = treemodel[treeiter][0]
		self.populate_invoices()

	def invoice_match_selected (self, entrycompletion, treemodel, treeiter):
		self.invoice_id = treemodel[treeiter][0]
		self.builder.get_object('tracking_number_button').set_sensitive(True)

	def populate_invoices (self):
		self.invoice_store.clear()
		self.cursor.execute("SELECT "
								"i.id::text, i.name "
							"FROM invoices AS i "
							"WHERE (i.canceled, i.customer_id) = (False, %s) "
							"ORDER BY i.id"
							, (self.customer_id,))
		for row in self.cursor.fetchall():
			self.invoice_store.append(row)

	def tracking_number_changed (self, entry):
		self.builder.get_object('tracking_number_button').set_sensitive(True)

	def invoice_changed (self, combobox):
		invoice_id = combobox.get_active_id()
		if invoice_id != None:
			self.invoice_id = invoice_id
			self.builder.get_object('tracking_number_button').set_sensitive(True)

	def add_tracking_number_clicked (self, button):
		tracking_number = self.builder.get_object('entry1').get_text()
		try:
			self.cursor.execute("INSERT INTO shipping_info "
							"(tracking_number, invoice_id) "
							"VALUES (%s, %s)", 
							(tracking_number, self.invoice_id))
			self.db.commit()
		except Exception as e:
			self.show_message(str(e))
			self.db.rollback()
		self.builder.get_object('tracking_number_button').set_sensitive(False)
		self.populate_shipping_history()

	def populate_shipping_history (self):
		store = self.builder.get_object('shipping_history_store')
		store.clear()
		self.cursor.execute("SELECT "
								"sh.id, i.id, sh.tracking_number "
							"FROM shipping_info AS sh "
							"JOIN invoices AS i ON i.id = sh.invoice_id "
							"WHERE i.customer_id = %s ",
							(self.customer_id,))
		for row in self.cursor.fetchall():
			store.append(row)

	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()
		


