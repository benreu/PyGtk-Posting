# test_mail_record.py
#
# The row written for every message Posting sends. Until there was one, the
# only trace of a sent invoice was the copy in the server's Sent folder, which
# nobody else in the company can see and nothing in Posting can show.
#
# What is checked hardest here is that the row is only ever written for a
# message that actually went, and that failing to write it is reported without
# turning a sent message into a failed one. The message cannot be unsent by
# then, so saying it failed would be the same lie the old xdg-email path told,
# in the other direction.
#
# Nothing here reaches a server: send and append_to_sent are mocked in every
# test that would connect.

import os, sys, threading, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
import mail_schema
from mail_schema import MailTestCase
import credentials, emailing
from test_emailing import account


class RecordTest (MailTestCase):

	def setUp (self):
		MailTestCase.setUp(self)
		# the user's own account is active; this one is not, so the one active
		# partial unique index is left alone
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active, from_name, from_address, "
							"imap_host, sent_folder) "
							"VALUES ('test', False, 'Silrep', "
							"'silrep@example.com', 'imap.example.com', 'Sent') "
							"RETURNING id")
		self.account_id = self.cursor.fetchone()[0]
		self.acct = account(id = self.account_id,
							imap_host = 'imap.example.com',
							sent_folder = 'Sent')

	def message (self, **kwargs):
		fields = dict(to = [emailing.address('Bob Smith', 'bob@example.com')],
						subject = 'Invoice 1234', body = 'Hi Bob,\n\nthanks.')
		fields.update(kwargs)
		return emailing.build(self.acct, fields['to'], fields['subject'],
								fields['body'],
								attachments = fields.get('attachments', ()),
								cc = fields.get('cc', ()))

	def row (self, row_id):
		self.cursor.execute("SELECT message_id, account_id, folder, uid, "
								"uidvalidity, date_sent, subject, "
								"from_address, from_name, to_addresses, "
								"cc_addresses, outgoing, has_attachments, "
								"raw_message, body_text "
							"FROM mail_messages WHERE id = %s", (row_id,))
		names = ('message_id account_id folder uid uidvalidity date_sent '
					'subject from_address from_name to_addresses '
					'cc_addresses outgoing has_attachments raw_message '
					'body_text').split()
		return dict(zip(names, self.cursor.fetchone()))

	def test_what_was_sent_is_what_the_row_says (self):
		message = self.message()
		row_id = emailing.record(self.acct, message, 'Hi Bob,\n\nthanks.',
									'Sent', (12, 907))
		row = self.row(row_id)
		self.assertEqual(row['account_id'], self.account_id)
		self.assertEqual(row['subject'], 'Invoice 1234')
		self.assertEqual(row['to_addresses'], 'Bob Smith <bob@example.com>')
		self.assertEqual(row['from_address'], 'silrep@example.com')
		self.assertEqual(row['from_name'], 'Silrep')
		self.assertEqual(row['body_text'], 'Hi Bob,\n\nthanks.')
		self.assertTrue(row['outgoing'])

	def test_the_row_can_be_found_from_the_message_id (self):
		# what ties the row to the copy the server files in Sent, and to the
		# copy that comes back through the sync
		message = self.message()
		row_id = emailing.record(self.acct, message, 'b', 'Sent', (12, 907))
		self.assertEqual(self.row(row_id)['message_id'],
							str(message['Message-ID']))
		self.assertNotEqual(self.row(row_id)['message_id'], '')

	def test_where_the_server_filed_the_copy_is_kept (self):
		row_id = emailing.record(self.acct, self.message(), 'b', 'Sent',
									(12, 907))
		row = self.row(row_id)
		self.assertEqual((row['folder'], row['uidvalidity'], row['uid']),
							('Sent', 12, 907))

	def test_a_copy_filed_under_an_unknown_uid_still_names_the_folder (self):
		# a server without UIDPLUS appends the copy and does not say where;
		# the copy is there, only its uid is unknown
		row_id = emailing.record(self.acct, self.message(), 'b', 'Sent', None)
		row = self.row(row_id)
		self.assertEqual(row['folder'], 'Sent')
		self.assertIsNone(row['uid'])
		self.assertIsNone(row['uidvalidity'])

	def test_no_server_copy_leaves_the_folder_empty (self):
		row_id = emailing.record(self.acct, self.message(), 'b')
		row = self.row(row_id)
		self.assertEqual(row['folder'], '')
		self.assertIsNone(row['uid'])

	def test_two_messages_with_no_server_copy_are_two_rows (self):
		# the uid index is partial for this reason: NULLs are distinct to a
		# plain unique index, so it would claim to prevent duplicates while
		# admitting these
		first = emailing.record(self.acct, self.message(), 'b')
		second = emailing.record(self.acct, self.message(), 'b')
		self.assertNotEqual(first, second)

	def test_the_same_server_copy_is_not_recorded_twice (self):
		emailing.record(self.acct, self.message(), 'b', 'Sent', (12, 907))
		with self.assertRaises(emailing.MailError):
			emailing.record(self.acct, self.message(), 'b', 'Sent', (12, 907))

	def test_the_connection_is_usable_after_a_refused_row (self):
		# an uncommitted failed statement makes every later one in the
		# transaction fail too, and the rest of the program is still in it
		emailing.record(self.acct, self.message(), 'b', 'Sent', (12, 907))
		with self.assertRaises(emailing.MailError):
			emailing.record(self.acct, self.message(), 'b', 'Sent', (12, 907))
		cursor = self.DB.cursor()
		cursor.execute("SELECT 1")
		self.assertEqual(cursor.fetchone()[0], 1)
		cursor.close()

	def test_an_attachment_is_noted_without_being_stored (self):
		# the document that went out is already in invoices.pdf_data on the
		# record the message is about, and the server's copy holds the message
		# itself; a second copy of every attachment here would put the whole
		# mailbox in Postgres and in every pg_dump of it
		message = self.message(attachments = [('Invoice 1234.pdf', b'%PDF-x')])
		row = self.row(emailing.record(self.acct, message, 'b'))
		self.assertTrue(row['has_attachments'])
		self.assertIsNone(row['raw_message'])

	def test_a_message_with_nothing_attached_says_so (self):
		row = self.row(emailing.record(self.acct, self.message(), 'b'))
		self.assertFalse(row['has_attachments'])

	def test_everyone_it_went_to_is_in_the_row (self):
		message = self.message(to = [emailing.address('Bob', 'bob@a.com'),
										emailing.address('', 'sue@a.com')],
								cc = [emailing.address('Acc', 'acc@a.com')])
		row = self.row(emailing.record(self.acct, message, 'b'))
		self.assertIn('bob@a.com', row['to_addresses'])
		self.assertIn('sue@a.com', row['to_addresses'])
		self.assertEqual(row['cc_addresses'], 'Acc <acc@a.com>')

	def test_a_name_with_a_comma_in_it_is_still_one_recipient (self):
		message = self.message(to = [emailing.address('Rissler, Reuben',
														'r@a.com')])
		row = self.row(emailing.record(self.acct, message, 'b'))
		self.assertEqual(row['to_addresses'], '"Rissler, Reuben" <r@a.com>')

	def test_when_it_was_sent_is_what_the_message_says (self):
		# the row, the copy in Sent and what the recipient sees all have to
		# agree, or the two copies cannot be matched up later
		message = self.message()
		row = self.row(emailing.record(self.acct, message, 'b'))
		self.assertEqual(row['date_sent'], emailing.sent_date(message))
		self.assertIsNotNone(row['date_sent'])

	def test_the_row_survives_the_account_being_deleted (self):
		# the correspondence is the point of the table and outlives the
		# account it was sent through
		row_id = emailing.record(self.acct, self.message(), 'b', 'Sent',
									(12, 907))
		self.cursor.execute("DELETE FROM settings.mail_accounts WHERE id = %s",
							(self.account_id,))
		row = self.row(row_id)
		self.assertIsNone(row['account_id'])
		self.assertEqual(row['subject'], 'Invoice 1234')


class ShippedSchemaTest (MailTestCase):
	'''The table is defined in two places that must not drift: the --0.7.37
	block, which is what an upgraded database gets, and mail_schema's copy,
	which is what every test in this folder runs against. A suite testing a
	different table from the one that ships tests nothing.

	This runs the shipped SQL rather than a copy of it.'''

	def block (self):
		"the --0.7.37 block out of the migration, as it will really be run"
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'db', 'update_db_minor.sql')
		with open(path) as sql_file:
			sql = sql_file.read()
		start = sql.index('--0.7.37')
		rest = sql.find('\n--0.7.', start + 1)
		return sql[start:] if rest == -1 else sql[start:rest]

	def shape (self, sql):
		self.cursor.execute("DROP TABLE IF EXISTS public.mail_messages")
		self.cursor.execute(sql)
		self.DB.commit()
		self.cursor.execute("SELECT column_name, data_type, is_nullable, "
								"column_default "
							"FROM information_schema.columns "
							"WHERE (table_schema, table_name) = "
								"('public', 'mail_messages') "
							"ORDER BY ordinal_position")
		columns = self.cursor.fetchall()
		self.cursor.execute("SELECT indexdef FROM pg_indexes "
							"WHERE (schemaname, tablename) = "
								"('public', 'mail_messages') "
							"ORDER BY indexname")
		return columns, self.cursor.fetchall()

	def test_the_suite_is_run_against_the_table_that_ships (self):
		shipped = self.shape(self.block())
		tested = self.shape(mail_schema.PENDING_MAIL_RECORD_SCHEMA)
		self.assertEqual(tested[0], shipped[0])
		self.assertEqual(tested[1], shipped[1])

	def test_an_upgrade_leaves_a_table_that_is_already_there_alone (self):
		# this file re-runs from the top on every upgrade, so every statement
		# in it has to be a no-op the second time
		self.shape(self.block())
		self.cursor.execute("INSERT INTO mail_messages (subject) "
							"VALUES ('kept') RETURNING id")
		row_id = self.cursor.fetchone()[0]
		self.cursor.execute(self.block())
		self.DB.commit()
		self.cursor.execute("SELECT subject FROM mail_messages WHERE id = %s",
							(row_id,))
		self.assertEqual(self.cursor.fetchone()[0], 'kept')

	def test_the_server_copy_index_is_the_one_the_sync_needs (self):
		# partial on uid, or the sync cannot insert a slice with ON CONFLICT
		# DO NOTHING and locally composed messages collide with each other
		self.shape(self.block())
		self.cursor.execute("SELECT indexdef FROM pg_indexes WHERE "
							"indexname = 'mail_messages_server_copy'")
		definition = self.cursor.fetchone()[0]
		self.assertIn('UNIQUE', definition)
		self.assertIn('WHERE (uid IS NOT NULL)', definition)
		for column in ('account_id', 'folder', 'uidvalidity', 'uid'):
			self.assertIn(column, definition)

	def test_a_message_id_is_not_unique (self):
		# the same message legitimately sits in INBOX and in Sent at once, so
		# a unique index would abort the sync transaction on every pass
		self.shape(self.block())
		for _ in range(2):
			self.cursor.execute("INSERT INTO mail_messages (message_id) "
								"VALUES ('<a@b>')")
		self.cursor.execute("SELECT count(*) FROM mail_messages "
							"WHERE message_id = '<a@b>'")
		self.assertEqual(self.cursor.fetchone()[0], 2)

	def test_nothing_notifies_per_row (self):
		# the initial sync inserts around 12,000 rows, and a trigger firing
		# per row with a distinct payload is 12,000 notifies Postgres cannot
		# collapse, which floods process_notifies
		self.shape(self.block())
		self.cursor.execute("SELECT count(*) FROM pg_trigger t "
							"JOIN pg_class c ON c.oid = t.tgrelid "
							"WHERE c.relname = 'mail_messages' "
								"AND NOT t.tgisinternal")
		self.assertEqual(self.cursor.fetchone()[0], 0)


class SentDateTest (unittest.TestCase):

	def test_a_built_message_carries_a_date (self):
		# nothing else sets one. A message with no Date is malformed, sorts
		# wrongly in Sent, and leaves the row with nothing to say when it went
		message = emailing.build(account(), ['a@b.com'], 's', 'b')
		self.assertIsNotNone(message['Date'])
		self.assertIsNotNone(emailing.sent_date(message))

	def test_a_message_with_no_date_is_not_an_error (self):
		message = emailing.build(account(), ['a@b.com'], 's', 'b')
		del message['Date']
		self.assertIsNone(emailing.sent_date(message))

	def test_an_unreadable_date_is_not_an_error (self):
		message = emailing.build(account(), ['a@b.com'], 's', 'b')
		del message['Date']
		message['Date'] = 'whenever'
		self.assertIsNone(emailing.sent_date(message))


class HasAttachmentsTest (unittest.TestCase):

	def test_the_body_on_its_own_is_not_an_attachment (self):
		self.assertFalse(emailing.has_attachments(
							emailing.build(account(), ['a@b.com'], 's', 'b')))

	def test_a_file_is (self):
		message = emailing.build(account(), ['a@b.com'], 's', 'b',
									attachments = [('a.pdf', b'%PDF-x')])
		self.assertTrue(emailing.has_attachments(message))


class SendAndRecordTest (unittest.TestCase):
	'''Where the row is written from. It is the main thread's work, out of the
	idle callback: the sending thread touches no database connection at all,
	because one that touches the shared connection segfaults the application
	rather than raising.'''

	def setUp (self):
		self.shown = mock.patch.object(emailing, 'show_message').start()
		self.send = mock.patch.object(emailing, 'send').start()
		self.append = mock.patch.object(emailing, 'append_to_sent',
										return_value = (12, 907)).start()
		self.record = mock.patch.object(emailing, 'record').start()
		mock.patch.object(credentials, 'password',
							return_value = 'secret').start()
		self.addCleanup(mock.patch.stopall)
		self.done = mock.Mock()

	def run_send (self, acct, body = 'b'):
		with mock.patch.object(emailing, 'account', return_value = acct), \
				mock.patch.object(emailing.GLib, 'idle_add') as idle:
			self.assertTrue(emailing.send_and_report(None, ['a@b.com'], 's',
										body, on_done = self.done))
			for thread in threading.enumerate():
				if thread is not threading.current_thread():
					thread.join(timeout = 5)
			call = idle.call_args
			# whatever the thread handed idle_add is the reporting; run it here
			# on this thread, which is where it would run
			call.args[0](*call.args[1:])
		return self.shown.call_args.args[2]

	def test_a_sent_message_is_recorded (self):
		self.run_send(account(imap_host = 'imap.example.com',
								sent_folder = 'Sent'))
		self.assertTrue(self.record.called)

	def test_the_row_is_told_where_the_copy_was_filed (self):
		acct = account(imap_host = 'imap.example.com', sent_folder = 'Sent')
		self.run_send(acct)
		args = self.record.call_args.args
		self.assertEqual(args[3], 'Sent')
		self.assertEqual(args[4], (12, 907))

	def test_what_was_typed_is_what_is_recorded (self):
		self.run_send(account(), body = 'Hi Bob,\n\nthanks.')
		self.assertEqual(self.record.call_args.args[2], 'Hi Bob,\n\nthanks.')

	def test_a_message_that_did_not_go_is_never_recorded (self):
		# the row says a message went out. One for a failed send would make
		# this table a record of things that did not happen, which is the
		# fault the whole of this work exists to fix
		self.send.side_effect = emailing.MailError('refused')
		said = self.run_send(account())
		self.assertFalse(self.record.called)
		self.assertIn('was not sent', said)

	def test_a_copy_that_was_not_filed_is_recorded_with_no_folder (self):
		self.append.side_effect = emailing.MailError('no such mailbox')
		acct = account(imap_host = 'imap.example.com', sent_folder = 'Sent')
		self.run_send(acct)
		self.assertTrue(self.record.called)
		self.assertEqual(self.record.call_args.args[3], '')
		self.assertIsNone(self.record.call_args.args[4])

	def test_a_row_that_could_not_be_written_is_said_and_not_a_failed_send (self):
		self.record.side_effect = emailing.MailError('out of disk')
		said = self.run_send(account())
		self.assertIn('Sent to', said)
		self.assertIn('could not be recorded', said)
		self.assertIn('out of disk', said)
		# and the window is told the message went, because it did
		self.assertIsNone(self.done.call_args.args[0])


if __name__ == '__main__':
	unittest.main()
