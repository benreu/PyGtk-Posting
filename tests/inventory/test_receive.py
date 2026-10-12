import unittest
from decimal import Decimal
from harness import DBTestCase

class ReceiveTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.location_id = self.new_location()
		vendor_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.po_id = self.one("INSERT INTO purchase_orders (vendor_id) "
								"VALUES (%s) RETURNING id", (vendor_id,))
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True WHERE id IN (19, 962, 1180)")

	def add_line(self, product_id, qty, price, canceled = False,
														received = None):
		return self.one("INSERT INTO purchase_order_items "
						"(purchase_order_id, product_id, qty, price, canceled, "
						"received) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
						(self.po_id, product_id, qty, price, canceled, received))

	def count(self, line_id, received):
		'''what the receive window writes as a line is counted in'''
		self.cursor.execute("UPDATE purchase_order_items SET received = %s "
							"WHERE id = %s", (received, line_id))

	def counted(self, line_id):
		return self.one("SELECT received FROM purchase_order_items "
						"WHERE id = %s", (line_id,))

	def received_rows(self):
		self.cursor.execute("SELECT product_id, qty_in, price "
							"FROM inventory_transactions "
							"WHERE purchase_order_item_id IN "
							"(SELECT id FROM purchase_order_items "
							"WHERE purchase_order_id = %s) ORDER BY product_id",
							(self.po_id,))
		return self.cursor.fetchall()

	def line_rows(self, line_id):
		'''the receipts of one line, oldest first, so a second shipment shows as
		the row of its own that it is'''
		self.cursor.execute("SELECT qty_in, price FROM inventory_transactions "
							"WHERE purchase_order_item_id = %s ORDER BY id",
							(line_id,))
		return self.cursor.fetchall()

	def receive(self):
		from inventory import inventorying
		inventorying.receive(self.po_id, self.location_id)

	def mark_received(self):
		from db.transactor import mark_purchase_order_received
		return mark_purchase_order_received(self.po_id)

	def test_priced_line_is_received(self):
		self.add_line(19, 5, Decimal('1.25'))
		self.receive()
		self.assertEqual(self.received_rows(), [(19, 5, Decimal('1.25'))])

	def test_line_without_a_price_does_not_break_receiving(self):
		self.add_line(19, 5, Decimal('1.25'))
		self.add_line(962, 2, None)
		self.receive()
		self.assertEqual(self.received_rows(),
						[(19, 5, Decimal('1.25')), (962, 2, Decimal('0'))])

	def test_canceled_and_zero_qty_lines_are_skipped(self):
		self.add_line(19, 5, 1)
		self.add_line(962, 3, 1, canceled = True)
		self.add_line(1180, 0, 1)
		self.receive()
		self.assertEqual([r[0] for r in self.received_rows()], [19])

	def test_receiving_twice_does_not_double_count(self):
		self.add_line(19, 5, 1)
		self.receive()
		self.receive()
		self.assertEqual(len(self.received_rows()), 1)

	def test_a_count_posts_only_what_arrived(self):
		self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.assertEqual(self.received_rows(), [(19, 3, Decimal('1'))])

	def test_a_line_nobody_counted_arrives_in_full(self):
		# the receive window lists no expense product and cannot list a line
		# added while it was open, so a count of NULL has to mean the whole line
		self.add_line(19, 10, 1, received = None)
		self.receive()
		self.assertEqual(self.received_rows(), [(19, 10, Decimal('1'))])

	def test_a_count_of_nothing_posts_nothing(self):
		self.add_line(19, 5, 1, received = 0)
		self.receive()
		self.assertEqual(self.received_rows(), [])

	def test_the_rest_of_the_shipment_is_a_receipt_of_its_own(self):
		line_id = self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.count(line_id, 10)
		self.receive()
		self.assertEqual(self.line_rows(line_id),
						[(3, Decimal('1')), (7, Decimal('1'))])
		self.assertEqual(self.on_hand(19, self.location_id), 10)

	def test_a_count_taken_back_down_takes_the_receipt_with_it(self):
		line_id = self.add_line(19, 10, 1, received = 5)
		self.receive()
		self.count(line_id, 3)
		self.receive()
		self.assertEqual(self.line_rows(line_id), [(3, Decimal('1'))])

	def test_a_count_taken_back_to_nothing_zeroes_the_receipt(self):
		# the row is left in place rather than deleted, the way a canceled line
		# and a canceled invoice both keep theirs
		line_id = self.add_line(19, 10, 1, received = 5)
		self.receive()
		self.count(line_id, 0)
		self.receive()
		self.assertEqual(self.line_rows(line_id), [(0, Decimal('1'))])

	def test_a_count_taken_down_trims_the_newest_shipment_first(self):
		line_id = self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.count(line_id, 10)
		self.receive()
		self.count(line_id, 4)
		self.receive()
		self.assertEqual(self.line_rows(line_id),
						[(3, Decimal('1')), (1, Decimal('1'))])

	def test_a_canceled_line_is_not_received_again_on_its_old_count(self):
		# cancel_purchase_order_item zeroes the receipt and leaves the count on
		# the line, so a shortfall measured against that count would post the
		# canceled stock all over again
		from db.transactor import cancel_purchase_order_item
		line_id = self.add_line(19, 5, 1, received = 5)
		self.receive()
		cancel_purchase_order_item(line_id)
		self.receive()
		self.assertEqual(self.line_rows(line_id), [(0, Decimal('1'))])

	def test_a_short_order_is_not_marked_received(self):
		self.add_line(19, 10, 1, received = 3)
		self.assertEqual(self.mark_received(), False)
		self.assertEqual(self.one("SELECT received FROM purchase_orders "
									"WHERE id = %s", (self.po_id,)), False)

	def test_an_order_that_all_arrived_is_marked_received(self):
		self.add_line(19, 10, 1, received = 10)
		self.add_line(962, 2, 1) # nobody counted it, so it arrived in full
		self.add_line(1180, 3, 1, canceled = True, received = 0)
		self.assertEqual(self.mark_received(), True)
		self.assertEqual(self.one("SELECT received FROM purchase_orders "
									"WHERE id = %s", (self.po_id,)), True)

class ResyncTest(ReceiveTest):
	def resync(self):
		from db import transactor
		transactor.resync_purchase_order_inventory(self.po_id)

	def test_price_removed_after_receipt_does_not_break_resync(self):
		line_id = self.add_line(19, 5, Decimal('1.25'))
		self.cursor.execute("UPDATE purchase_orders SET received = True WHERE id = %s",
							(self.po_id,))
		self.receive()
		self.cursor.execute("UPDATE purchase_order_items SET price = NULL, qty = 7 "
							"WHERE id = %s", (line_id,))
		self.resync()
		self.assertEqual(self.received_rows(), [(19, 7, Decimal('0'))])

	def test_unpriced_line_added_after_receipt_is_received(self):
		self.add_line(19, 5, 1)
		self.cursor.execute("UPDATE purchase_orders SET received = True WHERE id = %s",
							(self.po_id,))
		self.receive()
		self.add_line(962, 2, None)
		self.resync()
		self.assertEqual([r[0] for r in self.received_rows()], [19, 962])

	def test_a_partial_receipt_is_not_restored_to_the_whole_line(self):
		# the order is still unreceived while it is short, and a correction has
		# to follow the rows the partial receipt wrote rather than ignore them
		line_id = self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.cursor.execute("UPDATE purchase_order_items SET price = 2 "
							"WHERE id = %s", (line_id,))
		self.resync()
		self.assertEqual(self.line_rows(line_id), [(3, Decimal('2'))])

	def test_a_price_correction_lands_on_every_shipment(self):
		line_id = self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.count(line_id, 10)
		self.receive()
		self.cursor.execute("UPDATE purchase_order_items SET price = 2 "
							"WHERE id = %s", (line_id,))
		self.resync()
		self.assertEqual(self.line_rows(line_id),
						[(3, Decimal('2')), (7, Decimal('2'))])

	def test_a_correction_upwards_grows_the_newest_shipment(self):
		# a correction is not a shipment, so it takes no row and no date of its
		# own, which is the promise resync_purchase_order_inventory makes
		line_id = self.add_line(19, 10, 1, received = 3)
		self.receive()
		self.count(line_id, 10)
		self.receive()
		self.cursor.execute("UPDATE purchase_order_items SET qty = 12 "
							"WHERE id = %s", (line_id,))
		self.count(line_id, 12)
		self.resync()
		self.assertEqual(self.line_rows(line_id),
						[(3, Decimal('1')), (9, Decimal('1'))])

	def test_a_correction_below_what_arrived_takes_the_count_with_it(self):
		# the window cannot count a line past its quantity, so a count left
		# above the corrected quantity would hold stock nothing claims
		line_id = self.add_line(19, 10, 1, received = 10)
		self.receive()
		self.cursor.execute("UPDATE purchase_order_items SET qty = 4 "
							"WHERE id = %s", (line_id,))
		self.resync()
		self.assertEqual(self.line_rows(line_id), [(4, Decimal('1'))])
		self.assertEqual(self.counted(line_id), 4)

if __name__ == '__main__':
	unittest.main()
