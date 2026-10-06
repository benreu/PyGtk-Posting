import unittest
from unittest import mock
from harness import DBTestCase

class CountInventoryEntryTest(DBTestCase):
	def test_report_menu_opens_the_count_window(self):
		from reports import main_reports_window
		gui = main_reports_window.MainReportsGUI()
		with mock.patch('inventory.inventory_count.InventoryCountGUI') as count_gui:
			gui.count_inventory_clicked(None)
		count_gui.assert_called_once_with()

class HistoryProductSelectTest(DBTestCase):
	def test_choosing_a_product_fills_the_entry_and_history(self):
		from inventory import inventory_history
		gui = inventory_history.InventoryHistoryGUI()
		row = gui.product_store[0]
		gui.product_match_selected(None, gui.product_store, row.iter)
		self.assertEqual(gui.builder.get_object('combobox-entry').get_text(), row[1])
		self.assertEqual(str(gui.product_id), row[0])

if __name__ == '__main__':
	unittest.main()
