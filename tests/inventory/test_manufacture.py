import unittest
from harness import DBTestCase

class ManufactureTest(DBTestCase):
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		self.inventorying = inventorying
		self.cursor.execute("SELECT mp.id, mp.product_id, mp.qty FROM manufacturing_projects AS mp "
							"WHERE (SELECT count(*) FROM manufacturing_items "
							"WHERE manufacturing_project_id = mp.id AND qty > 0) >= 2 "
							"AND mp.qty > 0 LIMIT 1")
		self.project_id, self.product_id, self.project_qty = self.cursor.fetchone()
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0 "
							"AND product_id <> %s ORDER BY product_id",
							(self.project_id, self.product_id))
		self.components = self.cursor.fetchall()
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True WHERE id = %s OR id IN "
							"(SELECT product_id FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s)",
							(self.product_id, self.project_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE manufacturing_id = %s", (self.project_id,))
		self.DB.commit()

	def test_components_are_consumed_and_product_is_added(self):
		before = {p: self.on_hand(p) for p, q in self.components}
		before_product = self.on_hand(self.product_id)
		self.inventorying.manufacture(self.project_id)
		for product_id, qty in self.components:
			self.assertEqual(self.on_hand(product_id), before[product_id] - qty)
		self.assertEqual(self.on_hand(self.product_id),
						before_product + self.project_qty)

	def test_posting_twice_does_not_double_count(self):
		before = self.on_hand(self.product_id)
		self.inventorying.manufacture(self.project_id)
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.on_hand(self.product_id), before + self.project_qty)

	def test_products_without_inventory_are_left_alone(self):
		product_id, qty = self.components[0]
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (product_id,))
		self.inventorying.manufacture(self.project_id)
		self.assertEqual(self.one("SELECT count(*) FROM inventory_transactions "
								"WHERE manufacturing_id = %s AND product_id = %s",
								(self.project_id, product_id)), 0)

	def test_each_line_leaves_its_source_and_product_enters_the_destination(self):
		first_id = self.one("SELECT id FROM locations ORDER BY id LIMIT 1")
		second_id = self.new_location('Test source')
		third_id = self.new_location('Test destination')
		(line_product, q1), (other_product, q2) = self.components[:2]
		self.cursor.execute("UPDATE manufacturing_items SET source_location_id = %s "
							"WHERE manufacturing_project_id = %s AND product_id = %s",
							(second_id, self.project_id, line_product))
		self.cursor.execute("UPDATE manufacturing_projects "
							"SET destination_location_id = %s WHERE id = %s",
							(third_id, self.project_id))
		self.inventorying.manufacture(self.project_id)
		location = ("SELECT location_id FROM inventory_transactions "
					"WHERE manufacturing_id = %s AND product_id = %s")
		self.assertEqual(self.one(location, (self.project_id, line_product)), second_id)
		self.assertEqual(self.one(location, (self.project_id, other_product)), first_id)
		self.assertEqual(self.one(location, (self.project_id, self.product_id)), third_id)

	def stock(self, product_id, location_id, qty):
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
							(product_id, qty, location_id))

	def every_line(self):
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0",
							(self.project_id,))
		return self.cursor.fetchall()

	def point_every_line_at(self, location_id):
		self.cursor.execute("UPDATE manufacturing_items "
							"SET source_location_id = %s "
							"WHERE manufacturing_project_id = %s",
							(location_id, self.project_id))

	def test_stock_at_another_location_does_not_cover_a_line(self):
		'''the whole point of measuring per line: a part the company holds
		somewhere this build never touches leaves the source short, and saying
		otherwise is what let a post drive a location negative'''
		source_id = self.new_location('Test source')
		elsewhere_id = self.new_location('Test elsewhere')
		self.point_every_line_at(source_id)
		product_id, qty = self.components[0]
		self.stock(product_id, elsewhere_id, qty + 5)
		name = self.one("SELECT name FROM products WHERE id = %s", (product_id,))
		message = self.inventorying.manufacturing_shortage_message(self.project_id)
		self.assertIsNotNone(message)
		self.assertIn(name, message)
		self.assertIn('Test source', message)
		self.assertNotIn('Test elsewhere', message)

	def test_stock_at_the_source_covers_every_line(self):
		source_id = self.new_location('Test source')
		self.point_every_line_at(source_id)
		for product_id, qty in self.every_line():
			self.stock(product_id, source_id, qty)
		self.assertIsNone(
			self.inventorying.manufacturing_shortage_message(self.project_id))

	def test_reposting_does_not_warn_about_its_own_consumption(self):
		'''manufacture () deletes and rewrites the project's rows, so the stock
		its last post took is not stock taken yet'''
		source_id = self.new_location('Test source')
		self.point_every_line_at(source_id)
		for product_id, qty in self.every_line():
			self.stock(product_id, source_id, qty)
		self.inventorying.manufacture(self.project_id)
		self.assertIsNone(
			self.inventorying.manufacturing_shortage_message(self.project_id))

if __name__ == '__main__':
	unittest.main()
