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
	def __init__ (self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = self.db.cursor()

		self.window = self.builder.get_object('window')
		self.window.maximize()
		self.populate_contacts()
		self.populate_products()
		self.window.show_all()
		#self.window.set_keep_below(True)
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
		#self.window.set_keep_below(False)
		#self.window.present()
		#self.window.maximize()

	def populate_contacts (self):
		store = self.builder.get_object('contacts_store')
		store.clear()
		self.cursor.execute("SELECT "
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
		for row in self.cursor.fetchall():
			store.append(row)

	def populate_products (self):
		store = self.builder.get_object('products_store')
		store.clear()
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
					"JOIN products_markup_prices AS pmp ON pmp.product_id = p.id "
					"JOIN customer_markup_percent AS cmp ON cmp.id = pmp.markup_id "
					"WHERE p.deleted = False "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			store.append(row)



		