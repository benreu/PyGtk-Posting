# imap_sync.py
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

'''Reading the mail server, so correspondence is not only what Posting sent.

Until this, mail_messages held outbound rows only: the correspondence window
could show what had been written to a customer and nothing of what they
wrote back, which is half a conversation. This fills the other half, from
whichever workstation has the password, into the database every workstation
reads.

BODY.PEEK, never BODY. BODY[...] sets the \\Seen flag, so fetching with it
would mark every message in the mailbox read - twelve thousand of them, from
inside an accounting program, on the user's phone and in their webmail, with
nothing in Posting to say it had happened and no way back. The folder is
opened readonly as well, which makes the server refuse any flag change
whatever this file asks for. That is the single most important line in here.

Nothing issues a SEARCH. This server advertises X-ICEWARP-SEARCHLIMIT, which
lets it silently return fewer results than match, and a sync that trusted a
truncated SEARCH would quietly decide it was up to date. Everything here is
SELECT plus a ranged UID FETCH, which is arithmetic rather than a question.

A timer arming a worker thread, never IDLE. IDLE means a socket held open for
29 minutes watched by an io source, and this repository has two documented
disasters of that exact shape - see the IO_NVAL and re-arm comments in
db_connection. A suspend or a NAT timeout puts an IDLE socket into the first
of them. Here each pass opens a fresh connection and closes it, so there is
no socket to die between passes: that is the whole answer to what happens
after the laptop sleeps.'''

from gi.repository import GLib
from email import message_from_bytes, policy
from email.utils import parseaddr, parsedate_to_datetime
import email.errors, imaplib, re, ssl, threading
from db_connection import DB, background_connection, broadcaster
from constants import MAIL_SYNC_LOCK_CLASSID
import credentials, emailing

POLL_SECONDS = 300
# how many messages one FETCH asks for. Big enough that 12,000 is two dozen
# round trips, small enough that an interrupted pass loses little work and
# the correspondence window fills as it goes rather than at the end
SLICE = 500
NET_TIMEOUT = 30 # imaplib's own default means no timeout at all
# how much of a message body is kept. The server has the whole thing and this
# is for reading and searching, not for archiving: without a cap one 40 MB
# message would be 40 MB in Postgres and in every pg_dump of it
BODY_TEXT_LIMIT = 65536

# what is wanted of each message. The headers, enough of the first body part
# to read, and BODYSTRUCTURE, which rides along in the same round trip and is
# the only way to know whether anything was attached without fetching it
HEADER_FIELDS = 'MESSAGE-ID DATE SUBJECT FROM TO CC'
FETCH_ITEMS = ('(UID INTERNALDATE RFC822.SIZE BODYSTRUCTURE '
				'BODY.PEEK[HEADER.FIELDS (%s)] BODY.PEEK[1]<0.%s>)'
				% (HEADER_FIELDS, BODY_TEXT_LIMIT))

# a FETCH response begins each message with its sequence number and an open
# paren; imaplib hands the whole response back as one flat list
MESSAGE_START = re.compile(rb'^\s*\d+\s+\(')
UID = re.compile(rb'\bUID\s+(\d+)')
BODYSTRUCTURE = re.compile(rb'BODYSTRUCTURE\s+(\(.*)', re.S)


def slices (last_uid, uidnext, size = SLICE):
	'''The uid ranges still to be fetched, ascending.

	Ascending rather than newest first so that last_uid stays a truthful high
	water mark at every moment: an interrupted pass resumes from it with no
	other state kept anywhere.

	uidnext is what the server says the next new message will be called, so
	uidnext - 1 is the highest that can exist. Nothing is returned when there
	is nothing new, which is the common case and has to cost one round trip
	rather than a fetch.'''
	highest = int(uidnext or 0) - 1
	start = int(last_uid or 0) + 1
	ranges = []
	while start <= highest:
		end = min(start + size - 1, highest)
		ranges.append((start, end))
		start = end + 1
	return ranges

def uidvalidity_changed (known, found):
	'''Whether the server has renumbered the folder since we last looked.

	Not knowing yet is not a change: a folder read for the first time has no
	known value, and treating that as a renumbering would throw away the
	high water mark before it was ever used.'''
	if known == None or found == None:
		return False
	return int(known) != int(found)

def messages (data):
	'''imaplib's flat FETCH response, grouped one list per message.

	A single message arrives as several entries - a (prefix, literal) tuple
	per literal it asked for, plus loose bytes closing the parenthesis - and
	nothing marks where one ends except the next one starting with its
	sequence number.'''
	grouped = []
	for part in (data or ()):
		if isinstance(part, tuple):
			prefix, literal = part[0] or b'', part[1]
		else:
			prefix, literal = part or b'', None
		if MESSAGE_START.match(prefix):
			grouped.append([])
		if grouped == []:
			continue # loose bytes before any message began
		grouped[-1].append((prefix, literal))
	# a group with no literal in it carried no message, only punctuation
	return [group for group in grouped
				if any(literal != None for _, literal in group)]

def has_attachment (bodystructure):
	'''Whether the message carried anything attached.

	Read off BODYSTRUCTURE rather than by fetching the message, because the
	point of not fetching it is that there are twelve thousand of them. This
	looks for the word rather than walking the structure: a part that says it
	is an attachment is one, and a message whose parts are only text is not.
	It can be wrong about an inline image somebody would call an attachment,
	which costs a paperclip in a list and nothing else.'''
	return b'attachment' in (bodystructure or b'').lower()

def header_row (group, folder, outgoing):
	'''One message's FETCH pieces as the values mail_messages wants.

	The headers are parsed by the email module rather than by hand, so an
	encoded word subject arrives as the words somebody wrote and a folded
	header is one line again.'''
	prefix = b''.join(part for part, _ in group)
	found = UID.search(prefix)
	if found == None:
		return None # no uid, so nothing that could be stored or resumed from
	uid = int(found.group(1))
	headers, body = b'', b''
	for part, literal in group:
		if literal == None:
			continue
		if b'HEADER' in part.upper():
			headers = literal
		else:
			body = literal
	parsed = message_from_bytes(headers, policy = policy.default)
	structure = BODYSTRUCTURE.search(prefix)
	from_name, from_address = parseaddr(str(parsed.get('From', '')))
	return {'message_id': str(parsed.get('Message-ID', '') or '').strip(),
			'folder': folder,
			'uid': uid,
			'date_sent': sent_date(parsed),
			'subject': str(parsed.get('Subject', '') or ''),
			'from_address': from_address,
			'from_name': from_name,
			'to_addresses': str(parsed.get('To', '') or ''),
			'cc_addresses': str(parsed.get('Cc', '') or ''),
			'outgoing': outgoing,
			'has_attachments': has_attachment(
								structure.group(1) if structure else b''),
			'body_text': body_text(body)}

def sent_date (parsed):
	"when the message says it was sent, or None when it has no usable Date"
	header = parsed.get('Date')
	if header == None:
		return None
	stamp = getattr(header, 'datetime', None)
	if stamp != None:
		return stamp
	try:
		return parsedate_to_datetime(str(header))
	except (TypeError, ValueError):
		return None

def body_text (raw):
	'''The body as something readable, capped.

	The fetch asked for a prefix of the first body part, so this is usually
	the message's own text; it may be cut off mid sentence, and it may be
	base64 of something that was never text. Either way it is never allowed
	to raise: a message that cannot be decoded is still a message that
	arrived, and its headers are worth keeping.'''
	if not raw:
		return ''
	try:
		text = raw.decode('utf-8')
	except UnicodeDecodeError:
		text = raw.decode('latin-1', 'replace')
	return text[:BODY_TEXT_LIMIT]


class Watcher (object):
	'''The timer, and the one pass it arms.

	poll always returns True, whatever happened: a timer handler that returns
	anything false is removed, and a sync that stopped for good the first time
	the server was unreachable would be worse than one that says so and tries
	again in five minutes.'''

	def __init__ (self):
		self.running = False

	def start (self):
		GLib.timeout_add_seconds(POLL_SECONDS, self.poll)
		# once soon after the program opens, so the first look does not wait
		# five minutes, and late enough not to be part of startup
		GLib.timeout_add_seconds(10, self.first_poll)

	def first_poll (self):
		self.poll()
		return False # the repeating timer above carries on from here

	def poll (self):
		try:
			self.begin()
		except Exception as e:
			# nothing from a mail server may stop the timer
			print("imap_sync: %s" % e)
		return True

	def begin (self):
		'''Start a pass, on the main thread. Reads the account from the shared
		connection and hands it to a thread, which touches no database
		connection of ours: a worker on the shared one segfaults the program
		rather than raising.'''
		if self.running:
			return # last pass has not finished; it will be asked again in five
		acct = emailing.account()
		if acct == None or acct.imap_host == '' or acct.imap_user == '':
			return
		folders = self.wanted_folders(acct)
		if folders == []:
			return # nothing is turned on, so nothing to ask the server
		self.running = True
		threading.Thread(target = self.work, args = (acct, folders),
							daemon = True).start()

	def wanted_folders (self, acct):
		"the folders turned on for this account, and where each got to"
		cursor = DB.cursor()
		cursor.execute("SELECT folder, uidvalidity, last_uid "
						"FROM settings.mail_folders "
						"WHERE account_id = %s AND sync = True ORDER BY folder",
						(acct.id,))
		folders = cursor.fetchall()
		cursor.close()
		DB.rollback()
		return folders

	def work (self, acct, folders):
		try:
			secret = credentials.password('imap', acct.imap_host,
											acct.imap_user)
			with background_connection() as conn:
				if not self.take_lock(conn, acct):
					return # another workstation is doing this pass
				mailbox = emailing.imap_connection(acct, secret)
				try:
					for folder, uidvalidity, last_uid in folders:
						self.read_folder(conn, mailbox, acct, folder,
											uidvalidity, last_uid)
				finally:
					try:
						mailbox.logout()
					except Exception:
						pass
		except Exception as e:
			print("imap_sync: %s" % e)
		finally:
			# whatever happened, the next tick must be able to start. Without
			# this a single failure leaves the flag set and nothing ever syncs
			# again for the life of the program
			self.running = False

	def take_lock (self, conn, acct):
		'''One workstation reads the server per pass. Taken on this
		connection and given back when it closes, rather than held for the
		life of the program: a session lock would make whichever workstation
		booted first the only one that ever syncs.'''
		cursor = conn.cursor()
		cursor.execute("SELECT pg_try_advisory_lock(%s, %s)",
						(MAIL_SYNC_LOCK_CLASSID, acct.id))
		got = cursor.fetchone()[0]
		cursor.close()
		conn.rollback()
		return got

	def read_folder (self, conn, mailbox, acct, folder, uidvalidity, last_uid):
		found, uidnext = self.examine(mailbox, folder)
		if found == None:
			return
		if uidvalidity_changed(uidvalidity, found):
			# the server has renumbered it. Read it again from the start, and
			# leave the rows already stored alone: they are the
			# correspondence, and message_id ties the generations together
			last_uid = 0
		ranges = slices(last_uid, uidnext)
		if ranges == []:
			# nothing new, which is the common case. The mark is still written
			# so that the numbering is recorded the first time a folder is
			# looked at, so a folder the server renumbered to empty does not
			# stay reset on every pass forever, and so last_synced means what
			# it says rather than only "last time something arrived"
			self.touch(conn, acct, folder, found, last_uid)
			return
		for start, end in ranges:
			rows = self.fetch(mailbox, folder, start, end,
								outgoing = folder == acct.sent_folder)
			self.store(conn, acct, folder, found, rows, end)

	def examine (self, mailbox, folder):
		'''Open the folder readonly and say what it is numbered and how far it
		goes. EXAMINE rather than SELECT, so the server itself refuses any
		flag change: BODY.PEEK is what keeps messages unread, and this is the
		second lock on the same door.'''
		result, _ = mailbox.select('"%s"' % folder, readonly = True)
		if result != 'OK':
			print("imap_sync: %s would not open %s: %s"
					% (mailbox.host, folder, result))
			return None, None
		return (self.untagged(mailbox, 'UIDVALIDITY'),
				self.untagged(mailbox, 'UIDNEXT'))

	def untagged (self, mailbox, name):
		result, data = mailbox.response(name)
		if not data or data[0] == None:
			return None
		try:
			return int(data[0])
		except (TypeError, ValueError):
			return None

	def fetch (self, mailbox, folder, start, end, outgoing):
		result, data = mailbox.uid('FETCH', '%s:%s' % (start, end),
									FETCH_ITEMS)
		if result != 'OK':
			raise imaplib.IMAP4.error("%s would not fetch %s:%s from %s: %s"
										% (mailbox.host, start, end, folder,
											result))
		rows = []
		for group in messages(data):
			try:
				row = header_row(group, folder, outgoing)
			except (email.errors.MessageError, ValueError, TypeError) as e:
				# one unreadable message does not stop the slice, and the uid
				# is not recorded, so it will be offered again next time
				print("imap_sync: %s in %s: %s" % (folder, start, e))
				continue
			if row != None:
				rows.append(row)
		return rows

	def touch (self, conn, acct, folder, uidvalidity, last_uid):
		"record that the folder was looked at, without anything having arrived"
		cursor = conn.cursor()
		cursor.execute("UPDATE settings.mail_folders "
							"SET uidvalidity = %s, last_uid = %s, "
								"last_synced = now() "
						"WHERE account_id = %s AND folder = %s",
						(uidvalidity, last_uid, acct.id, folder))
		conn.commit()
		cursor.close()
		# deliberately no notify: nothing arrived, so there is nothing for a
		# correspondence window to go and read

	def store (self, conn, acct, folder, uidvalidity, rows, through_uid):
		'''Write a slice and move the high water mark, in one transaction.

		ON CONFLICT DO NOTHING on the server copy index, which is what makes
		a folder safe to re-enumerate: a message already stored is skipped
		rather than being a constraint violation that aborts the pass.'''
		cursor = conn.cursor()
		for row in rows:
			cursor.execute("INSERT INTO mail_messages (message_id, account_id, "
								"folder, uid, uidvalidity, date_sent, subject, "
								"from_address, from_name, to_addresses, "
								"cc_addresses, outgoing, has_attachments, "
								"body_text) "
							"VALUES (%(message_id)s, %(account_id)s, "
								"%(folder)s, %(uid)s, %(uidvalidity)s, "
								"%(date_sent)s, %(subject)s, %(from_address)s, "
								"%(from_name)s, %(to_addresses)s, "
								"%(cc_addresses)s, %(outgoing)s, "
								"%(has_attachments)s, %(body_text)s) "
							"ON CONFLICT (account_id, folder, uidvalidity, uid) "
								"WHERE uid IS NOT NULL DO NOTHING",
							dict(row, account_id = acct.id,
									uidvalidity = uidvalidity))
		cursor.execute("UPDATE settings.mail_folders "
							"SET uidvalidity = %s, last_uid = %s, "
								"last_synced = now() "
						"WHERE account_id = %s AND folder = %s",
						(uidvalidity, through_uid, acct.id, folder))
		# one per slice, not one per row: a notify per message would be 12,000
		# of them on the first pass, each with its own payload so the database
		# cannot collapse them. This is why mail_messages has no trigger
		cursor.execute("SELECT pg_notify('mail_messages', '')")
		conn.commit()
		cursor.close()


_watcher = None


def start_mail_watcher ():
	'''Begin syncing, if this workstation can. Guarded three ways, each
	returning quietly: without the password check a workstation where nobody
	entered one would put a keyring prompt on screen every five minutes
	forever.'''
	global _watcher
	if _watcher != None:
		return _watcher
	acct = emailing.account()
	if acct == None or acct.imap_host == '' or acct.imap_user == '':
		return None
	try:
		if not credentials.have_password('imap', acct.imap_host,
											acct.imap_user):
			return None
	except credentials.CredentialError:
		# no libsecret here: mail can be read on the workstations that have it
		return None
	_watcher = Watcher()
	_watcher.start()
	return _watcher
