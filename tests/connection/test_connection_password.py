# test_connection_password.py
#
# The database password lives in the workstation's login keyring, not in
# local_settings, which every program on the machine - and, while it was 0644,
# every account - could read. Nothing here touches the real keyring or a real
# local_settings: libsecret is harness.FakeSecret, and each test has its own
# sqlite file in a temporary directory.

import os, sys, stat, tempfile, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from harness import FakeSecret
import apsw, psycopg2
import credentials, sqlite_utils, db_connection
from db import database_backup, database_tools

SECRET = 'correct-horse-battery-staple'


class KeyringTestCase (unittest.TestCase):

	def setUp (self):
		self.secret = FakeSecret()
		credentials._schema = None
		patch = mock.patch.object(credentials, 'Secret', self.secret)
		patch.start()
		self.addCleanup(patch.stop)
		self.addCleanup(setattr, credentials, '_schema', None)
		directory = tempfile.TemporaryDirectory()
		self.addCleanup(directory.cleanup)
		self.path = os.path.join(directory.name, 'local_settings')
		self.sqlite = apsw.Connection(self.path)
		self.addCleanup(self.sqlite.close)
		self.cursor = self.sqlite.cursor()
		sqlite_utils.create_apsw_tables(self.cursor)
		sqlite_utils.update_apsw_tables(self.cursor)

	def default (self, host, port, user, password, db_name = 'silrep'):
		self.cursor.execute("UPDATE postgres_conn SET host = ?, port = ?, "
							"user = ?, password = ?, db_name = ?",
							(host, port, user, password, db_name))

	def connection (self, host, port, user, password, db_name = 'silrep'):
		self.cursor.execute("INSERT INTO db_connections "
							"(name, server, port, user, password, db_name, "
							"standard, mobile) "
							"VALUES ('test', ?, ?, ?, ?, ?, 'False', 'False')",
							(host, port, user, password, db_name))
		return self.sqlite.last_insert_rowid()

	def stored (self, host, user):
		key = (('host', host), ('service', 'postgres'), ('user', user))
		return self.secret.stored.get(key, (None, None))[1]

	def passwords (self):
		return [row[0] for row in self.cursor.execute(
							"SELECT password FROM postgres_conn UNION ALL "
							"SELECT password FROM db_connections")]


class MoveToKeyringTest (KeyringTestCase):

	def test_a_password_moves_to_the_keyring_and_out_of_the_file (self):
		self.default('192.168.50.120', '5432', 'postgres', SECRET)
		self.connection('192.168.50.120', '5432', 'postgres', SECRET)
		self.assertEqual(sqlite_utils.move_passwords_to_keyring(self.cursor), 1)
		self.assertEqual(self.stored('192.168.50.120:5432', 'postgres'), SECRET)
		self.assertNotIn(SECRET, self.passwords())

	def test_nothing_of_it_is_left_in_the_free_pages (self):
		# an UPDATE leaves the old value readable in the page until VACUUM
		self.default('h', '5432', 'u', SECRET)
		sqlite_utils.move_passwords_to_keyring(self.cursor)
		with open(self.path, 'rb') as f:
			self.assertNotIn(SECRET.encode(), f.read())

	def test_a_keyring_that_cannot_be_reached_leaves_every_password_in_place (self):
		# it may be the only copy of the password there is
		self.default('h', '5432', 'u', SECRET)
		self.connection('h', '5432', 'u', SECRET)
		before = self.passwords()
		with mock.patch.object(credentials, 'store_password',
					side_effect = credentials.CredentialError('no keyring')):
			self.assertEqual(sqlite_utils.move_passwords_to_keyring(self.cursor),
								0)
		self.assertEqual(self.passwords(), before)

	def test_the_default_connections_password_wins_over_a_stale_one (self):
		self.connection('h', '5432', 'u', 'stale')
		self.default('h', '5432', 'u', 'current')
		sqlite_utils.move_passwords_to_keyring(self.cursor)
		self.assertEqual(self.stored('h:5432', 'u'), 'current')
		self.assertNotIn('stale', self.passwords())
		self.assertNotIn('current', self.passwords())

	def test_another_port_is_another_password (self):
		self.connection('h', '5432', 'u', 'production')
		self.connection('h', '5433', 'u', 'scratch')
		self.assertEqual(sqlite_utils.move_passwords_to_keyring(self.cursor), 2)
		self.assertEqual(self.stored('h:5432', 'u'), 'production')
		self.assertEqual(self.stored('h:5433', 'u'), 'scratch')

	def test_the_placeholder_rows_are_not_passwords (self):
		self.assertEqual(sqlite_utils.move_passwords_to_keyring(self.cursor), 0)
		self.assertEqual(self.secret.stored, {})

	def test_a_second_run_finds_nothing_to_move (self):
		self.default('h', '5432', 'u', SECRET)
		sqlite_utils.move_passwords_to_keyring(self.cursor)
		self.assertEqual(sqlite_utils.move_passwords_to_keyring(self.cursor), 0)


class FetchParamsTest (KeyringTestCase):

	def test_the_password_comes_from_the_keyring (self):
		self.default('h', '5432', 'u', '')
		self.secret.lookup_result = SECRET
		params, mobile, missing = db_connection._fetch_params(self.sqlite, None)
		self.assertEqual(params['password'], SECRET)
		self.assertIsNone(missing)

	def test_a_row_the_keyring_could_not_take_yet_still_works (self):
		row_id = self.connection('h', '5432', 'u', 'legacy')
		with mock.patch.object(credentials, 'password') as lookup:
			params, mobile, missing = db_connection._fetch_params(self.sqlite,
																	row_id)
		self.assertEqual(params['password'], 'legacy')
		self.assertFalse(lookup.called)

	def test_nothing_stored_says_why (self):
		self.default('h', '5432', 'u', '')
		self.secret.lookup_result = None
		params, mobile, missing = db_connection._fetch_params(self.sqlite, None)
		self.assertIsNone(params['password'])
		self.assertIn('saved on this computer', missing)

	def test_the_placeholder_row_never_reaches_the_keyring (self):
		with mock.patch.object(credentials, 'password') as lookup:
			params, mobile, missing = db_connection._fetch_params(self.sqlite,
																	None)
		self.assertFalse(lookup.called)
		self.assertIsNone(missing)


class FirstConnectTest (KeyringTestCase):
	'''The first connect reads the keyring, asks for a password that is
	missing or refused, and keeps one once the server has accepted it.'''

	MISSING = "No postgres password for u has been saved on this computer."

	def setUp (self):
		KeyringTestCase.setUp(self)
		self.params = {'dbname': 'silrep', 'host': 'h', 'port': '5432',
						'user': 'u', 'password': None}
		self.start(mock.patch.object(db_connection, 'get_db_params',
					side_effect = lambda row_id: (dict(self.params), False,
													self.MISSING)))
		self.connect = self.start(mock.patch.object(db_connection.psycopg2,
														'connect'))
		self.ask = self.start(mock.patch.object(db_connection, 'ask_password'))

	def start (self, patch):
		self.addCleanup(patch.stop)
		return patch.start()

	def refused (self):
		return psycopg2.OperationalError('connection to server at "h", port '
						'5432 failed: FATAL:  password authentication failed '
						'for user "u"')

	def test_a_missing_password_is_asked_for_and_kept_once_it_works (self):
		self.connect.side_effect = [psycopg2.OperationalError(
										'fe_sendauth: no password supplied'),
									mock.Mock()]
		self.ask.return_value = SECRET
		db = db_connection.DBConnection(None)
		self.assertEqual(self.ask.call_args[0][1], self.MISSING)
		self.assertEqual(self.connect.call_args[1]['password'], SECRET)
		self.assertEqual(self.stored('h:5432', 'u'), SECRET)
		self.assertEqual(db._params['password'], SECRET)

	def test_a_wrong_password_is_asked_for_again_with_what_the_server_said (self):
		self.connect.side_effect = [self.refused(), self.refused(), mock.Mock()]
		self.ask.side_effect = ['wrong', SECRET]
		db_connection.DBConnection(None)
		self.assertIn('password authentication failed',
						self.ask.call_args_list[1][0][1])
		self.assertEqual(self.stored('h:5432', 'u'), SECRET)

	def test_canceling_opens_the_connection_picker_as_before (self):
		self.addCleanup(setattr, db_connection, 'db_name',
						db_connection.db_name)
		self.connect.side_effect = self.refused()
		self.ask.return_value = None
		self.assertFalse(db_connection.connect(None))
		self.assertEqual(self.secret.stored, {})

	def test_a_server_that_is_down_is_not_a_password_question (self):
		self.connect.side_effect = psycopg2.OperationalError(
						'could not connect to server: Connection refused')
		with self.assertRaises(psycopg2.OperationalError):
			db_connection.DBConnection(None)
		self.assertFalse(self.ask.called)

	def test_a_password_that_already_worked_is_not_stored_again (self):
		self.params['password'] = SECRET
		self.connect.return_value = mock.Mock()
		with mock.patch.object(credentials, 'store_password') as store:
			db_connection.DBConnection(None)
		self.assertFalse(store.called)
		self.assertFalse(self.ask.called)

	def test_a_keyring_that_will_not_take_it_still_connects_this_session (self):
		self.connect.side_effect = [self.refused(), mock.Mock()]
		self.ask.return_value = SECRET
		with mock.patch.object(credentials, 'store_password',
					side_effect = credentials.CredentialError('no keyring')):
			db = db_connection.DBConnection(None)
		self.assertEqual(db._params['password'], SECRET)

	def test_a_reconnect_reads_neither_the_settings_nor_the_keyring (self):
		# reconnect() runs on the main loop, where a keyring prompt would freeze
		# the application until it was answered
		self.params['password'] = SECRET
		self.connect.return_value = mock.Mock()
		db = db_connection.DBConnection(None)
		with mock.patch.object(db_connection, 'get_db_params',
								side_effect = AssertionError('settings read')), \
				mock.patch.object(credentials, 'password',
								side_effect = AssertionError('keyring read')):
			db._connect()
		self.assertEqual(self.connect.call_args[1]['password'], SECRET)


class BackupCommandTest (unittest.TestCase):
	'''pg_dump, psql and pg_restore get the password through the environment,
	which only this user can read, never on the command line, which ps shows
	to every account on the machine.'''

	def test_the_url_has_no_password_in_it (self):
		self.assertEqual(database_backup.connection_url('postgres', 'h', '5432',
														'silrep'),
							'postgresql://postgres@h:5432/silrep')

	def test_the_password_is_in_the_environment_once (self):
		with mock.patch.dict(os.environ, {'PGPASSWORD': 'old'}):
			envv = database_backup.password_environment(SECRET)
		self.assertEqual([v for v in envv if v.startswith('PGPASSWORD=')],
							['PGPASSWORD=' + SECRET])
		self.assertIn('PATH=' + os.environ['PATH'], envv)

	def test_no_password_leaves_the_environment_alone (self):
		with mock.patch.dict(os.environ, {'PGPASSWORD': 'from-the-shell'}):
			envv = database_backup.password_environment(None)
		self.assertIn('PGPASSWORD=from-the-shell', envv)


class PrivateFileTest (unittest.TestCase):

	def setUp (self):
		directory = tempfile.TemporaryDirectory()
		self.addCleanup(directory.cleanup)
		self.path = os.path.join(directory.name, 'local_settings')

	def mode (self):
		return stat.S_IMODE(os.stat(self.path).st_mode)

	def test_an_old_world_readable_file_is_narrowed (self):
		open(self.path, 'w').close()
		os.chmod(self.path, 0o644)
		sqlite_utils.make_private(self.path)
		self.assertEqual(self.mode(), 0o600)

	def test_a_new_file_is_created_private (self):
		sqlite_utils.make_private(self.path)
		self.assertEqual(self.mode(), 0o600)


class ConnectionsWindowTest (KeyringTestCase):
	'''Save and Delete in the database tools window: the password goes to the
	keyring, and leaves it when the last connection using it goes.'''

	class Thread (object):
		"runs the work at once, so the test can see what it did"
		def __init__ (self, target, daemon = False):
			self.target = target
		def start (self):
			self.target()

	def setUp (self):
		KeyringTestCase.setUp(self)
		self.gui = database_tools.GUI.__new__(database_tools.GUI)
		self.gui.builder = mock.Mock()
		self.gui.populate_databases = mock.Mock()
		self.gui.status_update = mock.Mock()
		threading = mock.Mock(Thread = self.Thread)
		for name, value in (('threading', threading), ('GLib', mock.Mock()),
							('get_apsw_connection',
								lambda: apsw.Connection(self.path))):
			patch = mock.patch.object(database_tools, name, value)
			patch.start()
			self.addCleanup(patch.stop)

	def delete (self, row_id):
		self.gui.forget_password = mock.Mock()
		model = {'row': [row_id]}
		self.gui.builder.get_object.return_value.get_selected.return_value = (
														model, 'row')
		self.gui.delete_connection_clicked(None)
		return self.gui.forget_password

	def test_a_password_is_kept_under_server_and_port (self):
		self.gui.keep_password('h', '5432', 'u', SECRET)
		self.assertEqual(self.stored('h:5432', 'u'), SECRET)

	def test_a_keyring_that_will_not_take_it_says_posting_will_ask (self):
		with mock.patch.object(credentials, 'store_password',
					side_effect = credentials.CredentialError('no keyring')):
			self.gui.keep_password('h', '5432', 'u', SECRET)
		said = database_tools.GLib.idle_add.call_args[0][1]
		self.assertIn('ask for it', said)

	def test_deleting_the_last_connection_to_a_server_forgets_it (self):
		row_id = self.connection('h', '5432', 'u', '')
		forget = self.delete(row_id)
		forget.assert_called_once_with('h', '5432', 'u')

	def test_another_connection_to_the_server_keeps_it (self):
		row_id = self.connection('h', '5432', 'u', '', 'silrep')
		self.connection('h', '5432', 'u', '', 'silrep_restore')
		self.assertFalse(self.delete(row_id).called)

	def test_the_default_connection_using_it_keeps_it (self):
		self.default('h', '5432', 'u', '')
		row_id = self.connection('h', '5432', 'u', '')
		self.assertFalse(self.delete(row_id).called)


if __name__ == '__main__':
	unittest.main()
