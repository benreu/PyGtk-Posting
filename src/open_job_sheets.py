# open_job_sheets.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
from invoice_window import create_new_invoice 
import constants

UI_FILE = constants.ui_directory + "/open_job_sheets.ui"


class OpenJobSheetsGUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()

		self.jobs_store = self.get_object('jobs_to_invoice_store')
		self.job_sheet_line_store = self.get_object("job_sheet_line_store")
		self.populate_job_store ()
		self.populate_contact_store ()
		
		self.window = self.get_object('window1')
		self.window.show_all()

	def populate_contact_store (self):
		store = self.get_object ('contact_store')
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"ORDER BY name, ext_name")
		for row in self.cursor.fetchall():
			store.append(row)

	def populate_job_store(self):
		self.jobs_store.clear()
		self.job_sheet_line_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
					"js.id, "
					"js.description, "
					"js.date_inserted::text, "
					"format_date(js.date_inserted), "
					"jt.name, "
					"c.id, "
					"c.name "
					"FROM job_sheets AS js "
					"JOIN contacts AS c ON c.id = js.contact_id "
					"JOIN job_types AS jt ON jt.id = js.job_type_id "
					"WHERE (js.completed, js.invoiced) = (False, False)")
		for row in c.fetchall():
			self.jobs_store.append(row)
		c.close()

	def job_treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('menu')
			menu.show_all()
			menu.popup_at_pointer()

	def move_job_to_contact_menu_activated (self, menuitem):
		dialog = self.get_object('move_dialog')
		response = dialog.run()
		dialog.hide()
		if response != Gtk.ResponseType.ACCEPT:
			return
		customer_id = self.get_object ('contact_combo').get_active_id()
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		job_id = model[path][0]
		self.cursor.execute("UPDATE job_sheets SET contact_id = %s "
							"WHERE id = %s", (customer_id, job_id))
		self.db.commit()
		self.populate_job_store ()

	def contact_match_selected (self, entrycompletion, model, t_iter):
		contact_id = model[t_iter][0]
		self.get_object('contact_combo').set_active_id(contact_id)

	def row_activate(self, treeview, path, treeviewcolumn):
		job_id = self.jobs_store[path][0]
		self.get_object("box2").set_sensitive(True)
		store = self.get_object("job_sheet_line_store")
		store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
					"jsli.id, "
					"jsli.qty::text, "
					"p.name, "
					"jsli.remark "
					"FROM job_sheet_line_items AS jsli "
					"JOIN products AS p ON p.id = jsli.product_id "
					"WHERE jsli.job_sheet_id = %s", (job_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()

	def open_in_job_sheet_window_clicked (self, button):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		job_sheet_id = model[path][0]
		customer_id = model[path][5]
		import job_sheet
		js = job_sheet.JobSheetGUI()
		js.get_object('combobox1').set_active_id (str(customer_id))
		js.get_object('comboboxtext2').set_active_id (str(job_sheet_id))

	def post_job_to_invoice_clicked (self, button):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		job_sheet_id = model[path][0]
		customer_id = model[path][5]
		customer_name = model[path][6]
		self.cursor.execute("SELECT id, name FROM invoices "
							"WHERE (posted, canceled, active, customer_id) = "
							"(False, False, True, %s) "
							"LIMIT 1", (customer_id,))
		for row in self.cursor.fetchall():
			invoice_id = row[0]
			invoice_name = row[1]
			message = "Invoice '%s' already exists for customer '%s'.\n"\
						"Do you want to append the items?" \
						% (invoice_name, customer_name)
			action = self.show_invoice_exists_message (message) 
			if action == 2:
				break # append the items
			else:
				return # cancel posting to invoice altogether
		else: # create new invoice
			invoice_id = create_new_invoice (datetime.today(), customer_id)
		c = self.db.cursor()
		c.execute("INSERT INTO invoice_items "
						"(qty, product_id, remark, invoice_id) "
					"SELECT qty, product_id, remark, %s "
					"FROM job_sheet_line_items AS jsli "
						"WHERE jsli.job_sheet_id = %s; "
					"UPDATE job_sheets SET (invoiced, completed) "
						"= (True, True) WHERE id = %s", 
					(invoice_id, job_sheet_id, job_sheet_id))
		self.db.commit()
		self.populate_job_store ()

	def post_job_as_completed_clicked (self, button):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		job_sheet_id = model[path][0]
		self.cursor.execute("UPDATE job_sheets SET completed = True "
							"WHERE id = %s", (job_sheet_id,))
		self.db.commit()
		self.populate_job_store()

	def focus (self, window, event):
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.populate_job_store()
		selection.select_path(path)

	def show_invoice_exists_message (self, message):
		dialog = Gtk.Dialog("", self.window, 0)
		dialog.add_button("Cancel", 1)
		dialog.add_button("Append items", 2)
		label = Gtk.Label(message)
		box = dialog.get_content_area()
		box.add(label)
		label.show()
		response = dialog.run()
		dialog.destroy()
		return response



