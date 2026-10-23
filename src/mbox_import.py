# mbox_import.py
#
# Copyright (C) 2026 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

'''Mail that exists in no mailbox any more, read out of a Thunderbird file.

The IMAP sync can only fetch what the server still has. This company's mail
was on POP until 2024, fetched to one workstation and deleted from the server
fourteen days later, so a decade of correspondence exists nowhere but in a
Thunderbird profile on that machine - thousands of messages, and the only
copy of each. That is what this reads.

A one-off, pointed at a file by hand, rather than anything that runs by
itself: the file it reads is irreplaceable and nothing here writes to it.
The mbox is opened for reading, and messages are read one at a time rather
than loaded together, because the Inbox is over a gigabyte.

This is the one place an email address is matched to a contact. Everywhere
else in this feature the link is recorded when the message is sent, because
the compose window knew who was chosen and guessing would be worse than
knowing - contacts.email is not unique, not trimmed and not case folded. For
a message from 2016 there is nothing recorded and never will be, so matching
is the only way it is ever found under a customer, and the rule is that only
an address belonging to exactly one contact is linked. Two contacts sharing
an address link to neither, and the count is reported rather than hidden.'''

from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
import email.errors, mailbox
from imap_sync import BODY_TEXT_LIMIT

# how many messages are written before a commit. Small enough that a failure
# halfway through leaves most of the work done, big enough not to be a commit
# per message over six thousand of them
BATCH = 200


class ImportError_ (Exception):
	"something about the file, said in words that name the file"
	pass


def opened (path):
	'''The mbox, for reading. mailbox.mbox is used rather than scanning for
	From_ lines by hand because it already knows the escaping rules, and
	create = False so that pointing this at a typo makes an error rather than
	an empty mbox where a decade of mail was supposed to be.'''
	try:
		return mailbox.mbox(path, create = False)
	except Exception as e:
		raise ImportError_("%s could not be read as a mail file:\n%s"
							% (path, e))

def text_body (message, limit = BODY_TEXT_LIMIT):
	'''The readable text of a message, capped.

	Never raises. A message from 2014 may be base64 of something that was
	never text, may name a character set that does not exist, or may be
	malformed in a way no library will parse; it still arrived, and its
	headers are worth keeping either way.'''
	try:
		if message.is_multipart():
			for part in message.walk():
				if part.get_content_type() != 'text/plain':
					continue
				if (part.get('Content-Disposition') or '').startswith(
															'attachment'):
					continue
				return decoded(part)[:limit]
			return ''
		return decoded(message)[:limit]
	except Exception:
		return ''

def decoded (part):
	payload = part.get_payload(decode = True)
	if payload == None:
		return ''
	charset = part.get_content_charset() or 'utf-8'
	try:
		return payload.decode(charset, 'replace')
	except (LookupError, UnicodeDecodeError):
		return payload.decode('latin-1', 'replace')

def attached (message):
	"whether anything was attached, as the message's own parts describe it"
	if not message.is_multipart():
		return False
	for part in message.walk():
		disposition = (part.get('Content-Disposition') or '').lower()
		if disposition.startswith('attachment'):
			return True
	return False

def header (message, name):
	'''One header as the words somebody wrote: encoded words decoded, folded
	lines joined, and nothing raising.

	The decoding is done here rather than by a policy because mailbox.mbox
	parses with compat32 and takes no policy argument, so a subject with
	anything but ascii in it arrives as =?utf-8?B?...?= and would be stored
	that way - a list of those is unreadable.'''
	try:
		value = message.get(name)
	except Exception:
		return ''
	if value == None:
		return ''
	try:
		text = str(make_header(decode_header(str(value))))
	except Exception:
		# a header too malformed to decode is still better shown raw than
		# dropped, and this is a decade of mail from everywhere
		text = str(value)
	return ' '.join(text.split())

def sent_date (message):
	"when it says it was sent, or None; a 2014 Date header is often nonsense"
	raw = message.get('Date')
	if raw == None:
		return None
	try:
		return parsedate_to_datetime(str(raw))
	except (TypeError, ValueError, OverflowError):
		return None

def correspondents (message, outgoing):
	'''The addresses this message is with - who it went to, or who it came
	from. Lower cased, because that is what a contact's address has to be
	compared as: nothing in this program normalises one on the way in.'''
	names = ('To', 'Cc') if outgoing else ('From',)
	raw = []
	for name in names:
		value = message.get_all(name) or []
		raw.extend([str(one) for one in value])
	found = []
	for _, address in getaddresses(raw):
		address = (address or '').strip().lower()
		if address != '' and '@' in address and address not in found:
			found.append(address)
	return found

def row_from (message, folder, outgoing):
	"one message as the values mail_messages wants"
	from_name, from_address = '', ''
	parsed = getaddresses([header(message, 'From')])
	if parsed:
		from_name, from_address = parsed[0][0], parsed[0][1].strip().lower()
	return {'message_id': header(message, 'Message-ID'),
			'folder': folder,
			'date_sent': sent_date(message),
			'subject': header(message, 'Subject'),
			'from_address': from_address,
			'from_name': from_name,
			'to_addresses': header(message, 'To'),
			'cc_addresses': header(message, 'Cc'),
			'outgoing': outgoing,
			'has_attachments': attached(message),
			'body_text': text_body(message)}


class Summary (object):
	"what an import did, for the window to show and the tests to assert on"

	def __init__ (self):
		self.read = 0
		self.stored = 0
		self.already_here = 0
		self.linked = 0
		self.ambiguous = 0
		self.no_contact = 0
		self.unreadable = 0

	def said (self):
		lines = ["%s messages read, %s stored." % (self.read, self.stored)]
		if self.already_here:
			lines.append("%s were already in the database and were left "
							"alone." % self.already_here)
		if self.linked:
			lines.append("%s were filed under a contact by their address."
							% self.linked)
		if self.ambiguous:
			lines.append("%s had an address belonging to more than one "
							"contact, so they are filed under none of them."
							% self.ambiguous)
		if self.no_contact:
			lines.append("%s had no address matching a contact." % self.no_contact)
		if self.unreadable:
			lines.append("%s could not be read and were skipped."
							% self.unreadable)
		return '\n'.join(lines)


class Importer (object):
	'''Reads a file into mail_messages. Given its own connection by the
	caller, because this runs on a worker thread and a worker touching the
	shared connection segfaults the program rather than raising.'''

	def __init__ (self, conn, account_id = None):
		self.conn = conn
		self.account_id = account_id
		self.cancelled = False

	def scan (self, path):
		'''How many messages are in the file and what dates they cover,
		writing nothing. Pointing this at the wrong file should be a sentence
		on screen, not six thousand rows to undo.'''
		box = opened(path)
		count, earliest, latest = 0, None, None
		try:
			for key in box.keys():
				try:
					message = box.get(key)
				except Exception:
					continue
				count += 1
				stamp = sent_date(message)
				if stamp == None:
					continue
				# compared as dates, because a decade of mail carries every
				# kind of timezone and some carry none
				day = stamp.date()
				earliest = day if earliest == None else min(earliest, day)
				latest = day if latest == None else max(latest, day)
		finally:
			box.close()
		return count, earliest, latest

	def known_message_ids (self):
		'''Every message id already in the database, so a second run of the
		same file adds nothing.

		message_id is deliberately not unique in the schema - the same
		message legitimately sits in two folders - so this is the importer's
		job rather than a constraint's. A message with no Message-ID at all
		cannot be told apart this way and may be stored twice; there is one
		such message in this archive.'''
		cursor = self.conn.cursor()
		cursor.execute("SELECT message_id FROM mail_messages "
						"WHERE message_id <> ''")
		known = set(row[0] for row in cursor.fetchall())
		cursor.close()
		return known

	def contact_for (self, addresses, summary):
		'''The one contact an address belongs to, or None.

		Both address columns are looked at: a company's own address on
		contacts, and the address of a named person at it on
		contact_individuals. Leaving the second out would lose every message
		to somebody by name, which for this archive is most of them.'''
		if addresses == []:
			summary.no_contact += 1
			return None
		cursor = self.conn.cursor()
		cursor.execute("SELECT id FROM contacts "
							"WHERE deleted = False "
							"AND lower(trim(email)) = ANY(%s) "
						"UNION "
						"SELECT contact_id FROM contact_individuals "
							"WHERE lower(trim(email)) = ANY(%s)",
						(addresses, addresses))
		found = [row[0] for row in cursor.fetchall()]
		cursor.close()
		# deliberately no rollback, unlike the read-then-rollback every window
		# in this program does. This connection is the importer's own and is
		# mid transaction: rolling back here would throw away every message
		# row inserted since the last batch commit
		if len(found) == 1:
			return found[0]
		if len(found) > 1:
			# an address two contacts share. Linking either would put one
			# customer's mail under another's name, which is the whole reason
			# nothing else in this feature matches on an address
			summary.ambiguous += 1
			return None
		summary.no_contact += 1
		return None

	def run (self, path, folder, outgoing, link_contacts = True,
				progress = None):
		'''Read the file in. progress (read, stored) is called every batch,
		for a window to show something moving over six thousand messages.

		This commits as it goes, so a caller cannot undo it by rolling back
		its own transaction: a failure part way through is meant to leave the
		work it had done, and running the file again adds only what is
		missing. scan is the call that writes nothing.'''
		box = opened(path)
		summary = Summary()
		known = self.known_message_ids()
		try:
			for key in box.keys():
				if self.cancelled:
					break
				try:
					message = box.get(key)
				except Exception:
					summary.unreadable += 1
					continue
				summary.read += 1
				try:
					self.store(message, folder, outgoing, known,
								link_contacts, summary)
				except (email.errors.MessageError, ValueError, TypeError):
					# one unreadable message does not stop a decade of them
					summary.unreadable += 1
				if summary.read % BATCH == 0:
					self.conn.commit()
					if progress != None:
						progress(summary.read, summary.stored)
			self.conn.commit()
		finally:
			box.close()
		if progress != None:
			progress(summary.read, summary.stored)
		return summary

	def store (self, message, folder, outgoing, known, link_contacts, summary):
		row = row_from(message, folder, outgoing)
		if row['message_id'] != '' and row['message_id'] in known:
			summary.already_here += 1
			return
		cursor = self.conn.cursor()
		cursor.execute("INSERT INTO mail_messages (message_id, account_id, "
							"folder, uid, uidvalidity, date_sent, subject, "
							"from_address, from_name, to_addresses, "
							"cc_addresses, outgoing, has_attachments, "
							"body_text) "
						"VALUES (%(message_id)s, %(account_id)s, %(folder)s, "
							"NULL, NULL, %(date_sent)s, %(subject)s, "
							"%(from_address)s, %(from_name)s, "
							"%(to_addresses)s, %(cc_addresses)s, "
							"%(outgoing)s, %(has_attachments)s, "
							"%(body_text)s) "
						"RETURNING id",
						dict(row, account_id = self.account_id))
		message_row_id = cursor.fetchone()[0]
		summary.stored += 1
		if row['message_id'] != '':
			known.add(row['message_id'])
		if link_contacts:
			contact_id = self.contact_for(correspondents(message, outgoing),
											summary)
			if contact_id != None:
				cursor.execute("INSERT INTO mail_links (mail_messages_id, "
									"contact_id) VALUES (%s, %s) "
								"ON CONFLICT DO NOTHING",
								(message_row_id, contact_id))
				summary.linked += 1
		cursor.close()
