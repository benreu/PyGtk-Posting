#duplicate_contact.py
# Copyright (C) 2016 reuben 
# 
# duplicate_contact is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# duplicate_contact is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk

UI_FILE = "src/admin/duplicate_contact.ui"

class DuplicateContactGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.name_filter = ''
		self.ext_name_filter = ''
		self.address_filter = ''
		self.city_filter = ''
		self.state_filter = ''
		self.zip_filter = ''
		self.fax_filter = ''
		self.phone_filter = ''
		self.email_filter = ''

		store = self.builder.get_object('filter_store')
		for row in [('Name', ''), ('Ext name', ''), ('Address', ''), ('City', ''), ('State', ''), ('Zip', ''), ('Fax', ''), ('Phone', ''), ('Email', '')]:
			store.append(row)
		self.duplicate_contact_store = self.builder.get_object('duplicate_contact_store')
		self.filtered_store = self.builder.get_object(
													'duplicate_contact_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.merging = False
		
		self.db = db
		self.cursor = db.cursor()
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def filter_text_edited (self, store, path, text):
		store[path][1] = text
		self.name_filter = store[0][1]
		self.ext_name_filter = store[1][1]
		self.address_filter = store[2][1]
		self.city_filter = store[3][1]
		self.state_filter = store[4][1]
		self.zip_filter = store[5][1]
		self.fax_filter = store[6][1]
		self.phone_filter = store[7][1]
		self.email_filter = store[8][1]
		self.filtered_store.refilter()

	def filter_func(self, model, tree_iter, r):
		if self.name_filter not in model[tree_iter][1]:
			return False
		if self.ext_name_filter not in model[tree_iter][2]:
			return False
		if self.address_filter not in model[tree_iter][3]:
			return False
		if self.city_filter not in model[tree_iter][4]:
			return False
		if self.state_filter not in model[tree_iter][5]:
			return False
		if self.zip_filter not in model[tree_iter][6]:
			return False
		if self.fax_filter not in model[tree_iter][7]:
			return False
		if self.phone_filter not in model[tree_iter][8]:
			return False
		if self.email_filter not in model[tree_iter][9]:
			return False
		return True

	def duplicate_contact_selection_changed (self, selection):
		model, path = selection.get_selected_rows()
		if self.merging == False and len(path) >= 1: # multiple contacts selected
			self.paths = path
			self.builder.get_object('revealer1').set_reveal_child(True)
		elif self.merging == True and len(path) < 2: # ask for single contact
			self.builder.get_object('revealer2').set_reveal_child(True)
			self.builder.get_object('revealer1').set_reveal_child(False)
			if len(path) == 1: # single contact selected
				self.builder.get_object('button2').set_sensitive(True)
			else:
				self.builder.get_object('button2').set_sensitive(False)
		else:    # nothing selected
			self.builder.get_object('revealer1').set_reveal_child(False)
			self.builder.get_object('revealer2').set_reveal_child(False)

	def merge_clicked (self, button):
		self.merging = False
		selection = self.builder.get_object('treeview-selection2')
		model, path = selection.get_selected_rows()
		final_contact_id = model[path][0]
		for p in self.paths:
			contact_id = model[p][0]
			self.cursor.execute("UPDATE files SET contact_id = %s "
								"WHERE contact_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE incoming_invoices "
								"SET contact_id = %s WHERE contact_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE invoices "
								"SET customer_id = %s WHERE customer_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE job_sheets "
								"SET contact_id = %s WHERE contact_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE payments_incoming "
								"SET customer_id = %s WHERE customer_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE purchase_orders "
								"SET vendor_id = %s WHERE vendor_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE resources "
								"SET contact_id = %s WHERE contact_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("UPDATE statements "
								"SET customer_id = %s WHERE customer_id = %s", 
								(final_contact_id, contact_id))
			self.cursor.execute("DELETE FROM vendor_product_numbers "
								"WHERE vendor_id = %s", 
								(contact_id,))
			self.cursor.execute("DELETE FROM contacts WHERE id = %s", 
								(contact_id,))
			self.cursor.execute("UPDATE contacts SET deleted = False "
								"WHERE id = %s", (final_contact_id,))
		self.db.commit()
		selection.unselect_all()
		self.populate_duplicate_contact_store ()

	def cancel_clicked (self, button):
		self.merging = False
		self.populate_duplicate_contact_store ()

	def merging_continue_clicked (self, button):
		self.merging = True

	def duplicate_selector_cursor_changed(self, treeview):
		self.merging = False
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.search = model[path][1]
		column = model[path][2]
		self.builder.get_object(column).clicked()
		self.populate_duplicate_contact_store ()

	def populate_duplicate_contact_store (self):
		self.duplicate_contact_store.clear()
		self.cursor.execute("SELECT id, name, ext_name, address, city, state, zip, "
							"fax, phone, email FROM contacts c_outer "
							"WHERE (SELECT count(%s) FROM contacts c_inner "
							"WHERE c_inner.%s = c_outer.%s) > 1 "
							"AND c_outer.%s != ''" % 
							(self.search, self.search, 
							self.search, self.search))
		for row in self.cursor.fetchall():
			contact_id = row[0]
			name = row[1]
			ext_name = row[2]
			address = row[3]
			city = row[4]
			state = row[5]
			zip = row[6]
			fax = row[7]
			phone = row[8]
			email = row[9]
			self.duplicate_contact_store.append([contact_id, name, ext_name, address,
												city, state, zip, fax, phone, email])






			