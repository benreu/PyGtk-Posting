# product_markup.py
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/product_markup.ui"


class ProductMarkupGUI (Gtk.Builder):
	def __init__ (self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.store = self.get_object("product_markup_store")
		self.populate_markup_store ()
		window = self.get_object("window")
		window.show_all()

	def populate_markup_store (self):
		c = DB.cursor()
		c.execute("SELECT *, markup::text FROM "
					"(SELECT "
						"p.id, "
						"p.name, "
						"p.ext_name, "
						"(((GREATEST(pmp.price, 0.01) / GREATEST(p.cost, 0.01))"
							"-1) * 100)::numeric(12, 2) "
							"AS markup " 
						"FROM products AS p "
					"JOIN products_markup_prices AS pmp "
						"ON pmp.product_id = p.id "
					"JOIN customer_markup_percent "
						"AS cmp ON cmp.id = pmp.markup_id "
						"AND cmp.standard = True "
					"GROUP BY p.id, p.name, markup "
					"ORDER BY markup DESC ) AS m")
		for row in c.fetchall():
			self.store.append(row)
		c.close()
		DB.rollback()


