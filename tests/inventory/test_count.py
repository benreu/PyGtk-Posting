import unittest
from decimal import Decimal
from harness import DBTestCase
from unittest import mock

from gi.repository import Gtk

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
EXPENSE_ACCOUNT = 3876

class CountQtyEditedTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.product_id = self.one("SELECT id FROM products WHERE NOT deleted LIMIT 1")
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		location_id = self.one("SELECT id FROM locations ORDER BY id LIMIT 1")
		self.summary_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id, location_id) "
									"VALUES ('unit test', %s, %s) "
									"RETURNING id", (fiscal_id, location_id))
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

class CloseButtonTest(DBTestCase):
	'''the button itself: the confirmation it asks for, and the state it has to
	leave the window in so the next scan cannot count into a closed count'''
	def setUp(self):
		super().setUp()
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.location_id = self.new_location('Close button location')
		self.summary_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id, location_id) "
									"VALUES ('close button test', %s, %s) "
									"RETURNING id", (fiscal_id, self.location_id))
		self.product_id = self.one("SELECT id FROM products "
									"WHERE NOT deleted AND stock ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, inventory_enabled = True, "
							"cost = 2.50 WHERE id = %s",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.product_id))
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, location_id, price, reason, "
							"date_inserted) VALUES (%s, 5, %s, 2.50, 'test', "
							"CURRENT_DATE)", (self.product_id, self.location_id))
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, 8, 2.50, 4.00)",
							(self.summary_id, self.product_id))
		self.DB.commit()
		from inventory import inventory_count
		self.gui = inventory_count.InventoryCountGUI()
		self.gui.summary_id = str(self.summary_id) # what the combo really hands out
		self.gui.populate_inventory_count()

	def click_close(self, response = Gtk.ResponseType.YES):
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = response):
			self.gui.close_count_clicked(None)

	def active(self):
		return self.one("SELECT active FROM inventory.count_summaries "
						"WHERE id = %s", (self.summary_id,))

	def corrections(self):
		return self.one("SELECT count(*) FROM inventory_transactions "
						"WHERE count_summary_id = %s", (self.summary_id,))

	def test_a_yes_closes_the_count_and_corrects_the_stock(self):
		self.click_close()
		self.assertFalse(self.active())
		self.assertEqual(self.corrections(), 1)
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 8)

	def test_a_no_leaves_the_count_open(self):
		self.click_close(Gtk.ResponseType.NO)
		self.assertTrue(self.active())
		self.assertEqual(self.corrections(), 0)
		self.assertEqual(self.on_hand(self.product_id, self.location_id), 5)

	def test_a_string_summary_id_closes(self):
		'''the combo hands out a string, close_count needs a number'''
		self.assertIsInstance(self.gui.summary_id, str)
		self.click_close()
		self.assertFalse(self.active())

	def test_the_closed_count_leaves_the_window(self):
		self.click_close()
		listed = [row[0] for row in
					self.gui.get_object('inventory_summaries_store')]
		self.assertNotIn(str(self.summary_id), listed)
		self.assertFalse(self.gui.get_object('widget_box').get_sensitive())
		self.assertEqual(len(self.gui.get_object('inventory_rows_store')), 0)
		self.assertIsNone(self.gui.summary_id)

	def test_the_combo_names_the_location(self):
		self.gui.populate_stores()
		for row in self.gui.get_object('inventory_summaries_store'):
			if row[0] == str(self.summary_id):
				self.assertIn('Close button location', row[1])
				return
		self.fail('summary not listed')

	def test_the_product_combo_leaves_out_unstocked_products(self):
		unstocked = self.one("UPDATE products SET stock = False "
							"WHERE id = %s RETURNING id", (self.product_id,))
		self.DB.commit()
		self.gui.populate_stores()
		listed = [row[0] for row in self.gui.get_object('product_store')]
		self.assertNotIn(str(unstocked), listed)

if __name__ == '__main__':
	unittest.main()
