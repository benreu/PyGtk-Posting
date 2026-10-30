import unittest
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk, GObject

class RecordViewTest(DBTestCase):
	'''Double clicking a Complete search result showed the record with a NULL
	integer as 0 and a NULL text as the word None'''
	def setUp(self):
		super().setUp()
		import complete_search
		self.complete_search = complete_search
		# a temporary table goes with the test's rollback like everything else
		self.cursor.execute("CREATE TEMP TABLE complete_search_test "
							"(n integer, t text, b boolean)")
		self.cursor.execute("INSERT INTO complete_search_test VALUES "
							"(NULL, 'needle', NULL), (7, NULL, True)")
		self.DB.commit()

	def record(self, where):
		'''the record view, opened on the row where picks out'''
		ctid = self.one("SELECT ctid::text FROM complete_search_test "
						"WHERE %s" % where)
		gui = self.complete_search.CompleteSearchGUI()
		gui.store.append(['pg_temp', 'complete_search_test', 't', 'needle',
							ctid])
		gui.treeview_row_activated(gui.treeview, Gtk.TreePath(0), None)
		store = gui.get_object('record_treeview').get_model()
		self.assertEqual(len(store), 1)
		return store

	def test_nulls_blank(self):
		store = self.record("t = 'needle'")
		self.assertEqual([store[0][0], store[0][1], store[0][2]],
							['', 'needle', False])

	def test_integer_without_null_stays_a_number(self):
		store = self.record("n = 7")
		self.assertEqual(store.get_column_type(0), GObject.TYPE_INT)
		self.assertEqual([store[0][0], store[0][1], store[0][2]],
							[7, '', True])

if __name__ == '__main__':
	unittest.main()
