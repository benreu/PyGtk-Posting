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
from constants import DB

def sell (invoice_store, location_id, contact_id, date):
	'''adjust inventory taking in consideration that invoices can be edited afterwards'''
	cursor = DB.cursor()
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
							date, price, invoice_line_id))
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

def receive (po_id, location_id):
	cursor = DB.cursor()
	cursor.execute("WITH cte AS "
						"(SELECT "
							"poli.id, "
							"poli.qty, "
							"poli.product_id, "
							"poli.price, "
							"%s::int, "
							"CURRENT_DATE "
						"FROM purchase_order_items AS poli "
						"JOIN products AS p ON p.id = poli.product_id "
						"WHERE (poli.purchase_order_id, p.inventory_enabled) = "
						"(%s, True) "
						") "
					"INSERT INTO inventory_transactions "
					"(purchase_order_line_id, qty_in, product_id, "
					"price, location_id, date_inserted"
					") "
					"SELECT * FROM cte", 
					(location_id, po_id))
	cursor.close()

def transfer (transfer_store):
	cursor = DB.cursor()
	cursor.close()

def manufacture (manufacturing_id):
	cursor = DB.cursor()
	
	cursor.close()


