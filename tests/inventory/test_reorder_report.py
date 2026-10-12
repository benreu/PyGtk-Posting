import unittest
from decimal import Decimal
from harness import DBTestCase

class ProductsToReorderTest(DBTestCase):
	'''min_inventory and reorder_qty were written by the product editor and read
	by nothing. This is the consumer, so what it lists is the whole contract'''
	def setUp(self):
		super().setUp()
		self.location_id = self.new_location('reorder location')
		self.vendor_id = self.one("SELECT id FROM contacts LIMIT 1")

	def new_product(self, name, min_inventory = 0, reorder_qty = 0,
					stock = True, purchasable = True, deleted = False):
		tax_rate_id = self.one("SELECT id FROM tax_rates WHERE standard = True")
		return self.one("INSERT INTO products (name, ext_name, description, "
						"unit, cost, tax_rate_id, min_inventory, reorder_qty, "
						"stock, purchasable, deleted, default_expense_account, "
						"revenue_account) "
						"VALUES (%s, '', '', 1, 1.00, %s, %s, %s, %s, %s, %s, "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 3 LIMIT 1), "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 4 LIMIT 1)) RETURNING id",
						(name, tax_rate_id, min_inventory, reorder_qty, stock,
						purchasable, deleted))

	def stock(self, product_id, qty_in, location_id = None):
		self.one("INSERT INTO inventory_transactions "
					"(product_id, qty_in, date_inserted, location_id, price, "
					"reason) VALUES (%s, %s, CURRENT_DATE, %s, 1.00, 'test') "
					"RETURNING id",
					(product_id, qty_in,
					self.location_id if location_id is None else location_id))

	def listed(self):
		from reports import products_to_reorder
		gui = products_to_reorder.ProductsToReorderGUI()
		return {row[0]: tuple(row[1:]) for row in gui.store}

	def test_a_product_below_its_floor_is_listed(self):
		product_id = self.new_product('below floor', min_inventory = 10,
										reorder_qty = 25)
		self.stock(product_id, 3)
		self.DB.commit()
		row = self.listed()[product_id]
		self.assertEqual(row[0], 'below floor') # name
		self.assertEqual(row[2], 3)             # on hand
		self.assertEqual(row[3], 10)            # minimum
		self.assertEqual(row[4], 25)            # reorder qty

	def test_a_product_at_its_floor_is_listed(self):
		'''at the floor is already too few: the floor is what has to be kept'''
		product_id = self.new_product('at floor', min_inventory = 5,
										reorder_qty = 5)
		self.stock(product_id, 5)
		self.DB.commit()
		self.assertIn(product_id, self.listed())

	def test_a_product_above_its_floor_is_left_out(self):
		product_id = self.new_product('above floor', min_inventory = 5,
										reorder_qty = 5)
		self.stock(product_id, 6)
		self.DB.commit()
		self.assertNotIn(product_id, self.listed())

	def test_a_product_with_no_floor_set_is_left_out(self):
		'''zero is the default nobody has touched, and every product in the
		catalogue is at or below zero at some point'''
		product_id = self.new_product('no floor at all', min_inventory = 0,
										reorder_qty = 5)
		self.DB.commit()
		self.assertNotIn(product_id, self.listed())

	def test_a_deleted_product_is_left_out(self):
		product_id = self.new_product('deleted product', min_inventory = 10,
										reorder_qty = 5, deleted = True)
		self.DB.commit()
		self.assertNotIn(product_id, self.listed())

	def test_a_product_that_is_not_stocked_is_left_out(self):
		product_id = self.new_product('not stocked', min_inventory = 10,
										reorder_qty = 5, stock = False)
		self.DB.commit()
		self.assertNotIn(product_id, self.listed())

	def test_a_product_that_cannot_be_purchased_is_left_out(self):
		product_id = self.new_product('not purchasable', min_inventory = 10,
										reorder_qty = 5, purchasable = False)
		self.DB.commit()
		self.assertNotIn(product_id, self.listed())

	def test_on_hand_is_the_total_over_every_location(self):
		'''the floor is a per product column with no location of its own, so
		the stock it is weighed against cannot have one either'''
		elsewhere = self.new_location('reorder elsewhere')
		product_id = self.new_product('spread about', min_inventory = 10,
										reorder_qty = 5)
		self.stock(product_id, 3)
		self.stock(product_id, 4, location_id = elsewhere)
		self.DB.commit()
		self.assertEqual(self.listed()[product_id][2], 7)

	def test_the_usual_vendor_is_named(self):
		product_id = self.new_product('has a vendor', min_inventory = 10,
										reorder_qty = 5)
		self.one("INSERT INTO vendor_product_numbers "
					"(vendor_sku, vendor_id, product_id, vendor_barcode) "
					"VALUES ('sku-1', %s, %s, '') RETURNING id",
					(self.vendor_id, product_id))
		self.DB.commit()
		row = self.listed()[product_id]
		self.assertEqual(row[5], self.vendor_id)
		self.assertNotEqual(row[6], '') # the vendor's name, for the user

	def test_a_product_with_no_vendor_is_still_listed(self):
		'''it still needs ordering; the window refuses to order it rather than
		hiding that it is short'''
		product_id = self.new_product('no vendor', min_inventory = 10,
										reorder_qty = 5)
		self.DB.commit()
		self.assertEqual(self.listed()[product_id][5], 0)

	def test_a_deleted_vendor_number_is_not_used(self):
		product_id = self.new_product('deleted vendor number',
										min_inventory = 10, reorder_qty = 5)
		self.one("INSERT INTO vendor_product_numbers "
					"(vendor_sku, vendor_id, product_id, vendor_barcode, "
					"deleted) VALUES ('sku-2', %s, %s, '', True) RETURNING id",
					(self.vendor_id, product_id))
		self.DB.commit()
		self.assertEqual(self.listed()[product_id][5], 0)

if __name__ == '__main__':
	unittest.main()
