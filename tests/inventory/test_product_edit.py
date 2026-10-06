import unittest
from unittest import mock
from harness import DBTestCase

class SaveFailureTest(DBTestCase):
	def test_failed_save_keeps_the_window_open_and_changes_nothing(self):
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True WHERE id = 19")
		self.DB.commit()
		cost_before = self.one("SELECT cost FROM products WHERE id = 19")
		import product_edit_main
		gui = product_edit_main.ProductEditMainGUI()
		gui.select_product(19)
		gui.inventory_account = None # inventory_enabled requires an account
		with mock.patch.object(gui, 'show_message') as show_message, \
				mock.patch.object(gui, 'save_product_terms_prices') as save_terms, \
				mock.patch.object(gui.window, 'destroy') as destroy:
			gui.get_object('spinbutton1').set_value(float(cost_before) + 5)
			gui.save_clicked()
		show_message.assert_called_once()
		save_terms.assert_not_called()
		destroy.assert_not_called()
		self.assertEqual(self.one("SELECT cost FROM products WHERE id = 19"),
						cost_before)

class CurrentInventoryLabelTest(DBTestCase):
	def test_label_shows_on_hand(self):
		self.cursor.execute("DELETE FROM inventory_transactions WHERE product_id = 19")
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, qty_out, price, location_id, "
							"date_inserted, reason) VALUES "
							"(19, 9, 0, 1, (SELECT id FROM locations LIMIT 1), "
							"CURRENT_DATE, 'test'), "
							"(19, 0, 4, 1, (SELECT id FROM locations LIMIT 1), "
							"CURRENT_DATE, 'test')")
		self.DB.commit()
		import product_edit_main
		gui = product_edit_main.ProductEditMainGUI()
		gui.select_product(19)
		self.assertEqual(gui.get_object('label24').get_label(), '5')

if __name__ == '__main__':
	unittest.main()
