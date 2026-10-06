import unittest
from harness import DBTestCase
from unittest import mock

class LocationsTest(DBTestCase):
	def setUp(self):
		super().setUp()
		import locations
		self.gui = locations.LocationsGUI()

	def test_new_location_is_inserted(self):
		self.gui.new_clicked(None)
		self.gui.builder.get_object('entry1').set_text('Unit test location')
		self.gui.save_clicked(None)
		self.assertNotEqual(self.gui.location_id, 0)
		name = self.one("SELECT name FROM locations WHERE id = %s",
						(self.gui.location_id,))
		self.assertEqual(name, 'Unit test location')

	def test_rename_location(self):
		location_id = self.new_location('before')
		self.DB.commit()
		self.gui.location_id = location_id
		self.gui.builder.get_object('entry1').set_text('after')
		self.gui.save_clicked(None)
		self.assertEqual(self.one("SELECT name FROM locations WHERE id = %s",
									(location_id,)), 'after')

	def select_location(self, location_id):
		self.gui.location_treeview_populate()
		for row in self.gui.location_store:
			if row[0] == location_id:
				selection = self.gui.builder.get_object('treeview-selection2')
				selection.select_path(row.path)
				return
		self.fail('location not listed')

	def test_unused_location_is_deleted(self):
		location_id = self.new_location()
		self.DB.commit()
		self.select_location(location_id)
		self.gui.delete_clicked(None)
		self.cursor.execute("SELECT 1 FROM locations WHERE id = %s", (location_id,))
		self.assertEqual(self.cursor.fetchall(), [])

	def test_used_location_survives_delete(self):
		location_id = self.new_location()
		product_id = self.one("SELECT id FROM products LIMIT 1")
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, location_id, price, reason, date_inserted) "
							"VALUES (%s, 1, %s, 1, 'test', CURRENT_DATE)", (product_id, location_id))
		self.DB.commit()
		self.select_location(location_id)
		with mock.patch('gi.repository.Gtk.MessageDialog.run'):
			self.gui.delete_clicked(None)
		self.assertEqual(self.one("SELECT count(*) FROM locations WHERE id = %s",
								(location_id,)), 1)

if __name__ == '__main__':
	unittest.main()
