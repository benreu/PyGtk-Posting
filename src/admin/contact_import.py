#
# contact_import.py
# Copyright (C) 2016 Reuben Rissler
# 
# contact_import is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# contact_import is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk
import xlrd
from xlrd.biffh import XLRDError
from constants import DB, ui_directory

UI_FILE = ui_directory + "/admin/contact_import.ui"


class ContactsImportGUI:
	error = None
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_combos()

	def populate_combos (self):
		markup_combo = self.builder.get_object('markup_combo')
		c = DB.cursor()
		c.execute("SELECT id::text, name "
					"FROM customer_markup_percent "
					"WHERE deleted = False ORDER BY name")
		for row in c.fetchall():
			markup_combo.append(row[0], row[1])
		markup_combo.set_active(0)
		terms_combo = self.builder.get_object('terms_combo')
		c.execute("SELECT id::text, name "
					"FROM terms_and_discounts WHERE deleted = False "
					"ORDER BY name")
		for row in c.fetchall():
			terms_combo.append(row[0], row[1])
		terms_combo.set_active(0)
		c.close()
		DB.rollback()

####### start import to treeview

	def load_xls (self, filename):
		store = self.builder.get_object('xls_import_store')
		store.clear()
		try:
			book = xlrd.open_workbook(filename)
		except XLRDError as e:
			self.error = e
			return False
		try:
			sheet = book.sheet_by_name ('Contacts')
		except XLRDError as e:
			self.error = e
			return False
		for i in range(sheet.nrows):
			if i == 0:
				continue # skip the header
			try:
				xls_row = sheet.row(i)
				name = xls_row[0].value
				ext_name = xls_row[1].value
				address = xls_row[2].value
				city = xls_row[3].value
				state = xls_row[4].value
				zip_ = xls_row[5].value
				fax = xls_row[6].value
				phone = xls_row[7].value
				email = xls_row[8].value
				misc = xls_row[9].value
				tax_number = xls_row[10].value
				customer = xls_row[11].value
				vendor = xls_row[12].value
				employee = xls_row[13].value
				service_provider = xls_row[14].value
				custom1 = xls_row[15].value
				custom2 = xls_row[16].value
				custom3 = xls_row[17].value
				custom4 = xls_row[18].value
				notes = xls_row[19].value
			except Exception as e:
				self.error = str(e) + "\n\nPlease export some data from Posting and match that format.\nHint : You are missing one or more columns."
				return False
			try:
				zip_code = str(int(zip_))
			except Exception:
				zip_code = str(zip_)
			try:
				store.append([	str(name), 
								str(ext_name),
								str(address),
								str(city),
								str(state),
								zip_code,
								str(fax),
								str(phone),
								str(email),
								str(misc),
								str(tax_number),
								bool(customer),
								bool(vendor),
								bool(employee),
								bool(service_provider),
								str(custom1),
								str(custom2),
								str(custom3),
								str(custom4),
								str(notes)    ])
			except Exception as e:
				self.error = str(e) + "\n\nPlease export some data from Posting and match that format.\nHint : You have wrong cell data."
				return False
		return True

####### end import to treeview

	def treeview_button_press_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('right click menu')
			menu.popup_at_pointer()
			treeview.stop_emission_by_name('button-press-event')

	def delete_contact_activated (self, menu):
		selection = self.builder.get_object('xls_import_selection')
		model, paths = selection.get_selected_rows ()
		if paths == []:
			return
		for path in reversed(paths): # remove last rows first
			iter_ = model.get_iter(path)
			model.remove(iter_)

	def import_clicked (self, button):
		term_id = self.builder.get_object('terms_combo').get_active_id()
		markup_id = self.builder.get_object('markup_combo').get_active_id()
		model = self.builder.get_object('xls_import_store')
		c = DB.cursor()
		for row in model:
			c.execute ("INSERT INTO contacts ("
												"name, "
												"ext_name, "
												"address, "
												"city, "
												"state, "
												"zip, "
												"fax, "
												"phone, "
												"email, "
												"label, "
												"tax_number, "
												"customer, "
												"vendor, "
												"employee, "
												"service_provider, "
												"custom1, "
												"custom2, "
												"custom3, "
												"custom4, "
												"notes, "
												"terms_and_discounts_id, "
												"markup_percent_id )"
						"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
								"%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s ) "
						"RETURNING id",
						(row[0],row[1],row[2],row[3],row[4],row[5],row[6],
						row[7],row[8],row[9],row[10],row[11],row[12],row[13],
						row[14],row[15],row[16],row[17],row[18],row[19],
						term_id, markup_id))
			contact_id = c.fetchone()[0]
			c.execute("WITH cte AS "
							"(SELECT %s AS contact_id, id FROM mailing_lists "
							"WHERE auto_add = True) "
						"INSERT INTO mailing_list_register "
						"(contact_id, mailing_list_id) "
						"SELECT contact_id, id FROM cte "
						"ON CONFLICT (contact_id, mailing_list_id) "
						"DO NOTHING", (contact_id,))
		c.close()
		DB.commit()
		
	def text_renderer_edited (self, text_renderer, path, new_text):
		treeview = self.builder.get_object('xls_treeview')
		path, column = treeview.get_cursor()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id()
		model[path][col_index] = new_text

	def boolean_renderer_toggled (self, toggle_renderer, path):
		treeview = self.builder.get_object('xls_treeview')
		old_path, column = treeview.get_cursor ()
		model = treeview.get_model ()
		col_index = column.get_sort_column_id ()
		model[path][col_index] = not model[path][col_index]

	def destroy (self, window = None):
		self.window.destroy()

