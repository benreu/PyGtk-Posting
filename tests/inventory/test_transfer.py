import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
EXPENSE_ACCOUNT = 3876

class TransferBase(DBTestCase):
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.source = self.new_location('transfer source')
		self.destination = self.new_location('transfer destination')
		self.cursor.execute("SELECT id FROM products "
							"WHERE NOT deleted AND stock ORDER BY id LIMIT 3")
		self.products = [row[0] for row in self.cursor.fetchall()]
		self.product_id = self.products[0]
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, "
							"inventory_enabled = True, cost = 2.50 "
							"WHERE id = ANY(%s)",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.products))
		self.DB.commit()

	def stock(self, product_id, qty, location_id = None):
		'''put qty on the shelf without going through any document'''
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, location_id, price, reason, "
							"date_inserted) VALUES (%s, %s, %s, 2.50, 'test', "
							"CURRENT_DATE)",
							(product_id, qty,
							location_id if location_id else self.source))

	def move(self, lines, source = None, destination = None, notes = None,
				moved_on = None):
		return self.inventorying.transfer(lines,
							self.source if source == None else source,
							self.destination if destination == None
												else destination,
							notes, moved_on)

	def rows(self, transfer_id):
		'''the stock rows a transfer wrote, oldest first'''
		self.cursor.execute("SELECT location_id, qty_in, qty_out, price, "
								"reason, product_id, date_inserted, "
								"gl_entries_id "
							"FROM inventory_transactions "
							"WHERE transfer_id = %s ORDER BY id",
							(transfer_id,))
		return self.cursor.fetchall()

	def headers(self):
		self.cursor.execute("SELECT id, source_location_id, "
								"destination_location_id, notes, date_inserted "
							"FROM inventory.transfers ORDER BY id")
		return self.cursor.fetchall()

class TransferTest(TransferBase):
	'''a transfer moves stock between two locations and changes nothing about how
	much the company holds. That is the whole promise: every other writer in this
	module adds stock or takes it away'''

	def test_stock_leaves_the_source_and_arrives_at_the_destination(self):
		self.stock(self.product_id, 10)
		self.move([[self.product_id, 4]])
		self.assertEqual(self.on_hand(self.product_id, self.source), 6)
		self.assertEqual(self.on_hand(self.product_id, self.destination), 4)

	def test_the_company_wide_total_is_unchanged(self):
		self.stock(self.product_id, 10)
		before = self.on_hand(self.product_id)
		self.move([[self.product_id, 4]])
		self.assertEqual(self.on_hand(self.product_id), before)

	def test_both_rows_point_at_the_one_transfer(self):
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 4]])
		rows = self.rows(transfer_id)
		self.assertEqual(len(rows), 2)
		out, into = rows
		self.assertEqual((out[0], out[1], out[2]), (self.source, 0, 4))
		self.assertEqual((into[0], into[1], into[2]),
							(self.destination, 4, 0))
		self.assertEqual([row[4] for row in rows],
							['Inventory transfer'] * 2)

	def test_both_rows_carry_the_product_cost(self):
		'''the value that leaves the source is the value that arrives, so the
		move is neutral however it is read'''
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 4]])
		cost = self.one("SELECT cost FROM products WHERE id = %s",
						(self.product_id,))
		self.assertEqual([row[3] for row in self.rows(transfer_id)],
							[cost, cost])

	def test_no_ledger_entry_is_written(self):
		'''the inventory account is on the product, not on the location, so both
		sides would debit and credit the one account for the one amount'''
		self.stock(self.product_id, 10)
		transactions = self.one("SELECT COUNT(*) FROM gl_transactions")
		entries = self.one("SELECT COUNT(*) FROM gl_entries")
		transfer_id = self.move([[self.product_id, 4]])
		self.assertEqual([row[7] for row in self.rows(transfer_id)],
							[None, None])
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_transactions"),
							transactions)
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_entries"), entries)

	def test_the_header_records_the_move(self):
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 4]], notes = 'to the van')
		self.assertEqual(self.headers(),
							[(transfer_id, self.source, self.destination,
								'to the van', date.today())])

	def test_a_date_of_none_is_today(self):
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 4]])
		self.assertEqual([row[6] for row in self.rows(transfer_id)],
							[date.today()] * 2)

	def test_a_given_date_is_taken_by_the_header_and_both_rows(self):
		'''one move cannot straddle two days'''
		self.stock(self.product_id, 10)
		moved_on = date.today() - timedelta(days = 9)
		transfer_id = self.move([[self.product_id, 4]], moved_on = moved_on)
		self.assertEqual([row[6] for row in self.rows(transfer_id)],
							[moved_on] * 2)
		self.assertEqual(self.headers()[0][4], moved_on)

	def test_several_products_move_in_one_transfer(self):
		for product_id in self.products:
			self.stock(product_id, 10)
		transfer_id = self.move([[product_id, 2]
									for product_id in self.products])
		self.assertEqual(len(self.rows(transfer_id)), 6)
		for product_id in self.products:
			self.assertEqual(self.on_hand(product_id, self.source), 8)
			self.assertEqual(self.on_hand(product_id, self.destination), 2)

	def test_a_product_listed_twice_moves_once_for_the_total(self):
		'''one row per side per product is the shape the unique index holds the
		database to'''
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 2], [self.product_id, 3]])
		rows = self.rows(transfer_id)
		self.assertEqual(len(rows), 2)
		self.assertEqual((rows[0][2], rows[1][1]), (5, 5))
		self.assertEqual(self.on_hand(self.product_id, self.destination), 5)

	def test_a_line_of_nothing_is_skipped(self):
		self.stock(self.product_id, 10)
		self.stock(self.products[1], 10)
		transfer_id = self.move([[self.product_id, 0], [self.products[1], 3]])
		self.assertEqual(len(self.rows(transfer_id)), 2)
		self.assertEqual(self.on_hand(self.product_id, self.destination), 0)
		self.assertEqual(self.on_hand(self.products[1], self.destination), 3)

	def test_a_store_with_nothing_to_move_writes_no_transfer(self):
		'''an empty move must not leave an empty header behind, the way
		post_inventory_count leaves no empty transaction'''
		self.assertIsNone(self.move([]))
		self.assertIsNone(self.move([[self.product_id, 0]]))
		self.assertEqual(self.headers(), [])

	def test_nothing_is_committed(self):
		'''the header and both sides of every move are one unit; the caller
		decides'''
		self.stock(self.product_id, 10)
		self.DB.commit()
		transfer_id = self.move([[self.product_id, 4]])
		self.DB.rollback()
		self.assertEqual(self.headers(), [])
		self.assertEqual(self.rows(transfer_id), [])
		self.assertEqual(self.on_hand(self.product_id, self.source), 10)

	def test_each_post_is_its_own_transfer(self):
		'''transfer () creates its own header, so it has nothing to recognise a
		repeat by: stopping a double post is the window's job'''
		self.stock(self.product_id, 10)
		first = self.move([[self.product_id, 2]])
		second = self.move([[self.product_id, 2]])
		self.assertNotEqual(first, second)
		self.assertEqual(len(self.headers()), 2)
		self.assertEqual(self.on_hand(self.product_id, self.destination), 4)

class TransferRefusedTest(TransferBase):
	'''the refusals, which is where a transfer differs from a sale. A sale the
	count was wrong about has still left the building, so the books have to
	follow it; stock that was never at the source cannot have arrived anywhere'''

	def test_moving_more_than_is_on_hand_is_refused(self):
		self.stock(self.product_id, 3)
		with self.assertRaises(ValueError) as caught:
			self.move([[self.product_id, 5]])
		message = str(caught.exception)
		self.assertIn('3 on hand', message)
		self.assertIn('transfer source', message)
		self.assertIn('would be -2', message)

	def test_a_refused_transfer_moves_nothing_and_writes_no_header(self):
		self.stock(self.product_id, 3)
		self.stock(self.products[1], 10)
		with self.assertRaises(ValueError):
			self.move([[self.products[1], 2], [self.product_id, 5]])
		self.assertEqual(self.on_hand(self.product_id, self.source), 3)
		self.assertEqual(self.on_hand(self.products[1], self.source), 10)
		self.assertEqual(self.on_hand(self.products[1], self.destination), 0)
		self.assertEqual(self.headers(), [])

	def test_every_short_product_is_named(self):
		'''a store with two problems in it is not fixed one message at a time'''
		self.stock(self.product_id, 1)
		self.stock(self.products[1], 1)
		names = [self.one("SELECT name FROM products WHERE id = %s", (p,))
					for p in self.products[:2]]
		with self.assertRaises(ValueError) as caught:
			self.move([[self.product_id, 5], [self.products[1], 5]])
		for name in names:
			self.assertIn(name, str(caught.exception))

	def test_stock_at_another_location_does_not_cover_the_move(self):
		elsewhere = self.new_location('transfer elsewhere')
		self.stock(self.product_id, 100, elsewhere)
		self.stock(self.product_id, 1)
		with self.assertRaises(ValueError):
			self.move([[self.product_id, 5]])

	def test_moving_exactly_what_is_on_hand_is_allowed(self):
		self.stock(self.product_id, 5)
		self.move([[self.product_id, 5]])
		self.assertEqual(self.on_hand(self.product_id, self.source), 0)
		self.assertEqual(self.on_hand(self.product_id, self.destination), 5)

	def test_the_lines_are_weighed_summed(self):
		'''two lines of 3 against 5 on hand is one move of 6, not two of 3'''
		self.stock(self.product_id, 5)
		with self.assertRaises(ValueError) as caught:
			self.move([[self.product_id, 3], [self.product_id, 3]])
		self.assertIn('moving 6', str(caught.exception))
		self.assertEqual(self.on_hand(self.product_id, self.destination), 0)

	def test_an_untracked_product_is_refused_and_named(self):
		'''with stock rows present, so the refusal is the tracking rule and not
		an accident of a zero balance. Writing rows for it would start tracking
		it without saying so, which only close_count is entitled to do'''
		self.stock(self.product_id, 10)
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		name = self.one("SELECT name FROM products WHERE id = %s",
						(self.product_id,))
		with self.assertRaises(ValueError) as caught:
			self.move([[self.product_id, 4]])
		self.assertIn(name, str(caught.exception))
		self.assertIn('not tracked', str(caught.exception))
		self.assertEqual(self.on_hand(self.product_id, self.destination), 0)

	def test_source_equal_to_destination_is_refused(self):
		self.stock(self.product_id, 10)
		with self.assertRaises(ValueError):
			self.move([[self.product_id, 4]], destination = self.source)
		self.assertEqual(self.headers(), [])
		self.assertEqual(self.on_hand(self.product_id, self.source), 10)

	def test_the_database_refuses_a_transfer_to_the_same_location(self):
		'''the invariant the unique index on
		(transfer_id, product_id, location_id) leans on: with both sides at one
		location the key would stop being unique per side'''
		import psycopg2
		with self.assertRaises(psycopg2.IntegrityError):
			self.cursor.execute("INSERT INTO inventory.transfers "
								"(source_location_id, destination_location_id) "
								"VALUES (%s, %s)", (self.source, self.source))

class TransferWindowTest(TransferBase):
	'''what the window owns and the function cannot: which products can be
	picked, what a line's figures mean, and that one post is one move'''
	def setUp(self):
		super().setUp()
		from inventory import inventory_transfer
		self.gui = inventory_transfer.InventoryTransferGUI()
		self.gui.get_object('transfer_source_combo').set_active_id(
													str(self.source))
		self.gui.get_object('transfer_destination_combo').set_active_id(
													str(self.destination))

	def add(self, product_id, qty):
		self.gui.product_id = product_id
		self.gui.get_object('transfer_qty_spinbutton').set_value(qty)
		self.gui.transfer_add_clicked(None)

	def lines(self):
		return [tuple(row) for row in self.gui.lines_store]

	def test_only_tracked_products_are_offered(self):
		untracked = self.one("SELECT id FROM products WHERE NOT deleted "
								"AND stock AND NOT inventory_enabled LIMIT 1")
		offered = [row[0] for row in self.gui.product_store]
		self.assertIn(str(self.product_id), offered)
		self.assertNotIn(str(untracked), offered)

	def test_adding_a_product_twice_makes_one_line_of_the_total(self):
		self.stock(self.product_id, 10)
		self.DB.commit()
		self.add(self.product_id, 2)
		self.add(self.product_id, 3)
		self.assertEqual(len(self.lines()), 1)
		self.assertEqual(self.gui.lines_store[0][1], 5)

	def test_a_garbage_quantity_edit_is_rejected(self):
		self.stock(self.product_id, 10)
		self.DB.commit()
		self.add(self.product_id, 4)
		for bad in ('1.5', 'abc', '0', '-2', ''):
			self.gui.transfer_qty_edited(None, '0', bad)
			self.assertEqual(self.gui.lines_store[0][1], 4)
		self.gui.transfer_qty_edited(None, '0', '7')
		self.assertEqual(self.gui.lines_store[0][1], 7)

	def test_the_lines_show_on_hand_at_the_source(self):
		self.stock(self.product_id, 10)
		self.DB.commit()
		self.add(self.product_id, 4)
		self.assertEqual(self.gui.lines_store[0][3], 10)

	def test_changing_the_source_restates_every_line(self):
		'''every figure on screen is stock at the location the move will be taken
		from, so they have to follow the combo'''
		elsewhere = self.new_location('transfer elsewhere')
		self.stock(self.product_id, 10)
		self.stock(self.product_id, 2, elsewhere)
		self.DB.commit()
		self.add(self.product_id, 4)
		self.assertEqual(self.gui.lines_store[0][3], 10)
		self.gui.transfer_focus_in(None, None) # the new location is picked up
		self.gui.get_object('transfer_source_combo').set_active_id(
													str(elsewhere))
		self.assertEqual(self.gui.lines_store[0][3], 2)

	def test_a_location_added_elsewhere_is_picked_up_on_focus(self):
		'''the locations button opens another window, so the store behind both
		combos is stale until the user comes back'''
		elsewhere = self.new_location('transfer added later')
		self.DB.commit()
		listed = [row[0] for row in
					self.gui.get_object('transfer_location_store')]
		self.assertNotIn(str(elsewhere), listed)
		self.gui.transfer_focus_in(None, None)
		listed = [row[0] for row in
					self.gui.get_object('transfer_location_store')]
		self.assertIn(str(elsewhere), listed)
		# the refresh clears the store, so the picked locations have to survive it
		self.assertEqual(self.gui.source_location_id(), self.source)
		self.assertEqual(self.gui.destination_location_id(), self.destination)

	def test_no_source_shows_nothing_rather_than_the_company_total(self):
		'''on_hand reads a location of None as every location, which is the one
		figure a column headed "on hand at source" must never show'''
		elsewhere = self.new_location('transfer elsewhere')
		self.stock(self.product_id, 10)
		self.stock(self.product_id, 7, elsewhere)
		self.DB.commit()
		self.add(self.product_id, 4)
		self.gui.get_object('transfer_source_combo').set_active(-1)
		self.assertIsNone(self.gui.source_location_id())
		self.assertEqual(self.gui.lines_store[0][3], 0)
		self.assertEqual(
			self.gui.get_object('transfer_on_hand_label').get_text(),
			'no location')

	def test_the_button_is_dead_until_a_destination_differs_and_a_line_exists(self):
		combo = self.gui.get_object('transfer_destination_combo')
		button = self.gui.get_object('transfer_post_button')
		status = self.gui.get_object('transfer_status_label')
		self.assertFalse(button.get_sensitive())
		self.assertIn('Add a product', status.get_text())
		combo.set_active_id(str(self.source)) # the same place
		self.assertFalse(button.get_sensitive())
		self.assertIn('same location', status.get_text())
		combo.set_active_id(str(self.destination))
		self.stock(self.product_id, 10)
		self.DB.commit()
		self.add(self.product_id, 4)
		self.assertTrue(button.get_sensitive())
		self.assertEqual(status.get_text(), '')

	def test_posting_twice_moves_the_stock_once(self):
		'''the double post gate, which lives here because transfer () creates its
		own header and has nothing to recognise a repeat by'''
		self.stock(self.product_id, 10)
		self.DB.commit()
		self.add(self.product_id, 4)
		button = self.gui.get_object('transfer_post_button')
		with mock.patch('gi.repository.Gtk.MessageDialog.run'):
			self.gui.transfer_post_clicked(button)
			self.gui.transfer_post_clicked(button)
		self.assertEqual(len(self.headers()), 1)
		self.assertEqual(self.on_hand(self.product_id, self.destination), 4)
		self.assertEqual(self.on_hand(self.product_id, self.source), 6)
		self.assertFalse(button.get_sensitive())
		self.assertEqual(self.lines(), [])

	def test_a_refused_post_reports_and_leaves_the_button_live(self):
		self.stock(self.product_id, 3)
		self.DB.commit()
		self.add(self.product_id, 3)
		self.gui.lines_store[0][1] = 5 # more than the shelf holds
		button = self.gui.get_object('transfer_post_button')
		with mock.patch('gi.repository.Gtk.MessageDialog.run') as run:
			self.gui.transfer_post_clicked(button)
			self.assertTrue(run.called)
		self.assertEqual(self.headers(), [])
		self.assertEqual(self.on_hand(self.product_id, self.source), 3)
		self.assertTrue(button.get_sensitive())
		self.assertEqual(len(self.lines()), 1) # the lines are still there to fix

class TransferLocationDeleteTest(TransferBase):
	'''inventory.transfers points at locations with RESTRICT, so a place a move
	was made to or from can no longer be deleted even once its stock rows have
	gone. locations has no deleted column and leans on the FK raising, so this is
	a new way into a path that already existed'''
	def setUp(self):
		super().setUp()
		import locations
		self.locations_gui = locations.LocationsGUI()

	def select_location(self, location_id):
		self.locations_gui.location_treeview_populate()
		for row in self.locations_gui.location_store:
			if row[0] == location_id:
				selection = self.locations_gui.builder.get_object(
													'treeview-selection2')
				selection.select_path(row.path)
				return
		self.fail('location not listed')

	def delete(self, location_id):
		self.select_location(location_id)
		with mock.patch('gi.repository.Gtk.MessageDialog.run'):
			self.locations_gui.delete_clicked(None)

	def test_a_location_a_transfer_names_survives_delete(self):
		self.stock(self.product_id, 10)
		transfer_id = self.move([[self.product_id, 4]])
		# the stock rows go, so only the header is left pointing at the places
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE transfer_id = %s", (transfer_id,))
		self.DB.commit()
		for location_id in (self.source, self.destination):
			self.delete(location_id)
			self.assertEqual(
				self.one("SELECT COUNT(*) FROM locations WHERE id = %s",
							(location_id,)), 1)

	def test_a_location_no_transfer_names_is_still_deleted(self):
		'''the guard above must not make every location undeletable'''
		spare = self.new_location('transfer spare')
		self.DB.commit()
		self.delete(spare)
		self.assertEqual(self.one("SELECT COUNT(*) FROM locations WHERE id = %s",
									(spare,)), 0)

if __name__ == '__main__':
	unittest.main()
