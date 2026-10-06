import unittest
from harness import DBTestCase

class CountQtyEditedTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.product_id = self.one("SELECT id FROM products WHERE NOT deleted LIMIT 1")
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.summary_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id) VALUES ('unit test', %s) "
									"RETURNING id", (fiscal_id,))
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, 3, 1, 2)", (self.summary_id, self.product_id))
		self.DB.commit()
		from inventory import inventory_count
		self.gui = inventory_count.InventoryCountGUI()
		self.gui.summary_id = self.summary_id
		self.gui.populate_inventory_count()
		self.store = self.gui.get_object('inventory_rows_store')

	def stored_qty(self):
		return self.one("SELECT qty FROM inventory.count_rows "
						"WHERE (count_summary_id, product_id) = (%s, %s)",
						(self.summary_id, self.product_id))

	def test_integer_qty_is_saved(self):
		self.gui.qty_edited(None, '0', '7')
		self.assertEqual(self.stored_qty(), 7)
		self.assertEqual(self.store[0][0], 7)

	def test_fractional_qty_is_rejected_without_saving(self):
		self.gui.qty_edited(None, '0', '1.5')
		self.assertEqual(self.stored_qty(), 3)
		self.assertEqual(self.store[0][0], 3)

	def test_garbage_qty_is_rejected(self):
		self.gui.qty_edited(None, '0', 'abc')
		self.assertEqual(self.stored_qty(), 3)

if __name__ == '__main__':
	unittest.main()
