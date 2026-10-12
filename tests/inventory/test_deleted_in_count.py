import unittest
from decimal import Decimal
from harness import DBTestCase

class _Combo:
	def __init__(self, active_id):
		self.active_id = active_id
	def get_active_id(self):
		return self.active_id

class _Selection:
	'''the compare window's buttons read their rows off a selection'''
	def __init__(self, model, rows):
		self.model = model
		self.rows = rows
	def get_selected_rows(self):
		return self.model, self.rows

class DeletedProductCountTest(DBTestCase):
	'''a deleted product must not be able to get into a count: close_count can
	only skip it, and uncorrectable_count_message can only complain about it'''
	def setUp(self):
		super().setUp()
		location_id = self.one("SELECT id FROM locations ORDER BY id LIMIT 1")
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.summary_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id, location_id) "
									"VALUES ('deleted product count', %s, %s) "
									"RETURNING id", (fiscal_id, location_id))
		self.product_id = self.one("SELECT id FROM products "
									"WHERE NOT deleted AND stock LIMIT 1")
		self.barcode = 'deleted-test-barcode'
		self.cursor.execute("UPDATE products SET (barcode, deleted) = (%s, True) "
							"WHERE id = %s", (self.barcode, self.product_id))
		self.DB.commit()

	def counted_products(self):
		self.cursor.execute("SELECT product_id FROM inventory.count_rows "
							"WHERE count_summary_id = %s", (self.summary_id,))
		return [row[0] for row in self.cursor.fetchall()]

	def count_window(self):
		from inventory import inventory_count
		gui = inventory_count.InventoryCountGUI()
		gui.summary_id = self.summary_id
		return gui

	def test_scanning_a_deleted_product_counts_nothing(self):
		gui = self.count_window()
		gui.barcode_entry_activated(_Entry(self.barcode))
		self.assertEqual(self.counted_products(), [])

	def test_scanning_a_deleted_product_reports_the_barcode_as_missing(self):
		'''it falls through to the unknown barcode list, which is where a
		barcode the count cannot use belongs'''
		gui = self.count_window()
		gui.barcode_entry_activated(_Entry(self.barcode))
		missing = [(row[0], row[1])
					for row in gui.get_object('missing_barcode_store')]
		self.assertEqual(missing, [(1, self.barcode)])

	def test_the_picker_still_leaves_it_out(self):
		gui = self.count_window()
		listed = [int(row[0]) for row in gui.get_object('product_store')]
		self.assertNotIn(self.product_id, listed)

	def test_a_product_deleted_after_it_was_counted_is_marked(self):
		'''its row stays visible, or the close would warn about something the
		user can neither see nor delete'''
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, 3, 1, 2)",
							(self.summary_id, self.product_id))
		self.DB.commit()
		gui = self.count_window()
		gui.populate_inventory_count()
		rows = [(row[1], row[2])
				for row in gui.get_object('inventory_rows_store')]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][0], self.product_id)
		self.assertTrue(rows[0][1].endswith(' (deleted)'), rows[0][1])

	def test_the_close_still_names_it_as_uncorrectable(self):
		from inventory import inventorying
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"inventory_account = NULL WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, 3, 1, 2)",
							(self.summary_id, self.product_id))
		self.DB.commit()
		self.assertIsNotNone(inventorying.uncorrectable_count_message(
															self.summary_id))

class DeletedProductCompareTest(DBTestCase):
	'''copy, update and create carry rows out of an older count, so each is a
	second door into a live one'''
	def setUp(self):
		super().setUp()
		location_id = self.one("SELECT id FROM locations ORDER BY id LIMIT 1")
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.previous_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id, location_id, date_created) "
									"VALUES ('older', %s, %s, '2020-01-01') "
									"RETURNING id", (fiscal_id, location_id))
		self.summary_id = self.one("INSERT INTO inventory.count_summaries "
									"(name, fiscal_id, location_id, date_created) "
									"VALUES ('newer', %s, %s, '2021-01-01') "
									"RETURNING id", (fiscal_id, location_id))
		self.product_id = self.one("SELECT id FROM products "
									"WHERE NOT deleted AND stock LIMIT 1")
		self.cursor.execute("UPDATE products SET deleted = True WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, 4, 1, 2)",
							(self.previous_id, self.product_id))
		self.DB.commit()

	def counted_products(self):
		self.cursor.execute("SELECT product_id FROM inventory.count_rows "
							"WHERE count_summary_id = %s", (self.summary_id,))
		return [row[0] for row in self.cursor.fetchall()]

	def compare_window(self):
		from inventory import inventory_compare
		gui = inventory_compare.InventoryCompareGUI()
		gui.inventory_summary_changed(_Combo(str(self.summary_id)))
		return gui

	def previous_selection(self, gui):
		store = gui.get_object('previous_inventory_store')
		gui.get_object('previous_inventory_selection') # the real one is unset
		return _Selection(store, [row.path for row in store])

	def test_copy_leaves_a_deleted_product_behind(self):
		gui = self.compare_window()
		gui.get_object = _patched_selection(gui, self.previous_selection(gui))
		gui.copy_inventory_clicked(None)
		self.assertEqual(self.counted_products(), [])

	def test_create_leaves_a_deleted_product_behind(self):
		gui = self.compare_window()
		gui.get_object = _patched_selection(gui, self.previous_selection(gui))
		gui.create_inventory_clicked(None)
		self.assertEqual(self.counted_products(), [])

	def test_update_leaves_a_deleted_product_behind(self):
		gui = self.compare_window()
		gui.get_object = _patched_selection(gui, self.previous_selection(gui))
		gui.update_inventory_clicked(None)
		self.assertEqual(self.counted_products(), [])

	def test_the_previous_count_still_shows_it_marked(self):
		gui = self.compare_window()
		rows = [row[2] for row in gui.get_object('previous_inventory_store')]
		self.assertEqual(len(rows), 1)
		self.assertTrue(rows[0].endswith(' (deleted)'), rows[0])

class _Entry:
	def __init__(self, text):
		self.text = text
	def get_text(self):
		return self.text
	def select_region(self, start, end):
		pass

def _patched_selection(gui, selection):
	'''the buttons fetch their selection by name, and a real GtkTreeSelection
	cannot be given rows from a test'''
	original = gui.get_object
	def get_object(name):
		if name == 'previous_inventory_selection':
			return selection
		return original(name)
	return get_object

if __name__ == '__main__':
	unittest.main()
