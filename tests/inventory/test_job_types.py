import unittest
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk

class JobTypesTest(DBTestCase):
	'''Customer > Job sheet > Job: Delete set a deleted column that did not
	exist, so it raised and the type stayed in every list'''
	def setUp(self):
		super().setUp()
		import job_types, job_sheet
		self.job_types = job_types
		self.job_sheet = job_sheet
		self.kept = self.one("INSERT INTO job_types (name) "
								"VALUES ('Test kept type') RETURNING id")
		self.gone = self.one("INSERT INTO job_types (name) "
								"VALUES ('Test deleted type') RETURNING id")
		self.DB.commit()

	def delete(self, gui, job_type_id):
		'''select the type in the Job Types window and click Delete'''
		row = [row[0] for row in gui.job_store].index(job_type_id)
		gui.get_object('treeview-selection1').select_path(Gtk.TreePath(row))
		gui.delete(None)

	def test_delete_hides_the_type(self):
		gui = self.job_types.GUI()
		self.delete(gui, self.gone)
		self.assertTrue(self.one("SELECT deleted FROM job_types WHERE id = %s",
									(self.gone,)))
		ids = [row[0] for row in gui.job_store]
		self.assertNotIn(self.gone, ids)
		self.assertIn(self.kept, ids)

	def test_deleting_the_type_being_edited_leaves_the_editor(self):
		gui = self.job_types.GUI()
		row = [row[0] for row in gui.job_store].index(self.gone)
		gui.row_activate(None, Gtk.TreePath(row), None)
		self.assertEqual(gui.job_id, self.gone)
		self.delete(gui, self.gone)
		self.assertEqual(gui.job_id, 0) # Save now adds a type
		gui.get_object('entry1').set_text('Test renamed')
		gui.save(gui.get_object('entry1'))
		self.assertEqual(self.one("SELECT name FROM job_types WHERE id = %s",
									(self.gone,)), 'Test deleted type')

	def test_job_sheet_leaves_deleted_types_out(self):
		self.cursor.execute("UPDATE job_types SET deleted = True "
							"WHERE id = %s", (self.gone,))
		self.DB.commit()
		gui = self.job_sheet.JobSheetGUI()
		gui.job_combobox_populate()
		ids = [row[0] for row in gui.job_type_store]
		self.assertNotIn(str(self.gone), ids)
		self.assertIn(str(self.kept), ids)

	def test_a_job_keeps_its_deleted_type(self):
		customer_id = self.one("SELECT id FROM contacts "
								"WHERE (deleted, customer) = (False, True) "
								"ORDER BY id LIMIT 1")
		self.cursor.execute("INSERT INTO job_sheets (contact_id, job_type_id, "
							"description) VALUES (%s, %s, 'Test job')",
							(customer_id, self.gone))
		self.cursor.execute("UPDATE job_types SET deleted = True "
							"WHERE id = %s", (self.gone,))
		self.DB.commit()
		gui = self.job_sheet.JobSheetGUI()
		gui.customer_id = str(customer_id)
		gui.populate_existing_job_combobox()
		jobs = [row[0] for row in gui.get_object('comboboxtext2').get_model()]
		self.assertIn('Test deleted type : Test job', jobs)

if __name__ == '__main__':
	unittest.main()
