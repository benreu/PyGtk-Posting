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

def fractional_quantity_message (invoice_store):
	'''inventory is counted in whole units, so a fractional quantity of a tracked
	product would be silently truncated. Returns a message, or None if all is fine'''
	cursor = DB.cursor()
	message = None
	for row in invoice_store:
		if Decimal(row[1]) != int(Decimal(row[1])):
			cursor.execute("SELECT name, inventory_enabled FROM products "
							"WHERE id = %s", (row[2],))
			name, inventory_enabled = cursor.fetchone()
			if inventory_enabled:
				message = ("'%s' is tracked in inventory, so its quantity "
							"must be a whole number (%s)" % (name, row[1]))
				break
	cursor.close()
	return message

def negative_stock_message (invoice_store, location_id):
	'''a sale is allowed to take stock below zero (the count may be off), but the
	user should be told. Returns a message, or None if no product goes negative'''
	selling = {} # product id: quantity over all of its lines
	for row in invoice_store:
		selling[row[2]] = selling.get(row[2], 0) + int(Decimal(row[1]))
	line_ids = [row[0] for row in invoice_store]
	cursor = DB.cursor()
	lines = []
	for product_id, qty in selling.items():
		cursor.execute("SELECT name, inventory_enabled FROM products "
						"WHERE id = %s", (product_id,))
		name, inventory_enabled = cursor.fetchone()
		if not inventory_enabled:
			continue
		# lines already posted are rewritten by sell (), so they are not stock taken yet
		cursor.execute("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
						"FROM inventory_transactions "
						"WHERE product_id = %s AND location_id = %s "
						"AND (invoice_line_id IS NULL "
						"OR NOT invoice_line_id = ANY(%s))",
						(product_id, location_id, line_ids))
		on_hand = cursor.fetchone()[0]
		if on_hand - qty < 0:
			lines.append("'%s': %s on hand, selling %s (would be %s)" %
							(name, on_hand, qty, on_hand - qty))
	cursor.close()
	if lines:
		return "\n".join(lines)

def sell (invoice_store, location_id, contact_id, date):
	'''adjust inventory taking in consideration that invoices can be edited afterwards'''
	message = fractional_quantity_message (invoice_store)
	if message != None:
		raise ValueError(message)
	cursor = DB.cursor()
	for row in invoice_store:
		invoice_line_id = row[0]
		qty = int(Decimal(row[1])) # the store holds text like '1.00', qty_out is an integer
		product_id = row[2]
		#price carries the cost here, not the selling price; it is the basis the
		#cost of goods sold entry is posted from, the same as every other writer
		cursor.execute("SELECT inventory_enabled, cost "
						"FROM products WHERE id = %s", (product_id,))
		enabled, price = cursor.fetchone()
		if enabled == True:
			cursor.execute("UPDATE inventory_transactions "
							"SET (qty_out, product_id, location_id, "
							"date_inserted, price) = (%s, %s, %s, %s, %s) "
							"WHERE invoice_line_id = %s RETURNING id", 
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

def resync_invoice_inventory (invoice_id, location_id = None, date = None):
	'''follow an edit of a posted invoice into the ledger. A posted invoice can
	still be changed and every change is saved as it is typed, so the sale rows are
	rebuilt from invoice_items rather than from what is on screen: a line canceled
	after posting keeps its invoice_items row, and a product whose tracking was
	turned off has to lose its sale row altogether. A draft invoice is left alone,
	sell () takes its stock when it is posted. A location_id of None leaves every
	row where it is, and a date of None keeps the date the sale was recorded under,
	so correcting a quantity cannot move a posted sale into another month'''
	cursor = DB.cursor()
	cursor.execute("SELECT posted FROM invoices WHERE id = %s", (invoice_id,))
	row = cursor.fetchone()
	if row == None or row[0] == False: # sell () takes the stock at posting time
		cursor.close()
		return
	# a canceled line and a product no longer tracked both keep their invoice_items
	# row, so the sale row has to be dropped instead of updated
	cursor.execute("DELETE FROM inventory_transactions "
					"WHERE invoice_line_id IN "
						"(SELECT ii.id FROM invoice_items AS ii "
						"JOIN products AS p ON p.id = ii.product_id "
						"WHERE ii.invoice_id = %s "
						"AND (ii.canceled OR NOT p.inventory_enabled))",
					(invoice_id,))
	# TRUNC like sell () does; a plain cast rounds, which would change a quantity
	# the user never touched
	cursor.execute("UPDATE inventory_transactions AS it SET "
						"(qty_out, product_id, location_id, date_inserted, price) = "
						"(TRUNC(ii.qty)::int, ii.product_id, "
						"COALESCE(%s::int, it.location_id), "
						"COALESCE(%s::date, it.date_inserted), p.cost) "
					"FROM invoice_items AS ii "
					"JOIN products AS p ON p.id = ii.product_id "
					"WHERE it.invoice_line_id = ii.id "
					"AND (ii.invoice_id, ii.canceled, p.inventory_enabled) = "
						"(%s, False, True)",
					(location_id, date, invoice_id))
	# lines added after the invoice was posted still have to take their stock
	cursor.execute("INSERT INTO inventory_transactions "
						"(invoice_line_id, qty_out, product_id, price, "
						"location_id, date_inserted) "
					"SELECT ii.id, TRUNC(ii.qty)::int, ii.product_id, p.cost, "
						"COALESCE(%s::int, "
							"(SELECT it.location_id "
								"FROM inventory_transactions AS it "
								"JOIN invoice_items AS sibling "
									"ON sibling.id = it.invoice_line_id "
								"WHERE sibling.invoice_id = i.id "
								"ORDER BY it.id LIMIT 1), "
							"(SELECT id FROM locations ORDER BY id LIMIT 1)), "
						"COALESCE(%s::date, i.dated_for, CURRENT_DATE) "
					"FROM invoice_items AS ii "
					"JOIN invoices AS i ON i.id = ii.invoice_id "
					"JOIN products AS p ON p.id = ii.product_id "
					"WHERE (ii.invoice_id, ii.canceled, p.inventory_enabled) = "
						"(%s, False, True) "
					"AND NOT EXISTS (SELECT 1 FROM inventory_transactions "
						"WHERE invoice_line_id = ii.id)",
					(location_id, date, invoice_id))
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
						"AND NOT EXISTS (SELECT 1 FROM inventory_transactions AS it "
							"WHERE it.purchase_order_item_id = poli.id) "
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

def manufacture (manufacturing_id, destination_location_id = None):
	'''consume each component from its line's source location and add the
	finished product to the destination. Rerunning replaces the project's earlier
	rows. A source not set on the line, or a destination neither given nor saved
	on the project, falls back to the first location'''
	cursor = DB.cursor()
	cursor.execute("SELECT id FROM locations ORDER BY id LIMIT 1")
	first_location = cursor.fetchone()[0]
	if destination_location_id == None:
		cursor.execute("SELECT destination_location_id "
						"FROM manufacturing_projects WHERE id = %s",
						(manufacturing_id,))
		destination_location_id = cursor.fetchone()[0] or first_location
	cursor.execute("DELETE FROM inventory_transactions "
					"WHERE manufacturing_id = %s", (manufacturing_id,))
	cursor.execute("INSERT INTO inventory_transactions "
					"(manufacturing_id, product_id, qty_out, price, "
					"location_id, date_inserted) "
					"SELECT mi.manufacturing_project_id, mi.product_id, mi.qty, "
						"mi.cost, COALESCE(mi.source_location_id, %s), CURRENT_DATE "
					"FROM manufacturing_items AS mi "
					"JOIN products AS p ON p.id = mi.product_id "
					"WHERE mi.manufacturing_project_id = %s "
					"AND p.inventory_enabled AND mi.qty > 0",
					(first_location, manufacturing_id))
	cursor.execute("INSERT INTO inventory_transactions "
					"(manufacturing_id, product_id, qty_in, price, "
					"location_id, date_inserted) "
					"SELECT mp.id, mp.product_id, mp.qty, p.cost, %s, CURRENT_DATE "
					"FROM manufacturing_projects AS mp "
					"JOIN products AS p ON p.id = mp.product_id "
					"WHERE mp.id = %s AND p.inventory_enabled AND mp.qty > 0",
					(destination_location_id, manufacturing_id))
	cursor.close()


