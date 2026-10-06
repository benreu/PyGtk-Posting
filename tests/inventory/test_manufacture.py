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

if __name__ == '__main__':
	unittest.main()
