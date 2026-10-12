import unittest
from harness import DBTestCase

class _Treeview:
	def __init__(self, store):
		self.store = store
	def get_model(self):
		return self.store

class SummariesLocationTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.fiscal_id = self.one("SELECT id FROM fiscal_years "
									"WHERE active = True LIMIT 1")
		self.location_id = self.new_location('Summary test location')
		self.DB.commit()
		from inventory import inventory_summaries
		self.gui = inventory_summaries.InventorySummariesGUI()

	def summary(self, name = 'unit test', active = True, location = True):
		if location == False:
			# a count taken before 0.7.22, on a database whose locations had all
			# been deleted, so the backfill had nothing to write. The constraint
			# is dropped inside the test transaction and rolls back with it
			self.cursor.execute("ALTER TABLE inventory.count_summaries "
								"ALTER COLUMN location_id DROP NOT NULL")
		return self.one("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, location_id, active) "
						"VALUES (%s, %s, %s, %s) RETURNING id",
						(name, self.fiscal_id,
						self.location_id if location else None, active))

	def fill_in(self, name = 'unit test'):
		self.gui.get_object('name_entry').set_text(name)
		self.gui.get_object('fiscal_year_combo').set_active_id(str(self.fiscal_id))
		self.gui.get_object('location_combo').set_active_id(str(self.location_id))

	def activate(self, summary_id):
		'''the treeview has no id in the .ui, and the handler only ever asks it
		for its model, so a stand in is enough to drive a row activation'''
		self.gui.populate_stores()
		store = self.gui.get_object('inventory_summaries_store')
		for row in store:
			if row[0] == summary_id:
				self.gui.treeview_row_activated(_Treeview(store), row.path, None)
				return
		self.fail('summary not listed')

	def test_a_new_summary_keeps_its_location(self):
		self.fill_in('location unit test')
		self.gui.save_clicked(None)
		self.assertNotEqual(self.gui.id, 0)
		self.assertEqual(self.one("SELECT location_id FROM "
									"inventory.count_summaries WHERE id = %s",
									(self.gui.id,)), self.location_id)

	def test_an_edited_summary_keeps_its_location(self):
		summary_id = self.summary('before')
		self.DB.commit()
		other = self.new_location('Somewhere else')
		self.DB.commit()
		self.activate(summary_id)
		self.gui.get_object('location_combo').set_active_id(str(other))
		self.gui.save_clicked(None)
		self.assertEqual(self.one("SELECT location_id FROM "
									"inventory.count_summaries WHERE id = %s",
									(summary_id,)), other)

	def test_row_activated_restores_the_location(self):
		summary_id = self.summary('restore me')
		self.DB.commit()
		self.activate(summary_id)
		self.assertEqual(self.gui.get_object('location_combo').get_active_id(),
							str(self.location_id))

	def test_the_save_button_refuses_without_a_location(self):
		self.fill_in()
		self.gui.get_object('location_combo').set_active(-1)
		self.gui.check_info_validity()
		button = self.gui.get_object('save_button')
		self.assertFalse(button.get_sensitive())
		self.assertEqual(button.get_label(), 'No location')

	def test_a_closed_count_cannot_be_edited(self):
		summary_id = self.summary('closed one', active = False)
		self.DB.commit()
		self.activate(summary_id)
		button = self.gui.get_object('save_button')
		self.assertFalse(button.get_sensitive())
		self.assertEqual(button.get_label(), 'Count closed')

	def test_a_closed_count_is_not_moved_by_a_save(self):
		'''the button is insensitive, but save_clicked is reachable from a stale
		window, and moving a closed count would orphan its corrections'''
		summary_id = self.summary('closed one', active = False)
		self.DB.commit()
		self.activate(summary_id)
		other = self.new_location('Somewhere else')
		self.DB.commit()
		self.gui.get_object('location_combo').set_active_id(str(other))
		self.gui.save_clicked(None)
		self.assertEqual(self.one("SELECT location_id FROM "
									"inventory.count_summaries WHERE id = %s",
									(summary_id,)), self.location_id)

	def test_a_summary_with_no_location_still_lists(self):
		summary_id = self.summary('legacy', location = False)
		self.DB.commit()
		self.gui.populate_stores() # must not raise on the gint column
		listed = [row[0] for row in
					self.gui.get_object('inventory_summaries_store')]
		self.assertIn(summary_id, listed)

	def test_a_summary_with_no_location_cannot_be_saved(self):
		summary_id = self.summary('legacy', location = False)
		self.DB.commit()
		self.activate(summary_id)
		button = self.gui.get_object('save_button')
		self.assertFalse(button.get_sensitive())
		self.assertEqual(button.get_label(), 'No location')

	def test_the_location_survives_a_repopulate(self):
		'''save_clicked repopulates, and clearing the store unsets the combo'''
		self.fill_in()
		self.gui.populate_stores()
		self.assertEqual(self.gui.get_object('location_combo').get_active_id(),
							str(self.location_id))

if __name__ == '__main__':
	unittest.main()
