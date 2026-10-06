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
from decimal import Decimal
from db_connection import DB

def sell (invoice_store, location_id, contact_id, date):
	'''adjust inventory taking in consideration that invoices can be edited afterwards'''
	cursor = DB.cursor()
	for row in invoice_store:
		invoice_line_id = row[0]
		qty = int(Decimal(row[1])) # the store holds text like '1.00', qty_out is an integer
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

def unsell (invoice_id):
	'''put the stock of a canceled invoice back by dropping its sale rows'''
	cursor = DB.cursor()
	cursor.execute("DELETE FROM inventory_transactions "
					"WHERE invoice_line_id IN "
					"(SELECT id FROM invoice_items WHERE invoice_id = %s)",
					(invoice_id,))
	cursor.close()

def restock (credit_memo_id):
	'''return credit memo items to the location they were sold from. Items whose
	sale never reached the ledger (invoiced before inventory was enabled) are
	skipped, because they were never deducted'''
	cursor = DB.cursor()
	cursor.execute("INSERT INTO inventory_transactions "
					"(product_id, qty_in, price, location_id, date_inserted, reason) "
					"SELECT ii.product_id, TRUNC(cmi.qty)::int, p.cost, "
						"sale.location_id, CURRENT_DATE, 'Credit memo returned' "
					"FROM credit_memo_items AS cmi "
					"JOIN invoice_items AS ii ON ii.id = cmi.invoice_item_id "
					"JOIN products AS p ON p.id = ii.product_id "
					"JOIN LATERAL (SELECT location_id FROM inventory_transactions "
						"WHERE invoice_line_id = ii.id "
						"ORDER BY id LIMIT 1) AS sale ON True "
					"WHERE cmi.credit_memo_id = %s AND NOT cmi.deleted "
					"AND p.inventory_enabled AND TRUNC(cmi.qty) > 0",
					(credit_memo_id,))
	cursor.close()

def receive (po_id, location_id):
	cursor = DB.cursor()
	cursor.execute("WITH cte AS "
						"(SELECT "
							"poli.id, "
							"poli.qty, "
							"poli.product_id, "
							"COALESCE(poli.price, 0), "
							"%s::int, "
							"CURRENT_DATE "
						"FROM purchase_order_items AS poli "
						"JOIN products AS p ON p.id = poli.product_id "
						"WHERE (poli.purchase_order_id, p.inventory_enabled, "
						"poli.canceled) = (%s, True, False) "
						"AND poli.qty > 0 "
						") "
					"INSERT INTO inventory_transactions "
					"(purchase_order_item_id, qty_in, product_id, "
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


