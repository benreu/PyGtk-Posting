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

	def add_line(self, product_id, qty, price, canceled = False):
		return self.one("INSERT INTO purchase_order_items "
						"(purchase_order_id, product_id, qty, price, canceled) "
						"VALUES (%s, %s, %s, %s, %s) RETURNING id",
						(self.po_id, product_id, qty, price, canceled))

	def received_rows(self):
		self.cursor.execute("SELECT product_id, qty_in, price "
							"FROM inventory_transactions "
							"WHERE purchase_order_item_id IN "
							"(SELECT id FROM purchase_order_items "
							"WHERE purchase_order_id = %s) ORDER BY product_id",
							(self.po_id,))
		return self.cursor.fetchall()

	def receive(self):
		from inventory import inventorying
		inventorying.receive(self.po_id, self.location_id)

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

if __name__ == '__main__':
	unittest.main()
