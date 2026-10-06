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

class TrackInventoryCheckboxTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = False WHERE id = 19")
		self.DB.commit()
		import product_edit_main
		self.gui = product_edit_main.ProductEditMainGUI()
		self.gui.select_product(19)
		self.box = self.gui.get_object('inventory_enabled_checkbutton')

	def save(self):
		with mock.patch.object(self.gui, 'save_product_terms_prices'), \
				mock.patch.object(self.gui.window, 'destroy'):
			self.gui.save_clicked()

	def enabled(self):
		return self.one("SELECT inventory_enabled FROM products WHERE id = 19")

	def test_checkbox_reflects_and_saves_the_flag(self):
		self.assertFalse(self.box.get_active())
		self.box.set_active(True)
		self.save()
		self.assertTrue(self.enabled())
		self.box.set_active(False)
		self.save()
		self.assertFalse(self.enabled())

	def test_enabling_without_an_account_is_refused(self):
		self.gui.inventory_account = None
		self.box.set_active(True)
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.save()
		show_message.assert_called_once()
		self.assertFalse(self.enabled())

if __name__ == '__main__':
	unittest.main()
