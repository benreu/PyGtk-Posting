import unittest
from harness import DBTestCase

class PreviousCountTest(DBTestCase):
	def summary(self, name, date):
		fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		location_id = self.one("SELECT id FROM locations ORDER BY id LIMIT 1")
		return self.one("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, date_created, location_id) "
						"VALUES (%s, %s, %s, %s) "
						"RETURNING id", (name, fiscal_id, date, location_id))

	def previous_label(self, summary_id):
		from inventory import inventory_compare
		gui = inventory_compare.InventoryCompareGUI()
		gui.inventory_summary_changed(_Combo(str(summary_id)))
		return gui.get_object('previous_summary_label').get_label()

	def test_previous_is_by_date_not_by_id(self):
		newer = self.summary('newer', '2021-01-01') # lower id, later date
		self.summary('older', '2020-01-01')
		self.DB.commit()
		self.assertEqual(self.previous_label(newer), 'older')

	def test_first_count_has_no_previous(self):
		first = self.summary('first', '1999-01-01')
		self.DB.commit()
		self.assertEqual(self.previous_label(first), 'does not exist')

class _Combo:
	def __init__(self, active_id):
		self.active_id = active_id
	def get_active_id(self):
		return self.active_id

if __name__ == '__main__':
	unittest.main()
