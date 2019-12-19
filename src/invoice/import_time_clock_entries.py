# import_time_clock_entries.py
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


from gi.repository import Gtk
from datetime import datetime
from pricing import get_customer_product_price
from constants import ui_directory, DB

UI_FILE = ui_directory + "/invoice/import_time_clock_entries.ui"

class ImportGUI():
	def __init__(self, contact_id, invoice_id):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.contact_id = contact_id
		self.invoice_id = invoice_id

		self.import_store = self.builder.get_object('import_store')
		self.product_store = self.builder.get_object('product_store')
		self.populate_time_clock_import_store()
		self.populate_product_store ()
		self.calculate_total_time ()
		completion = self.builder.get_object('product_completion')
		completion.set_match_func(self.product_match_string)

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def product_match_string(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[iter][1].lower():
				return False
		return True

	def populate_time_clock_import_store (self):
		c = DB.cursor()
		c.execute("SELECT "
						"entry.id, "
						"project.name, "
						"EXTRACT(epoch FROM (stop_time - start_time))::bigint, "
						"(stop_time - start_time)::text, "
						"stop_time::text, "
						"format_timestamp(stop_time), "
						"True "
					"FROM time_clock_entries AS entry "
					"JOIN time_clock_projects AS project "
					"ON project.id = entry.project_id "
					"JOIN job_sheets "
					"ON job_sheets.id = project.job_sheet_id "
					"JOIN contacts "
					"ON contacts.id = job_sheets.contact_id "
					"WHERE (job_sheets.contact_id, entry.running, "
						"entry.invoiced) = "
					"(%s, False, False) ORDER BY start_time", 
					(self.contact_id,))
		for row in c.fetchall():
			self.import_store.append(row)
		c.close()
		DB.rollback()

	def product_combo_changed (self, combo):
		self.product_id = combo.get_active_id()
		self.builder.get_object('button3').set_sensitive(True)

	def product_match_selected (self, completion, model, iter_):
		product_id = model[iter_][0]
		self.builder.get_object('combobox1').set_active_id(product_id)

	def unselect_all_clicked (self, button):
		for row in self.import_store:
			row[6] = False

	def select_all_clicked (self, button):
		for row in self.import_store:
			row[6] = True

	def post_to_invoice_clicked (self, button):
		price = get_customer_product_price (self.contact_id, self.product_id)
		ext_price = round(float(self.invoicing_time ) * float(price), 2)
		description = self.builder.get_object('entry1').get_text()
		self.cursor.execute("INSERT INTO invoice_items "
							"(invoice_id, qty, product_id, price, ext_price, "
							"remark, canceled, imported) "
							"VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
							"RETURNING id", 
							(self.invoice_id, self.invoicing_time, 
							self.product_id, price, ext_price, description, 
							False, True))
		line_item_id = self.cursor.fetchone()[0]
		for row in self.import_store:
			if row[6] == True:
				row_id = row[0]
				self.cursor.execute("UPDATE time_clock_entries "
									"SET (invoiced, invoice_line_id) = "
									"(True, %s) WHERE id = %s", 
									(line_item_id, row_id))
		DB.commit()
		self.window.destroy()
					
	def populate_product_store (self):
		self.cursor.execute("SELECT id::text, name FROM products "
							"WHERE (sellable, purchasable, manufactured, "
							"deleted) = (True, False, False, False) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)
		DB.rollback()

	def import_renderer_toggled(self, cell_renderer, path):
		is_active = cell_renderer.get_active()
		self.import_store[path][6] = not is_active
		self.calculate_total_time ()

	def calculate_total_time (self):
		total_seconds = 0
		for row in self.import_store:
			import_row = row[6]
			if import_row is True:
				total_seconds += row[2]
		time, hours, minutes, seconds = self.convert_seconds(total_seconds)
		fractional_hours = int(minutes/6)
		if minutes % 6 != 0 or seconds % 60 != 0 :
			fractional_hours += 1 #round to the next .1 hour
		self.invoicing_time = str(hours) + "." + str(fractional_hours)
		self.builder.get_object('label2').set_label(time)
		self.builder.get_object('label4').set_label(self.invoicing_time)

	def convert_seconds(self, start_seconds):
		leftover_seconds = int(start_seconds) 
		hours = int(leftover_seconds / 3600)
		leftover_seconds = (leftover_seconds - (hours * 3600))
		minutes = int(leftover_seconds / 60)
		leftover_seconds = (leftover_seconds - (minutes * 60))
		seconds = int(leftover_seconds)
		if minutes < 10:
			minutes = "0" + str(minutes)
		if seconds < 10:
			seconds = "0" + str(seconds)
		time_string = str(hours) + ":" + str(minutes) + ":" + str(seconds)
		return time_string, hours, int(minutes), int(seconds)



