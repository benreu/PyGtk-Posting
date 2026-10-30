# test_mbox_import.py
#
# Mail that exists in no mailbox any more. This company was on POP until 2024,
# fetching to one workstation and letting the server delete its copy a
# fortnight later, so a decade of correspondence is in a Thunderbird file and
# nowhere else. The IMAP sync cannot reach it; this reads it.
#
# Two things here matter most. The file holds the only copy of every message
# in it, so nothing may write to it - there is a test that checks the bytes
# are unchanged afterwards. And this is the one place an address is matched to
# a contact, because a message from 2016 has no recorded link and never will,
# so the exactly-one-contact rule is tested from both sides.
#
# The mbox files are written here rather than taken from the user's profile:
# this business's mail does not belong in the repository.

import email.utils, hashlib, os, sys, tempfile, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from mail_schema import MailTestCase

import mbox_import


def message (date, sender, to, subject, body, message_id = '<a@b>',
				cc = '', attachment = None, charset = 'utf-8'):
	'''One mbox entry, in the shape Thunderbird really writes: a From_ line,
	then the message. Deliberately awkward in places - a subject needing an
	encoded word, a sender name with a comma, a declared character set that
	is not utf-8 - because a decade of mail is all of those.'''
	lines = ['From - %s' % date,
				'Date: %s' % date,
				'From: %s' % sender,
				'To: %s' % to]
	if cc:
		lines.append('Cc: %s' % cc)
	if message_id:
		lines.append('Message-ID: %s' % message_id)
	lines.append('Subject: %s' % subject)
	if attachment == None:
		lines.append('Content-Type: text/plain; charset="%s"' % charset)
		lines.append('')
		lines.append(body)
	else:
		lines.append('MIME-Version: 1.0')
		lines.append('Content-Type: multipart/mixed; boundary="=-aBc"')
		lines.append('')
		lines.append('--=-aBc')
		lines.append('Content-Type: text/plain; charset="%s"' % charset)
		lines.append('')
		lines.append(body)
		lines.append('--=-aBc')
		lines.append('Content-Type: application/pdf; name="%s"' % attachment)
		lines.append('Content-Disposition: attachment; filename="%s"'
						% attachment)
		lines.append('Content-Transfer-Encoding: base64')
		lines.append('')
		lines.append('JVBERi0xLjQK')
		lines.append('--=-aBc--')
	return '\n'.join(lines) + '\n\n'


SENT = (message('Fri, 03 Oct 2014 05:49:38 -0400', 'us@example.com',
					'Linden Grove <grove@example.com>', 'Still Around',
					'Long time no see.', '<first@example.com>')
		+ message('Sat, 18 Oct 2014 23:04:16 -0400', 'us@example.com',
					'mike@example.com', 'Funnies I got',
					'Here they are.', '<second@example.com>',
					attachment = 'jokes.pdf'))

RECEIVED = (message('Tue, 19 May 2015 18:36:13 +0000',
					'"Esh, Omar" <omar@example.com>', 'us@example.com',
					'=?utf-8?B?Rlc6IE1hbnVhbCBmb3Igd2lkZ2V0?=',
					'See attached.', '<third@example.com>',
					cc = 'book@example.com', attachment = 'manual.pdf')
			+ message('Wed, 17 Aug 2016 10:38:59 +0200', 'sue@example.com',
					'us@example.com', 'Re: parts on order',
					'When can we expect it?', '')) # no Message-ID at all


class FixtureTestCase (MailTestCase):

	def setUp (self):
		MailTestCase.setUp(self)
		self.cursor.execute("DELETE FROM mail_links")
		self.cursor.execute("DELETE FROM mail_messages")
		self.directory = tempfile.mkdtemp(prefix = 'posting_mbox_test_')
		self.addCleanup(self.clean_up)
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active) VALUES ('test', False) RETURNING id")
		self.account_id = self.cursor.fetchone()[0]
		self.DB.commit()

	def clean_up (self):
		for name in os.listdir(self.directory):
			os.remove(os.path.join(self.directory, name))
		os.rmdir(self.directory)

	def mbox (self, text, name = 'Inbox'):
		path = os.path.join(self.directory, name)
		with open(path, 'w') as mbox_file:
			mbox_file.write(text)
		return path

	def importer (self, account_id = False):
		return mbox_import.Importer(self.DB,
					self.account_id if account_id == False else account_id)

	def stored (self):
		self.cursor.execute("SELECT message_id, folder, uid, subject, "
								"from_address, from_name, to_addresses, "
								"cc_addresses, outgoing, has_attachments, "
								"body_text, date_sent "
							"FROM mail_messages ORDER BY date_sent")
		names = ('message_id folder uid subject from_address from_name '
					'to_addresses cc_addresses outgoing has_attachments '
					'body_text date_sent').split()
		return [dict(zip(names, row)) for row in self.cursor.fetchall()]

	def links (self):
		self.cursor.execute("SELECT m.subject, l.contact_id "
							"FROM mail_links AS l "
							"JOIN mail_messages AS m ON m.id = l.mail_messages_id "
							"ORDER BY m.subject")
		return self.cursor.fetchall()


class TheFileIsNotTouchedTest (FixtureTestCase):
	'''The only copy of every message in it.'''

	def digest (self, path):
		with open(path, 'rb') as mbox_file:
			return hashlib.sha256(mbox_file.read()).hexdigest()

	def test_importing_does_not_change_the_file (self):
		path = self.mbox(RECEIVED)
		before = self.digest(path)
		self.importer().run(path, 'Inbox', False)
		self.assertEqual(self.digest(path), before)

	def test_looking_does_not_change_the_file (self):
		path = self.mbox(RECEIVED)
		before = self.digest(path)
		self.importer().scan(path)
		self.assertEqual(self.digest(path), before)

	def test_looking_writes_no_rows (self):
		# a wrong file should be a sentence on screen, not thousands of rows
		# to find and undo
		path = self.mbox(RECEIVED)
		self.importer().scan(path)
		self.assertEqual(self.stored(), [])

	def test_a_file_that_is_not_there_is_named_in_the_error (self):
		with self.assertRaises(mbox_import.ImportError_) as caught:
			self.importer().scan(os.path.join(self.directory, 'no-such-file'))
		self.assertIn('no-such-file', str(caught.exception))


class LookingTest (FixtureTestCase):

	def test_how_many_and_from_when (self):
		count, earliest, latest = self.importer().scan(self.mbox(RECEIVED))
		self.assertEqual(count, 2)
		self.assertEqual((earliest.year, earliest.month), (2015, 5))
		self.assertEqual((latest.year, latest.month), (2016, 8))

	def test_an_empty_file (self):
		self.assertEqual(self.importer().scan(self.mbox('')), (0, None, None))


class StoringTest (FixtureTestCase):

	def test_what_was_received (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		first = self.stored()[0]
		self.assertEqual(first['subject'], 'FW: Manual for widget')
		self.assertEqual(first['from_address'], 'omar@example.com')
		self.assertEqual(first['from_name'], 'Esh, Omar')
		self.assertEqual(first['cc_addresses'], 'book@example.com')
		self.assertFalse(first['outgoing'])
		self.assertTrue(first['has_attachments'])
		self.assertIn('See attached.', first['body_text'])

	def test_what_was_sent (self):
		self.importer().run(self.mbox(SENT, 'Sent'), 'Sent', True,
							link_contacts = False)
		rows = self.stored()
		self.assertTrue(all(row['outgoing'] for row in rows))
		self.assertEqual(rows[0]['to_addresses'],
							'Linden Grove <grove@example.com>')

	def test_an_encoded_word_subject_arrives_as_words (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		self.assertIn('FW: Manual for widget',
						[row['subject'] for row in self.stored()])

	def test_the_archive_is_named_in_every_row (self):
		self.importer().run(self.mbox(RECEIVED), 'POP Inbox 2015', False,
							link_contacts = False)
		self.assertEqual(set(row['folder'] for row in self.stored()),
							{'POP Inbox 2015'})

	def test_an_imported_message_has_no_server_copy (self):
		# uid NULL is what says it is not on a server any more, and is why
		# the uid index is partial: these would collide with each other
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		self.assertTrue(all(row['uid'] == None for row in self.stored()))

	def test_two_messages_with_no_server_copy_are_two_rows (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(len(self.stored()), 2)

	def test_when_each_was_sent (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		years = [row['date_sent'].year for row in self.stored()]
		self.assertEqual(years, [2015, 2016])

	def test_a_message_with_no_message_id_is_still_stored (self):
		# it is not a header a sender is obliged to set, and this archive has
		# one such message in it
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		self.assertIn('', [row['message_id'] for row in self.stored()])

	def test_the_account_is_recorded (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
							link_contacts = False)
		self.cursor.execute("SELECT DISTINCT account_id FROM mail_messages")
		self.assertEqual(self.cursor.fetchall(), [(self.account_id,)])

	def test_no_mail_account_set_up_is_not_a_reason_not_to_import (self):
		self.importer(account_id = None).run(self.mbox(RECEIVED), 'Inbox',
											False, link_contacts = False)
		self.assertEqual(len(self.stored()), 2)

	def test_the_count_is_reported (self):
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
										link_contacts = False)
		self.assertEqual((summary.read, summary.stored), (2, 2))


class RunningItTwiceTest (FixtureTestCase):
	'''message_id is deliberately not unique in the schema, because the same
	message legitimately sits in two folders. Not importing it twice is
	therefore the importer's job rather than a constraint's.'''

	def test_the_same_file_twice_adds_nothing (self):
		path = self.mbox(RECEIVED)
		self.importer().run(path, 'Inbox', False, link_contacts = False)
		summary = self.importer().run(path, 'Inbox', False,
										link_contacts = False)
		# the one message with no Message-ID cannot be told apart this way
		self.assertEqual(summary.already_here, 1)
		self.assertEqual(len([row for row in self.stored()
								if row['message_id'] != '']), 1)

	def test_a_message_already_fetched_from_the_server_is_left_alone (self):
		# the archive overlaps the server wherever the fourteen day window
		# had not expired, and a second copy of a message is not history
		self.cursor.execute("INSERT INTO mail_messages (account_id, "
								"message_id, folder, uid, uidvalidity, "
								"subject) "
							"VALUES (%s, '<third@example.com>', 'INBOX', 9, "
								"1, 'already synced')", (self.account_id,))
		self.DB.commit()
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
										link_contacts = False)
		self.assertEqual(summary.already_here, 1)
		self.assertIn('already synced',
						[row['subject'] for row in self.stored()])

	def test_a_half_finished_import_can_be_run_again (self):
		path = self.mbox(RECEIVED)
		importer = self.importer()
		importer.cancelled = True
		self.assertEqual(importer.run(path, 'Inbox', False).read, 0)
		self.assertEqual(self.importer().run(path, 'Inbox', False,
								link_contacts = False).stored, 2)


class ContactMatchingTest (FixtureTestCase):
	'''The one place in this feature an address is matched to a contact.
	Everywhere else the link was recorded when the message was sent, because
	the compose window knew who was chosen; a message from 2016 has nothing
	recorded and never will.'''

	def setUp (self):
		FixtureTestCase.setUp(self)
		self.cursor.execute("SELECT id, customer_id FROM invoices "
							"ORDER BY id LIMIT 1")
		_, self.template = self.cursor.fetchone()
		self.omar = self.contact('Omar Esh', 'omar@example.com')
		self.DB.commit()

	def contact (self, name, address):
		self.cursor.execute("INSERT INTO contacts (name, email, "
								"terms_and_discounts_id, markup_percent_id) "
							"SELECT %s, %s, terms_and_discounts_id, "
								"markup_percent_id "
							"FROM contacts WHERE id = %s RETURNING id",
							(name, address, self.template))
		return self.cursor.fetchone()[0]

	def individual (self, contact_id, name, address):
		self.cursor.execute("INSERT INTO contact_individuals "
								"(name, email, contact_id) "
							"VALUES (%s, %s, %s)", (name, address, contact_id))

	def test_received_mail_is_filed_under_who_sent_it (self):
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(self.links(),
							[('FW: Manual for widget', self.omar)])
		self.assertEqual(summary.linked, 1)

	def test_sent_mail_is_filed_under_who_it_went_to (self):
		grove = self.contact('Linden Grove', 'grove@example.com')
		self.DB.commit()
		self.importer().run(self.mbox(SENT, 'Sent'), 'Sent', True)
		self.assertIn(('Still Around', grove), self.links())

	def test_an_address_belonging_to_two_contacts_is_filed_under_neither (self):
		# linking either would put one customer's mail under another's name,
		# which is the whole reason nothing else here matches on an address
		self.contact('Omar Esh again', 'omar@example.com')
		self.DB.commit()
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(self.links(), [])
		self.assertEqual(summary.ambiguous, 1)

	def test_a_named_person_at_a_company_counts (self):
		# contact_individuals.email is a second address column, and leaving it
		# out would lose every message addressed to somebody by name
		company = self.contact('Widget Co', 'office@example.com')
		self.individual(company, 'Sue', 'sue@example.com')
		self.DB.commit()
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertIn(('Re: parts on order', company), self.links())

	def test_an_address_matching_nobody_is_counted_not_guessed (self):
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(summary.no_contact, 1)

	def test_case_and_spacing_do_not_stop_a_match (self):
		# nothing in this program normalises an address on the way in:
		# contact_edit_main saves exactly what was typed
		self.cursor.execute("UPDATE contacts SET email = '  OMAR@Example.COM ' "
							"WHERE id = %s", (self.omar,))
		self.DB.commit()
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(self.links(),
							[('FW: Manual for widget', self.omar)])

	def test_a_deleted_contact_is_not_matched (self):
		self.cursor.execute("UPDATE contacts SET deleted = True WHERE id = %s",
							(self.omar,))
		self.DB.commit()
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(self.links(), [])
		self.assertEqual(summary.no_contact, 2)

	def test_linking_can_be_turned_off (self):
		summary = self.importer().run(self.mbox(RECEIVED), 'Inbox', False,
										link_contacts = False)
		self.assertEqual(self.links(), [])
		self.assertEqual(summary.linked, 0)

	def test_the_message_is_stored_whether_or_not_it_could_be_filed (self):
		self.importer().run(self.mbox(RECEIVED), 'Inbox', False)
		self.assertEqual(len(self.stored()), 2)


class AwkwardMailTest (FixtureTestCase):
	'''A decade of mail from everywhere. None of this may stop an import: a
	message that cannot be read is still a message that arrived.'''

	def test_a_character_set_that_is_not_utf8 (self):
		text = message('Mon, 01 Jun 2015 09:00:00 -0400', 'a@example.com',
						'us@example.com', 'Accents', 'café wall',
						'<cs@example.com>', charset = 'iso-8859-1')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(len(self.stored()), 1)

	def test_a_character_set_that_does_not_exist (self):
		text = message('Mon, 01 Jun 2015 09:00:00 -0400', 'a@example.com',
						'us@example.com', 'Nonsense charset', 'body',
						'<cs2@example.com>', charset = 'x-not-a-charset')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(len(self.stored()), 1)

	def test_an_unparseable_date_is_not_a_reason_to_skip_it (self):
		text = message('whenever', 'a@example.com', 'us@example.com',
						'No date', 'body', '<nd@example.com>')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		rows = self.stored()
		self.assertEqual(len(rows), 1)
		self.assertIsNone(rows[0]['date_sent'])

	def test_a_message_with_no_body_at_all (self):
		text = ('From - Mon, 01 Jun 2015 09:00:00 -0400\n'
				'Date: Mon, 01 Jun 2015 09:00:00 -0400\n'
				'From: a@example.com\n'
				'To: us@example.com\n'
				'Message-ID: <empty@example.com>\n'
				'Subject: Nothing in it\n\n')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(self.stored()[0]['body_text'], '')

	def test_a_body_longer_than_the_cap_is_cut (self):
		text = message('Mon, 01 Jun 2015 09:00:00 -0400', 'a@example.com',
						'us@example.com', 'Long', 'x' * 200000,
						'<long@example.com>')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(len(self.stored()[0]['body_text']),
							mbox_import.BODY_TEXT_LIMIT)

	def test_a_subject_with_a_newline_folded_into_it (self):
		text = message('Mon, 01 Jun 2015 09:00:00 -0400', 'a@example.com',
						'us@example.com', 'A question about\n the parts',
						'body', '<fold@example.com>')
		self.importer().run(self.mbox(text), 'Inbox', False,
							link_contacts = False)
		self.assertEqual(self.stored()[0]['subject'],
							'A question about the parts')


class PureFunctionTest (unittest.TestCase):
	'''The parts worth testing without a database.'''

	def parsed (self, text):
		import email
		return email.message_from_string(text.split('\n', 1)[1])

	def test_who_a_received_message_is_with (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'"Esh, Omar" <Omar@Example.com>', 'us@example.com',
						's', 'b'))
		self.assertEqual(mbox_import.correspondents(one, False),
							['omar@example.com'])

	def test_who_a_sent_message_is_with (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'us@example.com', 'a@example.com, b@example.com',
						's', 'b', cc = 'c@example.com'))
		self.assertEqual(mbox_import.correspondents(one, True),
							['a@example.com', 'b@example.com',
								'c@example.com'])

	def test_the_same_address_twice_is_once (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'us@example.com', 'a@example.com, A@Example.com',
						's', 'b'))
		self.assertEqual(mbox_import.correspondents(one, True),
							['a@example.com'])

	def test_something_that_is_not_an_address_is_not_one (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'us@example.com', 'undisclosed-recipients:;',
						's', 'b'))
		self.assertEqual(mbox_import.correspondents(one, True), [])

	def test_a_text_body (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'a@example.com', 'us@example.com', 's', 'the words'))
		self.assertIn('the words', mbox_import.text_body(one))

	def test_the_text_part_of_a_message_with_an_attachment (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'a@example.com', 'us@example.com', 's', 'the words',
						attachment = 'a.pdf'))
		body = mbox_import.text_body(one)
		self.assertIn('the words', body)
		self.assertNotIn('JVBERi', body) # not the pdf's base64

	def test_an_attachment_is_noticed (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'a@example.com', 'us@example.com', 's', 'b',
						attachment = 'a.pdf'))
		self.assertTrue(mbox_import.attached(one))

	def test_a_plain_message_has_nothing_attached (self):
		one = self.parsed(message('Mon, 01 Jun 2015 09:00:00 -0400',
						'a@example.com', 'us@example.com', 's', 'b'))
		self.assertFalse(mbox_import.attached(one))

	def test_the_cap_is_the_sync_s_cap (self):
		# one number for how much of a body is kept, wherever it came from
		import imap_sync
		self.assertEqual(mbox_import.BODY_TEXT_LIMIT,
							imap_sync.BODY_TEXT_LIMIT)


class SummaryTest (unittest.TestCase):

	def test_a_plain_import (self):
		summary = mbox_import.Summary()
		summary.read, summary.stored = 3325, 3300
		self.assertIn('3325 messages read, 3300 stored.', summary.said())

	def test_what_could_not_be_filed_is_said_not_hidden (self):
		summary = mbox_import.Summary()
		summary.read = summary.stored = 10
		summary.ambiguous = 2
		summary.no_contact = 3
		said = summary.said()
		self.assertIn('more than one contact', said)
		self.assertIn('no address matching a contact', said)

	def test_nothing_unusual_is_not_mentioned (self):
		summary = mbox_import.Summary()
		summary.read = summary.stored = 10
		self.assertEqual(summary.said().count('\n'), 0)


if __name__ == '__main__':
	unittest.main()
