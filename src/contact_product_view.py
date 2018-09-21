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

UI_FILE = 'src/contact_product_view.ui'

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

	def populate_contacts (self):
		self.contacts_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
								"id::text, "
								"name, "
								"ext_name "
								"FROM contacts WHERE deleted = False "
								"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.contacts_store.append(row)
		c.close()

	def populate_products (self):
		self.products_store.clear()
		c = self.db.cursor()
		c.execute("SELECT "
					"id::text, "
					"name, "
					"ext_name "
					"FROM products "
					"WHERE (deleted, stock) = (False, True) "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.products_store.append(row)
		c.close()

	def contact_combo_changed (self, combobox):
		contact_id = combobox.get_active_id ()
		if contact_id == None:
			return
		self.contact_id = contact_id
		self.populating = True
		self.cursor.execute("SELECT name, ext_name, address, city, state, zip, "
							"phone, notes "
							"FROM contacts WHERE id = (%s)", 
							(contact_id, ))
		for row in self.cursor.fetchall():
			self.builder.get_object('c_name').set_text(row[0])
			self.builder.get_object('c_ext_name').set_text(row[1])
			self.builder.get_object('c_address').set_text(row[2])
			self.builder.get_object('c_city').set_text(row[3])
			self.builder.get_object('c_state').set_text(row[4])
			self.builder.get_object('c_zip').set_text(row[5])
			self.builder.get_object('c_phone').set_text(row[6])
			self.builder.get_object('notes_buffer').set_text(row[7])
		self.populating = False

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id ()
		if product_id == None:
			return
		self.product_id = product_id
		self.populating = True
		self.cursor.execute("SELECT "
								"p.name, "
								"p.ext_name, "
								"p.cost::money, "
								"COALESCE(pmp.price, 0.00)::money, "
								"description "
								"FROM products AS p "
								"LEFT JOIN products_markup_prices AS pmp ON pmp.product_id = p.id "
								"LEFT JOIN customer_markup_percent AS cmp ON cmp.id = pmp.markup_id "
								"WHERE p.id = (%s)", 
								(product_id, ))
		for row in self.cursor.fetchall():
			self.builder.get_object('p_name').set_text(row[0])
			self.builder.get_object('p_ext_name').set_text(row[1])
			self.builder.get_object('p_cost').set_text(row[2])
			self.builder.get_object('p_selling_price').set_text(row[3])
			self.builder.get_object('description_buffer').set_text(row[4])
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

	def contact_name_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET name = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def contact_ext_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET ext_name = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def address_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET address = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def city_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET city = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def state_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET state = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def zip_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET zip = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def phone_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE contacts SET phone = %s WHERE id = %s", 
							(text, self.contact_id))
		self.db.commit()

	def product_name_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE products SET name = %s WHERE id = %s", 
							(text, self.product_id))
		self.db.commit()

	def product_ext_name_changed (self, entry):
		if self.populating == True:
			return
		text = entry.get_text()
		self.cursor.execute("UPDATE products SET ext_name = %s WHERE id = %s", 
							(text, self.product_id))
		self.db.commit()
		

		


		