# contact_hub.py
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
import constants

UI_FILE = constants.ui_directory + "/contact_hub.ui"

class ContactHubGUI:
	def __init__(self, contact_id):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.contact_id = contact_id
		self.cursor = self.db.cursor()
		self.cursor.execute("SELECT name, vendor, customer, service_provider "
							"FROM contacts WHERE id = %s", (contact_id,))
		for row in self.cursor.fetchall():
			self.name = row[0]
			self.builder.get_object('button4').set_sensitive(row[1])
			self.builder.get_object('button2').set_sensitive(row[2])
			self.builder.get_object('button7').set_sensitive(row[2])
			break
		else:
			raise Exception ("Contact not found")
		self.builder.get_object('label1').set_label(self.name)
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, window):
		self.cursor.close()

	def invoice_to_payment_matching_clicked (self, button):
		from reports import invoice_to_payment_matching
		i = invoice_to_payment_matching.GUI()
		i.builder.get_object('combobox1').set_active_id(self.contact_id)
		self.window.destroy()

	def cancel_clicked (self, button):
		self.window.destroy()

	def edit_contact_clicked (self, button):
		import contacts
		c = contacts.GUI (self.contact_id)
		c.select_contact ()
		self.window.destroy()

	def job_sheet_history_clicked (self, button):
		from reports import job_sheet_history
		j = job_sheet_history.JobSheetHistoryGUI()
		j.builder.get_object('searchentry1').set_text(self.name)
		self.window.destroy()

	def contact_history_clicked (self, button):
		from reports import contact_history
		c = contact_history.ContactHistoryGUI()
		c.get_object('combobox1').set_active_id(str(self.contact_id))
		self.window.destroy()

	def customer_invoices_clicked (self, button):
		from reports import invoice_history
		i = invoice_history.InvoiceHistoryGUI()
		i.get_object('combobox1').set_active_id(str(self.contact_id))
		self.window.destroy()

	def vendor_po_clicked (self, button):
		from reports import vendor_history
		v = vendor_history.VendorHistoryGUI()
		v.builder.get_object('combobox1').set_active_id(str(self.contact_id))
		self.window.destroy()

	def customer_payments_clicked (self, button):
		from reports import payments_received
		p = payments_received.PaymentsReceivedGUI()
		p.builder.get_object('combobox1').set_active_id(str(self.contact_id))
		self.window.destroy()


		
