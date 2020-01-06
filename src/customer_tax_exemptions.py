# customer_tax_exemptions.py
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

from gi.repository import Gtk, GdkPixbuf, Gdk, GLib
import os, sys, subprocess
from datetime import datetime
from constants import ui_directory, DB, help_dir

UI_FILE = ui_directory + "/customer_tax_exemptions.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class CustomerTaxExemptionsGUI:
	def __init__(self, window, customer_id):

		self.customer_id = customer_id
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.cursor.execute("SELECT name FROM contacts WHERE id = %s",
							(customer_id,))
		customer_name = self.cursor.fetchone()[0]
		self.builder.get_object('label1').set_label("Tax exemptions for '%s'" 
													% customer_name)
		self.tax_exemption_store =self.builder.get_object('tax_exemption_store')
		
		self.populate_treeview ()

		self.dialog = self.builder.get_object('dialog1')
		self.dialog.set_transient_for(window)
		self.dialog.run()
		self.dialog.hide()

	def destroy (self, widget):
		self.cursor.close()

	def help_clicked (self, widget):
		subprocess.Popen(["yelp", help_dir + "/tax_exemptions.page"])

	def populate_treeview (self):
		self.tax_exemption_store.clear()
		self.cursor.execute("SELECT tax_rates.id, tax_rates.name "
							"FROM tax_rates "
							"WHERE tax_rates.exemption = True "
							,(self.customer_id,))
		for row in self.cursor.fetchall():
			exemption_id = str(row[0])
			exemption_name = row[1]
			self.cursor.execute("SELECT id FROM customer_tax_exemptions "
								"WHERE (customer_id, tax_rate_id) = (%s, %s)",
								(self.customer_id, exemption_id))
			for row in self.cursor.fetchall():
				self.tax_exemption_store.append([exemption_id,
											exemption_name, True])
				break
			else:
				self.tax_exemption_store.append([exemption_id,
											exemption_name, False])
		DB.rollback()

	def regenerate_exemption_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			tax_id = model[path][0]
			GLib.timeout_add(10 , self.open_exemption, tax_id)
		
	def available_toggled (self, renderer, path):
		available = not self.tax_exemption_store[path][2]
		tax_id = self.tax_exemption_store[path][0]
		if available == True:
			self.tax_exemption_store[path][2] = available
			self.cursor.execute("INSERT INTO customer_tax_exemptions "
							"(tax_rate_id, customer_id) VALUES (%s, %s)", 
							(tax_id, self.customer_id))
			GLib.timeout_add(10 , self.open_exemption, tax_id)
			DB.commit()
		else:
			dialog = self.builder.get_object('dialog2')
			dialog.run()
			dialog.hide()
			#self.cursor.execute("DELETE FROM customer_tax_exemptions WHERE "
			#				"(tax_rate_id, customer_id) = (%s, %s)", 
			#				(tax_id, self.customer_id))

	def open_exemption (self, tax_id):
		self.cursor.execute("SELECT exemption_template_path FROM tax_rates "
							"WHERE id = %s", (tax_id,))
		template_path = self.cursor.fetchone()[0]
		if template_path == None:
			return # no template set
		template_file_name = template_path.split("/")[-1]
		exemption_template = "./templates/%s" % template_file_name
		self.cursor.execute("SELECT * FROM contacts WHERE id = (%s)",
													[self.customer_id])
		customer = Item()
		for row in self.cursor.fetchall():
			customer.name = row[1]
			customer.ext_name = row[2]
			customer.address = row[3]
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
			company.address = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
			company.tax_number = row[11]
		date = Item()
		today = str(datetime.today())
		date.day = today[8:10]
		date.year = today[0:4]
		date.month = today[5:7]
		data = dict(date = date, customer = customer, company = company)
		from py3o.template import Template #import for every invoice or there is an error about invalid magic header numbers
		t = Template(exemption_template, "/tmp/%s" % template_file_name , True)
		t.render(data) #the self.data holds all the info of the invoice
		subprocess.Popen("soffice /tmp/%s" % template_file_name, shell = True)
		




		
