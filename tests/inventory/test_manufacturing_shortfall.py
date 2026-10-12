import unittest
from unittest import mock
from harness import DBTestCase
from gi.repository import Gtk

class ShortfallTest(DBTestCase):
	'''the project window's own view of what is short. ProjectEditGUI.__init__
	opens a window and takes an advisory lock on the project, so its methods are
	called unbound against a stand-in self holding only what they touch, the way
	test_manufacturing_projects drives show_message. parts_needed_store is built
	from the real .ui file, so the column order asserted here is the one the
	window renders'''
	def setUp(self):
		super().setUp()
		from manufacturing import project_edit_main
		self.gui = project_edit_main.ProjectEditGUI
		self.cursor.execute("SELECT mp.id FROM manufacturing_projects AS mp "
							"WHERE (SELECT count(*) FROM manufacturing_items "
							"WHERE manufacturing_project_id = mp.id "
							"AND qty > 0) >= 2 AND mp.qty > 0 LIMIT 1")
		self.project_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0 "
							"ORDER BY product_id", (self.project_id,))
		self.product_id, self.needed = self.cursor.fetchall()[0]
		self.source_id = self.new_location('Test source')
		self.elsewhere_id = self.new_location('Test elsewhere')
		self.cursor.execute("UPDATE manufacturing_items "
							"SET source_location_id = %s "
							"WHERE manufacturing_project_id = %s",
							(self.source_id, self.project_id))
		builder = Gtk.Builder()
		builder.add_objects_from_file(project_edit_main.UI_FILE,
										['parts_needed_store'])
		self.fake = mock.Mock()
		self.fake.parts_needed_store = builder.get_object('parts_needed_store')
		self.fake.project_id = self.project_id
		self.fake.default_source_id = self.one("SELECT id FROM locations "
												"ORDER BY id LIMIT 1")
		self.fake.default_source_name = self.one("SELECT name FROM locations "
												"ORDER BY id LIMIT 1")
		# refresh_shortfall leans on get_on_hand_qty, which a Mock self would
		# stub out, so the real method is bound to the stand-in
		self.fake.get_on_hand_qty = \
				self.gui.get_on_hand_qty.__get__(self.fake)
		self.DB.commit() # the window rolls back after every read of its own

	def stock(self, product_id, location_id, qty):
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
							(product_id, qty, location_id))
		self.DB.commit()

	def line_row(self):
		self.gui.populate_parts_needed_store(self.fake)
		for row in self.fake.parts_needed_store:
			if row[2] == self.product_id:
				return row
		self.fail('the line under test is not in the store')

	def test_on_hand_is_the_stock_at_the_lines_own_source(self):
		total_before = self.on_hand(self.product_id)
		self.stock(self.product_id, self.elsewhere_id, self.needed + 5)
		row = self.line_row()
		self.assertEqual(row[5], 0) # nothing of it is at the source
		self.assertEqual(row[13], total_before + self.needed + 5)
		self.assertEqual(row[8], self.needed) # so the whole line is short
		self.assertEqual(row[12], self.source_id)

	def test_stock_at_the_source_leaves_nothing_to_order(self):
		self.stock(self.product_id, self.source_id, self.needed)
		row = self.line_row()
		self.assertEqual(row[5], self.needed)
		self.assertEqual(row[8], 0)

	def test_refresh_shortfall_follows_the_source(self):
		'''choosing another Source asks a different question of the same line'''
		self.stock(self.product_id, self.elsewhere_id, self.needed)
		row = self.line_row()
		self.assertEqual(row[8], self.needed)
		row[12] = self.elsewhere_id # what source_combo_changed writes
		self.gui.refresh_shortfall(self.fake, row.iter)
		self.assertEqual(row[5], self.needed)
		self.assertEqual(row[8], 0)

	def test_a_line_with_no_source_falls_back_to_the_first_location(self):
		'''NULL means the first location to manufacture (), so it has to mean
		the same here'''
		self.cursor.execute("UPDATE manufacturing_items "
							"SET source_location_id = NULL "
							"WHERE manufacturing_project_id = %s AND product_id = %s",
							(self.project_id, self.product_id))
		self.DB.commit()
		first_id = self.fake.default_source_id
		row = self.line_row()
		self.assertEqual(row[12], first_id)
		self.assertEqual(row[11], self.fake.default_source_name)
		self.assertEqual(row[5], self.on_hand(self.product_id, first_id))

	def test_get_on_hand_qty_scopes_to_one_location(self):
		total_before = self.on_hand(self.product_id)
		self.stock(self.product_id, self.elsewhere_id, 7)
		get = self.gui.get_on_hand_qty
		self.assertEqual(get(self.fake, self.product_id, self.elsewhere_id), 7)
		self.assertEqual(get(self.fake, self.product_id, self.source_id), 0)
		self.assertEqual(get(self.fake, self.product_id), total_before + 7)

if __name__ == '__main__':
	unittest.main()
