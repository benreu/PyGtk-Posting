import re
import unittest
from unittest import mock
from harness import DBTestCase
from gi.repository import Gtk

class ProjectEditWindowTest(DBTestCase):
	'''the window as the application really builds it: the .ui file loaded, the
	signals connected, the advisory lock taken and the parts needed list filled
	by __init__. test_manufacturing_shortfall pins the quantities against the
	SQL; what is checked here is that the real window and its real handlers show
	the stock manufacture () will consume'''
	def setUp(self):
		super().setUp()
		from manufacturing import project_edit_main
		self.module = project_edit_main
		self.cursor.execute("SELECT mp.id FROM manufacturing_projects AS mp "
							"WHERE (SELECT count(*) FROM manufacturing_items "
							"WHERE manufacturing_project_id = mp.id "
							"AND qty > 0) >= 2 AND mp.qty > 0 LIMIT 1")
		self.project_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT product_id, qty FROM manufacturing_items "
							"WHERE manufacturing_project_id = %s AND qty > 0 "
							"ORDER BY product_id", (self.project_id,))
		self.component_id, self.needed = self.cursor.fetchall()[0]
		self.source_id = self.new_location('Test source')
		self.elsewhere_id = self.new_location('Test elsewhere')
		self.cursor.execute("UPDATE manufacturing_items "
							"SET source_location_id = %s "
							"WHERE manufacturing_project_id = %s",
							(self.source_id, self.project_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE manufacturing_id = %s", (self.project_id,))
		# the case the window used to read as nothing to order: the part is in
		# stock, but at a location this build never touches
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, %s, 1, %s, CURRENT_DATE, 'test')",
							(self.component_id, self.needed + 5,
							self.elsewhere_id))
		self.DB.commit() # the window rolls back after every read of its own
		self.windows = []

	def tearDown(self):
		for gui in self.windows:
			gui.destroy(gui.window) # releases the advisory lock on the project
		super().tearDown()

	def open_window(self):
		gui = self.module.ProjectEditGUI(mock.Mock(), self.project_id)
		self.windows.append(gui)
		self.assertTrue(gui.project_lock_acquired,
						'the window gave up on the project lock')
		return gui

	def row_for(self, gui, product_id):
		for row in gui.parts_needed_store:
			if row[2] == product_id:
				return row
		self.fail('product %s is not in the parts needed list' % product_id)

	def location_iter(self, gui, name):
		for row in gui.location_store:
			if row[1] == name:
				return row.iter
		self.fail('%s is not in the location combo' % name)

	def test_every_ui_handler_exists_on_the_class(self):
		'''connect_signals only warns about a handler it cannot find, so a
		renamed one leaves a dead column in a window that still opens'''
		with open(self.module.UI_FILE) as f:
			handlers = set(re.findall(r'handler="([a-z_]+)"', f.read()))
		self.assertTrue(handlers)
		self.assertEqual([h for h in sorted(handlers)
						if not hasattr(self.module.ProjectEditGUI, h)], [])

	def test_the_window_opens_on_the_source_scoped_shortfall(self):
		gui = self.open_window()
		self.assertEqual(gui.default_source_id,
						self.one("SELECT id FROM locations "
								"ORDER BY id LIMIT 1"))
		row = self.row_for(gui, self.component_id)
		self.assertEqual(row[5], 0) # none of it is at the source
		self.assertEqual(row[13], self.needed + 5) # it is all elsewhere
		self.assertEqual(row[8], self.needed) # so the whole line is short
		self.assertEqual(row[11], 'Test source')

	def test_choosing_another_source_recomputes_the_line(self):
		'''the Source combo's own handler, with the arguments GTK hands it. It
		used to write the location and leave the old location's shortfall on
		screen'''
		gui = self.open_window()
		row = self.row_for(gui, self.component_id)
		gui.source_combo_changed(gui.get_object('source_combo_renderer'),
								row.path.to_string(),
								self.location_iter(gui, 'Test elsewhere'))
		self.assertEqual(row[11], 'Test elsewhere')
		self.assertEqual(row[5], self.needed + 5)
		self.assertEqual(row[8], 0) # it is covered at the new source
		self.assertEqual(self.one("SELECT source_location_id "
								"FROM manufacturing_items WHERE id = %s",
								(row[0],)), self.elsewhere_id)

	def test_raising_the_needed_qty_raises_the_order_qty(self):
		gui = self.open_window()
		row = self.row_for(gui, self.component_id)
		gui.needed_qty_edited(None, row.path.to_string(), str(self.needed + 2))
		self.assertEqual(row[1], self.needed + 2)
		self.assertEqual(row[5], 0)
		self.assertEqual(row[8], self.needed + 2)

if __name__ == '__main__':
	unittest.main()
