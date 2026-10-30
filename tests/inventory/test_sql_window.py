import unittest
from unittest import mock
import psycopg2
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk, GObject

NAME = 'SQL window test'
CHANGE = "UPDATE sql.history SET command = 'after' WHERE name = '%s'" % NAME

class SQLWindowTest(DBTestCase):
	'''Administration > SQL window rolled back every statement, so an UPDATE
	reported its rows affected and changed nothing. It now rolls back unless
	its Commit box is ticked'''
	def setUp(self):
		super().setUp()
		from db import sql_window
		self.sql_window = sql_window
		# the window opens on the Current row, and fails without one
		self.cursor.execute("INSERT INTO sql.history "
								"(name, command, date_inserted, current) "
							"VALUES ('Current', '', CURRENT_DATE, True) "
							"ON CONFLICT DO NOTHING")
		self.cursor.execute("INSERT INTO sql.history "
								"(name, command, date_inserted) "
							"VALUES (%s, 'before', CURRENT_DATE) "
							"ON CONFLICT (name) DO UPDATE SET command = 'before'",
							(NAME,))
		self.DB.commit()

	def run_sql(self, command, commit = False):
		gui = self.sql_window.SQLWindowGUI()
		gui.get_object('commit_checkbutton').set_active(commit)
		gui.source_buffer.set_text(command)
		gui.run_sql_clicked(None)
		self.store = gui.get_object('treeview1').get_model()
		buffer_ = gui.get_object('sql_error_buffer')
		start, end = buffer_.get_bounds()
		return buffer_.get_text(start, end, True)

	def column(self, index = 0):
		return [row[index] for row in self.store]

	def command(self):
		'''what the scratch row holds once anything still open is undone, so
		only a change the window committed survives'''
		self.DB.rollback()
		return self.one("SELECT command FROM sql.history WHERE name = %s",
						(NAME,))

	def test_unticked_on_open(self):
		gui = self.sql_window.SQLWindowGUI()
		self.assertFalse(gui.get_object('commit_checkbutton').get_active())

	def test_unticked_rolls_back(self):
		message = self.run_sql(CHANGE)
		self.assertEqual(message,
					"1 row(s) would be affected; rolled back, nothing changed")
		self.assertEqual(self.command(), 'before')

	def test_ticked_commits(self):
		message = self.run_sql(CHANGE, commit = True)
		self.assertEqual(message, "1 row(s) affected and committed")
		self.assertEqual(self.command(), 'after')

	def test_change_kept_as_current(self):
		'''only queries with a result were kept as Current'''
		self.run_sql(CHANGE)
		self.assertEqual(self.one("SELECT command FROM sql.history "
									"WHERE current = True"), CHANGE)

	def test_returning_follows_the_box(self):
		'''an UPDATE ... RETURNING takes the path that fills the table'''
		self.run_sql(CHANGE + " RETURNING name")
		self.assertEqual(self.command(), 'before')
		self.run_sql(CHANGE + " RETURNING name", commit = True)
		self.assertEqual(self.command(), 'after')

	def test_failure_rolled_back_when_ticked(self):
		message = self.run_sql(CHANGE + "; SELECT 1/0", commit = True)
		self.assertIn('division by zero', message)
		self.assertEqual(self.command(), 'before')

	def test_null_integer_blank(self):
		'''int(None) raised, so a NULL integer put up a traceback and an
		empty table. The column still sorts as numbers, even ones further
		apart than a C int holds'''
		command = ("SELECT * FROM (VALUES (2), (NULL), (10), (2000000000), "
					"(-2000000000)) AS v (n)")
		self.run_sql(command)
		self.assertEqual(self.column(),
						['2', '', '10', '2000000000', '-2000000000'])
		self.store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
		self.assertEqual(self.column(),
						['', '-2000000000', '2', '10', '2000000000'])
		self.assertEqual(self.one("SELECT command FROM sql.history "
									"WHERE current = True"), command)

	def test_integer_without_null_stays_a_number(self):
		'''so it sorts, and Report hub exports it to xls, as numbers'''
		self.run_sql("SELECT * FROM (VALUES (10), (2)) AS v (n)")
		self.assertEqual(self.store.get_column_type(0), GObject.TYPE_INT)
		self.assertEqual(self.column(), [10, 2])

	def test_null_text_and_boolean(self):
		'''text showed the word None'''
		self.run_sql("SELECT NULL::text AS t, NULL::boolean AS b")
		self.assertEqual(self.column(0), [''])
		self.assertEqual(self.column(1), [False])

	def test_refused_commit_shown(self):
		with mock.patch.object(self.DB, 'commit',
						side_effect = psycopg2.Error('commit refused')):
			message = self.run_sql(CHANGE, commit = True)
		self.assertEqual(message, 'commit refused')
		self.assertEqual(self.command(), 'before')

class NumberSortTest(unittest.TestCase):
	'''GTK takes the sort func's answer as a C int. Which rows a sort
	compares head on changes from run to run, so the sorting test above
	does not always meet a pair whose difference overflows; this does'''
	def compare(self, a, b):
		import query_results
		store = Gtk.ListStore(str)
		iter_a = store.append([a])
		iter_b = store.append([b])
		return query_results.number_sort_func(store, iter_a, iter_b, 0)

	def test_far_apart(self):
		self.assertEqual(self.compare('2000000000', '-2000000000'), 1)
		self.assertEqual(self.compare('-2000000000', '2000000000'), -1)

	def test_blank_first(self):
		self.assertEqual(self.compare('', '-2000000000'), -1)
		self.assertEqual(self.compare('5', ''), 1)
		self.assertEqual(self.compare('', ''), 0)
		self.assertEqual(self.compare('5', '5'), 0)

if __name__ == '__main__':
	unittest.main()
