# test_emailing.py
#
# Sending mail from Posting itself. What this replaced handed the job to
# xdg-email or thunderbird -compose and learned nothing back, so these check
# the three things that silently went wrong: the address, the attachment, and
# what happens when there is nothing to send to.
#
# Nothing here may reach a real server. smtplib.SMTP and smtplib.SMTP_SSL are
# mocked in every test that could connect, the same absolute rule test_faxing
# applies to subprocess.run.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import emailing


def account (**overrides):
	acct = emailing.Account()
	acct.id = 1
	acct.name = 'test'
	acct.imap_host = ''
	acct.imap_port = 993
	acct.imap_user = ''
	acct.smtp_host = 'smtp.example.com'
	acct.smtp_port = 587
	acct.smtp_user = 'silrep@example.com'
	acct.smtp_security = 'starttls'
	acct.from_name = 'Silrep'
	acct.from_address = 'silrep@example.com'
	acct.sent_folder = ''
	for name, value in overrides.items():
		setattr(acct, name, value)
	return acct


class AddressTest (unittest.TestCase):

	def test_the_brackets_hold_the_address_and_nothing_else (self):
		# the old code built these by hand as "%s < %s >", and one of the two
		# wrapped the result in shell quotes that never reached a shell
		self.assertEqual(emailing.address('Reuben Rissler', 'a@b.com'),
							'Reuben Rissler <a@b.com>')
		self.assertNotIn('< ', emailing.address('Reuben', 'a@b.com'))
		self.assertNotIn("'", emailing.address('Reuben', 'a@b.com'))

	def test_a_name_with_a_comma_stays_one_recipient (self):
		formed = emailing.address('Rissler, Reuben', 'a@b.com')
		self.assertEqual(formed, '"Rissler, Reuben" <a@b.com>')

	def test_no_name_is_just_the_address (self):
		self.assertEqual(emailing.address('', 'a@b.com'), 'a@b.com')

	def test_surrounding_space_is_dropped (self):
		self.assertEqual(emailing.address('R', '  a@b.com '), 'R <a@b.com>')

	def test_what_is_not_an_address (self):
		# '' is the common one: contacts.email is NOT NULL DEFAULT '', so it
		# is what every contact nobody filled in holds
		for text in ('', None, 'nobody', 'a@', '@b.com', 'a b@c.com',
						'a@b', 'a@@b.com'):
			self.assertFalse(emailing.valid_address(text), repr(text))

	def test_what_is (self):
		for text in ('a@b.com', 'Reuben <a@b.com>', 'first.last@sub.b.co.uk'):
			self.assertTrue(emailing.valid_address(text), repr(text))


class BuildTest (unittest.TestCase):

	def test_the_message_carries_the_account_and_the_recipient (self):
		message = emailing.build(account(),
						[emailing.address('Alvin', 'alvin@example.com')],
						'Invoice 12', 'body')
		self.assertEqual(message['From'], 'Silrep <silrep@example.com>')
		self.assertEqual(message['To'], 'Alvin <alvin@example.com>')
		self.assertEqual(message['Subject'], 'Invoice 12')
		self.assertTrue(message['Message-ID'])
		self.assertEqual(message.get_content_type(), 'text/plain')

	def test_an_attachment_goes_byte_for_byte_under_its_own_name (self):
		pdf = b'%PDF-1.4 not really, but these exact bytes'
		message = emailing.build(account(), ['a@b.com'], 's', 'body',
						attachments = [('Invoice 1234.pdf', pdf)])
		self.assertEqual(message.get_content_maintype(), 'multipart')
		attachments = list(message.iter_attachments())
		self.assertEqual(len(attachments), 1)
		self.assertEqual(attachments[0].get_filename(), 'Invoice 1234.pdf')
		self.assertEqual(attachments[0].get_content_type(), 'application/pdf')
		self.assertEqual(attachments[0].get_payload(decode = True), pdf)

	def test_no_usable_recipient_is_refused_before_connecting (self):
		with mock.patch('smtplib.SMTP') as smtp:
			for recipients in ([], [''], [None], ['nobody']):
				with self.assertRaises(emailing.MailError):
					emailing.build(account(), recipients, 's', 'b')
			self.assertFalse(smtp.called)

	def test_an_account_with_no_from_address_is_refused (self):
		with self.assertRaises(emailing.MailError):
			emailing.build(account(from_address = ''), ['a@b.com'], 's', 'b')

	def test_too_much_is_refused_before_the_upload_not_after (self):
		big = b'0' * (emailing.ATTACHMENT_CAP + 1)
		with mock.patch('smtplib.SMTP') as smtp:
			with self.assertRaises(emailing.MailError) as caught:
				emailing.build(account(), ['a@b.com'], 's', 'b',
								attachments = [('big.pdf', big)])
			self.assertFalse(smtp.called)
		self.assertIn('MB', str(caught.exception))

	def test_several_attachments_all_arrive (self):
		message = emailing.build(account(), ['a@b.com'], 's', 'b',
						attachments = [('one.pdf', b'1'), ('two.txt', b'2')])
		names = [part.get_filename() for part in message.iter_attachments()]
		self.assertEqual(names, ['one.pdf', 'two.txt'])

	def test_an_unknown_extension_still_goes (self):
		message = emailing.build(account(), ['a@b.com'], 's', 'b',
						attachments = [('label.zpl', b'^XA^XZ')])
		part = list(message.iter_attachments())[0]
		self.assertEqual(part.get_content_type(), 'application/octet-stream')
		self.assertEqual(part.get_payload(decode = True), b'^XA^XZ')


class SendTest (unittest.TestCase):

	def message (self):
		return emailing.build(account(), ['a@b.com'], 's', 'b')

	def test_starttls_is_negotiated_and_the_message_handed_over (self):
		with mock.patch('smtplib.SMTP') as smtp:
			emailing.send(account(), 'secret', self.message())
			smtp.assert_called_once_with('smtp.example.com', 587,
											timeout = emailing.NET_TIMEOUT)
			server = smtp.return_value
			self.assertTrue(server.starttls.called)
			server.login.assert_called_once_with('silrep@example.com', 'secret')
			self.assertTrue(server.send_message.called)
			self.assertTrue(server.quit.called)

	def test_implicit_tls_uses_the_ssl_class_and_does_not_starttls (self):
		with mock.patch('smtplib.SMTP_SSL') as smtp:
			emailing.send(account(smtp_security = 'tls', smtp_port = 465),
							'secret', self.message())
			smtp.assert_called_once_with('smtp.example.com', 465,
											timeout = emailing.NET_TIMEOUT)
			self.assertFalse(smtp.return_value.starttls.called)

	def test_a_server_with_no_user_is_not_logged_in_to (self):
		with mock.patch('smtplib.SMTP') as smtp:
			emailing.send(account(smtp_user = '', smtp_security = 'none'),
							'', self.message())
			self.assertFalse(smtp.return_value.login.called)

	def test_an_unreachable_server_is_reported_not_raised_raw (self):
		with mock.patch('smtplib.SMTP', side_effect = OSError('refused')):
			with self.assertRaises(emailing.MailError) as caught:
				emailing.send(account(), 'secret', self.message())
		self.assertIn('refused', str(caught.exception))

	def test_a_refused_password_says_what_the_server_said (self):
		import smtplib
		error = smtplib.SMTPAuthenticationError(535, b'5.7.8 Bad password')
		with mock.patch('smtplib.SMTP') as smtp:
			smtp.return_value.login.side_effect = error
			with self.assertRaises(emailing.MailError) as caught:
				emailing.send(account(), 'wrong', self.message())
		self.assertIn('Bad password', str(caught.exception))

	def test_an_account_with_no_smtp_server_is_refused (self):
		with mock.patch('smtplib.SMTP') as smtp:
			with self.assertRaises(emailing.MailError):
				emailing.send(account(smtp_host = ''), '', self.message())
			self.assertFalse(smtp.called)

	def test_a_rude_hangup_after_the_message_is_not_a_failed_send (self):
		# quit() raising means the server dropped the connection once the
		# message was already accepted; that has not unsent it
		with mock.patch('smtplib.SMTP') as smtp:
			smtp.return_value.quit.side_effect = OSError('hung up')
			emailing.send(account(), 'secret', self.message())


class VerifyLoginTest (unittest.TestCase):

	def test_an_empty_form_is_refused (self):
		with self.assertRaises(emailing.MailError):
			emailing.verify_login(account(smtp_host = '', imap_host = ''), 'x')

	def test_a_good_password_raises_nothing (self):
		with mock.patch('smtplib.SMTP'):
			emailing.verify_login(account(), 'secret')

	def test_a_bad_password_is_reported (self):
		import smtplib
		with mock.patch('smtplib.SMTP') as smtp:
			smtp.return_value.login.side_effect = \
					smtplib.SMTPAuthenticationError(535, b'nope')
			with self.assertRaises(emailing.MailError):
				emailing.verify_login(account(), 'wrong')

	def test_imap_is_checked_too_when_it_is_configured (self):
		with mock.patch('smtplib.SMTP'), \
				mock.patch('imaplib.IMAP4_SSL') as imap:
			emailing.verify_login(account(imap_host = 'imap.example.com',
											imap_user = 'silrep'), 'secret')
			imap.assert_called_once_with('imap.example.com', 993,
											timeout = emailing.NET_TIMEOUT)
			imap.return_value.login.assert_called_once_with('silrep', 'secret')


if __name__ == '__main__':
	unittest.main()


class SendAndReportTest (unittest.TestCase):
	'''The contract the windows depend on: when it returns False nothing was
	sent and on_done has not run, so the caller still owns its window. The
	invoice window hands its destroy in as on_done, and running it on these
	paths as well would destroy the window twice.'''

	def setUp (self):
		self.shown = mock.patch.object(emailing, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		self.done = mock.Mock()

	def test_no_account_set_up_says_so_and_leaves_the_window_alone (self):
		with mock.patch.object(emailing, 'account', return_value = None):
			started = emailing.send_and_report(None, ['a@b.com'], 's', 'b',
												on_done = self.done)
		self.assertFalse(started)
		self.assertFalse(self.done.called)
		self.assertIn('No mail account', self.shown.call_args.args[2])

	def test_an_unsendable_message_says_so_and_leaves_the_window_alone (self):
		with mock.patch.object(emailing, 'account', return_value = account()):
			started = emailing.send_and_report(None, [''], 's', 'b',
												on_done = self.done)
		self.assertFalse(started)
		self.assertFalse(self.done.called)
		self.assertTrue(self.shown.called)
