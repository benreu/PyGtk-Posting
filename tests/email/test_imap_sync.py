# test_imap_sync.py
#
# Reading the mail server. Three things here matter more than the rest:
#
# BODY.PEEK and nothing else. BODY[...] sets \Seen, so a fetch using it would
# mark every message in the mailbox read - twelve thousand of them, from
# inside an accounting program, on the user's phone too, with no way back.
# Two tests guard it: the fetch items themselves, and that the folder is
# opened readonly so the server would refuse a flag change anyway.
#
# The uid arithmetic, which is why it is in free functions. A slices() that
# is wrong either misses mail silently or fetches the mailbox twice.
#
# That the timer cannot be stopped by anything the server does. poll must
# return True however badly the pass went, or the sync quietly never runs
# again for the life of the program.
#
# Nothing here reaches a mail server: every test that would connect is given
# a mailbox of its own making.

import os, sys, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from mail_schema import MailTestCase
from test_emailing import account

import credentials, emailing, imap_sync


# A FETCH response in the shape imaplib really hands back: one (prefix,
# literal) tuple per literal asked for, loose bytes closing each message, and
# nothing marking where one message ends but the next one's sequence number.
#
# Constructed rather than captured off the server, so it is the RFC 3501 shape
# and this business's mail is not in the repository. The awkward parts are
# deliberate: an encoded word subject, a folded subject line, a From name
# with a comma in it, a missing Message-ID, and an attachment that has to be
# seen in BODYSTRUCTURE without fetching it.
WITH_ATTACHMENT = (
	b'1 (UID 101 INTERNALDATE "22-Oct-2026 09:14:02 -0400" RFC822.SIZE 94210 '
	b'BODYSTRUCTURE (("text" "plain" ("charset" "utf-8") NIL NIL '
	b'"quoted-printable" 714 19 NIL NIL NIL NIL)("application" "pdf" '
	b'("name" "Invoice 1234.pdf") NIL NIL "base64" 92310 NIL '
	b'("attachment" ("filename" "Invoice 1234.pdf")) NIL NIL) "mixed" '
	b'("boundary" "=-aBc") NIL NIL NIL) '
	b'BODY[HEADER.FIELDS (MESSAGE-ID DATE SUBJECT FROM TO CC)] {242}',
	b'Message-ID: <first@example.com>\r\n'
	b'Date: Thu, 22 Oct 2026 09:14:02 -0400\r\n'
	b'Subject: =?utf-8?B?SW52b2ljZSAxMjM0IGlzIGR1ZQ==?=\r\n'
	b'From: "Smith, Bob" <bob@example.com>\r\n'
	b'To: us@example.com\r\n'
	b'Cc: book@example.com\r\n'
	b'\r\n')
WITH_ATTACHMENT_BODY = (b' BODY[1]<0> {31}',
						b'Here is the invoice.\r\n\r\nBob\r\n')

PLAIN = (
	b'2 (UID 102 INTERNALDATE "23-Oct-2026 11:02:00 -0400" RFC822.SIZE 806 '
	b'BODYSTRUCTURE ("text" "plain" ("charset" "us-ascii") NIL NIL "7bit" '
	b'120 4 NIL NIL NIL NIL) '
	b'BODY[HEADER.FIELDS (MESSAGE-ID DATE SUBJECT FROM TO CC)] {168}',
	b'Date: Fri, 23 Oct 2026 11:02:00 -0400\r\n'
	b'Subject: A question about the\r\n parts on order\r\n'
	b'From: sue@example.com\r\n'
	b'To: us@example.com\r\n'
	b'\r\n')
PLAIN_BODY = (b' BODY[1]<0> {22}', b'When can we expect it?')

RESPONSE = [WITH_ATTACHMENT, WITH_ATTACHMENT_BODY, b')',
			PLAIN, PLAIN_BODY, b')']


class SafetyTest (unittest.TestCase):
	'''The one thing in this feature that cannot be undone.'''

	def test_the_fetch_never_asks_for_body_without_peek (self):
		# BODY[...] sets \Seen. BODY.PEEK[...] does not. That one word is the
		# difference between reading the mailbox and marking all of it read
		self.assertIn('BODY.PEEK[', imap_sync.FETCH_ITEMS)
		without_peek = imap_sync.FETCH_ITEMS.replace('BODY.PEEK[', '')
		self.assertNotIn('BODY[', without_peek)

	def test_nothing_in_the_module_fetches_with_a_bare_body (self):
		# crude, and worth it: a bare BODY[ anywhere in a command string here
		# would be the same mistake somewhere this file's tests do not reach
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'imap_sync.py')
		with open(path) as source_file:
			source = source_file.read()
		# the response parsing legitimately matches on BODY[1], which the
		# server says back to us; what matters is what is sent
		for line in source.splitlines():
			if 'FETCH' in line or 'PEEK' in line:
				self.assertNotIn("'BODY[", line, line)
				self.assertNotIn('"BODY[', line, line)

	def test_the_folder_is_opened_readonly (self):
		# the second lock on the same door: EXAMINE rather than SELECT, so the
		# server refuses a flag change whatever this file asks for
		mailbox = mock.Mock()
		mailbox.select.return_value = ('OK', [b'1'])
		mailbox.response.return_value = ('OK', [b'1'])
		imap_sync.Watcher().examine(mailbox, 'INBOX')
		self.assertTrue(mailbox.select.call_args.kwargs['readonly'])

	def test_nothing_issues_a_search (self):
		# this server advertises X-ICEWARP-SEARCHLIMIT and may silently
		# return fewer results than match, so a truncated SEARCH would have
		# the sync decide it was up to date
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'imap_sync.py')
		with open(path) as source_file:
			source = source_file.read()
		self.assertNotIn("'SEARCH'", source)
		self.assertNotIn('"SEARCH"', source)


class SlicesTest (unittest.TestCase):

	def test_nothing_new_is_no_work (self):
		# the common case, and it has to cost one round trip rather than a
		# fetch of anything
		self.assertEqual(imap_sync.slices(100, 101), [])

	def test_one_new_message (self):
		self.assertEqual(imap_sync.slices(100, 102), [(101, 101)])

	def test_a_first_look_at_a_folder (self):
		self.assertEqual(imap_sync.slices(0, 6, size = 500), [(1, 5)])

	def test_a_full_mailbox_is_two_dozen_slices (self):
		ranges = imap_sync.slices(0, 12001, size = 500)
		self.assertEqual(len(ranges), 24)
		self.assertEqual(ranges[0], (1, 500))
		self.assertEqual(ranges[-1], (11501, 12000))

	def test_the_slices_are_contiguous_and_ascending (self):
		ranges = imap_sync.slices(0, 1234, size = 100)
		self.assertEqual(ranges[0][0], 1)
		self.assertEqual(ranges[-1][1], 1233)
		for earlier, later in zip(ranges, ranges[1:]):
			self.assertEqual(later[0], earlier[1] + 1)

	def test_a_mark_past_the_end_asks_for_nothing (self):
		# a folder the server renumbered downward, or a mark somebody edited
		self.assertEqual(imap_sync.slices(900, 100), [])

	def test_a_server_that_said_nothing_is_not_a_fetch_of_everything (self):
		self.assertEqual(imap_sync.slices(0, None), [])
		self.assertEqual(imap_sync.slices(None, None), [])

	def test_resuming_starts_after_the_mark_not_on_it (self):
		# on it would re-fetch the last message of every interrupted pass
		self.assertEqual(imap_sync.slices(500, 1000, size = 100)[0], (501, 600))


class UidValidityTest (unittest.TestCase):

	def test_the_same_numbering_is_no_change (self):
		self.assertFalse(imap_sync.uidvalidity_changed(42, 42))

	def test_a_different_numbering_is (self):
		self.assertTrue(imap_sync.uidvalidity_changed(42, 43))

	def test_not_knowing_yet_is_not_a_change (self):
		# a folder read for the first time has no known value, and calling
		# that a renumbering would throw the mark away before it was used
		self.assertFalse(imap_sync.uidvalidity_changed(None, 42))

	def test_a_server_that_did_not_say_is_not_a_change (self):
		self.assertFalse(imap_sync.uidvalidity_changed(42, None))

	def test_text_and_number_are_the_same_value (self):
		self.assertFalse(imap_sync.uidvalidity_changed('42', 42))


class GroupingTest (unittest.TestCase):
	'''imaplib hands back one flat list for a whole FETCH, and nothing in it
	says where one message stops.'''

	def test_two_messages_are_two_groups (self):
		self.assertEqual(len(imap_sync.messages(RESPONSE)), 2)

	def test_each_group_keeps_its_literals (self):
		first, second = imap_sync.messages(RESPONSE)
		self.assertEqual(len([lit for _, lit in first if lit != None]), 2)
		self.assertEqual(len([lit for _, lit in second if lit != None]), 2)

	def test_punctuation_alone_is_not_a_message (self):
		self.assertEqual(imap_sync.messages([b')', b')']), [])

	def test_loose_bytes_before_a_message_are_dropped (self):
		grouped = imap_sync.messages([b'* 1 EXISTS'] + RESPONSE)
		self.assertEqual(len(grouped), 2)

	def test_nothing_at_all (self):
		self.assertEqual(imap_sync.messages(None), [])
		self.assertEqual(imap_sync.messages([]), [])


class HeaderRowTest (unittest.TestCase):

	def row (self, index = 0, folder = 'INBOX', outgoing = False):
		groups = imap_sync.messages(RESPONSE)
		return imap_sync.header_row(groups[index], folder, outgoing)

	def test_the_uid_is_read_out (self):
		self.assertEqual(self.row()['uid'], 101)
		self.assertEqual(self.row(1)['uid'], 102)

	def test_an_encoded_word_subject_arrives_as_words (self):
		# =?utf-8?B?...?= is what a subject with anything but ascii in it
		# looks like on the wire, and a list full of those is unreadable
		self.assertEqual(self.row()['subject'], 'Invoice 1234 is due')

	def test_a_folded_subject_is_one_line_again (self):
		self.assertEqual(self.row(1)['subject'],
							'A question about the parts on order')

	def test_a_from_name_with_a_comma_is_not_two_people (self):
		self.assertEqual(self.row()['from_name'], 'Smith, Bob')
		self.assertEqual(self.row()['from_address'], 'bob@example.com')

	def test_a_from_with_no_name (self):
		self.assertEqual(self.row(1)['from_address'], 'sue@example.com')
		self.assertEqual(self.row(1)['from_name'], '')

	def test_the_message_id_is_kept (self):
		self.assertEqual(self.row()['message_id'], '<first@example.com>')

	def test_a_missing_message_id_is_not_an_error (self):
		# it is not a header a sender is obliged to set
		self.assertEqual(self.row(1)['message_id'], '')

	def test_when_it_was_sent (self):
		stamp = self.row()['date_sent']
		self.assertEqual((stamp.year, stamp.month, stamp.day), (2026, 10, 22))

	def test_everyone_it_went_to (self):
		self.assertEqual(self.row()['to_addresses'], 'us@example.com')
		self.assertEqual(self.row()['cc_addresses'], 'book@example.com')

	def test_no_cc_is_empty_rather_than_missing (self):
		self.assertEqual(self.row(1)['cc_addresses'], '')

	def test_an_attachment_is_seen_without_fetching_it (self):
		# BODYSTRUCTURE rides along in the same round trip, which is the only
		# way to know this without pulling 92 KB of pdf for every message
		self.assertTrue(self.row()['has_attachments'])

	def test_a_message_with_only_text_has_nothing_attached (self):
		self.assertFalse(self.row(1)['has_attachments'])

	def test_the_body_is_kept_to_read (self):
		self.assertIn('Here is the invoice.', self.row()['body_text'])

	def test_the_folder_it_came_from_is_recorded (self):
		self.assertEqual(self.row(folder = 'INBOX')['folder'], 'INBOX')

	def test_which_way_it_went_is_the_callers_to_say (self):
		# the folder decides it: a message in Sent is one of ours
		self.assertFalse(self.row(outgoing = False)['outgoing'])
		self.assertTrue(self.row(outgoing = True)['outgoing'])

	def test_a_message_with_no_uid_is_not_a_row (self):
		group = [(b'1 (INTERNALDATE "x" BODY[HEADER.FIELDS (DATE)] {2}',
					b'\r\n')]
		self.assertIsNone(imap_sync.header_row(group, 'INBOX', False))


class BodyTextTest (unittest.TestCase):

	def test_nothing_is_empty_rather_than_an_error (self):
		self.assertEqual(imap_sync.body_text(b''), '')
		self.assertEqual(imap_sync.body_text(None), '')

	def test_it_is_capped (self):
		# the server has the whole thing; without a cap one 40 MB message
		# would be 40 MB in Postgres and in every pg_dump of it
		text = imap_sync.body_text(b'x' * (imap_sync.BODY_TEXT_LIMIT * 2))
		self.assertEqual(len(text), imap_sync.BODY_TEXT_LIMIT)

	def test_bytes_that_are_not_utf8_do_not_raise (self):
		# a message that cannot be decoded still arrived, and its headers are
		# worth keeping
		self.assertIsInstance(imap_sync.body_text(b'caf\xe9 wall'), str)

	def test_utf8_is_decoded (self):
		self.assertEqual(imap_sync.body_text('café'.encode()), 'café')


class HasAttachmentTest (unittest.TestCase):

	def test_an_attachment_disposition (self):
		self.assertTrue(imap_sync.has_attachment(b'... ("ATTACHMENT" ...)'))

	def test_text_only (self):
		self.assertFalse(imap_sync.has_attachment(
							b'("text" "plain" ("charset" "utf-8"))'))

	def test_nothing_said (self):
		self.assertFalse(imap_sync.has_attachment(b''))
		self.assertFalse(imap_sync.has_attachment(None))


class PollTest (unittest.TestCase):
	'''A timer handler that returns anything false is removed. A sync that
	stopped for good the first time the server was unreachable would be worse
	than one that says so and tries again in five minutes.'''

	def test_a_pass_that_raises_keeps_the_timer (self):
		watcher = imap_sync.Watcher()
		with mock.patch.object(watcher, 'begin',
								side_effect = Exception('no server')):
			self.assertTrue(watcher.poll())

	def test_a_pass_that_works_keeps_the_timer (self):
		watcher = imap_sync.Watcher()
		with mock.patch.object(watcher, 'begin'):
			self.assertTrue(watcher.poll())

	def test_the_first_look_does_not_repeat_itself (self):
		# it is a one-off, with the five minute timer carrying on after it
		watcher = imap_sync.Watcher()
		with mock.patch.object(watcher, 'begin'):
			self.assertFalse(watcher.first_poll())


class BeginTest (MailTestCase):
	'''What has to be true before anything dials the server.'''

	def setUp (self):
		MailTestCase.setUp(self)
		self.cursor.execute("DELETE FROM settings.mail_folders")
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active, imap_host, imap_user) VALUES "
							"('test', False, 'imap.example.com', 'us') "
							"RETURNING id")
		self.account_id = self.cursor.fetchone()[0]
		self.acct = account(id = self.account_id,
							imap_host = 'imap.example.com', imap_user = 'us')
		self.DB.commit()
		self.thread = mock.patch.object(imap_sync.threading, 'Thread').start()
		self.addCleanup(mock.patch.stopall)
		self.watcher = imap_sync.Watcher()

	def folder (self, name = 'INBOX', sync = True):
		self.cursor.execute("INSERT INTO settings.mail_folders "
							"(account_id, folder, sync) VALUES (%s, %s, %s)",
							(self.account_id, name, sync))
		self.DB.commit()

	def begin (self, acct = False):
		with mock.patch.object(emailing, 'account',
						return_value = self.acct if acct == False else acct):
			self.watcher.begin()

	def test_a_folder_turned_on_starts_a_pass (self):
		self.folder()
		self.begin()
		self.assertTrue(self.thread.called)

	def test_no_account_asks_nothing (self):
		self.folder()
		self.begin(acct = None)
		self.assertFalse(self.thread.called)

	def test_an_account_with_no_imap_server_asks_nothing (self):
		self.folder()
		self.begin(acct = account(imap_host = '', imap_user = 'us'))
		self.assertFalse(self.thread.called)

	def test_no_folder_turned_on_asks_nothing (self):
		# sync defaults to False, so an upgrade on its own reads nothing
		self.folder(sync = False)
		self.begin()
		self.assertFalse(self.thread.called)

	def test_no_folders_at_all_asks_nothing (self):
		self.begin()
		self.assertFalse(self.thread.called)

	def test_a_pass_still_running_is_not_started_again (self):
		self.folder()
		self.watcher.running = True
		self.begin()
		self.assertFalse(self.thread.called)

	def test_where_each_folder_got_to_is_handed_over (self):
		self.folder()
		self.cursor.execute("UPDATE settings.mail_folders "
							"SET uidvalidity = 7, last_uid = 400 "
							"WHERE account_id = %s", (self.account_id,))
		self.DB.commit()
		self.begin()
		self.assertEqual(self.thread.call_args.kwargs['args'][1],
							[('INBOX', 7, 400)])


class ReadFolderTest (MailTestCase):
	'''One folder, against a mailbox of our own making.'''

	def setUp (self):
		MailTestCase.setUp(self)
		self.cursor.execute("DELETE FROM mail_links")
		self.cursor.execute("DELETE FROM mail_messages")
		self.cursor.execute("DELETE FROM settings.mail_folders")
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active, imap_host, imap_user, sent_folder) "
							"VALUES ('test', False, 'imap.example.com', 'us', "
							"'Sent') RETURNING id")
		self.account_id = self.cursor.fetchone()[0]
		self.acct = account(id = self.account_id,
							imap_host = 'imap.example.com', imap_user = 'us',
							sent_folder = 'Sent')
		self.cursor.execute("INSERT INTO settings.mail_folders "
							"(account_id, folder, sync) VALUES (%s, 'INBOX', "
							"True)", (self.account_id,))
		self.DB.commit()
		self.watcher = imap_sync.Watcher()
		self.mailbox = mock.Mock()
		self.mailbox.host = 'imap.example.com'
		self.mailbox.select.return_value = ('OK', [b'2'])
		self.mailbox.uid.return_value = ('OK', RESPONSE)
		self.untagged = {'UIDVALIDITY': 7, 'UIDNEXT': 103}
		self.mailbox.response.side_effect = \
			lambda name: ('OK', [str(self.untagged.get(name, '')).encode()])

	def read (self, uidvalidity = None, last_uid = 0, folder = 'INBOX'):
		self.watcher.read_folder(self.DB, self.mailbox, self.acct, folder,
									uidvalidity, last_uid)

	def stored (self):
		self.cursor.execute("SELECT uid, folder, subject, outgoing, "
								"has_attachments, uidvalidity "
							"FROM mail_messages WHERE account_id = %s "
							"ORDER BY uid", (self.account_id,))
		return self.cursor.fetchall()

	def mark (self, folder = 'INBOX'):
		self.cursor.execute("SELECT uidvalidity, last_uid, "
								"last_synced IS NOT NULL "
							"FROM settings.mail_folders "
							"WHERE account_id = %s AND folder = %s",
							(self.account_id, folder))
		return self.cursor.fetchone()

	def test_what_the_server_sent_is_stored (self):
		self.read()
		self.assertEqual([row[0] for row in self.stored()], [101, 102])

	def test_the_mark_moves_to_the_end_of_the_slice (self):
		self.read()
		self.assertEqual(self.mark(), (7, 102, True))

	def test_nothing_new_is_not_a_fetch (self):
		self.read(uidvalidity = 7, last_uid = 102)
		self.assertFalse(self.mailbox.uid.called)

	def test_a_folder_with_nothing_new_still_says_it_was_looked_at (self):
		self.read(uidvalidity = 7, last_uid = 102)
		self.assertEqual(self.mark(), (7, 102, True))

	def test_the_numbering_is_recorded_the_first_time_a_folder_is_seen (self):
		# an empty folder would otherwise never record its uidvalidity, and
		# every later pass would treat it as freshly renumbered
		self.untagged['UIDNEXT'] = 1
		self.read()
		self.assertEqual(self.mark(), (7, 0, True))

	def test_nothing_new_does_not_notify (self):
		cursor = self.DB.cursor()
		with mock.patch.object(self.DB, 'cursor') as made:
			recorder = Recording(cursor)
			made.return_value = recorder
			self.read(uidvalidity = 7, last_uid = 102)
		self.assertEqual([sql for sql in recorder.statements
							if 'pg_notify' in sql], [])

	def test_a_folder_that_will_not_open_is_not_fetched (self):
		self.mailbox.select.return_value = ('NO', [b'nope'])
		self.read()
		self.assertFalse(self.mailbox.uid.called)

	def test_a_renumbered_folder_is_read_again_from_the_start (self):
		self.read(uidvalidity = 6, last_uid = 102)
		self.assertEqual([row[0] for row in self.stored()], [101, 102])

	def test_a_renumbered_folder_keeps_what_was_already_stored (self):
		# those rows are the correspondence, some of it attached to invoices;
		# message_id is what ties the old numbering to the new
		self.cursor.execute("INSERT INTO mail_messages (account_id, folder, "
								"uidvalidity, uid, subject) "
							"VALUES (%s, 'INBOX', 6, 101, 'the old numbering')",
							(self.account_id,))
		self.DB.commit()
		self.read(uidvalidity = 6, last_uid = 102)
		subjects = [row[2] for row in self.stored()]
		self.assertIn('the old numbering', subjects)

	def test_the_same_slice_twice_is_not_two_sets_of_rows (self):
		# what makes a folder safe to re-enumerate: ON CONFLICT DO NOTHING on
		# the server copy index rather than a violation that aborts the pass
		self.read()
		self.read()
		self.assertEqual(len(self.stored()), 2)

	def test_a_message_in_the_sent_folder_is_outgoing (self):
		self.read(folder = 'Sent')
		self.assertTrue(all(row[3] for row in self.stored()))

	def test_a_message_in_the_inbox_is_not (self):
		self.read()
		self.assertFalse(any(row[3] for row in self.stored()))

	def test_the_attachment_mark_survives_the_round_trip (self):
		self.read()
		marks = dict((row[0], row[4]) for row in self.stored())
		self.assertTrue(marks[101])
		self.assertFalse(marks[102])

	def test_the_numbering_is_stored_with_each_row (self):
		self.read()
		self.assertEqual(set(row[5] for row in self.stored()), {7})

	def test_a_fetch_the_server_refuses_raises (self):
		# it must not look like an empty folder, which would move the mark
		# past mail that was never read
		self.mailbox.uid.return_value = ('NO', [b'over quota'])
		with self.assertRaises(Exception):
			self.read()
		self.assertEqual(self.mark()[1], 0)

	def test_one_unreadable_message_does_not_lose_the_others (self):
		self.mailbox.uid.return_value = ('OK', [WITH_ATTACHMENT,
							WITH_ATTACHMENT_BODY, b')', PLAIN, PLAIN_BODY, b')'])
		with mock.patch.object(imap_sync, 'header_row',
				side_effect = [ValueError('mangled'),
								imap_sync.header_row(
									imap_sync.messages(RESPONSE)[1],
									'INBOX', False)]):
			self.read()
		self.assertEqual([row[0] for row in self.stored()], [102])

	def test_every_slice_notifies (self):
		# one per slice, so the correspondence window fills as it goes rather
		# than at the end of a two minute first pass
		cursor = self.DB.cursor()
		with mock.patch.object(self.DB, 'cursor') as made:
			recorder = Recording(cursor)
			made.return_value = recorder
			self.read()
		self.assertEqual(len([sql for sql in recorder.statements
								if 'pg_notify' in sql]), 1)


class Recording (object):
	"a real cursor that remembers what was run through it"

	def __init__ (self, cursor):
		self.cursor = cursor
		self.statements = []

	def execute (self, sql, args = None):
		self.statements.append(sql)
		if args == None:
			return self.cursor.execute(sql)
		return self.cursor.execute(sql, args)

	def __getattr__ (self, name):
		return getattr(self.cursor, name)


class LockTest (MailTestCase):
	'''One workstation reads the server per pass, and gives the lock back
	when the pass ends. Held for the life of the process, whichever
	workstation booted first would be the only one that ever syncs.'''

	def test_the_lock_is_taken_per_pass (self):
		watcher = imap_sync.Watcher()
		conn = mock.Mock()
		cursor = mock.Mock()
		conn.cursor.return_value = cursor
		cursor.fetchone.return_value = (True,)
		self.assertTrue(watcher.take_lock(conn, account(id = 1)))
		sql, args = cursor.execute.call_args.args
		self.assertIn('pg_try_advisory_lock', sql)
		self.assertEqual(args[0], harness.constants.MAIL_SYNC_LOCK_CLASSID)
		self.assertEqual(args[1], 1)

	def test_a_locked_out_workstation_does_not_read (self):
		watcher = imap_sync.Watcher()
		conn = mock.Mock()
		conn.cursor.return_value.fetchone.return_value = (False,)
		self.assertFalse(watcher.take_lock(conn, account(id = 1)))

	def test_it_is_not_a_session_lock (self):
		# pg_advisory_lock would be held until the connection closed, which
		# for a session lock is the life of the program
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'imap_sync.py')
		with open(path) as source_file:
			source = source_file.read()
		self.assertIn('pg_try_advisory_lock', source)
		self.assertNotIn('pg_advisory_lock', source.replace(
											'pg_try_advisory_lock', ''))


class WorkTest (MailTestCase):
	'''The thread. Whatever happens, the next tick has to be able to start.'''

	def setUp (self):
		MailTestCase.setUp(self)
		self.watcher = imap_sync.Watcher()
		self.watcher.running = True
		mock.patch.object(credentials, 'password',
							return_value = 'secret').start()
		self.addCleanup(mock.patch.stopall)

	def test_a_failure_lets_the_next_pass_start (self):
		# without this one failure leaves the flag set and nothing ever syncs
		# again for the life of the program
		with mock.patch.object(imap_sync, 'background_connection',
								side_effect = Exception('no database')):
			self.watcher.work(account(), [('INBOX', None, 0)])
		self.assertFalse(self.watcher.running)

	def test_a_keyring_without_the_password_lets_the_next_pass_start (self):
		with mock.patch.object(credentials, 'password',
						side_effect = credentials.CredentialError('not here')):
			self.watcher.work(account(), [('INBOX', None, 0)])
		self.assertFalse(self.watcher.running)


class StartTest (MailTestCase):
	'''Three guards, each returning quietly. Without the password check a
	workstation where nobody entered one would put a keyring prompt on screen
	every five minutes forever.'''

	def setUp (self):
		MailTestCase.setUp(self)
		imap_sync._watcher = None
		self.addCleanup(setattr, imap_sync, '_watcher', None)
		self.have = mock.patch.object(credentials, 'have_password',
										return_value = True).start()
		self.timer = mock.patch.object(imap_sync.GLib,
										'timeout_add_seconds').start()
		self.addCleanup(mock.patch.stopall)

	def start (self, acct):
		with mock.patch.object(emailing, 'account', return_value = acct):
			return imap_sync.start_mail_watcher()

	def test_an_account_with_a_password_here_starts (self):
		self.assertIsNotNone(self.start(account(
							imap_host = 'imap.example.com', imap_user = 'us')))
		self.assertTrue(self.timer.called)

	def test_no_account_does_not_start (self):
		self.assertIsNone(self.start(None))
		self.assertFalse(self.timer.called)

	def test_no_imap_server_does_not_start (self):
		self.assertIsNone(self.start(account(imap_host = '')))
		self.assertFalse(self.timer.called)

	def test_no_password_on_this_workstation_does_not_start (self):
		self.have.return_value = False
		self.assertIsNone(self.start(account(
							imap_host = 'imap.example.com', imap_user = 'us')))
		self.assertFalse(self.timer.called)

	def test_no_libsecret_does_not_start (self):
		self.have.side_effect = credentials.CredentialError('not installed')
		self.assertIsNone(self.start(account(
							imap_host = 'imap.example.com', imap_user = 'us')))
		self.assertFalse(self.timer.called)

	def test_it_is_started_once (self):
		acct = account(imap_host = 'imap.example.com', imap_user = 'us')
		first = self.start(acct)
		self.assertIs(self.start(acct), first)


if __name__ == '__main__':
	unittest.main()
