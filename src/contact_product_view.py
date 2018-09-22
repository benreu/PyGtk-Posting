# contact_product_view.py
#
# Copyright (C) 2018 - reuben
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


from gi.repository import Gtk, GLib
import main

UI_FILE = main.ui_directory + "/contact_product_view.ui"

class ContactProductViewGUI :
	def __init__ (self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()

		self.window = self.builder.get_object('window')
		self.window.maximize()
		self.contacts_store = self.builder.get_object('contacts_store')
		self.products_store = self.builder.get_object('products_store')
		self.populate_contacts()
		self.populate_products()
		self.window.show_all()
		self.size_widgets()

	def size_widgets (self):
		while Gtk.events_pending():
			Gtk.main_iteration()
		window_size = self.window.get_size()
		width = window_size.width * 0.65
		height = window_size.height * 0.8
		self.builder.get_object('center_pane').set_position(width)
		self.builder.get_object('notes_pane').set_position(height)
		self.builder.get_object('description_pane').set_position(height)

	def populate_contacts (self):
		self.contacts_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
								"id, "
								"name, "
								"ext_name, "
								"address, "
								"city, "
								"state, "
								"zip, "
								"phone, "
								"customer, "
								"vendor, "
								"service_provider "
								"FROM contacts WHERE deleted = False "
								"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.contacts_store.append(row)
		c.close()

	def populate_products (self):
		self.products_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
					"p.id, "
					"p.name, "
					"p.ext_name, "
					"COALESCE(pmp.price, 0.00), "
					"COALESCE(pmp.price::text, 'N/A'), "
					"sellable, "
					"purchasable, "
					"manufactured "
					"FROM products AS p "
					"LEFT JOIN products_markup_prices AS pmp ON pmp.product_id = p.id "
					"LEFT JOIN customer_markup_percent AS cmp ON cmp.id = pmp.markup_id "
					"WHERE (p.deleted, stock) = (False, True) "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.products_store.append(row)
		c.close()

	def contact_treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.builder.get_object('contact_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.builder.get_object('product_menu')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def contact_hub_activated (self, menuitem):
		import contact_hub
		contact_hub.ContactHubGUI(self.main, self.contact_id)

	def product_hub_activated (self, menuitem):
		import product_hub
		product_hub.ProductHubGUI(self.main, self.product_id)

	def contact_treeview_selection_changed (self, selection):
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.populating = True
		self.contact_id = model[path][0]
		self.cursor.execute("SELECT notes FROM contacts WHERE id = %s", 
							(self.contact_id,))
		notes = self.cursor.fetchone()[0]
		self.builder.get_object('notes_buffer').set_text(notes)
		self.populating = False

	def product_treeview_selection_changed (self, selection):
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.populating = True
		self.product_id = model[path][0]
		self.cursor.execute("SELECT description FROM products WHERE id = %s", 
							(self.product_id,))
		description = self.cursor.fetchone()[0]
		self.builder.get_object('description_buffer').set_text(description)
		self.populating = False

	def notes_changed (self, textbuffer):
		if self.populating == True:
			return
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		text = textbuffer.get_text(start, end, True)
		self.cursor.execute("UPDATE contacts SET notes = %s "
							"WHERE id = %s", (text, self.contact_id))
		self.db.commit()

	def description_changed (self, textbuffer):
		if self.populating == True:
			return
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		text = textbuffer.get_text(start, end, True)
		self.cursor.execute("UPDATE products SET description = %s "
							"WHERE id = %s", (text, self.product_id))
		self.db.commit()

	def contact_name_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET name = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][1] = text
		self.db.commit()

	def contact_ext_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET ext_name = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][2] = text
		self.db.commit()

	def address_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET address = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][3] = text
		self.db.commit()

	def city_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET city = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][4] = text
		self.db.commit()

	def state_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET state = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][5] = text
		self.db.commit()

	def zip_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET zip = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][6] = text
		self.db.commit()

	def phone_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE contacts SET phone = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][7] = text
		self.db.commit()

	def is_customer_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][8]
		self.cursor.execute("UPDATE contacts SET customer = %s WHERE id = %s", 
							(active, row_id))
		self.contacts_store[path][8] = active
		self.db.commit()

	def is_vendor_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][9]
		self.cursor.execute("UPDATE contacts SET vendor = %s WHERE id = %s", 
							(active, row_id))
		self.contacts_store[path][9] = active
		self.db.commit()

	def is_service_provider_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][10]
		self.cursor.execute("UPDATE contacts SET service_provider = %s "
							"WHERE id = %s", (active, row_id))
		self.contacts_store[path][10] = active
		self.db.commit()

	def product_name_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE products SET name = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][1] = text
		self.db.commit()

	def product_ext_name_edited (self, cellrenderertext, path, text):
		row_id = self.contacts_store[path][0]
		self.cursor.execute("UPDATE products SET ext_name = %s WHERE id = %s", 
							(text, row_id))
		self.contacts_store[path][2] = text
		self.db.commit()

	def is_sellable_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][5]
		self.cursor.execute("UPDATE products SET sellable = %s "
							"WHERE id = %s", (active, row_id))
		self.contacts_store[path][5] = active
		self.db.commit()

	def is_purchasable_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][6]
		self.cursor.execute("UPDATE products SET purchasable = %s "
							"WHERE id = %s", (active, row_id))
		self.contacts_store[path][6] = active
		self.db.commit()

	def is_manufactured_toggled (self, cellrenderertoggle, path):
		row_id = self.contacts_store[path][0]
		active = not self.contacts_store[path][7]
		self.cursor.execute("UPDATE products SET manufactured = %s "
							"WHERE id = %s", (active, row_id))
		self.contacts_store[path][7] = active
		self.db.commit()

		

		


		
