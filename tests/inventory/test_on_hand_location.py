import unittest
from decimal import Decimal
from harness import DBTestCase

class OnHandHelperTest(DBTestCase):
	'''inventorying.on_hand is the shared read every screen showing a quantity
	goes through, so the one thing it has to get right is which stock it counts'''
	def setUp(self):
		super().setUp()
		self.here = self.new_location('on hand here')
		self.there = self.new_location('on hand there')
		self.product_id = self.one("SELECT id FROM products WHERE NOT deleted "
									"LIMIT 1")

	def stock(self, location_id, qty_in = 0, qty_out = 0):
		self.one("INSERT INTO inventory_transactions "
					"(product_id, qty_in, qty_out, date_inserted, location_id, "
					"price, reason) "
					"VALUES (%s, %s, %s, CURRENT_DATE, %s, 1.00, 'test') "
					"RETURNING id",
					(self.product_id, qty_in, qty_out, location_id))

	def on_hand_helper(self, location_id = None):
		from inventory import inventorying
		return inventorying.on_hand(self.product_id, location_id)

	def test_a_location_counts_only_its_own_stock(self):
		self.stock(self.here, qty_in = 7)
		self.stock(self.there, qty_in = 4)
		self.assertEqual(self.on_hand_helper(self.here), 7)
		self.assertEqual(self.on_hand_helper(self.there), 4)

	def test_no_location_is_the_company_total(self):
		self.stock(self.here, qty_in = 7)
		self.stock(self.there, qty_in = 4)
		self.assertEqual(self.on_hand_helper(), 11)

	def test_a_location_holding_nothing_is_zero_not_none(self):
		self.stock(self.there, qty_in = 4)
		self.assertEqual(self.on_hand_helper(self.here), 0)

	def test_stock_out_is_subtracted(self):
		self.stock(self.here, qty_in = 7)
		self.stock(self.here, qty_out = 2)
		self.assertEqual(self.on_hand_helper(self.here), 5)

	def test_a_caller_in_a_transaction_can_hand_in_its_cursor(self):
		'''the same contract first_location_id makes: no second cursor is
		opened on a transaction that is already going'''
		from inventory import inventorying
		self.stock(self.here, qty_in = 3)
		qty = inventorying.on_hand(self.product_id, self.here,
									cursor = self.cursor)
		self.assertEqual(qty, 3)
		self.assertFalse(self.cursor.closed) # the caller still owns it

class PurchaseOrderInventoryBlockedTest(DBTestCase):
	'''the negative stock gate on a purchase order correction. It is the one
	place a wrong location reading lets stock go negative rather than merely
	showing the wrong number'''
	def setUp(self):
		super().setUp()
		self.here = self.new_location('po gate here')
		self.there = self.new_location('po gate there')
		vendor_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.po_id = self.one("INSERT INTO purchase_orders (vendor_id) "
								"VALUES (%s) RETURNING id", (vendor_id,))

	def new_product(self, name):
		tax_rate_id = self.one("SELECT id FROM tax_rates WHERE standard = True")
		return self.one("INSERT INTO products (name, ext_name, description, "
						"unit, cost, tax_rate_id, default_expense_account, "
						"revenue_account) "
						"VALUES (%s, '', '', 1, 1.00, %s, "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 3 LIMIT 1), "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 4 LIMIT 1)) RETURNING id",
						(name, tax_rate_id))

	def add_line(self, product_id, qty = 1):
		return self.one("INSERT INTO purchase_order_items "
						"(purchase_order_id, product_id, qty, price) "
						"VALUES (%s, %s, %s, 1.00) RETURNING id",
						(self.po_id, product_id, qty))

	def stock(self, product_id, location_id, qty_in = 0, qty_out = 0):
		self.one("INSERT INTO inventory_transactions "
					"(product_id, qty_in, qty_out, date_inserted, location_id, "
					"price, reason) "
					"VALUES (%s, %s, %s, CURRENT_DATE, %s, 1.00, 'test') "
					"RETURNING id",
					(product_id, qty_in, qty_out, location_id))

	def blocked(self):
		from db.transactor import purchase_order_inventory_blocked
		return purchase_order_inventory_blocked(self.po_id)

	def test_stock_at_another_location_does_not_cover_a_shortfall(self):
		'''5 short here and 5 spare there nets to zero over the company, but
		the stock here still cannot be given back'''
		product_id = self.new_product('gate product')
		self.add_line(product_id)
		self.stock(product_id, self.here, qty_out = 5)
		self.stock(product_id, self.there, qty_in = 5)
		message = self.blocked()
		self.assertIsNotNone(message)
		self.assertIn('gate product', message)
		self.assertIn('po gate here', message) # and it says where

	def test_two_products_sharing_a_name_are_weighed_apart(self):
		'''grouped on the name alone, one product's surplus hid the other's
		shortfall'''
		short = self.new_product('same name')
		spare = self.new_product('same name')
		self.add_line(short)
		self.add_line(spare)
		self.stock(short, self.here, qty_out = 5)
		self.stock(spare, self.here, qty_in = 5)
		self.assertIsNotNone(self.blocked())

	def test_stock_covered_everywhere_is_not_blocked(self):
		product_id = self.new_product('covered product')
		self.add_line(product_id)
		self.stock(product_id, self.here, qty_in = 5)
		self.stock(product_id, self.there, qty_in = 5)
		self.assertIsNone(self.blocked())

	def test_it_leaves_the_transaction_open_for_its_caller(self):
		'''the docstring's contract: it reads corrections written in the open
		transaction, so it must not commit or roll back'''
		product_id = self.new_product('open transaction product')
		self.add_line(product_id)
		self.stock(product_id, self.here, qty_in = 1)
		self.blocked()
		# the line is still visible, so nothing was rolled back under us
		self.assertEqual(self.one("SELECT COUNT(*) FROM purchase_order_items "
									"WHERE purchase_order_id = %s",
									(self.po_id,)), 1)

class AdjustmentWindowFiguresTest(DBTestCase):
	'''the window picks a location and its INSERT obeys it, but the figures it
	showed beside that picker were the whole company's stock'''
	def setUp(self):
		super().setUp()
		self.product_id = 19
		self.here = self.new_location('adjustment here')
		self.there = self.new_location('adjustment there')
		self.cursor.execute("UPDATE products SET cost = 2.50, "
							"inventory_account = 1761, "
							"default_expense_account = 3876, "
							"inventory_enabled = True WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id = %s", (self.product_id,))
		self.DB.commit()

	def stock(self, location_id, qty_in):
		self.one("INSERT INTO inventory_transactions "
					"(product_id, qty_in, date_inserted, location_id, price, "
					"reason) VALUES (%s, %s, CURRENT_DATE, %s, 1.00, 'test') "
					"RETURNING id", (self.product_id, qty_in, location_id))
		self.DB.commit()

	def window(self, location_id):
		from inventory import inventory_adjustment
		gui = inventory_adjustment.InventoryAdjustmentGUI(self.product_id)
		gui.builder.get_object('combobox3').set_active_id(str(location_id))
		return gui

	def current(self, gui):
		return gui.builder.get_object('label24').get_text()

	def projected(self, gui):
		return gui.builder.get_object('label23').get_text()

	def test_the_figure_is_the_stock_at_the_chosen_location(self):
		self.stock(self.here, 6)
		self.stock(self.there, 9)
		self.assertEqual(self.current(self.window(self.here)), '6')
		self.assertEqual(self.current(self.window(self.there)), '9')

	def test_switching_location_moves_the_figure(self):
		self.stock(self.here, 6)
		self.stock(self.there, 9)
		gui = self.window(self.here)
		self.assertEqual(self.current(gui), '6')
		gui.builder.get_object('combobox3').set_active_id(str(self.there))
		self.assertEqual(self.current(gui), '9')

	def test_the_projected_figure_follows_the_location_too(self):
		self.stock(self.here, 6)
		self.stock(self.there, 9)
		gui = self.window(self.here)
		gui.builder.get_object('spinbutton12').set_value(2)
		self.assertEqual(self.projected(gui), '8.0')

	def test_a_location_holding_nothing_shows_zero(self):
		self.stock(self.there, 9)
		self.assertEqual(self.current(self.window(self.here)), '0')

	def test_an_untracked_product_still_shows_a_figure(self):
		'''the stray GROUP BY made this query return no row at all, so the
		label kept whatever it had'''
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.DB.commit()
		self.assertEqual(self.current(self.window(self.here)), '0')

if __name__ == '__main__':
	unittest.main()
