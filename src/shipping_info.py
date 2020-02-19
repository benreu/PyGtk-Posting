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
from dateutils import DateTimeCalendar
from constants import ui_directory, DB

UI_FILE = ui_directory + "/shipping_info.ui"

class ShippingInfoGUI(Gtk.Builder):
	shipping_description = None
	invoice_id = None
	incoming_invoice = None
	def __init__ (self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		
		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None

		self.contact_store = self.get_object('contact_store')
		self.invoice_store = self.get_object('invoice_store')
		self.cursor.execute("SELECT "
								"id::text, name, ext_name "
							"FROM contacts AS c "
							"WHERE deleted = False "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		DB.rollback()
		contact_completion = self.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		
		self.window = self.get_object('window')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def help_clicked (self, button):
		print ('please add help to shipping info')

	def contact_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def contact_changed (self, combobox):
		contact_id = combobox.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
			self.populate_invoices()
			self.populate_shipping_history ()

	def contact_match_selected (self, entrycompletion, treemodel, treeiter):
		self.contact_id = treemodel[treeiter][0]
		self.populate_invoices()
		self.populate_shipping_history ()

	def invoice_match_selected (self, entrycompletion, treemodel, treeiter):
		self.invoice_id = treemodel[treeiter][0]
		self.get_object('tracking_number_entry').set_sensitive(True)

	def shipping_description_changed (self, entry):
		description = entry.get_text()
		if description == '':
			self.get_object('tracking_number_entry').set_sensitive(False)
			self.shipping_description = None
		else:
			self.get_object('tracking_number_entry').set_sensitive(True)
			self.shipping_description = description

	def populate_invoices (self):
		self.get_object('shipping_description_entry').set_sensitive(True)
		self.invoice_store.clear()
		self.cursor.execute("SELECT "
								"i.id::text, i.name "
							"FROM invoices AS i "
							"WHERE (i.canceled, i.customer_id) = (False, %s) "
							"ORDER BY i.id"
							, (self.contact_id,))
		for row in self.cursor.fetchall():
			self.invoice_store.append(row)
		DB.rollback()

	def tracking_number_changed (self, entry):
		self.get_object('incoming_invoice_button').set_sensitive(True)

	def invoice_changed (self, combobox):
		invoice_id = combobox.get_active_id()
		if invoice_id != None:
			self.invoice_id = invoice_id
			self.get_object('tracking_number_entry').set_sensitive(True)

	def incoming_invoice_clicked (self, button):
		if not self.incoming_invoice:
			import incoming_invoice
			self.incoming_invoice = incoming_invoice.IncomingInvoiceGUI()
			self.incoming_invoice.window.set_transient_for (self.window)
			self.incoming_invoice.connect('invoice_applied', self.incoming_invoice_applied)
		else:
			self.incoming_invoice.window.show()

	def incoming_invoice_applied (self, incoming_invoice_object):
		self.incoming_invoice_id = incoming_invoice_object.invoice_id
		incoming_invoice_object.window.hide()
		self.get_object('tracking_number_button').set_sensitive(True)

	def add_tracking_number_clicked (self, button):
		c = DB.cursor()
		tracking_number = self.get_object('tracking_number_entry').get_text()
		try:
			c.execute("INSERT INTO shipping_info "
						"(date_shipped, tracking_number, reason, "
							"contact_id, invoice_id, incoming_invoice_id) "
						"VALUES (%s, %s, %s, %s, %s, %s)", 
						(self.date, tracking_number, self.shipping_description,
						self.contact_id, self.invoice_id, 
						self.incoming_invoice_id))
			DB.commit()
		except Exception as e:
			DB.rollback()
			self.show_message(str(e))
		self.get_object('tracking_number_button').set_sensitive(False)
		c.close()
		self.populate_shipping_history()

	def populate_shipping_history (self):
		store = self.get_object('shipping_history_store')
		store.clear()
		self.cursor.execute("SELECT "
								"sh.id, "
								"COALESCE(sh.invoice_id, 0), "
								"COALESCE(sh.invoice_id::text, 'N/A'), "
								"sh.tracking_number, "
								"sh.date_shipped::text, "
								"format_date(sh.date_shipped) "
							"FROM shipping_info AS sh "
							"WHERE sh.contact_id = %s ORDER BY date_shipped",
							(self.contact_id,))
		for row in self.cursor.fetchall():
			store.append(row)
		DB.rollback()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry2').set_text(day_text)
		self.get_object('contact_combo').set_sensitive(True)

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
		
	def shipping_history_clicked (self, button):
		from reports import shipping_history
		shipping_history.ShippingHistoryGUI()



