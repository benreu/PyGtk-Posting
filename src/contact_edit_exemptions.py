# contact_exemptions.py
#
# Copyright (C) 2019 - Reuben
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
import psycopg2, subprocess
from constants import ui_directory, DB

UI_FILE = ui_directory + "/contact_edit_exemptions.ui"

class ContactEditExemptionsGUI(Gtk.Builder):
	def __init__(self, contact_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.contact_id = contact_id
		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_tax_exemptions()

	def destroy (self, widget):
		self.cursor.close()
		DB.rollback()

	def populate_tax_exemptions (self):
		tax_exemption_store = self.get_object("tax_exemption_store")
		tax_exemption_store.clear()
		c = DB.cursor()
		try:
			c.execute("SELECT "
							"tax_rates.id, "
							"tax_rates.name, "
							"cte.id, "
							"TRUE, "
							"cte.pdf_available "
						"FROM customer_tax_exemptions AS cte "
						"JOIN tax_rates "
						"ON cte.tax_rate_id = tax_rates.id "
						"AND cte.customer_id = %s "
						"WHERE tax_rates.exemption = True "
						"ORDER BY tax_rates.name FOR UPDATE NOWAIT",
						(self.contact_id, ))
		except psycopg2.OperationalError as e:
			DB.rollback()
			error = str(e) + "Hint: somebody else is editing these exemptions"
			self.show_message (error)
			self.window.destroy()
			return
		for row in c.fetchall():
			tax_exemption_store.append(row)
		c.execute("SELECT "
						"tax_rates.id, "
						"tax_rates.name, "
						"0, "
						"FALSE, "
						"FALSE "
						"FROM tax_rates WHERE tax_rates.id NOT IN "
							"(SELECT tax_rate_id "
							"FROM customer_tax_exemptions "
							"WHERE customer_id = %s) ORDER BY name",
					(self.contact_id, ))
		for row in c.fetchall():
			tax_exemption_store.append(row)
		c.close()
				
	def add_exemption_clicked (self, widget):
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		exemption_id = model[path][0]
		import pdf_attachment
		paw = pdf_attachment.PdfAttachmentWindow(self.window)
		paw.window.set_modal(True)
		paw.connect("pdf_optimized", self.optimized_callback, exemption_id)
	
	def optimized_callback (self, pdf_attachment_window, exemption_id):
		binary = pdf_attachment_window.get_pdf ()
		selection = self.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		if model[path][3] == False:
			self.cursor.execute("INSERT INTO customer_tax_exemptions "
								"(pdf_data, customer_id, tax_rate_id, "
								"pdf_available) "
								"VALUES (%s, %s, %s, True) ",
								(binary, self.contact_id, exemption_id))
		else:
			self.cursor.execute("UPDATE customer_tax_exemptions "
								"SET (pdf_data, pdf_available) = "
								"(%s, True) "
								"WHERE (customer_id, tax_rate_id) = "
								"(%s, %s)", 
								(binary, self.contact_id, exemption_id))
		DB.commit()
		self.populate_tax_exemptions ()

	def view_exemption_clicked (self, button):
		exemption_selection = self.get_object('treeview-selection2')
		model, path = exemption_selection.get_selected_rows ()
		if model[path][4] == False:
			self.show_message("No exemption file scanned yet")
			return # no exemption file available
		customer_exemption_id = model[path][2]
		self.cursor.execute("SELECT pdf_data FROM customer_tax_exemptions "
							"WHERE id = %s", (customer_exemption_id,))
		for row in self.cursor.fetchall():
			pdf_data = row[0]
			with open("/tmp/exemption.pdf",'wb') as f:
				f.write(pdf_data)
			subprocess.Popen(["xdg-open", "/tmp/exemption.pdf"])

	def close_clicked (self, button):
		self.window.destroy()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()








	