# contacts_overview.py
# Copyright (C) 2019 reuben 
# 
# contact_overview is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# contact_overview is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
import subprocess
from constants import ui_directory, DB, template_dir, broadcaster
from main import get_apsw_connection

UI_FILE = ui_directory + "/contacts_overview.ui"

class Item(object):
	pass

class ContactsOverviewGUI(Gtk.Builder):
	def __init__(self, contact_id = 0):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.contact_id = contact_id
		self.name_filter = ''
		self.contact_store = self.get_object('contact_store')
		self.filtered_store = self.get_object('contact_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.treeview = self.get_object('treeview2')
		self.handler_ids = list()
		for connection in (("contacts_changed", self.show_refresh_button),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)
		self.populate_contact_store()
		self.window = self.get_object('window1')
		self.set_window_layout_from_settings ()
		self.window.show_all()
		GLib.idle_add(self.window.set_position, Gtk.WindowPosition.NONE)

	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def show_refresh_button (self, broadcast):
		self.get_object('refresh_button').set_visible(True)

	def refresh_button_clicked (self, button):
		self.populate_contact_store()
		button.set_visible(False)

	def set_window_layout_from_settings(self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT size FROM contact_overview "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT size FROM contact_overview "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT widget_id, size FROM contact_overview WHERE "
					"widget_id NOT IN ('window_height', 'window_width')")
		for row in c.fetchall():
			width = row[1]
			column = self.get_object(row[0])
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO contact_overview (widget_id, size) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO contact_overview (widget_id, size) "
					"VALUES ('window_height', ?)", (height,))
		for column in ['name_column', 
						'ext_name_column', 
						'address_column', 
						'city_column', 
						'state_column', 
						'zip_column', 
						'fax_column', 
						'phone_column', 
						'email_column']:
			try:
				width = self.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO contact_overview (widget_id, size) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def search_changed (self, search_entry):
		self.name_filter = search_entry.get_text().split()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		for text in self.name_filter:
			if text not in model[tree_iter][1].lower():
				return False
		return True

	def contact_type_radiobutton_changed (self, radiobutton):
		# dismiss callbacks from non active radiobuttons
		if radiobutton.get_active() == True: 
			self.populate_contact_store()

	def populate_contact_store (self):
		progressbar = self.get_object('progressbar')
		spinner = self.get_object('spinner')
		spinner.show()
		spinner.start()
		model = self.treeview.get_model()
		self.treeview.set_model(None) # unset the model for performance
		c = DB.cursor()
		self.contact_store.clear()
		if self.get_object('radiobutton1').get_active() == True:
			where = "WHERE (customer, deleted) = (True, False)"
		elif self.get_object('radiobutton2').get_active() == True:
			where = "WHERE (vendor, deleted) = (True, False)"
		elif self.get_object('radiobutton3').get_active() == True:
			where = "WHERE (employee, deleted) = (True, False)"
		elif self.get_object('radiobutton4').get_active() == True:
			where = "WHERE (service_provider, deleted) = (True, False)"
		else: # all contacts not deleted
			where = "WHERE deleted = False"
		c.execute("SELECT id, "
						"name, "
						"ext_name, "
						"address, "
						"city, "
						"state, "
						"zip, "
						"fax, "
						"phone, "
						"email "
					"FROM contacts %s "
					"ORDER BY name, ext_name" % where)
		c_tuple = c.fetchall()
		rows = len(c_tuple)
		for row_count, row in enumerate(c_tuple):
			progressbar.set_fraction((row_count + 1) / rows)
			self.contact_store.append(row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		DB.rollback()
		c.close()
		spinner.hide()
		spinner.stop()
		self.treeview.set_model(model)
		self.treeview.set_search_column(1)
		self.select_contact()

	def append_contact(self, contact_id):
		c = DB.cursor()
		c.execute("SELECT id, "
						"name, "
						"ext_name, "
						"address, "
						"city, "
						"state, "
						"zip, "
						"fax, "
						"phone, "
						"email "
					"FROM contacts "
					"WHERE id = %s" , (contact_id,))
		for row in c.fetchall():
			self.contact_store.append(row)
		c.close()

	def select_contact (self, contact_id = None):
		if contact_id != None:
			self.contact_id = contact_id
		for row in self.treeview.get_model(): 
			if row[0] == self.contact_id: 
				treeview_selection = self.get_object('treeview-selection2')
				treeview_selection.select_path(row.path)
				self.treeview.scroll_to_cell(row.path, None, True, 0.5)
				break

	def contact_selection_changed (self, treeselection):
		"populate contact individuals when a contact is selected"
		model, path = treeselection.get_selected_rows()
		if path == []:
			return
		self.contact_id = model[path][0]
		self.populate_contact_individuals()

	def contact_individuals_clicked (self, button):
		self.get_object('stack1').set_visible_child_name('individuals_page')

	def go_back_to_contacts_clicked (self, button):
		self.get_object('stack1').set_visible_child_name('contacts_page')

	def contact_activated (self, treeview, treepath, treeviewcolumn):
		model, path = treeview.get_selection().get_selected_rows()
		self.contact_id = model[path][0]
		self.edit_contact()

	def new_clicked (self, button):
		import contact_edit_main
		ce = contact_edit_main.ContactEditMainGUI(overview_class = self)
		ce.window.set_transient_for(self.window)

	def edit_clicked (self, button):
		model, path = self.get_object('treeview-selection2').get_selected_rows()
		if path == []:
			return
		self.contact_id = model[path][0]
		self.edit_contact()

	def edit_contact (self):
		import contact_edit_main
		ce = contact_edit_main.ContactEditMainGUI(self.contact_id)
		ce.window.set_transient_for(self.window)

	def contact_exemptions_clicked (self, button):
		model, path = self.get_object('treeview-selection2').get_selected_rows()
		if path == []:
			return
		contact_id = model[path][0]
		import contact_edit_exemptions 
		ce = contact_edit_exemptions.ContactEditExemptionsGUI(contact_id)
		ce.window.set_transient_for(self.window)

	def contact_files_clicked (self, button):
		model, path = self.get_object('treeview-selection2').get_selected_rows()
		if path == []:
			return
		contact_id = model[path][0]
		import contact_edit_files 
		cf = contact_edit_files.ContactEditFilesGUI(contact_id)
		cf.window.set_transient_for(self.window)

	def open_company_letter_head_activated (self, menuitem):
		contact = Item()
		c = DB.cursor()
		c.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in c.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
		company = Item()
		c.execute("SELECT * FROM company_info")
		for row in c.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		label_file = "/tmp/letter_head_template.odt"
		t = Template(template_dir+"/letter_head_template.odt", 
									label_file,
									True)
		t.render(data)
		subprocess.Popen(["soffice", label_file])
		c.close()
		DB.rollback()

	def print_mailing_envelope_activated (self, menuitem):
		contact = Item()
		c = DB.cursor()
		c.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in c.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
		company = Item()
		c.execute("SELECT * FROM company_info")
		for row in c.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		env_file = "/tmp/mailing_envelope_template.odt"
		t = Template(template_dir+"/mailing_envelope_template.odt", 
									env_file, 
									True)
		t.render(data)
		subprocess.Popen(["soffice", env_file])
		c.close()
		DB.rollback()

	def print_shipping_label_activated (self, menuitem):
		contact = Item()
		c = DB.cursor()
		c.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in c.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
		company = Item()
		c.execute("SELECT * FROM company_info")
		for row in c.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.country = row[6]
			company.phone = row[7]
			company.fax = row[8]
			company.email = row[9]
			company.website = row[10]
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		label_file = "/tmp/shipping_label_template.odt"
		t = Template("./templates/shipping_label_template.odt", 
												label_file, 
												True)
		t.render(data) 
		subprocess.Popen(["soffice", label_file])
		c.close()
		DB.rollback()

################   contact individuals

	def populate_contact_individuals (self):
		store = self.get_object('contact_individuals_store')
		store.clear()
		button = self.get_object('contact_individuals_button')
		c = DB.cursor()
		c.execute("SELECT id, "
						"name, "
						"ext_name, "
						"address, "
						"city, "
						"state, "
						"zip, "
						"phone, "
						"fax, "
						"email "
					"FROM contact_individuals WHERE contact_id = %s "
					"ORDER BY name, ext_name", 
					(self.contact_id,))
		tupl = c.fetchall()
		if tupl == []: # only show the individuals button when individuals exist
			button.hide()
		else:
			button.show()
		for row in tupl:
			store.append(row)
		c.close()
		DB.rollback()

	def new_individual_clicked (self, button):
		if self.contact_id == 0:
			return
		import contact_edit_individual
		ced_gui = contact_edit_individual.ContactEditIndividualGUI(self)
		ced_gui.window.set_transient_for(self.window)
		ced_gui.contact_id = self.contact_id

	def individual_row_activated (self, treeview, path, treeviewcolumn):
		model = self.get_object('contact_individuals_store')
		individual_id = model[path][0]
		self.edit_contact_individual (individual_id)

	def edit_individual_clicked (self, button):
		selection = self.get_object('treeview-selection3')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		individual_id = model[path][0]
		self.edit_contact_individual (individual_id)

	def edit_contact_individual (self, individual_id):
		import contact_edit_individual as ced
		ced_gui = ced.ContactEditIndividualGUI(self, individual_id)
		ced_gui.window.set_transient_for(self.window)



