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
		buffer_ = gui.get_object('sql_error_buffer')
		start, end = buffer_.get_bounds()
		return buffer_.get_text(start, end, True)

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

	def test_refused_commit_shown(self):
		with mock.patch.object(self.DB, 'commit',
						side_effect = psycopg2.Error('commit refused')):
			message = self.run_sql(CHANGE, commit = True)
		self.assertEqual(message, 'commit refused')
		self.assertEqual(self.command(), 'before')

if __name__ == '__main__':
	unittest.main()
