# test_credentials.py
#
# The mail password lives in the workstation's login keyring, never in the
# database, so that a backup, a restore copy or the SQL window cannot leak it.
#
# Nothing here touches the real keyring: libsecret is mocked in every test.
# The two assertions that matter most are the ones on the schema name and the
# attribute names - renaming either would orphan every password every user has
# already stored, and would do it silently, with no other test failing.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import credentials
from gi.repository import GLib


class FakeSchemaAttributeType (object):
	STRING = 'string'


class FakeSecret (object):
	"only what credentials.py asks of libsecret"
	COLLECTION_DEFAULT = 'default'
	SchemaAttributeType = FakeSchemaAttributeType

	class SchemaFlags (object):
		NONE = 0

	class ServiceFlags (object):
		OPEN_SESSION = 2

	class SearchFlags (object):
		NONE = 0
		UNLOCK = 2
		LOAD_SECRETS = 4

	class Schema (object):
		@staticmethod
		def new (name, flags, attributes):
			return {'name': name, 'flags': flags, 'attributes': attributes}

	def __init__ (self):
		self.stored = {}
		self.lookup_error = None
		self.lookup_result = None
		self.items = []
		self.searched = []

	def password_lookup_sync (self, schema, attributes, cancellable):
		if self.lookup_error != None:
			raise self.lookup_error
		return self.lookup_result

	def password_store_sync (self, schema, attributes, collection, label,
								password, cancellable):
		self.stored[tuple(sorted(attributes.items()))] = (label, password)
		return True

	def password_clear_sync (self, schema, attributes, cancellable):
		return self.stored.pop(tuple(sorted(attributes.items())), None) != None


class CredentialsTestCase (unittest.TestCase):

	def setUp (self):
		self.secret = FakeSecret()
		# the schema is built once and cached, so it has to be forgotten
		# between tests or the first test's fake schema outlives it
		credentials._schema = None
		self.patch = mock.patch.object(credentials, 'Secret', self.secret)
		self.patch.start()
		self.addCleanup(self.patch.stop)
		self.addCleanup(setattr, credentials, '_schema', None)


class SchemaTest (CredentialsTestCase):

	def test_the_schema_name_is_what_every_stored_password_is_under (self):
		# changing this orphans every password already in every keyring
		self.assertEqual(credentials.SCHEMA_NAME, 'org.pygtk_posting.Secret')
		self.assertEqual(credentials.schema()['name'],
							'org.pygtk_posting.Secret')

	def test_the_attributes_are_exactly_service_host_and_user (self):
		# likewise: an attribute added or renamed stops matching what is there
		self.assertEqual(set(credentials.schema()['attributes']),
							{'service', 'host', 'user'})

	def test_the_schema_name_takes_part_in_matching (self):
		# NONE, not DONT_MATCH_NAME, so these items cannot be confused with
		# anything else in the keyring
		self.assertEqual(credentials.schema()['flags'],
							FakeSecret.SchemaFlags.NONE)

	def test_an_account_is_keyed_on_service_host_and_user (self):
		self.assertEqual(credentials.attributes('imap', 'h', 'u'),
							{'service': 'imap', 'host': 'h', 'user': 'u'})

	def test_an_unknown_service_is_refused (self):
		with self.assertRaises(credentials.CredentialError):
			credentials.attributes('ftp', 'h', 'u')

	def test_postgres_is_a_service_so_this_could_serve_it_later (self):
		# not used yet, and deliberately: the connection password cannot be
		# fetched before it is known which database to dial
		self.assertIn('postgres', credentials.SERVICES)
		credentials.attributes('postgres', 'h', 'u')


class PasswordTest (CredentialsTestCase):

	def test_a_stored_password_comes_back (self):
		self.secret.lookup_result = 'secret'
		self.assertEqual(credentials.password('smtp', 'h', 'u'), 'secret')

	def test_nothing_stored_here_says_which_dialog_to_open (self):
		self.secret.lookup_result = None
		with self.assertRaises(credentials.CredentialError) as caught:
			credentials.password('smtp', 'h', 'u')
		self.assertIn('Set password', str(caught.exception))

	def test_a_keyring_that_will_not_answer_is_reported_not_swallowed (self):
		self.secret.lookup_error = GLib.Error('no can do')
		with self.assertRaises(credentials.CredentialError) as caught:
			credentials.password('smtp', 'h', 'u')
		self.assertIn('no can do', str(caught.exception))

	def test_storing_keeps_it_under_a_label_a_person_can_recognise (self):
		credentials.store_password('smtp', 'mail.example.com', 'silrep', 'pw')
		key = (('host', 'mail.example.com'), ('service', 'smtp'),
				('user', 'silrep'))
		label, password = self.secret.stored[key]
		self.assertEqual(password, 'pw')
		self.assertIn('silrep', label)
		self.assertIn('mail.example.com', label)
		self.assertIn('Posting', label)

	def test_forgetting_says_whether_there_was_one (self):
		credentials.store_password('smtp', 'h', 'u', 'pw')
		self.assertTrue(credentials.clear_password('smtp', 'h', 'u'))
		self.assertFalse(credentials.clear_password('smtp', 'h', 'u'))


class HavePasswordTest (CredentialsTestCase):
	'''have_password is the main-loop-safe question. It must never unlock
	anything, never read a secret and never put up a prompt, because it is
	asked while deciding whether sending is even possible.'''

	def search_sync (self, schema, attributes, flags, cancellable):
		self.flags = flags
		return self.found

	def service (self, found):
		self.found = found
		proxy = mock.Mock()
		proxy.search_sync = self.search_sync
		self.secret.Service = mock.Mock()
		self.secret.Service.get_sync = mock.Mock(return_value = proxy)
		return proxy

	def test_an_item_that_is_there (self):
		self.service([mock.Mock()])
		self.assertTrue(credentials.have_password('smtp', 'h', 'u'))

	def test_nothing_there (self):
		self.service([])
		self.assertFalse(credentials.have_password('smtp', 'h', 'u'))

	def test_it_neither_unlocks_nor_loads_the_secret (self):
		self.service([mock.Mock()])
		credentials.have_password('smtp', 'h', 'u')
		self.assertEqual(self.flags, FakeSecret.SearchFlags.NONE)

	def test_a_blank_host_or_user_is_not_asked_about_at_all (self):
		self.service([mock.Mock()])
		self.assertFalse(credentials.have_password('smtp', '', 'u'))
		self.assertFalse(credentials.have_password('smtp', 'h', ''))
		self.assertFalse(self.secret.Service.get_sync.called)

	def test_a_keyring_that_errors_is_false_rather_than_an_exception (self):
		self.secret.Service = mock.Mock()
		self.secret.Service.get_sync = mock.Mock(
										side_effect = GLib.Error('no bus'))
		self.assertFalse(credentials.have_password('smtp', 'h', 'u'))

	def test_a_locked_item_is_told_apart_from_a_missing_one (self):
		item = mock.Mock()
		item.get_locked = mock.Mock(return_value = True)
		self.service([item])
		self.assertTrue(credentials.have_password('smtp', 'h', 'u'))
		self.assertTrue(credentials.locked('smtp', 'h', 'u'))


class NoLibsecretTest (unittest.TestCase):

	def setUp (self):
		credentials._schema = None
		self.patch = mock.patch.object(credentials, 'Secret', None)
		self.patch.start()
		self.addCleanup(self.patch.stop)
		self.addCleanup(setattr, credentials, '_schema', None)

	def test_a_missing_package_is_named_rather_than_crashing_on_import (self):
		with self.assertRaises(credentials.CredentialError) as caught:
			credentials.password('smtp', 'h', 'u')
		self.assertIn('gir1.2-secret-1', str(caught.exception))

	def test_have_password_is_simply_false (self):
		self.assertFalse(credentials.have_password('smtp', 'h', 'u'))
		self.assertFalse(credentials.locked('smtp', 'h', 'u'))


if __name__ == '__main__':
	unittest.main()
