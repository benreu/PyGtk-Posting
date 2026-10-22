# test_sent_folder.py
#
# Filing a copy of what was sent in the server's Sent folder. Without it a
# message sent from Posting exists nowhere but in the recipient's mailbox: it
# is missing from Sent on the phone, in webmail and in Thunderbird, so what
# was sent to a customer depends on which program sent it.
#
# Nothing here reaches a server: imaplib and smtplib are mocked in every test
# that would connect.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import credentials, emailing
from test_emailing import account


# lines as servers actually send them, IceWarp's shape first
LINES = [br'(\HasNoChildren) "/" "INBOX"',
			br'(\HasNoChildren \Sent) "/" "Sent"',
			br'(\HasChildren \Noselect) "/" "Public Folders"',
			br'(\HasNoChildren \Trash) "/" "Trash"',
			br'(\HasNoChildren) "." "INBOX.Quotes"',
			br'(\HasNoChildren) "/" "Sent Items"']


class ParseListTest (unittest.TestCase):

	def test_a_flagged_folder_is_read_out (self):
		self.assertEqual(emailing.parse_list_line(LINES[1]),
							(['\\HasNoChildren', '\\Sent'], 'Sent'))

	def test_a_name_with_spaces_keeps_them (self):
		self.assertEqual(emailing.parse_list_line(LINES[5])[1], 'Sent Items')

	def test_a_dot_delimiter_namespace_is_read (self):
		self.assertEqual(emailing.parse_list_line(LINES[4])[1], 'INBOX.Quotes')

	def test_an_escaped_quote_in_a_name (self):
		line = b'(\\HasNoChildren) "/" "Bob\\"s mail"'
		self.assertEqual(emailing.parse_list_line(line)[1], 'Bob"s mail')

	def test_an_unquoted_name (self):
		self.assertEqual(emailing.parse_list_line(b'(\\Marked) "/" INBOX')[1],
							'INBOX')

	def test_a_nil_delimiter (self):
		self.assertEqual(emailing.parse_list_line(b'() NIL "Sent"')[1], 'Sent')

	def test_what_is_not_a_listing_line (self):
		for line in (b'', b'* OK something else', b'rubbish'):
			self.assertIsNone(emailing.parse_list_line(line), line)


class LikelySentFolderTest (unittest.TestCase):

	def entries (self, lines = None):
		return [emailing.parse_list_line(line) for line in (lines or LINES)]

	def test_the_folder_the_server_flags_wins (self):
		# believed over any name: it is called different things in different
		# languages and namespaces, and guessing wrong files everything
		# somewhere nobody looks
		self.assertEqual(emailing.likely_sent_folder(self.entries()), 'Sent')

	def test_a_flagged_folder_wins_even_with_an_odd_name (self):
		entries = [(['\\HasNoChildren'], 'Inbox'),
					(['\\Sent'], 'Gesendete Objekte')]
		self.assertEqual(emailing.likely_sent_folder(entries),
							'Gesendete Objekte')

	def test_without_a_flag_the_name_is_used (self):
		entries = [(['\\HasNoChildren'], 'INBOX'),
					(['\\HasNoChildren'], 'Sent Items')]
		self.assertEqual(emailing.likely_sent_folder(entries), 'Sent Items')

	def test_plain_sent_is_preferred_to_the_others (self):
		entries = [([], 'Sent Mail'), ([], 'Sent')]
		self.assertEqual(emailing.likely_sent_folder(entries), 'Sent')

	def test_nothing_obvious_is_not_guessed_at (self):
		entries = [([], 'INBOX'), ([], 'Archive'), ([], 'Work')]
		self.assertEqual(emailing.likely_sent_folder(entries), '')


class AppendUidTest (unittest.TestCase):

	def test_the_pair_is_read_out (self):
		response = [b'[APPENDUID 1759276800 4821] APPEND completed']
		self.assertEqual(emailing.appenduid(response), (1759276800, 4821))

	def test_a_server_that_does_not_say_is_not_a_failure (self):
		# the copy is filed either way; only knowing where is lost
		for response in ([b'APPEND completed'], [], None, [b''], ['text']):
			self.assertIsNone(emailing.appenduid(response), response)


class AppendToSentTest (unittest.TestCase):

	def setUp (self):
		self.imap = mock.patch('imaplib.IMAP4_SSL').start()
		self.mailbox = self.imap.return_value
		self.mailbox.append.return_value = ('OK',
								[b'[APPENDUID 1759276800 4821] APPEND done'])
		self.password = mock.patch.object(credentials, 'password',
											return_value = 'secret').start()
		self.addCleanup(mock.patch.stopall)

	def account (self, **overrides):
		values = {'imap_host': 'imap.example.com', 'imap_user': 'silrep',
					'sent_folder': 'Sent'}
		values.update(overrides)
		return account(**values)

	def message (self):
		return emailing.build(self.account(), ['a@b.com'], 'Invoice 12',
								'body', attachments = [('i.pdf', b'%PDF')])

	def test_the_copy_goes_to_the_chosen_folder (self):
		emailing.append_to_sent(self.account(), self.message())
		folder, flags, date, data = self.mailbox.append.call_args.args
		self.assertEqual(folder, 'Sent')

	def test_it_is_filed_as_already_read (self):
		# nobody needs telling they have unread mail they wrote themselves
		emailing.append_to_sent(self.account(), self.message())
		self.assertIn('Seen', self.mailbox.append.call_args.args[1])

	def test_the_copy_is_the_message_that_went (self):
		import email, email.policy
		message = self.message()
		emailing.append_to_sent(self.account(), message)
		data = self.mailbox.append.call_args.args[3]
		self.assertIn(b'Subject: Invoice 12', data)
		# the same message, not another one built to look like it: the
		# Message-ID is what ties this copy to what the server was handed
		self.assertIn(message['Message-ID'].encode(), data)
		filed = email.message_from_bytes(data, policy = email.policy.default)
		attachments = list(filed.iter_attachments())
		self.assertEqual(len(attachments), 1)
		self.assertEqual(attachments[0].get_filename(), 'i.pdf')
		self.assertEqual(attachments[0].get_payload(decode = True), b'%PDF')

	def test_the_literal_uses_crlf_as_the_protocol_requires (self):
		emailing.append_to_sent(self.account(), self.message())
		data = self.mailbox.append.call_args.args[3]
		self.assertIn(b'\r\n', data)
		self.assertEqual(data.count(b'\n'), data.count(b'\r\n'))

	def test_where_it_was_filed_comes_back (self):
		self.assertEqual(emailing.append_to_sent(self.account(),
							self.message()), (1759276800, 4821))

	def test_the_imap_password_is_the_one_asked_for (self):
		emailing.append_to_sent(self.account(), self.message())
		self.password.assert_called_once_with('imap', 'imap.example.com',
												'silrep')
		self.mailbox.login.assert_called_once_with('silrep', 'secret')

	def test_no_sent_folder_chosen_says_where_to_choose_one (self):
		with self.assertRaises(emailing.MailError) as caught:
			emailing.append_to_sent(self.account(sent_folder = ''),
									self.message())
		self.assertIn('Settings', str(caught.exception))
		self.assertFalse(self.mailbox.append.called)

	def test_no_imap_server_says_so (self):
		with self.assertRaises(emailing.MailError):
			emailing.append_to_sent(self.account(imap_host = ''),
									self.message())

	def test_a_server_that_refuses_the_copy_is_reported (self):
		self.mailbox.append.return_value = ('NO', [b'[TRYCREATE] no mailbox'])
		with self.assertRaises(emailing.MailError) as caught:
			emailing.append_to_sent(self.account(), self.message())
		self.assertIn('Sent', str(caught.exception))

	def test_it_logs_out_even_when_the_append_fails (self):
		self.mailbox.append.side_effect = OSError('dropped')
		with self.assertRaises(Exception):
			emailing.append_to_sent(self.account(), self.message())
		self.assertTrue(self.mailbox.logout.called)


class SendAndFileTest (unittest.TestCase):
	'''Filing is not sending. A copy that did not get filed is worth saying,
	but the message has gone and cannot be unsent.'''

	def setUp (self):
		self.shown = mock.patch.object(emailing, 'show_message').start()
		self.send = mock.patch.object(emailing, 'send').start()
		self.append = mock.patch.object(emailing, 'append_to_sent').start()
		mock.patch.object(credentials, 'password',
							return_value = 'secret').start()
		self.addCleanup(mock.patch.stopall)
		self.done = mock.Mock()

	def run_send (self, acct):
		import threading
		from gi.repository import Gtk
		with mock.patch.object(emailing, 'account', return_value = acct), \
				mock.patch.object(emailing.GLib, 'idle_add') as idle:
			started = emailing.send_and_report(None, ['a@b.com'], 's', 'b',
												on_done = self.done)
			self.assertTrue(started)
			for thread in threading.enumerate():
				if thread is not threading.current_thread():
					thread.join(timeout = 5)
			# the reporting is what idle_add was handed; run it here
			call = idle.call_args
			call.args[0](*call.args[1:])
		return self.shown.call_args.args[2]

	def test_a_sent_message_is_filed (self):
		acct = account(imap_host = 'imap.example.com', sent_folder = 'Sent')
		said = self.run_send(acct)
		self.assertTrue(self.append.called)
		self.assertIn('Sent to', said)
		self.assertNotIn('could not be filed', said)

	def test_a_copy_that_could_not_be_filed_is_still_a_sent_message (self):
		self.append.side_effect = emailing.MailError('no such mailbox')
		acct = account(imap_host = 'imap.example.com', sent_folder = 'Sent')
		said = self.run_send(acct)
		self.assertIn('Sent to', said)
		self.assertIn('could not be filed', said)
		self.assertIn('no such mailbox', said)
		# and it is reported as a send that worked, not one that failed
		self.assertIsNone(self.done.call_args.args[0])

	def test_a_message_that_did_not_go_is_never_filed (self):
		# a copy in Sent of something that was never sent is a record of
		# something that did not happen
		self.send.side_effect = emailing.MailError('refused')
		acct = account(imap_host = 'imap.example.com', sent_folder = 'Sent')
		said = self.run_send(acct)
		self.assertFalse(self.append.called)
		self.assertIn('was not sent', said)

	def test_an_account_with_no_imap_server_files_nothing (self):
		said = self.run_send(account(imap_host = ''))
		self.assertFalse(self.append.called)
		self.assertIn('Sent to', said)


if __name__ == '__main__':
	unittest.main()
