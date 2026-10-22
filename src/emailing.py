# emailing.py
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

'''Sending mail from Posting itself, over SMTP.

What this replaces handed the job to another program - xdg-email, or
thunderbird -compose - and then knew nothing. Whether the message was ever
sent, whether the address was even usable, whether the attachment existed:
none of it came back, so a failed send looked exactly like a successful one,
and nothing in the database recorded that anything had gone out.

Attachments are passed as (filename, bytes), never as paths. The documents
being mailed are already in the database - invoices.pdf_data,
documents.pdf_data - and taking the bytes means the attachment is provably
what was posted rather than whatever is at a /tmp path by the time the mail
goes. The old path was keyed on the document's name, so two windows open on
the same customer wrote the same file and the second overwrote the first.

Every send happens on a worker thread. An SMTP conversation carrying a 350 KB
attachment to a remote host takes as long as it takes, and the password lookup
in front of it can block on a locked keyring, so neither belongs in the main
loop. The thread touches no database connection at all: it is handed
everything it needs, and the row recording the send is written back on the
main thread from the idle callback.'''

from gi.repository import Gtk, GLib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr, make_msgid
import mimetypes, re, smtplib, ssl, threading
from db_connection import DB
import credentials

NET_TIMEOUT = 30 # seconds. smtplib's own default means "no timeout at all"
# Most servers refuse somewhere between 10 and 25 MB, and refuse it after the
# whole upload. Saying so before connecting beats a 552 half a minute later
ATTACHMENT_CAP = 20 * 1024 * 1024


class MailError (Exception):
	pass


class MailAuthError (MailError):
	'''The server was reached and refused the user name or the password.

	Told apart from every other MailError on purpose. A password that failed
	this way is known to be wrong and must never be stored, where one that
	could not be checked - the server was down, the port was wrong, the TLS
	settings did not match - has not been shown to be anything, and refusing
	to store it leaves a user who cannot reach their server unable to set a
	password at all.'''
	pass


class Account (object):
	"a row of settings.mail_accounts, with no password in it"
	pass


def account ():
	'''The active mail account, or None when none is set up. Reads the shared
	connection, so main thread only - hand the result to a worker thread.'''
	cursor = DB.cursor()
	cursor.execute("SELECT id, name, imap_host, imap_port, imap_user, "
						"smtp_host, smtp_port, smtp_user, smtp_security, "
						"from_name, from_address, sent_folder "
					"FROM settings.mail_accounts WHERE active = True")
	row = cursor.fetchone()
	cursor.close()
	DB.rollback()
	if row is None:
		return None
	acct = Account()
	(acct.id, acct.name, acct.imap_host, acct.imap_port, acct.imap_user,
		acct.smtp_host, acct.smtp_port, acct.smtp_user, acct.smtp_security,
		acct.from_name, acct.from_address, acct.sent_folder) = row
	return acct

def missing_account_message ():
	return ("No mail account is set up, so nothing can be sent.\n\n"
			"Open Settings, Mail accounts, fill in the server and press "
			"Set password.")

def valid_address (text):
	'''Whether text holds one address that can be sent to. contacts.email is
	'' when nobody filled it in - never null - so the blank case is the common
	one and is what this is mostly asked about.'''
	name, addr = parseaddr(text or '')
	if addr == '' or '@' not in addr:
		return False
	local, _, domain = addr.rpartition('@')
	if local == '' or domain == '' or '.' not in domain:
		return False
	return not any(c.isspace() for c in addr)

def address (name, addr):
	'''One recipient, correctly formed. The old code built these by hand as
	"%s < %s >", which puts spaces inside the angle brackets and is not an
	address; one version also wrapped it in shell quotes that never reached a
	shell. formataddr also quotes a name containing a comma, which would
	otherwise read as two recipients.'''
	return formataddr((name or '', (addr or '').strip()))

def build (acct, to, subject, body, attachments = (), cc = ()):
	'''The message to send. to and cc are lists of formed addresses, as
	address() returns; attachments is a list of (filename, bytes).'''
	recipients = [a for a in to if valid_address(a)]
	if not recipients:
		raise MailError("There is no email address to send to.")
	if acct.from_address == '':
		raise MailError("The mail account has no from address.\n\n"
						"Open Settings, Mail accounts, and fill it in.")
	total = sum(len(data) for name, data in attachments)
	if total > ATTACHMENT_CAP:
		raise MailError("The attachments come to %s MB, which is more than "
						"most mail servers accept (%s MB).\n\nSend fewer "
						"documents, or send them in more than one message."
						% (total // (1024 * 1024),
							ATTACHMENT_CAP // (1024 * 1024)))
	message = EmailMessage()
	message['From'] = address(acct.from_name, acct.from_address)
	message['To'] = ', '.join(recipients)
	if cc:
		message['Cc'] = ', '.join([a for a in cc if valid_address(a)])
	message['Subject'] = subject
	# ours, and generated here rather than by the server, so the row recording
	# the send can be tied to the copy the server files in Sent
	message['Message-ID'] = make_msgid()
	message.set_content(body)
	for name, data in attachments:
		guessed = mimetypes.guess_type(name)[0] or 'application/octet-stream'
		maintype, _, subtype = guessed.partition('/')
		message.add_attachment(data, maintype = maintype, subtype = subtype,
								filename = name)
	return message

def send (acct, secret, message):
	'''Hand the message to the server. Raises MailError, having said what the
	server said: everything here is reported, nothing is swallowed.'''
	if acct.smtp_host == '':
		raise MailError("The mail account has no SMTP server.\n\n"
						"Open Settings, Mail accounts, and fill it in.")
	try:
		if acct.smtp_security == 'tls':
			server = smtplib.SMTP_SSL(acct.smtp_host, acct.smtp_port,
										timeout = NET_TIMEOUT)
		else:
			server = smtplib.SMTP(acct.smtp_host, acct.smtp_port,
									timeout = NET_TIMEOUT)
	except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
		raise MailError("%s:%s could not be reached:\n%s"
						% (acct.smtp_host, acct.smtp_port, e))
	try:
		if acct.smtp_security == 'starttls':
			server.starttls(context = ssl.create_default_context())
			server.ehlo()
		if acct.smtp_user != '':
			server.login(acct.smtp_user, secret)
		server.send_message(message)
	except smtplib.SMTPAuthenticationError as e:
		raise MailAuthError("%s would not accept the password for %s:\n%s"
						% (acct.smtp_host, acct.smtp_user, _said(e)))
	except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
		raise MailError("The server did not accept the message:\n%s" % _said(e))
	finally:
		try:
			server.quit()
		except (OSError, smtplib.SMTPException, ssl.SSLError):
			# the message is already gone by here; a server that hangs up
			# rudely afterwards has not unsent it
			pass

def _said (error):
	"the server's own words out of an smtplib error, which arrive as bytes"
	message = getattr(error, 'smtp_error', None)
	if isinstance(message, bytes):
		return message.decode('utf-8', 'replace').strip()
	return str(error)

def show_message (parent, message_type, text):
	dialog = Gtk.MessageDialog(message_type = message_type,
								buttons = Gtk.ButtonsType.CLOSE)
	if parent is not None and parent.get_realized():
		# a window already destroyed is not a parent any more, and asking it
		# to be one puts a warning on stderr instead of a dialog on screen
		dialog.set_transient_for(parent)
	dialog.set_markup(GLib.markup_escape_text(text))
	dialog.run()
	dialog.destroy()

def send_and_report (parent, to, subject, body, attachments = (), cc = (),
						link = None, on_done = None):
	'''Send on a worker thread and say how it went.

	to and cc are lists of formed addresses; attachments is a list of
	(filename, bytes). link names the record the message belongs to, as a
	(column, id) pair such as ('invoice_id', 1234) - nothing is written for it
	until mail_links exists, and it is taken now so that adding a kind of
	record later changes no call site.

	on_done (error) runs on the main thread once the result has been shown,
	and is given None when the message went and whatever went wrong when it
	did not. A window that would otherwise close itself the instant Post was
	pressed hands its closing in here, because closing before the thread
	answers leaves the failure nowhere to be shown and an unsent invoice
	looking sent. It is handed the outcome because not every window wants the
	same thing from it: a posted invoice is finished either way, while a
	message somebody typed must stay on screen when it did not go, so it can
	be put right and sent again rather than retyped.

	Returns whether sending was started. When it returns False nothing was
	sent, the reason has already been shown, and on_done has NOT been run -
	the caller still owns its window and should carry on as it would have
	without sending. Running it here as well would mean a window destroyed
	twice on the paths that fail before the thread starts.'''
	acct = account()
	if acct is None:
		show_message(parent, Gtk.MessageType.ERROR, missing_account_message())
		return False
	try:
		message = build(acct, to, subject, body, attachments, cc)
	except MailError as e:
		show_message(parent, Gtk.MessageType.ERROR,
						"The email was not sent:\n%s" % e)
		return False

	def report (error, not_filed):
		if error is None:
			sent = "Sent to %s." % message['To']
			if not_filed is not None:
				# a copy that did not get filed is worth saying, but it is not
				# a failed send: the message has gone and cannot be unsent
				sent += ("\n\nThe copy could not be filed in %s:\n%s"
							% (acct.sent_folder or 'the Sent folder',
								not_filed))
			show_message(parent, Gtk.MessageType.INFO, sent)
		else:
			show_message(parent, Gtk.MessageType.ERROR,
							"The email was not sent:\n%s" % error)
		if on_done is not None:
			on_done(error)
		return False # idle_add: once, never re-armed

	def work ():
		error, not_filed = None, None
		try:
			secret = ''
			if acct.smtp_user != '':
				secret = credentials.password('smtp', acct.smtp_host,
												acct.smtp_user)
			send(acct, secret, message)
		except (MailError, credentials.CredentialError) as e:
			error = e
		except Exception as e:
			# an unexpected failure on a thread would otherwise be a traceback
			# on stderr and a window that sits there looking like it worked
			error = e
		if error is None and acct.imap_host != '':
			# only now: filing a copy of a message that never went would be a
			# record of something that did not happen
			try:
				append_to_sent(acct, message)
			except (MailError, credentials.CredentialError) as e:
				not_filed = e
			except Exception as e:
				not_filed = e
		GLib.idle_add(report, error, not_filed)

	threading.Thread(target = work, daemon = True).start()
	return True


def verify_login (acct, secret):
	'''Log in to the account's servers with this password and raise MailError
	saying why if either refuses. Blocks, so worker thread only.

	A password is tested before it is stored, never after, so "a password is
	saved on this computer" always means one that worked at least once - the
	same reason the Zebra printer page tests the form rather than the saved
	row.'''
	if acct.smtp_host == '' and acct.imap_host == '':
		raise MailError("Fill in a server first.")
	if acct.smtp_host != '':
		if acct.smtp_security == 'tls':
			opener = lambda: smtplib.SMTP_SSL(acct.smtp_host, acct.smtp_port,
												timeout = NET_TIMEOUT)
		else:
			opener = lambda: smtplib.SMTP(acct.smtp_host, acct.smtp_port,
											timeout = NET_TIMEOUT)
		try:
			server = opener()
		except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
			raise MailError("%s:%s could not be reached:\n%s"
							% (acct.smtp_host, acct.smtp_port, e))
		try:
			if acct.smtp_security == 'starttls':
				server.starttls(context = ssl.create_default_context())
				server.ehlo()
			if acct.smtp_user != '':
				server.login(acct.smtp_user, secret)
		except smtplib.SMTPAuthenticationError as e:
			raise MailAuthError("%s would not accept the login for %s:\n%s"
							% (acct.smtp_host, acct.smtp_user, _said(e)))
		except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
			raise MailError("%s could not be asked whether the login for %s "
							"works:\n%s"
							% (acct.smtp_host, acct.smtp_user, _said(e)))
		finally:
			try:
				server.quit()
			except (OSError, smtplib.SMTPException, ssl.SSLError):
				pass
	if acct.imap_host != '' and acct.imap_user != '':
		import imaplib
		try:
			mailbox = imaplib.IMAP4_SSL(acct.imap_host, acct.imap_port,
										timeout = NET_TIMEOUT)
		except (OSError, imaplib.IMAP4.error, ssl.SSLError) as e:
			raise MailError("%s:%s could not be reached:\n%s"
							% (acct.imap_host, acct.imap_port, e))
		try:
			mailbox.login(acct.imap_user, secret)
		except imaplib.IMAP4.error as e:
			# the server answered and said no; a socket or TLS failure below
			# never got that far
			raise MailAuthError("%s would not accept the login for %s:\n%s"
							% (acct.imap_host, acct.imap_user, e))
		except (OSError, ssl.SSLError) as e:
			raise MailError("%s could not be asked whether the login for %s "
							"works:\n%s" % (acct.imap_host, acct.imap_user, e))
		finally:
			try:
				mailbox.logout()
			except (OSError, imaplib.IMAP4.error, ssl.SSLError):
				pass


class PasswordDialog (Gtk.Dialog):
	'''Asks for the mail password. It only collects it: the caller tests it
	against the servers on a worker thread and stores it only if it worked,
	so a password that does not work is never written to the keyring.'''

	def __init__ (self, parent, acct):
		Gtk.Dialog.__init__(self, title = "Mail password",
							transient_for = parent, modal = True)
		self.add_button("Cancel", Gtk.ResponseType.CANCEL)
		self.save_button = self.add_button("Save", Gtk.ResponseType.OK)
		self.set_default_response(Gtk.ResponseType.OK)

		grid = Gtk.Grid(row_spacing = 6, column_spacing = 12, border_width = 10)
		self.get_content_area().pack_start(grid, True, True, 0)
		self.password_entry = Gtk.Entry(activates_default = True,
										visibility = False, width_chars = 28)
		self.password_entry.connect('changed', self.password_changed)
		user = acct.smtp_user or acct.imap_user
		host = acct.smtp_host or acct.imap_host
		rows = [("User", Gtk.Label(label = user or '(none)')),
				("Server", Gtk.Label(label = host or '(none)')),
				("Password", self.password_entry)]
		for row, (caption, widget) in enumerate(rows):
			grid.attach(Gtk.Label(label = caption, xalign = 1), 0, row, 1, 1)
			widget.set_halign(Gtk.Align.FILL if widget is self.password_entry
												else Gtk.Align.START)
			grid.attach(widget, 1, row, 1, 1)
		note = Gtk.Label(label = "Kept in this computer's login keyring, never "
								"in the database.\nIt is checked against the "
								"server before it is saved.", xalign = 0)
		note.get_style_context().add_class('dim-label')
		grid.attach(note, 0, len(rows), 2, 1)
		self.password_changed(self.password_entry)

	def password_changed (self, entry):
		self.save_button.set_sensitive(entry.get_text() != '')

	def get_password (self):
		"the password typed, or None when the user canceled"
		self.show_all()
		response = self.run()
		password = self.password_entry.get_text()
		self.destroy()
		return password if response == Gtk.ResponseType.OK else None


# A folder listing line: (\HasNoChildren \Sent) "/" "Sent"
LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+'
						rb'(?P<delimiter>"[^"]*"|NIL)\s+'
						rb'(?P<name>"(?:[^"\\]|\\.)*"|\S+)\s*$')
# the server's answer to a successful APPEND when it speaks UIDPLUS
APPENDUID = re.compile(rb'APPENDUID\s+(\d+)\s+(\d+)')
# what a Sent folder is called when the server does not say which one it is,
# best first
SENT_NAMES = ('sent', 'sent items', 'sent messages', 'sent mail',
				'inbox.sent', '[gmail]/sent mail')


def parse_list_line (line):
	'''One line of a LIST response as (flags, name), or None when it is not
	one. Server replies are bytes and the name may be quoted and escaped.'''
	if not isinstance(line, bytes):
		line = str(line).encode()
	match = LIST_LINE.match(line.strip())
	if match == None:
		return None
	name = match.group('name').decode('utf-8', 'replace')
	if name.startswith('"') and name.endswith('"'):
		name = name[1:-1].replace('\\"', '"').replace('\\\\', '\\')
	flags = match.group('flags').decode('ascii', 'replace').split()
	return flags, name

def likely_sent_folder (entries):
	'''Which of (flags, name) holds sent mail, or '' when none of them
	obviously does.

	A server that says which one it is, by flagging it \\Sent, is believed
	over any name: the folder is called different things in different
	languages and under different namespaces, and guessing wrong files
	everything somewhere nobody looks.'''
	for flags, name in entries:
		if any(flag.lower() == '\\sent' for flag in flags):
			return name
	for wanted in SENT_NAMES:
		for flags, name in entries:
			if name.lower() == wanted:
				return name
	return ''

def appenduid (response):
	'''The uid the server filed an APPEND under, as (uidvalidity, uid), or
	None when it did not say.

	Not saying is not a failure. The copy is filed either way; only knowing
	where is lost, so this never raises - an unparseable answer is treated as
	"appended, uid unknown".'''
	for part in (response or ()):
		if not isinstance(part, bytes):
			part = str(part).encode()
		match = APPENDUID.search(part)
		if match != None:
			return int(match.group(1)), int(match.group(2))
	return None

def imap_connection (acct, secret):
	"logged in, for the caller to use and log out of"
	import imaplib
	try:
		mailbox = imaplib.IMAP4_SSL(acct.imap_host, acct.imap_port,
									timeout = NET_TIMEOUT)
	except (OSError, imaplib.IMAP4.error, ssl.SSLError) as e:
		raise MailError("%s:%s could not be reached:\n%s"
						% (acct.imap_host, acct.imap_port, e))
	try:
		if acct.imap_user != '':
			mailbox.login(acct.imap_user, secret)
	except imaplib.IMAP4.error as e:
		mailbox.logout()
		raise MailAuthError("%s would not accept the login for %s:\n%s"
							% (acct.imap_host, acct.imap_user, e))
	except (OSError, ssl.SSLError) as e:
		mailbox.logout()
		raise MailError("%s could not be asked whether the login for %s "
						"works:\n%s" % (acct.imap_host, acct.imap_user, e))
	return mailbox

def list_folders (acct, secret):
	"Every folder on the server, as (flags, name). Blocks; worker thread only."
	mailbox = imap_connection(acct, secret)
	try:
		result, lines = mailbox.list()
		if result != 'OK':
			raise MailError("%s would not list its folders: %s"
							% (acct.imap_host, result))
		entries = [parse_list_line(line) for line in (lines or ())]
		return [entry for entry in entries if entry != None]
	finally:
		try:
			mailbox.logout()
		except Exception:
			pass

def append_to_sent (acct, message):
	'''File a copy of what was just sent in the account's Sent folder, and
	return where it was filed as (uidvalidity, uid), or None.

	Without this a message sent from Posting exists nowhere but in the
	recipient's mailbox: it is missing from Sent on the phone, in webmail and
	in Thunderbird, so the record of what was sent to a customer depends on
	which program it was sent from.

	It is marked \\Seen, because nobody needs to be told they have unread
	mail they wrote themselves. Blocks; worker thread only.'''
	import imaplib, time
	if acct.imap_host == '':
		raise MailError("The mail account has no IMAP server, so there is "
						"nowhere to file a copy.\n\nOpen Settings, Mail "
						"accounts, and fill one in.")
	if acct.sent_folder == '':
		raise MailError("The mail account has no Sent folder set.\n\nOpen "
						"Settings, Mail accounts, press Test, and choose one.")
	secret = ''
	if acct.imap_user != '':
		secret = credentials.password('imap', acct.imap_host, acct.imap_user)
	mailbox = imap_connection(acct, secret)
	try:
		# CRLF, which is what RFC 3501 says a literal is in; as_bytes() uses
		# the policy's own linesep, which is a bare newline, and a server
		# entitled to refuse that would refuse every copy
		data = message.as_bytes(policy = message.policy.clone(linesep = '\r\n'))
		result, response = mailbox.append(acct.sent_folder, '\\Seen',
							imaplib.Time2Internaldate(time.time()), data)
		if result != 'OK':
			raise MailError("%s would not file the copy in %s: %s"
							% (acct.imap_host, acct.sent_folder, result))
		return appenduid(response)
	except imaplib.IMAP4.error as e:
		raise MailError("%s would not file the copy in %s:\n%s"
						% (acct.imap_host, acct.sent_folder, e))
	finally:
		try:
			mailbox.logout()
		except Exception:
			# the copy is filed by now; a server that hangs up rudely
			# afterwards has not unfiled it
			pass
