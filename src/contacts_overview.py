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
from constants import ui_directory, DB
from main import get_apsw_connection

UI_FILE = ui_directory + "/contacts_overview.ui"

class ContactsOverviewGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.name_filter = ''
		self.contact_store = self.get_object('contact_store')
		self.filtered_store = self.get_object('contact_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.populate_contact_store()
		self.window = self.get_object('window1')
		self.set_window_layout_from_settings ()
		self.window.show_all()
		GLib.idle_add(self.window.set_position, Gtk.WindowPosition.NONE)

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

	def filter_text_edited (self, store, path, text):
		store[path][1] = text
		self.name_filter = store[0][1]
		self.filtered_store.refilter()

	def filter_func(self, model, tree_iter, r):
		if self.name_filter not in model[tree_iter][1]:
			return False
		return True

	def contact_type_radiobutton_changed (self, radiobutton):
		if radiobutton.get_active() == True:
			self.populate_contact_store()

	def populate_contact_store (self):
		c = DB.cursor()
		self.contact_store.clear()
		if self.get_object('radiobutton1').get_active() == True:
			where = "WHERE customer = True"
		elif self.get_object('radiobutton2').get_active() == True:
			where = "WHERE vendor = True"
		elif self.get_object('radiobutton3').get_active() == True:
			where = "WHERE employee = True"
		elif self.get_object('radiobutton4').get_active() == True:
			where = "WHERE service_provider = True"
		else: # all contacts
			where = ""
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
		for row in c.fetchall():
			self.contact_store.append(row)
		DB.rollback()
		c.close()

	def contact_activated (self, treeview, treepath, treeviewcolumn):
		model, path = treeview.get_selection().get_selected_rows()
		contact_id = model[path][0]
		import contact_edit_main
		ce = contact_edit_main.ContactEditMainGUI(contact_id)
		ce.window.set_transient_for(self.window)

	def new_clicked (self, button):
		import contact_edit_main
		contact_edit_main.ContactEditMainGUI()

	def edit_clicked (self, button):
		model, path = self.get_object('treeview-selection2').get_selected_rows()
		if path == []:
			return
		contact_id = model[path][0]
		import contact_edit_main
		ce = contact_edit_main.ContactEditMainGUI(contact_id)
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




