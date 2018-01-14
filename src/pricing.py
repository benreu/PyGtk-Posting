# pricing.py
#
# Copyright (C) 2017 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

def get_customer_product_price (db, customer_id, product_id):
	cursor = db.cursor()	
	cursor.execute("SELECT terms_and_discounts_id FROM contacts WHERE id = %s", (customer_id, ))
	term_id = cursor.fetchone()[0]
	cursor.execute("SELECT price FROM products_terms_prices WHERE (product_id, term_id) = (%s, %s)", (product_id, term_id))
	for row in cursor.fetchall():
		price = float(row[0])
		break
	else:
		cursor.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
		cost = float(cursor.fetchone()[0])
		cursor.execute("SELECT markup_percent FROM terms_and_discounts WHERE id = %s", (term_id,))
		markup = float(cursor.fetchone()[0])
		margin = (markup / 100) * cost
		price = margin + cost
	return price

def product_retail_price (db, product_id):
	cursor = db.cursor()	
	cursor.execute("SELECT id FROM terms_and_discounts WHERE standard = True")
	term_id = cursor.fetchone()[0]
	cursor.execute("SELECT price FROM products_terms_prices "
					"WHERE (product_id, term_id) = (%s, %s)", 
					(product_id, term_id))
	for row in cursor.fetchall():
		price = float(row[0])
		break
	else:
		cursor.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
		cost = float(cursor.fetchone()[0])
		cursor.execute("SELECT markup_percent FROM terms_and_discounts "
						"WHERE id = %s", (term_id,))
		markup = float(cursor.fetchone()[0])
		margin = (markup / 100) * cost
		price = margin + cost
	return price

		