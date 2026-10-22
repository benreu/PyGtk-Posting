# test_database_role.py
#
# Posting logs in as posting, which owns every Posting database and
# everything in it (src/db/posting_role.sql) and is not a superuser. What has
# to hold for that to keep working: every object belongs to that login, every
# upgrade can be run by it, and an upgrade run by somebody else - a
# workstation still on postgres - leaves what it creates to the owner as well.

import os, sys, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from psycopg2 import sql
from gi.repository import Gtk
from db import version, database_tools, database_restore
from constants import sql_dir

# the same objects posting_role.sql gives to the login, and lists when it has
# not: everything in Posting's schemas that no extension owns
NOT_OURS = """
SELECT 'schema', n.nspname::text, pg_get_userbyid(n.nspowner)
FROM pg_namespace AS n
WHERE n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(n.nspowner) NOT IN (current_user, 'pg_database_owner')
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_namespace'::regclass, n.oid, 'e'))
UNION ALL
SELECT 'relation', c.oid::regclass::text, pg_get_userbyid(c.relowner)
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S', 'c')
AND n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(c.relowner) <> current_user
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_class'::regclass, c.oid, 'e'))
UNION ALL
SELECT 'routine', p.oid::regprocedure::text, pg_get_userbyid(p.proowner)
FROM pg_proc AS p
JOIN pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(p.proowner) <> current_user
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_proc'::regclass, p.oid, 'e'))
ORDER BY 1, 2
"""


class RunAsOwnerTest (unittest.TestCase):
	'''version.run_as_database_owner, against a cursor that answers the one
	question it asks: who owns this database, who is asking, and may they
	act as the owner.'''

	def ask (self, owner, user, member):
		cursor = mock.Mock()
		cursor.fetchone.return_value = (owner, user, member)
		switched = version.run_as_database_owner(cursor)
		return switched, cursor.execute.call_args_list[1:]

	def test_the_owner_itself_changes_nothing (self):
		switched, more = self.ask('posting', 'posting', True)
		self.assertIsNone(switched)
		self.assertEqual(more, [])

	def test_a_superuser_upgrades_as_the_owner (self):
		switched, more = self.ask('posting', 'postgres', True)
		self.assertEqual(switched, 'posting')
		self.assertEqual(more, [mock.call(sql.SQL("SET LOCAL ROLE {}").format(
											sql.Identifier('posting')))])

	def test_a_database_not_yet_converted_is_left_as_it_is (self):
		# owned by postgres and opened as postgres, which is every database
		# posting_role.sql has not been run on
		switched, more = self.ask('postgres', 'postgres', True)
		self.assertIsNone(switched)
		self.assertEqual(more, [])

	def test_a_login_that_cannot_be_the_owner_does_not_try (self):
		switched, more = self.ask('posting', 'someone_else', False)
		self.assertIsNone(switched)
		self.assertEqual(more, [])


class RestoreLoginTest (unittest.TestCase):
	'''Restore asks which login to restore as rather than using the
	connection form's, which is posting - a login that may not create the
	database a restore needs.'''

	FORM = {'server_entry': '192.168.50.120', 'port_entry': '5432',
			'username_entry': 'posting', 'password_entry': 'the posting one',
			'entry6': 'silrep_copy'}

	def setUp (self):
		self.gui = database_tools.GUI.__new__(database_tools.GUI)
		self.gui.window = None
		self.gui.status_update = mock.Mock()
		self.gui.builder = mock.Mock()
		self.gui.builder.get_object.side_effect = lambda name: mock.Mock(
							get_text = mock.Mock(return_value = self.FORM[name]))
		self.ask = self.start(mock.patch.object(database_restore,
												'ask_restore_login'))
		self.restore = self.start(mock.patch.object(database_restore,
													'RestoreGUI'))

	def start (self, patch):
		self.addCleanup(patch.stop)
		return patch.start()

	def test_the_login_asked_for_is_the_one_restored_with (self):
		self.ask.return_value = ('postgres', 'the superuser one')
		self.gui.restore_database_clicked(None)
		self.ask.assert_called_once_with(None, '192.168.50.120', '5432',
											'silrep_copy')
		self.restore.assert_called_once_with('192.168.50.120', '5432',
								'postgres', 'the superuser one', 'silrep_copy')

	def test_canceling_restores_nothing (self):
		self.ask.return_value = None
		self.gui.restore_database_clicked(None)
		self.assertFalse(self.restore.called)

	def test_no_database_name_asks_nothing (self):
		self.FORM = dict(self.FORM, entry6 = '')
		self.gui.restore_database_clicked(None)
		self.assertFalse(self.ask.called)
		self.assertFalse(self.restore.called)


class RestoreDialogTest (unittest.TestCase):

	def test_the_dialog_offers_postgres_and_hides_the_password (self):
		seen = {}
		def run (dialog):
			entries = [w for w in dialog.get_content_area().get_children()[0]
							.get_children() if isinstance(w, Gtk.Entry)]
			# get_children () is last attached first
			password, user = entries
			seen['user'] = user.get_text()
			seen['hidden'] = not password.get_visibility()
			password.set_text('typed')
			return Gtk.ResponseType.OK
		with mock.patch.object(Gtk.Dialog, 'run', run), \
				mock.patch.object(Gtk.Widget, 'show_all', lambda self: None):
			login = database_restore.ask_restore_login(None, 'h', '5432', 'db')
		self.assertEqual(login, ('postgres', 'typed'))
		self.assertEqual(seen, {'user': 'postgres', 'hidden': True})


class HandOverTest (unittest.TestCase):
	'''Once the data is in, the restore runs posting_role.sql on the new
	database with the same login, so it belongs to posting.'''

	def setUp (self):
		self.gui = database_restore.RestoreGUI.__new__(database_restore.RestoreGUI)
		self.gui.bin_path, self.gui.db_name = '/usr/bin', 'silrep_copy'
		self.gui.host, self.gui.port = '192.168.50.120', '5432'
		self.gui.user, self.gui.password = 'postgres', 'the superuser one'
		self.gui.handler_id = 1
		self.gui.terminal = mock.Mock()
		self.label = mock.Mock()
		patch = mock.patch.object(database_restore.RestoreGUI, 'get_object',
									return_value = self.label)
		patch.start()
		self.addCleanup(patch.stop)
		patch = mock.patch.object(database_restore.Vte.Pty, 'new_sync')
		self.pty = patch.start().return_value
		self.addCleanup(patch.stop)

	def test_the_command_runs_the_script_on_the_new_database (self):
		argv = database_restore.hand_over_command('/usr/bin', 'postgres',
											'192.168.50.120', '5432', 'silrep_copy')
		script = [a for a in argv if a.startswith('--file=')][0][len('--file='):]
		self.assertTrue(os.path.exists(script), script)
		self.assertEqual(os.path.basename(script), 'posting_role.sql')
		self.assertEqual(argv[0], '/usr/bin/psql')
		self.assertIn('-X', argv) # no ~/.psqlrc changing how it runs
		self.assertEqual(argv[-1],
						'postgresql://postgres@192.168.50.120:5432/silrep_copy')

	def test_a_finished_restore_is_handed_over_with_the_same_login (self):
		self.gui.restore_finished_callback(self.gui.terminal, 0)
		argv, envv = self.pty.spawn_async.call_args[0][1:3]
		self.assertEqual(argv, database_restore.hand_over_command('/usr/bin',
								'postgres', '192.168.50.120', '5432',
								'silrep_copy'))
		self.assertNotIn('the superuser one', ' '.join(argv))
		self.assertIn('PGPASSWORD=the superuser one', envv)

	def test_a_failed_restore_is_not_handed_over (self):
		self.gui.restore_finished_callback(self.gui.terminal, 256)
		self.assertFalse(self.pty.spawn_async.called)
		self.label.set_label.assert_called_with('Restore failed!')

	def test_a_failed_hand_over_says_the_data_is_there (self):
		self.gui.hand_over_finished_callback(self.gui.terminal, 768)
		said = self.label.set_label.call_args[0][0]
		self.assertIn('Restored silrep_copy', said)
		self.assertIn('posting_role.sql', said)


class OwnLoginTest (harness.DBTestCase):
	'''Against silrep_restore, as the login the suite runs as - which should be
	posting, never a superuser.'''

	def superuser (self):
		self.cursor.execute("SELECT rolsuper FROM pg_roles "
							"WHERE rolname = current_user")
		return self.cursor.fetchone()[0]

	def test_the_suite_is_not_running_as_a_superuser (self):
		self.cursor.execute("SELECT current_user")
		user = self.cursor.fetchone()[0]
		self.assertFalse(self.superuser(),
						"%s is a superuser, so nothing here shows what "
						"Posting's own login can do; set POSTING_TEST_DB_USER"
						% user)

	def test_this_login_owns_the_database (self):
		self.cursor.execute("SELECT pg_get_userbyid(datdba) = current_user "
							"FROM pg_database "
							"WHERE datname = current_database()")
		self.assertTrue(self.cursor.fetchone()[0],
						"run src/db/posting_role.sql on this database")

	def test_this_login_owns_everything_posting_keeps_here (self):
		# what a workstation still logging in as postgres leaves behind, and
		# what stops the next upgrade
		self.cursor.execute(NOT_OURS)
		self.assertEqual(self.cursor.fetchall(), [],
						"run src/db/posting_role.sql on this database")

	def test_every_upgrade_runs_as_this_login (self):
		'''The whole of update_db_minor.sql, which every upgrade runs again
		from the top, through the database tools window's own execute_file,
		inside the test transaction that is rolled back. It takes the locks an
		upgrade takes until then, so it waits behind a Posting that is open on
		the copy.'''
		if self.superuser():
			self.skipTest("a superuser can run anything; this would prove "
							"nothing")
		gui = database_tools.GUI.__new__(database_tools.GUI)
		gui.db = self.DB
		gui.progressbar = mock.Mock()
		gui.builder = mock.Mock()
		with open(os.path.join(sql_dir, 'update_db_minor.sql')) as f:
			worked = gui.execute_file(f)
		error = gui.builder.get_object('error_label').set_label.call_args
		self.assertTrue(worked, error and error[0][0])


if __name__ == '__main__':
	unittest.main()
