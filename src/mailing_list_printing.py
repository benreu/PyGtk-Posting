# mailing_list_printing.py
#
# Copyright (C) 2019 - reuben
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
import subprocess, os
from constants import db, ui_directory, template_dir

UI_FILE = ui_directory + "/mailing_list_printing.ui"


class Item(object):#this is used by py3o library see their example for more info
	pass

class MailingListPrintingGUI(Gtk.Builder):
	
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.cursor = db.cursor()
		
		self.window = self.get_object('window1')
		self.window.show_all()
		self.populate_mailing_list_store ()

	def populate_mailing_list_store (self):
		model = self.get_object('mailing_list_store')
		model.clear()
		self.cursor.execute("SELECT "
								"id::text, "
								"name "
							"FROM mailing_lists ORDER BY name")
		for row in self.cursor.fetchall():
			model.append(row)
		db.rollback()

	def mailing_list_combo_changed (self, combobox):
		list_id = combobox.get_active_id()
		if list_id != None:
			self.mailing_list_id = list_id
			self.get_object('refresh_button').set_sensitive(True)
			self.get_object('print_mailing_button').set_sensitive(True)
			self.populate_contact_mailing_store()

	def refresh_contacts_clicked (self, button):
		self.get_object('print_mailing_button').set_sensitive(True)
		self.populate_contact_mailing_store()

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('menu')
			menu.popup_at_pointer()

	def contact_hub_activated (self, menuitem):
		selection = self.get_object('tree-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		contact_id = model[path][0]
		import contact_hub
		contact_hub.ContactHubGUI(contact_id)

	def view_mailing_file_activated (self, menuitem):
		selection = self.get_object('tree-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		company = Item()
		self.cursor.execute("SELECT * FROM company_info")
		for row in self.cursor.fetchall():
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
		temperary_folder = "/tmp/posting_mailing"
		if not os.path.exists(temperary_folder):
			os.mkdir(temperary_folder)
		row = model[path]
		contact_id = row[0]
		contact = Item()
		contact.name = row[1]
		contact.street = row[3]
		contact.city = row[4]
		contact.state = row[5]
		contact.zip = row[6]
		contact.phone = row[7]
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		mailing_file = "%s/contact_%s.odt" % (temperary_folder, contact_id)
		t = Template(template_dir+"/mailing_list_template.odt", 
						mailing_file, 
						True)
		t.render(data)
		subprocess.call(["soffice", mailing_file])

	def populate_contact_mailing_store (self):
		store = self.get_object('contact_mailing_list_store')
		store.clear()
		c = db.cursor()
		c.execute("SELECT c.id, "
							"c.name, "
							"ext_name, "
							"address, "
							"city, "
							"state, "
							"zip, "
							"phone "
					"FROM contacts AS c "
					"JOIN mailing_list_register AS mlr "
						"ON mlr.contact_id = c.id "
					"JOIN mailing_lists AS ml ON ml.id = mlr.mailing_list_id "
					"WHERE ml.id = %s ORDER BY c.name, c.ext_name", 
					(self.mailing_list_id,) )
		for row in c.fetchall():
			store.append(row)
		c.close()
		db.rollback()
		self.get_object('contacts_amount_label').set_text(str(len(store)))

	def print_mailing_list_clicked (self, button):
		button.set_sensitive(False)
		company = Item()
		self.cursor.execute("SELECT * FROM company_info")
		for row in self.cursor.fetchall():
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
		contact_mailing_store = self.get_object('contact_mailing_list_store')
		total = len(contact_mailing_store)
		progressbar = self.get_object('progressbar')
		count = 0.00
		temperary_folder = "/tmp/posting_mailing"
		if not os.path.exists(temperary_folder):
			os.mkdir(temperary_folder)
		for row in contact_mailing_store:
			count += 1
			contact_id = row[0]
			contact = Item()
			contact.name = row[1]
			contact.street = row[3]
			contact.city = row[4]
			contact.state = row[5]
			contact.zip = row[6]
			contact.phone = row[7]
			data = dict(contact = contact, company = company)
			from py3o.template import Template
			mailing_file = "%s/contact_%s.odt" % (temperary_folder, contact_id)
			t = Template(template_dir+"/mailing_list_template.odt", 
							mailing_file, 
							True)
			t.render(data)
			subprocess.call(["soffice", "-p", mailing_file])
			progressbar.set_fraction(count / total)
			while Gtk.events_pending():
				Gtk.main_iteration()
		button.set_sensitive(True)






