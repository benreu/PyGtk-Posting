# test_mail_accounts.py
#
# The Mail accounts page in Settings. The account - host, port, user, from
# address - is in the database; the password is not, it is in the
# workstation's login keyring through credentials.py, so that a backup, a
# restore copy or the SQL window cannot leak it.
#
# Nothing here reaches a server or the real keyring: emailing.verify_login and
# the credentials functions are mocked in every test that would.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import credentials, emailing
from gi.repository import Gtk


class MailAccountTest (harness.DBTestCase):

	FORM = {'mail_account_name_entry': 'Silrep',
			'mail_account_from_name_entry': 'Silrep Inc',
			'mail_account_from_address_entry': 'silrep@emypeople.net',
			'mail_account_smtp_host_entry': 'smtp.emypeople.net',
			'mail_account_smtp_user_entry': 'silrep@emypeople.net',
			'mail_account_imap_host_entry': 'imap.emypeople.net',
			'mail_account_imap_user_entry': 'silrep@emypeople.net'}

	def setUp (self):
		super().setUp()
		# the user works in this copy and has set their own account up in it,
		# so the table is not empty; cleared inside the test transaction,
		# which is rolled back, so their row is still there afterwards
		self.cursor.execute("DELETE FROM settings.mail_accounts")
		self.message = mock.patch.object(Gtk.MessageDialog, 'run',
											return_value = None).start()
		self.verify = mock.patch.object(emailing, 'verify_login').start()
		self.store = mock.patch.object(credentials, 'store_password').start()
		self.clear = mock.patch.object(credentials, 'clear_password',
										return_value = True).start()
		self.have = mock.patch.object(credentials, 'have_password',
										return_value = False).start()
		mock.patch.object(credentials, 'locked', return_value = False).start()
		self.addCleanup(mock.patch.stopall)
		import settings
		self.gui = settings.GUI()
		self.shown = mock.patch.object(self.gui, 'show_message').start()

	def fill (self, **overrides):
		values = dict(self.FORM)
		values.update(overrides)
		for widget, text in values.items():
			self.gui.builder.get_object(widget).set_text(text)
		self.gui.builder.get_object(
						'mail_account_security_combo').set_active_id('starttls')

	def accounts (self):
		self.cursor.execute("SELECT id, name, from_address, smtp_host, active "
							"FROM settings.mail_accounts ORDER BY id")
		return self.cursor.fetchall()

	def status (self):
		return self.gui.builder.get_object(
								'mail_account_status_label').get_text()


class FormTest (MailAccountTest):

	def test_a_named_account_with_a_server_saves (self):
		self.fill()
		self.gui.mail_account_save_clicked(None)
		rows = self.accounts()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][1:], ('Silrep', 'silrep@emypeople.net',
										'smtp.emypeople.net', True))
		self.assertFalse(self.shown.called)

	def test_a_named_server_is_accepted_where_the_zebra_page_wants_an_ip (self):
		# settings.zebra_printers.host is inet and its form validates with
		# ipaddress.ip_address; copying that here would refuse every real mail
		# server, so this is the test that it was not copied
		self.fill(mail_account_smtp_host_entry = 'smtp.emypeople.net')
		self.assertIsNotNone(self.gui.mail_account_form())

	def test_an_account_needs_a_name (self):
		self.fill(mail_account_name_entry = '')
		self.assertIsNone(self.gui.mail_account_form())
		self.assertIn('name', self.shown.call_args.args[0])

	def test_an_account_needs_an_address_to_send_from (self):
		for bad in ('', 'nobody', 'silrep@'):
			self.shown.reset_mock()
			self.fill(mail_account_from_address_entry = bad)
			self.assertIsNone(self.gui.mail_account_form(), bad)
			self.assertTrue(self.shown.called, bad)

	def test_an_account_needs_a_server_to_send_through (self):
		self.fill(mail_account_smtp_host_entry = '')
		self.assertIsNone(self.gui.mail_account_form())
		self.assertIn('SMTP', self.shown.call_args.args[0])

	def test_a_refused_form_writes_nothing (self):
		self.fill(mail_account_name_entry = '')
		self.gui.mail_account_save_clicked(None)
		self.assertEqual(self.accounts(), [])

	def test_the_form_carries_no_password_anywhere (self):
		# the whole point: an account is host, port and user, and the secret
		# is somewhere this database cannot reach
		self.fill()
		acct = self.gui.mail_account_form()
		self.assertFalse(any('password' in name for name in vars(acct)))
		self.cursor.execute("SELECT column_name FROM information_schema.columns "
							"WHERE (table_schema, table_name) = "
							"('settings', 'mail_accounts')")
		columns = [row[0] for row in self.cursor.fetchall()]
		self.assertFalse([c for c in columns if 'password' in c], columns)


class OneInUseTest (MailAccountTest):

	def test_saving_a_second_account_stands_the_first_one_down (self):
		self.fill()
		self.gui.mail_account_save_clicked(None)
		self.gui.mail_account_new_clicked(None)
		self.fill(mail_account_name_entry = 'Second',
					mail_account_from_address_entry = 'other@emypeople.net')
		self.gui.mail_account_save_clicked(None)
		rows = self.accounts()
		self.assertEqual(len(rows), 2)
		self.assertEqual([row[4] for row in rows], [False, True])

	def test_only_ever_one_is_in_use (self):
		# the unique index is the backstop; this is what keeps it from firing
		self.fill()
		self.gui.mail_account_save_clicked(None)
		self.gui.mail_account_new_clicked(None)
		self.fill(mail_account_name_entry = 'Second')
		self.gui.mail_account_save_clicked(None)
		self.cursor.execute("SELECT count(*) FROM settings.mail_accounts "
							"WHERE active")
		self.assertEqual(self.cursor.fetchone()[0], 1)

	def test_the_active_account_is_what_emailing_sends_from (self):
		self.fill()
		self.gui.mail_account_save_clicked(None)
		acct = emailing.account()
		self.assertEqual(acct.from_address, 'silrep@emypeople.net')
		self.assertEqual(acct.smtp_host, 'smtp.emypeople.net')
		self.assertEqual(acct.smtp_security, 'starttls')

	def test_no_account_at_all_is_said_rather_than_guessed (self):
		self.assertIsNone(emailing.account())


class SelectAndDeleteTest (MailAccountTest):

	def saved (self):
		self.fill()
		self.gui.mail_account_save_clicked(None)
		return self.gui.mail_account_id

	def test_selecting_an_account_fills_the_form (self):
		account_id = self.saved()
		self.gui.mail_account_new_clicked(None)
		self.assertEqual(
			self.gui.builder.get_object('mail_account_name_entry').get_text(), '')
		selection = self.gui.builder.get_object('mail_account_selection')
		store = self.gui.builder.get_object('mail_account_store')
		selection.select_iter(store.get_iter_first())
		self.assertEqual(self.gui.mail_account_id, account_id)
		self.assertEqual(
			self.gui.builder.get_object('mail_account_name_entry').get_text(),
			'Silrep')
		self.assertEqual(self.gui.builder.get_object(
			'mail_account_imap_host_entry').get_text(), 'imap.emypeople.net')
		self.assertEqual(self.gui.builder.get_object(
			'mail_account_security_combo').get_active_id(), 'starttls')

	def test_deleting_removes_the_account (self):
		self.saved()
		self.gui.mail_account_delete_clicked(None)
		self.assertEqual(self.accounts(), [])

	def test_deleting_leaves_the_keyring_alone_and_says_so (self):
		# the same mailbox may be configured in another database from this
		# workstation, so the secret is not collateral of deleting a row
		self.saved()
		self.gui.mail_account_delete_clicked(None)
		self.assertFalse(self.clear.called)
		self.assertIn('keyring', self.status())

	def test_changing_the_user_warns_that_the_password_is_orphaned (self):
		# secrets are keyed on user and host, so the old one is still there
		# under a key nothing will look for again
		self.saved()
		self.have.return_value = True
		self.fill(mail_account_smtp_user_entry = 'someone.else@emypeople.net')
		self.gui.mail_account_save_clicked(None)
		self.assertIn('Set password', self.status())

	def test_leaving_the_user_alone_warns_about_nothing (self):
		self.saved()
		self.have.return_value = True
		self.fill()
		self.gui.mail_account_save_clicked(None)
		self.assertNotIn('Set password', self.status())


class PasswordTest (MailAccountTest):

	def test_a_password_is_checked_against_the_server_before_being_kept (self):
		self.fill()
		acct = self.gui.mail_account_form()
		self.gui.store_checked_password(acct, 'secret')
		self.verify.assert_called_once_with(acct, 'secret')
		self.assertEqual(self.store.call_count, 2) # smtp and imap
		self.store.assert_any_call('smtp', 'smtp.emypeople.net',
									'silrep@emypeople.net', 'secret')
		self.store.assert_any_call('imap', 'imap.emypeople.net',
									'silrep@emypeople.net', 'secret')

	def test_a_password_the_server_refuses_is_never_written (self):
		self.verify.side_effect = emailing.MailError('bad password')
		self.fill()
		acct = self.gui.mail_account_form()
		with self.assertRaises(emailing.MailError):
			self.gui.store_checked_password(acct, 'wrong')
		self.assertFalse(self.store.called)

	def test_an_smtp_only_account_stores_one_secret (self):
		self.fill(mail_account_imap_host_entry = '',
					mail_account_imap_user_entry = '')
		acct = self.gui.mail_account_form()
		self.gui.store_checked_password(acct, 'secret')
		self.store.assert_called_once_with('smtp', 'smtp.emypeople.net',
										'silrep@emypeople.net', 'secret')

	def test_logging_in_uses_the_password_this_workstation_has (self):
		self.fill()
		acct = self.gui.mail_account_form()
		with mock.patch.object(credentials, 'password',
								return_value = 'stored') as lookup:
			self.gui.check_login(acct)
		lookup.assert_called_once_with('smtp', 'smtp.emypeople.net',
										'silrep@emypeople.net')
		self.verify.assert_called_once_with(acct, 'stored')

	def test_forgetting_says_what_was_forgotten (self):
		self.fill()
		self.gui.mail_account_forget_clicked(None)
		self.assertIn('SMTP', self.status())
		self.assertIn('IMAP', self.status())

	def test_no_user_means_no_password_to_set (self):
		self.fill(mail_account_smtp_user_entry = '',
					mail_account_imap_user_entry = '')
		with mock.patch.object(emailing, 'PasswordDialog') as dialog:
			self.gui.mail_account_password_clicked(None)
		self.assertFalse(dialog.called)
		self.assertTrue(self.shown.called)

	def test_nothing_saved_here_says_which_button_to_press (self):
		self.fill()
		self.gui.update_mail_account_status()
		self.assertIn('Set password', self.status())

	def test_a_locked_keyring_is_told_apart_from_a_missing_password (self):
		self.fill()
		self.have.return_value = True
		with mock.patch.object(credentials, 'locked', return_value = True):
			self.gui.update_mail_account_status()
		self.assertIn('locked', self.status())


if __name__ == '__main__':
	unittest.main()


class FailedCheckTest (MailAccountTest):
	'''What happens when Set password cannot confirm the password.

	The first version stored nothing whenever the check failed, for any
	reason, and said only what the server had said. The user was then left
	with no password saved, no sign that that was the outcome, and a second
	unrelated-looking complaint from Test about no password being saved.'''

	def setUp (self):
		super().setUp()
		self.fill()
		self.acct = self.gui.mail_account_form()

	def failed (self, error):
		return self.gui.password_check_failed(self.acct, 'secret', error)

	def answer (self, response):
		return mock.patch.object(Gtk.MessageDialog, 'run',
									return_value = response)

	def test_a_refused_login_is_never_stored (self):
		handled = self.failed(emailing.MailAuthError('535 bad password'))
		self.assertTrue(handled)
		self.assertFalse(self.store.called)

	def test_a_refused_login_says_nothing_was_saved (self):
		# the whole point: the outcome has to be visible here, not inferred
		# from a different error the next time something is pressed
		self.failed(emailing.MailAuthError('535 bad password'))
		said = self.shown.call_args.args[0]
		self.assertIn('Nothing was saved', said)
		self.assertIn('535 bad password', said)

	def test_a_refused_login_suggests_the_whole_address_as_the_user_name (self):
		self.failed(emailing.MailAuthError('535 bad password'))
		self.assertIn('whole email address', self.shown.call_args.args[0])

	def test_a_server_that_could_not_be_reached_offers_to_save_anyway (self):
		# otherwise somebody whose server is down can never set a password
		with self.answer(Gtk.ResponseType.YES):
			self.failed(emailing.MailError('connection refused'))
		self.assertTrue(self.store.called)
		self.store.assert_any_call('smtp', 'smtp.emypeople.net',
									'silrep@emypeople.net', 'secret')

	def test_declining_that_offer_stores_nothing (self):
		with self.answer(Gtk.ResponseType.NO):
			self.failed(emailing.MailError('connection refused'))
		self.assertFalse(self.store.called)

	def test_an_untested_password_is_saved_as_untested (self):
		message = self.gui.store_unchecked_password(self.acct, 'secret')
		self.assertIn('untested', message)
		self.assertTrue(self.store.called)

	def test_after_a_failure_the_status_says_there_is_no_password (self):
		# run the real reporting path, not just the handler
		self.verify.side_effect = emailing.MailAuthError('nope')
		with mock.patch.object(self.gui, 'password_check_failed',
								return_value = True):
			self.gui.run_mail_account_check(self.acct,
					lambda: self.gui.store_checked_password(self.acct, 'x'),
					'busy', on_error = self.gui.password_check_failed)
			self.settle()
		self.assertIn('No password is saved', self.status())

	def test_a_success_keeps_its_own_wording (self):
		self.gui.run_mail_account_check(self.acct,
				lambda: self.gui.store_checked_password(self.acct, 'secret'),
				'busy')
		self.settle()
		self.assertEqual(self.status(),
						'The password works and is saved on this computer.')

	def settle (self):
		while Gtk.events_pending():
			Gtk.main_iteration()


class AuthErrorTest (unittest.TestCase):
	'''verify_login has to tell a server that said no apart from a server it
	never reached, because only the first proves the password is wrong.'''

	def account (self):
		import test_emailing
		return test_emailing.account()

	def test_a_refused_password_is_an_auth_error (self):
		import smtplib
		with mock.patch('smtplib.SMTP') as smtp:
			smtp.return_value.login.side_effect = \
					smtplib.SMTPAuthenticationError(535, b'nope')
			with self.assertRaises(emailing.MailAuthError):
				emailing.verify_login(self.account(), 'wrong')

	def test_an_unreachable_server_is_not (self):
		with mock.patch('smtplib.SMTP', side_effect = OSError('refused')):
			with self.assertRaises(emailing.MailError) as caught:
				emailing.verify_login(self.account(), 'secret')
		self.assertNotIsInstance(caught.exception, emailing.MailAuthError)

	def test_tls_trouble_mid_session_is_not_either (self):
		import ssl
		with mock.patch('smtplib.SMTP') as smtp:
			smtp.return_value.starttls.side_effect = ssl.SSLError('handshake')
			with self.assertRaises(emailing.MailError) as caught:
				emailing.verify_login(self.account(), 'secret')
		self.assertNotIsInstance(caught.exception, emailing.MailAuthError)
		self.assertIn('could not be asked', str(caught.exception))

	def test_an_imap_server_that_says_no_is_an_auth_error (self):
		import imaplib
		acct = self.account()
		acct.imap_host, acct.imap_user = 'imap.example.com', 'silrep'
		with mock.patch('smtplib.SMTP'), \
				mock.patch('imaplib.IMAP4_SSL') as imap:
			imap.return_value.login.side_effect = \
					imaplib.IMAP4.error('AUTHENTICATIONFAILED')
			with self.assertRaises(emailing.MailAuthError):
				emailing.verify_login(acct, 'wrong')


class SecurityAndPortTest (MailAccountTest):
	'''465 is implicit TLS and 587 is STARTTLS. Crossed over, the connection
	dies in the TLS handshake with "wrong version number", which names neither
	setting - and then the password cannot even be tested, let alone saved.'''

	def port (self):
		return self.gui.builder.get_object(
						'mail_account_smtp_port_spinbutton').get_value_as_int()

	def choose (self, security):
		self.gui.builder.get_object(
						'mail_account_security_combo').set_active_id(security)

	def test_choosing_tls_moves_the_port_to_465 (self):
		self.fill()
		self.choose('tls')
		self.assertEqual(self.port(), 465)

	def test_choosing_starttls_moves_it_back_to_587 (self):
		self.fill()
		self.choose('tls')
		self.choose('starttls')
		self.assertEqual(self.port(), 587)

	def test_a_port_somebody_typed_is_left_alone (self):
		self.fill()
		self.gui.builder.get_object(
						'mail_account_smtp_port_spinbutton').set_value(2525)
		self.choose('tls')
		self.assertEqual(self.port(), 2525)

	def test_loading_an_account_keeps_the_port_it_was_saved_with (self):
		# the combo follows the port around, so filling the form from a row
		# must not count as a choice - otherwise opening an account silently
		# rewrites it
		self.fill()
		self.gui.builder.get_object(
						'mail_account_smtp_port_spinbutton').set_value(465)
		self.choose('tls')
		self.gui.mail_account_save_clicked(None)
		account_id = self.gui.mail_account_id
		self.gui.mail_account_new_clicked(None)
		selection = self.gui.builder.get_object('mail_account_selection')
		store = self.gui.builder.get_object('mail_account_store')
		selection.select_iter(store.get_iter_first())
		self.assertEqual(self.gui.mail_account_id, account_id)
		self.assertEqual(self.port(), 465)
		self.assertEqual(self.gui.builder.get_object(
					'mail_account_security_combo').get_active_id(), 'tls')

	def test_a_crossed_over_pair_is_named_in_a_connection_failure (self):
		# this is the combination that actually happened: TLS on 587
		self.fill()
		self.gui.builder.get_object(
						'mail_account_security_combo').set_active_id('tls')
		self.gui.builder.get_object(
						'mail_account_smtp_port_spinbutton').set_value(587)
		acct = self.gui.mail_account_form()
		hint = self.gui.security_mismatch_hint(acct)
		self.assertIn('587', hint)
		self.assertIn('STARTTLS', hint)

	def test_a_matching_pair_adds_no_hint (self):
		self.fill()
		acct = self.gui.mail_account_form()
		self.assertEqual(self.gui.security_mismatch_hint(acct), '')

	def test_an_unusual_port_adds_no_hint_either (self):
		self.fill()
		self.gui.builder.get_object(
						'mail_account_smtp_port_spinbutton').set_value(2525)
		acct = self.gui.mail_account_form()
		self.assertEqual(self.gui.security_mismatch_hint(acct), '')
