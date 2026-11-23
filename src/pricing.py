# pricing.py
#
# Copyright (C) 2017 - reuben
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
from db_connection import DB

def get_customer_product_price (customer_id, product_id):
	cursor = DB.cursor()	
	cursor.execute("SELECT markup_percent_id FROM contacts WHERE id = %s", (customer_id, ))
	markup_id = cursor.fetchone()[0]
	cursor.execute("SELECT price FROM products_markup_prices WHERE (product_id, markup_id) = (%s, %s)", (product_id, markup_id))
	for row in cursor.fetchall():
		price = float(row[0])
		break
	else:
		cursor.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
		cost = float(cursor.fetchone()[0])
		cursor.execute("SELECT markup_percent FROM customer_markup_percent WHERE id = %s", (markup_id,))
		markup = float(cursor.fetchone()[0])
		margin = (markup / 100) * cost
		price = margin + cost
	cursor.close()
	DB.rollback()
	return price

def product_retail_price (product_id):
	cursor = DB.cursor()	
	cursor.execute("SELECT id FROM customer_markup_percent WHERE standard = True")
	markup_id = cursor.fetchone()[0]
	cursor.execute("SELECT price FROM products_markup_prices "
					"WHERE (product_id, markup_id) = (%s, %s)", 
					(product_id, markup_id))
	for row in cursor.fetchall():
		price = float(row[0])
		break
	else:
		cursor.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
		cost = float(cursor.fetchone()[0])
		cursor.execute("SELECT markup_percent FROM customer_markup_percent "
						"WHERE id = %s", (markup_id,))
		markup = float(cursor.fetchone()[0])
		margin = (markup / 100) * cost
		price = margin + cost
	cursor.close()
	DB.rollback()
	return price

		
class MarkupPriceGrid:
	'''A markup % and a sell price for every markup level
	(customer_markup_percent), kept in step with each other and with a cost
	spinbutton. Changing the cost keeps each level's markup % and moves its
	price; changing a markup % moves its price; changing a price moves its
	markup %. A price cannot go below the cost.
	The rows are attached to a Gtk.Grid under its header row (row 0), and start
	at each level's own markup % on the cost the spinbutton holds, which is
	what a new product shows until load() reads a saved one. Used by the
	product edit window, the purchase order's cost update and assembled
	products.'''
	def __init__ (self, grid, cost_spin):
		self.cost_spin = cost_spin
		#set while one handler writes a spinbutton, so the others do not
		#answer it and round the value the user typed back and forth
		self.updating = False
		self.rows = list() #(markup_id, default markup %, markup spin, sell spin)
		cost = cost_spin.get_value()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name, markup_percent "
						"FROM customer_markup_percent ORDER BY name")
		for top, (markup_id, name, percent) in enumerate(cursor.fetchall(), 1):
			percent = float(percent)
			label = Gtk.Label(label = name, xalign = 0, hexpand = True)
			markup_spin = Gtk.SpinButton.new_with_range(0.00, 5000.00, 1.00)
			markup_spin.set_digits(2)
			markup_spin.set_value(percent)
			sell_spin = Gtk.SpinButton.new_with_range(0.00, 100000.00, 1.00)
			sell_spin.set_digits(2)
			sell_spin.get_adjustment().set_lower(cost)
			sell_spin.set_value(cost + cost * percent / 100)
			markup_spin.connect('value-changed', self.markup_changed, sell_spin)
			sell_spin.connect('value-changed', self.sell_changed, markup_spin)
			grid.attach(label, 0, top, 1, 1)
			grid.attach(markup_spin, 1, top, 1, 1)
			grid.attach(sell_spin, 2, top, 1, 1)
			self.rows.append((markup_id, percent, markup_spin, sell_spin))
		cursor.close()
		DB.rollback()
		cost_spin.connect('value-changed', self.cost_changed)
		grid.show_all()

	def cost_changed (self, cost_spin):
		if self.updating:
			return
		cost = cost_spin.get_value()
		self.updating = True
		for markup_id, default, markup_spin, sell_spin in self.rows:
			sell_spin.get_adjustment().set_lower(cost)
			markup = markup_spin.get_value()
			sell_spin.set_value(cost + cost * markup / 100)
		self.updating = False

	def markup_changed (self, markup_spin, sell_spin):
		if self.updating:
			return
		cost = self.cost_spin.get_value()
		self.updating = True
		sell_spin.set_value(cost + cost * markup_spin.get_value() / 100)
		self.updating = False

	def sell_changed (self, sell_spin, markup_spin):
		if self.updating:
			return
		cost = self.cost_spin.get_value()
		if cost == 0.00:
			return # a markup % of nothing means nothing
		self.updating = True
		markup_spin.set_value((sell_spin.get_value() - cost) / cost * 100)
		self.updating = False

	def load (self, product_id):
		'''Each level's saved price for the product, and the markup % that price
		makes on the cost spinbutton's cost. A level with no saved price gets
		the level's own markup %. A product that costs 0, like labor, keeps its
		saved prices; its markup % shows the level's own, since a percentage of
		nothing means nothing.'''
		cost = self.cost_spin.get_value()
		cursor = DB.cursor()
		self.updating = True
		for markup_id, default, markup_spin, sell_spin in self.rows:
			sell_spin.get_adjustment().set_lower(cost)
			cursor.execute("SELECT price FROM products_markup_prices "
							"WHERE (product_id, markup_id) = (%s, %s)",
							(product_id, markup_id))
			row = cursor.fetchone()
			if row is None:
				markup = default
				price = cost + cost * markup / 100
			elif cost == 0.00:
				markup = default
				price = float(row[0])
			else:
				price = float(row[0])
				markup = (price - cost) / cost * 100
			markup_spin.set_value(markup)
			sell_spin.set_value(price)
		self.updating = False
		cursor.close()
		DB.rollback()

	def save (self, cursor, product_id):
		'''Write every level's price for the product on the caller's cursor; the
		caller commits. Update, or insert when there is no row yet, rather than
		ON CONFLICT: no update block creates products_markup_prices_unique, so an
		upgraded database may not have it.'''
		self.cost_spin.update() # a value still being typed
		for markup_id, default, markup_spin, sell_spin in self.rows:
			markup_spin.update()
			sell_spin.update()
		for markup_id, default, markup_spin, sell_spin in self.rows:
			price = sell_spin.get_value()
			cursor.execute("UPDATE products_markup_prices SET price = %s "
							"WHERE (product_id, markup_id) = (%s, %s)",
							(price, product_id, markup_id))
			if cursor.rowcount == 0:
				cursor.execute("INSERT INTO products_markup_prices "
								"(product_id, markup_id, price) "
								"VALUES (%s, %s, %s)",
								(product_id, markup_id, price))
