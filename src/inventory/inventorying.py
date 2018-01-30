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
		qty -= qty * 2 #create a negative qty because we are selling
		product_id = row[2]
		cursor.execute("SELECT inventory_enabled "
						"FROM products WHERE id = %s", (product_id,))
		if cursor.fetchone()[0] == True:
			cursor.execute("SELECT id FROM inventory_transactions "
							"WHERE invoice_line_id = %s", 
							(invoice_line_id,))
			for row in cursor.fetchall():
				inventory_transaction_id = row[0]
				cursor.execute("UPDATE inventory_transactions "
								"SET (qty, product_id, location_id, "
								"date_inserted) = (%s, %s, %s, %s) "
								"WHERE id = %s", (qty, product_id, location_id, 
								date, inventory_transaction_id))
				break
			else:
				cursor.execute("INSERT INTO inventory_transactions "
								"(qty_out, product_id, "
								"invoice_line_id, location_id, "
								"date_inserted) VALUES (%s, %s, %s, %s, %s)",
								(qty, product_id, invoice_line_id, 
								location_id, date))
				break
		else:
			cursor.execute("DELETE FROM inventory_transactions "
							"WHERE invoice_line_id = %s", 
							(invoice_line_id,))
	db.commit()
	cursor.close()

def receive (db, purchase_order_store, location_id):
	cursor = db.cursor()
	for row in purchase_order_store:
		product_id = row[2]
		cursor.execute("SELECT inventory_enabled FROM products WHERE id = %s", (product_id,))
		t = cursor.fetchone()[0]
		if t == True:
			qty = row[1]
			cursor.execute("INSERT INTO inventory_transactions (qty_in, product_id, location_id, date_inserted) VALUES (%s, %s, %s, %s)", (qty, product_id, location_id, datetime.today()))
	db.commit()
	cursor.close()

def transfer (db, transfer_store):
	cursor = db.cursor()
	cursor.close()

def manufacture (db, manufacturing_id):
	cursor = db.cursor()
	
	cursor.close()


