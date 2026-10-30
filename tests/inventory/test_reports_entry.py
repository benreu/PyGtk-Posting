import unittest
from unittest import mock
import os, sys, ast, inspect, importlib.util, textwrap
from xml.etree import ElementTree
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase

class ReportsWindowEntryTest(DBTestCase):
	def test_report_menu_opens_the_count_window(self):
		from reports import main_reports_window
		gui = main_reports_window.MainReportsGUI()
		with mock.patch('inventory.inventory_count.InventoryCountGUI') as count_gui:
			gui.count_inventory_clicked(None)
		count_gui.assert_called_once_with()

	def test_report_menu_opens_the_inventory_history_window(self):
		from reports import main_reports_window
		gui = main_reports_window.MainReportsGUI()
		with mock.patch('inventory.inventory_history.InventoryHistoryGUI') as history_gui:
			gui.inventory_history_clicked(None)
		history_gui.assert_called_once_with()

class MainReportsButtonsTest(unittest.TestCase):
	def test_every_button_opens_a_module_that_exists(self):
		'''a button with no handler does nothing, and a handler importing a
		removed module raises; both only show when the button is clicked'''
		from reports import main_reports_window
		tree = ElementTree.parse(main_reports_window.UI_FILE)
		for button in tree.iter('object'):
			if button.get('class') != 'GtkButton':
				continue
			label = button.findtext("property[@name='label']")
			with self.subTest(button = label):
				signal = button.find("signal[@name='clicked']")
				self.assertIsNotNone(signal, 'no clicked handler')
				name = signal.get('handler')
				handler = getattr(main_reports_window.MainReportsGUI, name, None)
				self.assertIsNotNone(handler, name + ' is not in MainReportsGUI')
				source = textwrap.dedent(inspect.getsource(handler))
				for node in ast.walk(ast.parse(source)):
					if isinstance(node, ast.ImportFrom):
						for alias in node.names:
							module = node.module + '.' + alias.name
							self.assertIsNotNone(importlib.util.find_spec(module),
												module + ' does not exist')

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
