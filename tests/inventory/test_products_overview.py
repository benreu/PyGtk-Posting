import unittest
from harness import DBTestCase  # pins Gtk to 3.0, so it is imported first
from gi.repository import Gtk
from unittest import mock

class ProductFilterTest(DBTestCase):
	'''populate_product_store joins units and filters products on a bare
	"deleted". units has a deleted column of its own now, which made every one
	of these filters raise AmbiguousColumn, and nothing here ran that query'''

	def setUp(self):
		super().setUp()
		# the real loop pumps the main loop once per product, 2600 times
		patch = mock.patch('gi.repository.Gtk.events_pending',
							return_value = False)
		patch.start()
		self.addCleanup(patch.stop)
		import products_overview
		self.gui = products_overview.ProductsOverviewGUI()

	def test_every_product_filter_runs(self):
		for name in ('radiobutton1', 'radiobutton2', 'radiobutton3',
						'radiobutton4', 'radiobutton5', 'radiobutton6',
						'radiobutton7'):
			with self.subTest(filter = name):
				self.gui.get_object(name).set_active(True)
				self.gui.populate_product_store()

	def test_the_unit_name_reaches_the_store(self):
		'''store column 5 is u.name, the reason the join is there at all'''
		unit = self.one("SELECT u.name FROM products AS p "
						"JOIN units AS u ON u.id = p.unit WHERE p.id = 19")
		self.gui.get_object('radiobutton6').set_active(True)
		self.gui.populate_product_store()
		listed = [row[5] for row in self.gui.product_store if row[0] == 19]
		self.assertEqual(listed, [unit])

	def test_append_product_runs(self):
		self.gui.product_id = 19
		self.gui.append_product()
		self.assertIn(19, [row[0] for row in self.gui.product_store])

if __name__ == '__main__':
	unittest.main()
