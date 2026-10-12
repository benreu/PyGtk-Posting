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
from db import transactor

def first_location_id (cursor = None):
	'''the location every writer falls back to when none is named: the oldest
	one. manufacture () and the project window have to agree on this, or the
	shortfall the window shows is not the stock the post consumes. A caller
	already inside a transaction hands in its own cursor rather than have a
	second one opened on it'''
	own_cursor = cursor == None
	if own_cursor:
		cursor = DB.cursor()
	cursor.execute("SELECT id FROM locations ORDER BY id LIMIT 1")
	row = cursor.fetchone()
	if own_cursor:
		cursor.close()
	return row[0] if row != None else None

def on_hand (product_id, location_id = None, cursor = None):
	'''what a product holds: at one location, or over all of them when
	location_id is None. A list that spans every location shows the company wide
	figure and has to say so; anything that acts on stock at one place -- a sale,
	a build, an adjustment, a count -- has to name the location, or it measures
	against stock it cannot touch. A caller already inside a transaction hands in
	its own cursor, the same as first_location_id'''
	own_cursor = cursor == None
	if own_cursor:
		cursor = DB.cursor()
	cursor.execute("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
					"FROM inventory_transactions WHERE product_id = %s "
					"AND (%s::int IS NULL OR location_id = %s)",
					(product_id, location_id, location_id))
	qty = cursor.fetchone()[0]
	if own_cursor:
		cursor.close()
	return qty

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
	cursor.execute("SELECT posted AND NOT canceled FROM invoices "
					"WHERE id = %s", (invoice_id,))
	row = cursor.fetchone()
	# sell () takes the stock at posting time, and unsell () has already put the
	# stock of a canceled invoice back
	if row == None or row[0] == False:
		cursor.close()
		return
	# a canceled line and a product no longer tracked both keep their invoice_items
	# row, so the sale row has to be dropped instead of updated. The cost of goods
	# sold entry the row carries is zeroed first: dropping the row only breaks the
	# link, the entry itself would stay in the ledger, and nothing here deletes
	# from gl_entries
	cursor.execute("UPDATE gl_entries SET amount = 0.00 WHERE id IN "
					"(SELECT it.gl_entries_id FROM inventory_transactions AS it "
						"JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
						"JOIN products AS p ON p.id = ii.product_id "
						"WHERE ii.invoice_id = %s "
						"AND (ii.canceled OR NOT p.inventory_enabled) "
						"AND it.gl_entries_id IS NOT NULL)",
					(invoice_id,))
	cursor.execute("DELETE FROM inventory_transactions "
					"WHERE invoice_line_id IN "
						"(SELECT ii.id FROM invoice_items AS ii "
						"JOIN products AS p ON p.id = ii.product_id "
						"WHERE ii.invoice_id = %s "
						"AND (ii.canceled OR NOT p.inventory_enabled))",
					(invoice_id,))
	# TRUNC like sell () does; a plain cast rounds, which would change a quantity
	# the user never touched. The price is the cost the sale was relieved at and
	# stays put, the same promise post_invoice_cogs and restock () make: a cost
	# change must not restate a sale that is already posted. A line whose product
	# changed is a different good that was never relieved, so it takes the new
	# product's cost
	cursor.execute("UPDATE inventory_transactions AS it SET "
						"(qty_out, product_id, location_id, date_inserted, price) = "
						"(TRUNC(ii.qty)::int, ii.product_id, "
						"COALESCE(%s::int, it.location_id), "
						"COALESCE(%s::date, it.date_inserted), "
						"CASE WHEN it.product_id = ii.product_id "
							"THEN it.price ELSE p.cost END) "
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
	# the cost of goods sold entries belong to the invoice's own transaction, the
	# one post_invoice_cogs writes them to at posting time. Under cash basis the
	# invoice has none until it is paid, and no cost is due yet either, so the
	# stock work above stands on its own
	cursor.execute("SELECT ge.gl_transaction_id, "
						"COALESCE(%s::date, i.dated_for, CURRENT_DATE) "
					"FROM invoices AS i "
					"JOIN gl_entries AS ge ON ge.id = i.gl_entries_id "
					"WHERE i.id = %s", (date, invoice_id))
	row = cursor.fetchone()
	if row != None:
		# it books the rows added above, which carry no entry yet, and writes the
		# amounts of the ones that do back, so it covers both halves of an edit
		transactor.post_invoice_cogs (cursor, invoice_id, row[0], row[1])
	cursor.close()

def unsell (invoice_id):
	'''put the stock of a canceled invoice back by zeroing its sale rows. The rows
	stay so that the cost of goods sold entry hanging off gl_entries_id keeps its
	link, and so restock() can still find the location the item was sold from'''
	cursor = DB.cursor()
	cursor.execute("UPDATE inventory_transactions SET qty_out = 0 "
					"WHERE invoice_line_id IN "
					"(SELECT id FROM invoice_items WHERE invoice_id = %s)",
					(invoice_id,))
	cursor.close()

def restock (credit_memo_id):
	'''return credit memo items to the location they were sold from, valued at the
	cost they left at rather than at the cost the product carries now, so the entry
	that reverses the cost of the sale cancels it exactly. Items whose sale never
	reached the ledger (invoiced before inventory was enabled) are skipped, because
	they were never deducted. Posting the same memo twice restocks once. The row
	is dated with the memo, the date it prints with and the date its ledger
	entries take, the way sell () dates a sale with its invoice'''
	cursor = DB.cursor()
	cursor.execute("INSERT INTO inventory_transactions "
					"(product_id, qty_in, price, location_id, date_inserted, "
					"reason, credit_memo_item_id) "
					"SELECT ii.product_id, TRUNC(cmi.qty)::int, sale.price, "
						"sale.location_id, "
						"COALESCE(cm.dated_for, cm.date_created), "
						"'Credit memo returned', cmi.id "
					"FROM credit_memo_items AS cmi "
					"JOIN credit_memos AS cm ON cm.id = cmi.credit_memo_id "
					"JOIN invoice_items AS ii ON ii.id = cmi.invoice_item_id "
					"JOIN products AS p ON p.id = ii.product_id "
					"JOIN LATERAL (SELECT location_id, price "
						"FROM inventory_transactions "
						"WHERE invoice_line_id = ii.id "
						"ORDER BY id LIMIT 1) AS sale ON True "
					"WHERE cmi.credit_memo_id = %s AND NOT cmi.deleted "
					"AND p.inventory_enabled AND TRUNC(cmi.qty) > 0 "
					"AND NOT EXISTS (SELECT 1 FROM inventory_transactions "
						"WHERE credit_memo_item_id = cmi.id)",
					(credit_memo_id,))
	cursor.close()

def receive (po_id, location_id = None):
	'''posts what has arrived on an order and has not been posted yet. A line's
	receipt is the count the receive window entered,
	purchase_order_items.received; a line that window never counted arrives in
	full, which is what every order did before it could be received in part, and
	what the lines the window cannot list still need: an expense product that is
	tracked in inventory anyway, and a line added to the order while the window
	was open. Only the shortfall is written, as one row dated today, so a second
	shipment is a receipt of its own on its own date and receiving again with
	nothing new in between writes nothing. A count that has come down takes the
	rows with it. A location of None takes the one the order's last receipt used,
	for the resync path, which has no window to ask'''
	cursor = DB.cursor()
	if location_id == None:
		cursor.execute("SELECT it.location_id FROM inventory_transactions AS it "
						"JOIN purchase_order_items AS poli "
							"ON poli.id = it.purchase_order_item_id "
						"WHERE poli.purchase_order_id = %s "
						"ORDER BY it.id DESC LIMIT 1", (po_id,))
		row = cursor.fetchone()
		location_id = row[0] if row != None else first_location_id (cursor)
	transactor.trim_purchase_order_receipts (cursor, po_id)
	#a canceled line is left out rather than counted as zero: its rows are
	#already zeroed, by cancel_purchase_order_item and by the trim above, while
	#the count it was received at stays on the line, and a shortfall measured
	#against that count would post the canceled stock all over again
	cursor.execute("WITH cte AS "
						"(SELECT "
							"poli.id, "
							"COALESCE(poli.received, poli.qty)::int "
								"- COALESCE(posted.qty_in, 0), "
							"poli.product_id, "
							"COALESCE(poli.price, 0), "
							"%s::int, "
							"CURRENT_DATE "
						"FROM purchase_order_items AS poli "
						"JOIN products AS p ON p.id = poli.product_id "
						"LEFT JOIN LATERAL (SELECT SUM(it.qty_in) AS qty_in "
							"FROM inventory_transactions AS it "
							"WHERE it.purchase_order_item_id = poli.id) "
							"AS posted ON True "
						"WHERE (poli.purchase_order_id, p.inventory_enabled, "
						"poli.canceled) = (%s, True, False) "
						"AND COALESCE(poli.received, poli.qty)::int "
							"> COALESCE(posted.qty_in, 0) "
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

def manufacturing_shortage_message (manufacturing_id):
	'''a build is allowed to take stock below zero (the count may be off), but
	the user should be told, the same as a sale is. Each line is measured against
	its own source location, the one manufacture () will consume it from: stock
	the company holds anywhere else is not stock this build can use. Returns a
	message naming the short components, or None when every line is covered'''
	cursor = DB.cursor()
	params = {'project_id': manufacturing_id,
					'first_location': first_location_id(cursor)}
	cursor.execute("SELECT p.name, sl.name, src.qty, mi.qty "
					"FROM manufacturing_items AS mi "
					"JOIN products AS p ON p.id = mi.product_id "
					"JOIN locations AS sl "
						"ON sl.id = COALESCE(mi.source_location_id, "
							"%(first_location)s) "
					# the rows this project already wrote are not stock taken yet: a
					# repost deletes and rewrites them, so they are discounted here
					# the way negative_stock_message discounts the invoice it is
					# called for
					"JOIN LATERAL (SELECT COALESCE(SUM(it.qty_in - it.qty_out), 0) "
							"AS qty FROM inventory_transactions AS it "
							"WHERE it.product_id = mi.product_id "
							"AND it.location_id = "
								"COALESCE(mi.source_location_id, %(first_location)s) "
							"AND (it.manufacturing_id IS NULL "
							"OR it.manufacturing_id <> %(project_id)s)) AS src "
						"ON True "
					"WHERE mi.manufacturing_project_id = %(project_id)s "
					# the lines manufacture () moves stock for, and no others
					"AND p.inventory_enabled AND mi.qty > 0 "
					"AND src.qty < mi.qty "
					"ORDER BY p.name", params)
	lines = ["'%s': %s on hand at %s, consuming %s (would be %s)" %
					(name, on_hand, location, qty, on_hand - qty)
					for name, location, on_hand, qty in cursor.fetchall()]
	cursor.close()
	if lines:
		return "\n".join(lines)

def manufacture (manufacturing_id, destination_location_id = None):
	'''consume each component from its line's source location and add the
	finished product to the destination. Rerunning replaces the project's earlier
	rows. A source not set on the line, or a destination neither given nor saved
	on the project, falls back to the first location'''
	cursor = DB.cursor()
	first_location = first_location_id(cursor)
	if destination_location_id == None:
		cursor.execute("SELECT destination_location_id "
						"FROM manufacturing_projects WHERE id = %s",
						(manufacturing_id,))
		destination_location_id = cursor.fetchone()[0] or first_location
	# the transaction an earlier post wrote to, found while the rows that point
	# at it are still here: this is the last moment it can be found at all, and
	# handing it on is what keeps a rebuilt project to the one transaction
	cursor.execute("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
					"WHERE ge.id = (SELECT gl_entries_id "
						"FROM inventory_transactions "
						"WHERE manufacturing_id = %s "
						"AND gl_entries_id IS NOT NULL ORDER BY id LIMIT 1)",
					(manufacturing_id,))
	row = cursor.fetchone()
	transaction_id = row[0] if row != None else None
	if transaction_id != None:
		# zero the entries of an earlier post before the rows pointing at them
		# go. Dropping a row only breaks the link, the entry would stay in the
		# ledger and the new post would count the build twice. The whole
		# transaction is zeroed, which takes the variance entry with it, and
		# re-dated with the build so nothing is left behind in a period the
		# transaction no longer sits in
		cursor.execute("UPDATE gl_entries SET (amount, date_inserted) = "
							"(0.00, CURRENT_DATE) "
						"WHERE gl_transaction_id = %s", (transaction_id,))
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
	transactor.post_manufacturing_value (cursor, manufacturing_id,
										transaction_id)
	cursor.close()

def uncorrectable_count_message (count_summary_id):
	'''a counted product the close has to leave alone: one that is not tracked yet
	and has nowhere to carry its value, or that the rest of the application does
	not treat as stock at all. A product that is already tracked is never in here,
	its stock is real and the count is the authority on it. Returns a message
	naming them, or None when every counted product can be corrected'''
	cursor = DB.cursor()
	cursor.execute("SELECT p.name, p.ext_name, p.inventory_account IS NULL "
					"FROM inventory.count_rows AS cr "
					"JOIN products AS p ON p.id = cr.product_id "
					"WHERE cr.count_summary_id = %s "
					"AND NOT p.inventory_enabled "
					"AND (p.inventory_account IS NULL "
						"OR NOT p.stock OR p.deleted) "
					"ORDER BY p.name, p.ext_name", (count_summary_id,))
	lines = []
	for name, ext_name, no_account in cursor.fetchall():
		reason = 'no inventory account' if no_account else 'not a stocked product'
		lines.append("'%s %s': %s" % (name, ext_name, reason))
	cursor.close()
	if lines:
		return "\n".join(lines)

def close_count (count_summary_id, date = None):
	'''make the books agree with what was counted, then close the count. Only a
	product with a count row is touched, and only at the location the summary
	names: a product nobody counted was not looked at, and no count row is not
	evidence of no stock. What gets written is the difference between the counted
	quantity and what that location holds, so a product counted at the quantity
	the books already carry costs nothing and gets no row at all.

	A counted product that is not tracked yet holds nothing at the location, so
	the difference is the whole counted quantity, which is the opening stock
	inventory_adjustment writes by hand: one formula covers both and tracking is
	turned on afterwards. A product with no inventory account has nowhere for that
	value to sit, and one the application does not treat as stock would start
	taking sale rows forever after, so both are skipped and named by
	uncorrectable_count_message rather than guessed at. The count still values
	them, what was counted does not depend on what the books could do with it.

	A count row at zero is a correction like any other. inventory_compare exists
	to write those rows, they are the user saying the shelf is empty, and skipping
	them the way restock and receive skip empty lines would quietly keep stock
	that is not there.

	Nothing here commits, so the corrections, the ledger entries and the close
	itself are one unit and a failure anywhere leaves the count open and the books
	untouched. A date of None means today, and the stock rows, the entries and
	date_ended all take it, so one close cannot straddle two periods.

	Returns the number of products corrected'''
	if date == None:
		date = datetime.today()
	cursor = DB.cursor()
	# the lock is what stops two windows closing the same count at once; active
	# read behind it is the first of the guards against closing one twice
	cursor.execute("SELECT active, location_id, name "
					"FROM inventory.count_summaries WHERE id = %s FOR UPDATE",
					(count_summary_id,))
	row = cursor.fetchone()
	if row == None:
		cursor.close()
		return 0
	active, location_id, name = row
	if active == False:
		cursor.close()
		return 0
	if location_id == None:
		cursor.close()
		raise ValueError("'%s' has no location, so there is nothing to compare "
							"the count against" % name)
	# TRUNC rather than a cast, which rounds: see resync_invoice_inventory. The
	# variance is taken from the truncated count so the stock row agrees with it
	cursor.execute("INSERT INTO inventory_transactions "
						"(product_id, qty_in, qty_out, date_inserted, "
						"location_id, price, reason, count_summary_id) "
					"SELECT cr.product_id, "
						"GREATEST(TRUNC(cr.qty)::int - on_hand.qty, 0), "
						"GREATEST(on_hand.qty - TRUNC(cr.qty)::int, 0), "
						"%s, cs.location_id, cr.cost, 'Inventory count', cs.id "
					"FROM inventory.count_rows AS cr "
					"JOIN inventory.count_summaries AS cs "
						"ON cs.id = cr.count_summary_id "
					"JOIN products AS p ON p.id = cr.product_id "
					"JOIN LATERAL (SELECT COALESCE(SUM(it.qty_in - it.qty_out), 0) "
							"AS qty FROM inventory_transactions AS it "
							"WHERE it.product_id = cr.product_id "
							"AND it.location_id = cs.location_id) AS on_hand "
						"ON True "
					"WHERE cr.count_summary_id = %s "
					"AND TRUNC(cr.qty)::int <> on_hand.qty "
					"AND (p.inventory_enabled "
						"OR (p.inventory_account IS NOT NULL "
							"AND p.stock AND NOT p.deleted)) "
					"AND NOT EXISTS (SELECT 1 FROM inventory_transactions "
						"WHERE count_summary_id = cr.count_summary_id "
						"AND product_id = cr.product_id)",
					(date, count_summary_id))
	corrected = cursor.rowcount
	# the insert only wrote rows for products that have an account, so
	# products.inventory_account_is_applied cannot fire here
	cursor.execute("UPDATE products SET inventory_enabled = True "
					"WHERE NOT inventory_enabled AND id IN "
						"(SELECT product_id FROM inventory_transactions "
						"WHERE count_summary_id = %s)", (count_summary_id,))
	if corrected > 0:
		transactor.post_inventory_count (cursor, count_summary_id, date)
	# the totals are the count's own valuation, which is what the window showed
	# while it was being taken, and they cover every counted row including the
	# products the close had to skip
	cursor.execute("UPDATE inventory.count_summaries SET "
						"(active, date_ended, total_cost, total_retail) = "
						"(False, %s, "
						"(SELECT COALESCE(SUM(cost * qty), 0.00) "
							"FROM inventory.count_rows "
							"WHERE count_summary_id = %s), "
						"(SELECT COALESCE(SUM(retail * qty), 0.00) "
							"FROM inventory.count_rows "
							"WHERE count_summary_id = %s)) "
					"WHERE id = %s AND active",
					(date, count_summary_id, count_summary_id, count_summary_id))
	cursor.close()
	return corrected
