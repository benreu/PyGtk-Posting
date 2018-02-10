#
# Copyright (C) 2016 reuben
# 
# contacts is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# contacts is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
import psycopg2, subprocess, re, sane
from multiprocessing import Queue, Process
from queue import Empty
from main import Connection, Admin

dev = None

UI_FILE = "src/contacts.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class GUI(Connection, Admin):
	def __init__(self, main, contact_id = 0):
		#Connection.__init__(self)

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.cursor()
		self.contact_id = contact_id
		
		self.name_widget = self.builder.get_object('entry1')
		self.ext_name_widget = self.builder.get_object('entry2')
		self.address_widget = self.builder.get_object('entry3')
		self.city_widget = self.builder.get_object('entry4')
		self.state_widget = self.builder.get_object('entry5')
		self.zip_code = self.builder.get_object('entry6')
		self.phone_widget = self.builder.get_object('entry7')
		self.fax_widget = self.builder.get_object('entry8')
		self.email_widget = self.builder.get_object('entry9')
		self.terms_store = self.builder.get_object('terms_store')
		self.markup_percent_store = self.builder.get_object('markup_percent_store')
		
		#self.tax_exempt_widget = self.builder.get_object('checkbutton1')
		self.tax_exempt_number_widget = self.builder.get_object('entry10')
		self.misc_widget = self.builder.get_object('entry11')
		self.vendor_widget = self.builder.get_object('checkbutton2')
		self.customer_widget = self.builder.get_object('checkbutton3')
		self.employee_widget = self.builder.get_object('checkbutton4')
		self.service_provider_widget = self.builder.get_object('checkbutton1')
		self.custom1_widget = self.builder.get_object("entry16")
		self.custom2_widget = self.builder.get_object("entry26")
		self.custom3_widget = self.builder.get_object("entry27")
		self.custom4_widget = self.builder.get_object("entry28")
		self.note = self.builder.get_object("textbuffer1")
		self.duplicate_name_popover = Gtk.Popover()
		box = self.builder.get_object("box19")
		self.duplicate_name_popover.add(box)
		
		self.populate_terms_combo ()
		if self.contact_id == 0:
			self.new_contact(None)
		
		self.contact_store = self.builder.get_object('contact_store')
		self.individual_contact_store = self.builder.get_object('individual_contact_store')
		self.filtered_contact_store = self.builder.get_object(
													'filtered_contact_store')
		self.contact_filter_list = ""
		self.filtered_contact_store.set_visible_func(self.contact_filter_func)
		self.treeview = self.builder.get_object('treeview1')
		self.populate_contacts ()
		self.select_contact ()
		self.populate_zip_codes ()

		self.mailing_list_popover = Gtk.Popover()
		self.mailing_list_popover.add(self.builder.get_object("box18"))	
		self.initiate_mailing_info()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		self.data_queue = Queue()
		self.scanner_store = self.builder.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GLib.timeout_add(100, self.populate_scanners)

	def customer_markup_percent_clicked (self, button):
		if self.get_admin() == False:
			return
		self.window.present()
		import customer_markup_percent
		customer_markup_percent.CustomerMarkupPercentGUI(self.main)

	def populate_zip_codes (self):
		zip_code_store = self.builder.get_object("zip_code_store")
		zip_code_store.clear()
		self.cursor.execute("SELECT zip, city, state FROM contacts "
							"WHERE deleted = False GROUP BY zip, city, state")
		for row in self.cursor.fetchall():
			zip_code = row[0]
			city = row[1]
			state = row[2]
			zip_code_store.append([zip_code, city, state])

	def zip_code_match_selected (self, completion, store, _iter):
		city = store[_iter][1]
		state = store[_iter][2]
		self.builder.get_object("entry4").set_text(city)
		self.builder.get_object("entry5").set_text(state)

	def zip_activated (self, entry):
		zip_code = entry.get_text()
		self.cursor.execute("SELECT city, state FROM contacts "
							"WHERE (deleted, zip) = (False, %s) "
							"GROUP BY city, state LIMIT 1", (zip_code,))
		for row in self.cursor.fetchall():
			city = row[0]
			state = row[1]
			self.builder.get_object("entry4").set_text(city)
			self.builder.get_object("entry5").set_text(state)

	def populate_scanners(self):
		try:
			devices = self.data_queue.get_nowait()
			for scanner in devices:
				device_id = scanner[0]
				device_manufacturer = scanner[1]
				name = scanner[2]
				given_name = scanner[3]
				self.scanner_store.append([str(device_id), device_manufacturer,
											name, given_name])
		except Empty:
			return True
		
	def get_scanners(self):
		sane.init()
		devices = sane.get_devices()
		self.data_queue.put(devices)

	def scanner_combo_changed (self, combo):
		tree_iter = combo.get_active_iter()
		scanner_manufacturer = self.scanner_store.get_value(tree_iter, 1)
		scanner_name = self.scanner_store.get_value(tree_iter, 2)
		scanner_string = "%s %s" % (scanner_manufacturer, scanner_name)
		self.builder.get_object("label39").set_text(scanner_string)
		self.check_scan_button_validity ()
				
	def scan_file_clicked (self, widget):
		global device
		if device == None:
			device_address = self.builder.get_object("combobox2").get_active_id()
			device = sane.open(device_address)
		document = device.scan()
		misc_file_radiobutton = self.builder.get_object("radiobutton6")
		if misc_file_radiobutton.get_active() == True: #scan misc. file
			file_name = self.builder.get_object("entry16").get_text()
			path = "/tmp/" + file_name + ".pdf"
			document.save(path)
			f = open(path,'rb')
			data = f.read()
			binary = psycopg2.Binary(data)
			split_filename = path.split("/")
			name = split_filename[-1]
			name = re.sub(" ", "_", name)
			self.cursor.execute("INSERT INTO files(file_data, contact_id, name) "
								"VALUES (%s, %s, %s)", 
								(binary, self.contact_id, name))
		else:					#scan tax exemption
			exemption_selection = self.builder.get_object('treeview-selection2')
			model, path = exemption_selection.get_selected_rows ()
			customer_exemption_id = model[path][4]
			exemption_id = model[path][0]
			path = "/tmp/exemption.pdf"
			document.save(path)
			f = open(path,'rb')
			data = f.read()
			binary = psycopg2.Binary(data)
			if customer_exemption_id == 0:
				self.cursor.execute("INSERT INTO customer_tax_exemptions "
									"(pdf_data, customer_id, tax_rate_id, "
									"pdf_available) "
									"VALUES (%s, %s, %s, True) ",
									(binary, self.contact_id, exemption_id))
			else:
				self.cursor.execute("UPDATE customer_tax_exemptions "
									"SET (pdf_data, pdf_available) = "
									"(%s, True) "
									"WHERE id = %s", 
									(binary, customer_exemption_id))
		f.close()
		self.db.commit()
		self.populate_tax_exemptions ()

	def terms_clicked (self, button):
		if self.get_admin() == False:
			return
		self.window.present()
		import contact_terms
		contact_terms.ContactTermsGUI(self.db)

	def file_name_changed(self, widget):
		self.check_scan_button_validity ()

	def check_scan_button_validity (self):
		scan_button = self.builder.get_object("button2")
		scan_button.set_sensitive(False)
		if self.contact_id == 0:
			scan_button.set_label("No contact selected")
			return
		if self.builder.get_object("combobox2").get_active() == -1:
			scan_button.set_label("No scanner selected")
			return
		misc_file_radiobutton = self.builder.get_object("radiobutton6")
		if misc_file_radiobutton.get_active() == True: #misc. files
			scan_filename_entry = self.builder.get_object("entry29")
			if scan_filename_entry.get_text() == "" :
				scan_button.set_label("No filename")
				return
		else:										#tax exemption files
			exemption_selection = self.builder.get_object('treeview-selection2')
			model, path = exemption_selection.get_selected_rows ()
			if path == []:
				scan_button.set_label("No exemption selected")
				return
		scan_button.set_sensitive(True)
		scan_button.set_label("Scan file")

	def misc_files_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('box13').set_sensitive(active)
		self.check_scan_button_validity ()

	def tax_exemptions_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('scrolledwindow1').set_sensitive(active)
		self.check_scan_button_validity ()

	def exemption_row_activated (self, treeview, path, treeviewcolumn):
		self.check_scan_button_validity ()

	def file_combobox_populate(self):
		self.builder.get_object('comboboxtext3').remove_all()
		self.cursor.execute("SELECT * FROM files WHERE contact_id = %s", 
							[str(self.contact_id)])
		for files in self.cursor.fetchall():
			self.builder.get_object('comboboxtext3').append(str(files[0]), 
																files[3])

	def delete_file_clicked (self, widget):
		dialog = self.builder.get_object('dialog1')
		combo = self.builder.get_object('comboboxtext3')
		if self.get_admin() == False:
			self.builder.get_object('button17').set_sensitive(False)
			self.builder.get_object('label17').set_label("You are not admin !")
		else:
			file_name = combo.get_active_text()
			self.builder.get_object('button17').set_sensitive(True)
			self.builder.get_object('label17').set_label("Are you sure you "
														"want to delete '%s' ?"
														%file_name)
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			file_id = combo.get_active_id ()
			self.cursor.execute("DELETE FROM files WHERE id = (%s)", (file_id,))
			self.db.commit ()
			self.file_combobox_populate ()
		dialog.hide()

	def select_file_clicked (self, widget):
		dialog = self.builder.get_object('filechooserdialog1')
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			self.add_file_to_contact (dialog)
		dialog.hide()

	def add_file_to_contact (self, dialog):
		path = dialog.get_filename()
		f = open(path,'rb')
		dat = f.read()
		f.close()
		binary = psycopg2.Binary(dat)
		misc_file_radiobutton = self.builder.get_object("radiobutton6")
		if misc_file_radiobutton.get_active() == True: #insert misc. file
			split_filename = path.split("/")
			name = split_filename[-1]
			name = re.sub(" ", "_", name)
			self.cursor.execute("INSERT INTO files(file_data, contact_id, name) "
								"VALUES (%s, %s, %s)", 
								(binary, self.contact_id, name))
		else:					# insert tax exemption
			exemption_selection = self.builder.get_object('treeview-selection2')
			model, path = exemption_selection.get_selected_rows ()
			customer_exemption_id = model[path][4]
			exemption_id = model[path][0]
			if customer_exemption_id == 0:
				self.cursor.execute("INSERT INTO customer_tax_exemptions "
									"(pdf_data, customer_id, tax_rate_id, "
									"pdf_available) "
									"VALUES (%s, %s, %s, True) ",
									(binary, self.contact_id, exemption_id))
			else:
				self.cursor.execute("UPDATE customer_tax_exemptions "
									"SET (pdf_data, pdf_available) = "
									"(%s, True) "
									"WHERE id = %s", 
									(binary, customer_exemption_id))
			self.populate_tax_exemptions ()
		self.db.commit()

	def contact_help_clicked (self, widget):
		subprocess.Popen("yelp ./help/contacts.page", shell = True)

	def print_10_env_clicked (self, button):
		contact = Item()
		self.cursor.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
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
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		env_file = "/tmp/env10_template.odt"
		t = Template("./templates/env10_template.odt", env_file , True)
		t.render(data) #the data holds all the info of the invoice
		subprocess.Popen("soffice --headless -p " + env_file, shell = True)
		#subprocess.call("libreoffice " + label_file, shell = True)

	def open_co_letter_head (self, button):
		contact = Item()
		self.cursor.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
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
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		label_file = "/tmp/letter_template.odt"
		t = Template("./templates/letter_template.odt", label_file , True)
		t.render(data) #the data holds all the info of the invoice
		subprocess.call("libreoffice " + label_file, shell = True)

	def print_shipping_label_clicked (self, button):
		contact = Item()
		self.cursor.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email FROM contacts WHERE id = %s", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			contact.name = row[0]
			contact.street = row[1]
			contact.city = row[2]
			contact.state = row[3]
			contact.zip = row[4]
			contact.phone = row[5]
			contact.fax = row[6]
			contact.email = row[7]
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
		data = dict(contact = contact, company = company)
		from py3o.template import Template
		label_file = "/tmp/contact_label_template.odt"
		t = Template("./templates/contact_label_template.odt", label_file , True)
		t.render(data) #the data holds all the info of the invoice
		subprocess.call("libreoffice " + label_file, shell = True)

	def name_entry_changed (self, entry):
		entry.set_icon_from_icon_name (Gtk.EntryIconPosition.SECONDARY, None)

	def name_entry_focus_out_event (self, entry, event):
		name = entry.get_text().lower()
		store = self.builder.get_object('duplicate_contact_store')
		store.clear()
		self.cursor.execute("SELECT id, name, ext_name, address, deleted "
							"FROM contacts WHERE LOWER(name) = %s", (name,))
		for row in self.cursor.fetchall():
			c_id = row[0]
			name = row[1]
			ext_name = row[2]
			address = row[3]
			deleted = row[4]
			store.append([c_id, name, ext_name, address, deleted])
		if len(store) > 0 and self.contact_id == 0:
			entry.set_icon_from_icon_name (Gtk.EntryIconPosition.SECONDARY, 'dialog-error')
		else:
			entry.set_icon_from_icon_name (Gtk.EntryIconPosition.SECONDARY, None)
		self.duplicate_name_popover.set_relative_to(entry)

	def name_entry_icon_release (self, entry, pos, event):
		self.duplicate_name_popover.show()
		self.builder.get_object('treeview-selection3').unselect_all()

	def contact_treeview_cursor_changed (self, treeview):
		path = treeview.get_cursor().path
		if path == None or self.populating == True:
			return
		self.contact_id = self.filtered_contact_store[path][0]
		self.select_contact()

	def customer_checkbutton_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('button11').set_sensitive(active)
		self.builder.get_object('button9').set_sensitive(active)
		self.builder.get_object('combobox1').set_sensitive(active)
		self.builder.get_object('frame5').set_sensitive(active)
		if active == False:
			self.builder.get_object('radiobutton6').set_active(True)
		
	def focus_window(self, window, e):
		# keep the active entry when we refocus the window (which usually happens when we add a file and come back) 
		active = self.builder.get_object('comboboxtext3').get_active_id()
		self.populate_terms_combo ()
		self.file_combobox_populate() # repopulate
		self.builder.get_object('comboboxtext3').set_active_id(active)

	def view_file_clicked (self, button):
		misc_file_radiobutton = self.builder.get_object("radiobutton6")
		if misc_file_radiobutton.get_active() == True: #view misc. file
			file_id = self.builder.get_object('comboboxtext3').get_active_id()
			self.cursor.execute("SELECT * FROM files WHERE id = %s", (file_id,))
			for row in self.cursor.fetchall():
				file_name = row[3]
				file_data = row[1]
				view_file = open("/tmp/" + file_name,'wb')
				view_file.write(file_data)
				subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
				view_file.close()
		else:											#view exemption file
			exemption_selection = self.builder.get_object('treeview-selection2')
			model, path = exemption_selection.get_selected_rows ()
			if model[path][3] == False:
				return # no exemption file available
			customer_exemption_id = model[path][4]
			self.cursor.execute("SELECT pdf_data FROM customer_tax_exemptions "
								"WHERE id = %s", (customer_exemption_id,))
			for row in self.cursor.fetchall():
				pdf_data = row[0]
				view_file = open("/tmp/exemption.pdf",'wb')
				view_file.write(pdf_data)
				subprocess.call("xdg-open /tmp/exemption.pdf", shell = True)
				view_file.close()

	def tax_exemption_window(self, widget):
		if self.contact_id != 0:
			import customer_tax_exemptions
			customer_tax_exemptions.CustomerTaxExemptionsGUI(self.window,
												self.db, self.contact_id)

	def customer_active_state_changed(self, widget):
		if widget.get_active() == False:
			widget.set_label("Active")
		else:
			widget.set_label("Inactive")

	def populate_terms_combo (self):
		active_term_id = self.builder.get_object('combobox1').get_active_id()
		self.terms_store.clear()
		self.cursor.execute("SELECT id, name FROM terms_and_discounts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			term_id = row[0]
			term_name = row[1]
			self.terms_store.append([str(term_id), term_name])
		self.builder.get_object('combobox1').set_active_id(active_term_id)
		active_markup_id = self.builder.get_object('combobox4').get_active_id()
		self.markup_percent_store.clear()
		self.cursor.execute("SELECT id, name FROM customer_markup_percent "
									"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			markup_id = row[0]
			markup_name = row[1]
			self.markup_percent_store.append([str(markup_id), markup_name])
		self.builder.get_object('combobox4').set_active_id(active_markup_id)

	def contact_filter_func(self, model, tree_iter, r):
		for text in self.contact_filter_list:
			if text not in model[tree_iter][1].lower():
				return False
		return True

	def contact_search_changed (self, search_entry):
		filter_text = search_entry.get_text()
		self.contact_filter_list = filter_text.split(" ")
		self.filtered_contact_store.refilter()

	def contact_radiobutton_changed (self, radiobutton):
		self.populate_contacts ()

	def populate_contacts(self, m=None, i=None):
		self.populating = True
		self.contact_store.clear()
		if self.builder.get_object('radiobutton1').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE (customer, deleted) = (True, False) "
							"ORDER BY name")
		elif self.builder.get_object('radiobutton2').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE (vendor, deleted) = (True, False) "
							"ORDER BY name")
		elif self.builder.get_object('radiobutton3').get_active() == True:
			self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE (employee, deleted) = (True, False) "
							"ORDER BY name")
		else:
			self.cursor.execute("SELECT id, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for i in self.cursor.fetchall():
			serial_number = i[0]
			name = i[1]
			ext_name = i[2]
			self.contact_store.append([serial_number, name, ext_name])
		for row in self.contact_store:
			if row[0] == self.contact_id: # select the contact we had selected before repopulating
				treeview_selection = self.builder.get_object('treeview-selection')
				path = row.path
				treeview_selection.select_path(path)
				self.treeview.scroll_to_cell(path)
		self.populating = False
		
	def destroy(self, window):
		self.cursor.close()

	def tax_exempt_clicked(self, widget):
		sense = widget.get_active() 
		self.tax_exempt_number_widget.set_sensitive(sense)	
		if (sense == True):
			self.tax_exempt_number_widget.set_placeholder_text("Tax Exempt "
																	"Number")
		else:
			self.tax_exempt_number_widget.set_placeholder_text("")
		
	def delete_contact_clicked(self, widget): # !!!do not delete a contact in case we already have an invoice for that id
		#just set the deleted boolean to true in the database and then we ignore it
		self.cursor.execute("UPDATE contacts SET deleted = True "
							"WHERE id = %s ", [self.contact_id])
		self.db.commit()
		self.populate_contacts ()

	def exit(self, widget):
		self.destroy(None)

	def select_contact (self):
		self.cursor.execute("SELECT name, ext_name, address, city, state, zip, "
							"phone, fax, email, label, tax_number, vendor, "
							"customer, employee, organization, custom1, "
							"custom2, custom3, custom4, notes, "
							"terms_and_discounts_id::text, service_provider, "
							"checks_payable_to, markup_percent_id::text "
							"FROM contacts WHERE id = (%s)", 
							(self.contact_id, ) )
		for row in self.cursor.fetchall():
			self.name_widget.set_text(row[0])
			self.ext_name_widget.set_text(row[1])
			self.address_widget.set_text(row[2])
			self.city_widget.set_text(row[3])
			self.state_widget.set_text(row[4])
			self.zip_code.set_text(row[5])
			self.phone_widget.set_text(row[6])
			self.fax_widget.set_text(row[7])
			self.email_widget.set_text(row[8])
			self.misc_widget.set_text(row[9])
			self.tax_exempt_number_widget.set_text(row[10])
			self.vendor_widget.set_active(row[11])
			self.customer_widget.set_active(row[12])
			self.employee_widget.set_active(row[13])
			self.custom1_widget.set_text(row[15])
			self.custom2_widget.set_text(row[16])
			self.custom3_widget.set_text(row[17])
			self.custom4_widget.set_text(row[18])
			self.note.set_text(row[19])
			self.builder.get_object('combobox1').set_active_id(row[20])
			self.service_provider_widget.set_active(row[21])
			self.builder.get_object('entry13').set_text(row[22])
		
		self.initiate_mailing_info()
		# clear the individual contact entries
		self.builder.get_object('combobox-entry').set_text("")
		self.builder.get_object('entry18').set_text("")
		self.builder.get_object('entry19').set_text("")
		self.builder.get_object('entry20').set_text("")
		self.builder.get_object('entry21').set_text("") 
		self.builder.get_object('entry22').set_text("")
		self.builder.get_object('entry23').set_text("") 
		self.builder.get_object('entry24').set_text("")
		self.builder.get_object('entry25').set_text("")
		self.builder.get_object('entry12').set_text("")
			
		self.builder.get_object('entry23').set_sensitive(True)
		self.builder.get_object('entry29').set_sensitive(True)
		self.builder.get_object('entry29').set_text("")
		self.builder.get_object('button6').set_sensitive(True)
		self.builder.get_object("button1").set_sensitive(True)
		self.file_combobox_populate()
		self.populate_tax_exemptions ()
		self.populate_individual_store ()

	def populate_tax_exemptions (self):
		tax_exemption_store = self.builder.get_object("tax_exemption_store")
		tax_exemption_store.clear()
		self.cursor.execute("SELECT tax_rates.id, tax_rates.name, cte.id, "
							"cte.pdf_available "
							"FROM tax_rates "
							"LEFT OUTER JOIN customer_tax_exemptions AS cte "
							"ON cte.tax_rate_id = tax_rates.id "
							"AND (cte.customer_id = %s OR cte.id IS NULL) "
							"WHERE tax_rates.exemption = True ",
							(self.contact_id, ))
		for row in self.cursor.fetchall():
			exemption_id = row[0]
			exemption_name = row[1]
			customer_exemption_id = row[2]
			exemption_pdf_scanned = row[3]
			if customer_exemption_id == None:
				exemption_available = False
			else:
				exemption_available = True
			tax_exemption_store.append([exemption_id, exemption_name, 
										exemption_available, 
										exemption_pdf_scanned, 
										customer_exemption_id])
		self.check_scan_button_validity ()
		
	def new_contact (self, widget):
		self.builder.get_object('entry29').set_sensitive(False)
		self.builder.get_object('entry29').set_text("Select customer "
													"before scanning")
		self.builder.get_object('button2').set_sensitive(False)
		self.builder.get_object('button1').set_sensitive(False)		
		self.contact_id = 0		#this tells the rest of the program we have a new contact
		
		self.name_widget.set_text("New Contact")
		self.name_widget.select_region(0,-1)
		self.name_widget.grab_focus()
		self.address_widget.set_text("New address")
		self.employee_widget.set_active(False)
		self.customer_widget.set_active(True)#set default to customer to avoid database errors
		self.service_provider_widget.set_active(False)
		self.ext_name_widget.set_text("")
		self.city_widget.set_text("")
		self.state_widget.set_text("")
		self.zip_code.set_text("")
		self.fax_widget.set_text("")
		self.phone_widget.set_text("")
		self.email_widget.set_text("")
		self.cursor.execute("SELECT id FROM terms_and_discounts "
							"WHERE standard = True")
		default_term = self.cursor.fetchone()[0]
		self.builder.get_object('combobox1').set_active_id(str(default_term))
		self.cursor.execute("SELECT id FROM customer_markup_percent "
							"WHERE standard = True AND deleted = False")
		default_markup = self.cursor.fetchone()[0]
		self.builder.get_object('combobox4').set_active_id(str(default_markup))
		self.misc_widget.set_text("")
		self.tax_exempt_number_widget.set_text("")
		self.builder.get_object('entry13').set_text('')
		self.custom1_widget.set_text("")
		self.custom2_widget.set_text("")
		self.custom3_widget.set_text("")
		self.custom4_widget.set_text("")
		self.note.set_text("")
		self.builder.get_object('combobox-entry').set_text("")
		self.builder.get_object('entry18').set_text("")
		self.builder.get_object('entry19').set_text("")
		self.builder.get_object('entry20').set_text("")
		self.builder.get_object('entry21').set_text("") 
		self.builder.get_object('entry22').set_text("")
		self.builder.get_object('entry23').set_text("") 
		self.builder.get_object('entry24').set_text("")
		self.builder.get_object('entry25').set_text("")
		self.builder.get_object('entry12').set_text("")
		self.initiate_mailing_info ()

	def populate_individual_store (self):
		self.individual_contact_store.clear()
		self.cursor.execute("SELECT id, name FROM contact_individuals "
							"WHERE contact_id = %s ORDER BY name", 
							(self.contact_id,))
		for row in self.cursor.fetchall():
			individual_id = str(row[0])
			individual_name = row[1]
			self.individual_contact_store.append([individual_id, individual_name])

	def contact_individual_combo_button_release_event (self, combo, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def delete_individual_activated (self, menuitem):
		individual_id = self.builder.get_object('combobox3').get_active_id()
		self.builder.get_object('combobox-entry').set_text('')
		self.builder.get_object('entry18').set_text("")
		self.builder.get_object('entry19').set_text("")
		self.builder.get_object('entry20').set_text("")
		self.builder.get_object('entry21').set_text("") 
		self.builder.get_object('entry22').set_text("")
		self.builder.get_object('entry23').set_text("") 
		self.builder.get_object('entry24').set_text("")
		self.builder.get_object('entry25').set_text("")
		self.builder.get_object('entry12').set_text("")
		self.cursor.execute("DELETE FROM contact_individuals WHERE id = %s", 
							(individual_id,))
		self.db.commit ()
		self.populate_individual_store ()

	def contact_individual_combo_changed (self, combo):
		individual_id = combo.get_active_id()
		self.cursor.execute("SELECT name, address, city, state, zip, phone, "
							"fax, email, extension, role "
							"FROM contact_individuals WHERE id = (%s)", 
							(individual_id,))
		for row in self.cursor.fetchall():
			self.builder.get_object('combobox-entry').set_text( row[0]) 
			self.builder.get_object('entry18').set_text( row[1]) 
			self.builder.get_object('entry19').set_text( row[2])
			self.builder.get_object('entry20').set_text( row[3]) 
			self.builder.get_object('entry21').set_text( row[4]) 
			self.builder.get_object('entry22').set_text( row[5])
			self.builder.get_object('entry23').set_text( row[6]) 
			self.builder.get_object('entry24').set_text( row[7])
			self.builder.get_object('entry25').set_text( row[8])
			self.builder.get_object('entry12').set_text( row[9])

	def save_contact (self, widget):
		name = self.name_widget.get_text()
		if name == "":  #no text! so we exit
			return
		ext_name = self.ext_name_widget.get_text()
		address = self.address_widget.get_text()
		city = self.city_widget.get_text()
		state = self.state_widget.get_text()
		zip_code = self.zip_code.get_text()
		phone = self.phone_widget.get_text()
		fax = self.fax_widget.get_text()
		email = self.email_widget.get_text()
		term_id = self.builder.get_object('combobox1').get_active_id() 
		misc = self.misc_widget.get_text()
		checks_payable_to = self.builder.get_object('entry13').get_text()
		markup_id = self.builder.get_object('combobox4').get_active_id() 
		if checks_payable_to == '':
			checks_payable_to = name
		tax_number = self.tax_exempt_number_widget.get_text()
		vendor = self.vendor_widget.get_active()
		customer = self.customer_widget.get_active()
		employee = self.employee_widget.get_active()
		service_provider = self.service_provider_widget.get_active()
		custom1 = self.custom1_widget.get_text()
		custom2 = self.custom2_widget.get_text()
		custom3 = self.custom3_widget.get_text()
		custom4 = self.custom4_widget.get_text()
		
		start = self.note.get_start_iter()
		end = self.note.get_end_iter()
		notes = self.note.get_text(start, end, True)
		
		if self.contact_id != 0:   #if the serial number is more than 0 we update the info instead of inserting a new contact
			self.cursor.execute("UPDATE contacts SET "
								"(name, ext_name, address, city, state, zip, phone, "
								"fax, email, label, tax_number, vendor, "
								"customer, employee, custom1, "
								"custom2, custom3, custom4, notes, "
								"terms_and_discounts_id, service_provider, "
								"checks_payable_to, markup_percent_id) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s, %s, %s ,%s, %s, %s, %s, %s, %s) "
								"WHERE id = %s ", (name, ext_name, address, city, 
								state, zip_code, phone, fax, email, misc, 
								tax_number, vendor, customer, employee, 
								custom1, custom2, custom3, custom4, notes, 
								term_id, service_provider, checks_payable_to,
								markup_id, self.contact_id))
		else:
			self.cursor.execute("INSERT INTO contacts " 
								"(name, ext_name, address, city, state, zip, phone, "
								"fax, email, label, tax_number, vendor, "
								"customer, employee, custom1, "
								"custom2, custom3, custom4, notes, deleted, "
								"terms_and_discounts_id, service_provider, "
								"checks_payable_to, markup_percent_id) "
								"VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s, %s ,%s, %s, %s, %s, %s, False, "
								"%s, %s, %s, %s) RETURNING id ", 
								(name, ext_name, address, city, state, zip_code, 
								phone, fax, email, misc, tax_number, vendor, 
								customer, employee, custom1, custom2, 
								custom3, custom4, notes, term_id, 
								service_provider, checks_payable_to, 
								markup_id))
			self.contact_id = self.cursor.fetchone()[0]
		# all the individual contact info
		individual_id = self.builder.get_object('combobox3').get_active_id()
		name = self.builder.get_object('combobox-entry').get_text() 
		address = self.builder.get_object('entry18').get_text()
		city = self.builder.get_object('entry19').get_text()
		state = self.builder.get_object('entry20').get_text()
		zip_code = self.builder.get_object('entry21').get_text()
		phone = self.builder.get_object('entry22').get_text()
		fax = self.builder.get_object('entry23').get_text()
		email = self.builder.get_object('entry24').get_text()
		extension = self.builder.get_object('entry25').get_text()
		role = self.builder.get_object('entry12').get_text()
		if individual_id == None and name != '' :
			self.cursor.execute("INSERT INTO contact_individuals "
								"(name, address, city, state, zip, phone, "
								"fax, email, extension, role, contact_id) VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"RETURNING id", 
								(name, address, city, state, zip_code, 
								phone, fax, email, extension, role, self.contact_id))
			individual_id = self.cursor.fetchone()[0]
		elif individual_id != None:
			self.cursor.execute("UPDATE contact_individuals SET "
								"(name, address, city, state, zip, phone, "
								"fax, email, extension, role) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
								"WHERE id = %s", 
								(name, address, city, state, zip_code, 
								phone, fax, email, extension, role, individual_id))
		self.populate_individual_store ()
		self.builder.get_object('combobox3').set_active_id(str(individual_id))
		self.db.commit()
		self.populate_contacts ()
		self.populate_zip_codes ()
		
#*******************************************************************************
	#mailing list code
	
	def initiate_mailing_info(self):
		if self.contact_id == 0:
			self.builder.get_object("entry14").set_text("No Contact Selected")
			return
		set_entry14__text = "Not on any list"
		self.cursor.execute("SELECT ml.name FROM mailing_list_register AS mlr "
							"JOIN mailing_lists AS ml "
								"ON mlr.mailing_list_id = ml.id "
							"WHERE (contact_id, ml.active, mlr.active) = "
							"(%s, True, True)",
							(self.contact_id, )) 
		t =""  
		for i in self.cursor.fetchall():
			t = t + ".." + str(i[0])
			set_entry14__text = "On list: " + t
		self.builder.get_object("entry14").set_text(set_entry14__text)

	def mailing_list_icon_release (self, widget, icon, event):
		if self.contact_id == 0:
			return
		self.mailing_list_store = self.builder.get_object("mailing_list_store")
		entry14 = self.builder.get_object('entry14')
		self.mailing_list_store.clear()
		self.cursor.execute("SELECT ml.id, ml.name, COALESCE(mlr.active, False) "
							"FROM mailing_lists AS ml "
							"LEFT JOIN mailing_list_register AS mlr "
							"ON ml.id = mlr.mailing_list_id "
							"AND mlr.contact_id = %s AND mlr.active = True",
							(self.contact_id,))
		for item in self.cursor.fetchall():
			list_id = item[0]
			list_name = item[1]
			active = item[2]
			self.mailing_list_store.append([list_id, list_name, active])
		self.mailing_list_popover.set_relative_to(entry14)
		self.mailing_list_popover.show_all ()

	def active_toggled (self, cell_renderer, path):
		row_id = self.mailing_list_store[path][0]
		set_state = not cell_renderer.get_active()
		if set_state == True: # new
			self.cursor.execute("INSERT INTO mailing_list_register "
								"(contact_id, mailing_list_id) "
								"VALUES (%s,%s) ",
								(self.contact_id, row_id))
		elif set_state == False:
			self.cursor.execute("UPDATE mailing_list_register SET active = False "
								"WHERE (mailing_list_id,contact_id) = (%s,%s) ",
								(row_id, self.contact_id))
		self.db.commit()
		self.mailing_list_store[path][2] = set_state

		

