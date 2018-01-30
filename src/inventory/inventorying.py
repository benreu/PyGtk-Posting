# inventorying.py
#
# Copyright (C) 2016 - reuben
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

from datetime import datetime


def sell (db, invoice_store, location_id, contact_id, date):
	'''adjust inventory taking in consideration that invoices can be edited afterwards'''
	cursor = db.cursor()
	for row in invoice_store:
		invoice_line_id = row[0]
		qty = row[1]
		product_id = row[2]
		price = row[6]
		cursor.execute("SELECT inventory_enabled "
						"FROM products WHERE id = %s", (product_id,))
		if cursor.fetchone()[0] == True:
			cursor.execute("UPDATE inventory_transactions "
							"SET (qty_out, product_id, location_id, "
							"date_inserted, price) = (%s, %s, %s, %s, %s) "
							"WHERE id = (SELECT id FROM inventory_transactions "
							"WHERE invoice_line_id = %s) RETURNING id", 
							(qty, product_id, location_id, 
							date, inventory_transaction_id, price, 
							invoice_line_id))
			for row in cursor.fetchall():
				break
			else:
				cursor.execute("INSERT INTO inventory_transactions "
								"(qty_out, product_id, "
								"invoice_line_id, location_id, "
								"date_inserted, price) VALUES (%s, %s, %s, %s, %s, %s)",
								(qty, product_id, invoice_line_id, 
								location_id, date, price))
		else:
			cursor.execute("DELETE FROM inventory_transactions "
							"WHERE invoice_line_id = %s", 
							(invoice_line_id,))
	cursor.close()

def receive (db, purchase_order_store, location_id):
	cursor = db.cursor()
	for row in purchase_order_store:
		line_id = row[0]
		product_id = row[2]
		price = row[7]
		cursor.execute("SELECT inventory_enabled FROM products WHERE id = %s", (product_id,))
		if cursor.fetchone()[0] == True:
			qty = row[1]
			cursor.execute("INSERT INTO inventory_transactions "
							"(qty_in, product_id, location_id, price, purchase_order_line_id, date_inserted) "
							"VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)", 
							(qty, product_id, location_id, price, line_id))
	cursor.close()

def transfer (db, transfer_store):
	cursor = db.cursor()
	cursor.close()

def manufacture (db, manufacturing_id):
	cursor = db.cursor()
	
	cursor.close()


