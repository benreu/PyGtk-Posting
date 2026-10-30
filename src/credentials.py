# credentials.py
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

'''Passwords in the workstation's login keyring, through libsecret.

A password kept in the database is a password in every backup of it, in every
restore copy somebody made to try something out, and in reach of the SQL
window. The mail password is not kept there: settings.mail_accounts holds the
host, the port and the user name, and this module holds the secret, in the
keyring of whoever is logged in to this workstation. The cost is that mail can
only be sent from a workstation where someone has entered it once - reading
correspondence needs no password at all, because the sync writes the headers
into the database.

Secrets are keyed on service, host and user rather than on a mail_accounts row
id. One workstation connects to several databases (see db_connections in
sqlite_utils), so a row id means nothing outside the database it came from,
while user@host is the same mailbox whichever database named it. One stored
password then serves every database configured against that mailbox, and it
outlives the row being deleted and added back.

Nothing here is mail specific. 'postgres' is a service like any other, and
the database connection password is kept here too, under the host and port
from the local_settings row (postgres_host()), which is known before the
password is needed. sqlite_utils.move_passwords_to_keyring() moved the ones
that used to be in local_settings in plain text. A workstation with nothing
stored still starts: db_connection asks for the password, and keeps it here
once it has connected.

Every lookup is a blocking call onto the session bus. It is sub-millisecond
while the keyring is unlocked and open ended while it is not, because the
service puts up a prompt and waits for it to be answered - so password() is
called from the worker thread that is about to connect, never from the main
loop. The one exception is the connection password, read once at startup
before Gtk.main() runs, when there is no window yet to freeze; reconnects use
the copy held in memory. have_password() is the main-loop-safe question: it
asks the service for the item without unlocking it and without reading its
value.'''

try:
	import gi
	gi.require_version('Secret', '1')
	from gi.repository import Secret
	IMPORT_ERROR = None
except (ImportError, ValueError) as e:
	# gir1.2-secret-1 missing. Reported on use, the way main_window handles a
	# missing python3-cups, so the rest of the application still runs
	Secret = None
	IMPORT_ERROR = e

from gi.repository import GLib

SCHEMA_NAME = "org.pygtk_posting.Secret"
SERVICES = ('imap', 'smtp', 'postgres')
# what to do about a password that is not stored here, by service
MAIL_HINT = "Open Settings, Mail accounts, and press Set password."
MISSING_HINTS = {'imap': MAIL_HINT,
				'smtp': MAIL_HINT,
				'postgres': "Posting asks for it when it connects, and saves "
							"it in the login keyring once it works."}

_schema = None


class CredentialError (Exception):
	pass


def _secret ():
	if Secret is None:
		raise CredentialError("gir1.2-secret-1 is not installed, so Posting "
								"cannot read or store the password.\n\n"
								"Install it with:\n"
								"sudo apt install gir1.2-secret-1\n\n%s"
								% IMPORT_ERROR)
	return Secret

def schema ():
	'''the schema every item is stored under. NONE rather than
	DONT_MATCH_NAME, so the schema name takes part in matching and these items
	cannot be confused with anything else in the keyring.'''
	global _schema
	if _schema is None:
		secret = _secret()
		_schema = secret.Schema.new(SCHEMA_NAME, secret.SchemaFlags.NONE,
							{'service': secret.SchemaAttributeType.STRING,
							'host': secret.SchemaAttributeType.STRING,
							'user': secret.SchemaAttributeType.STRING})
	return _schema

def attributes (service, host, user):
	if service not in SERVICES:
		raise CredentialError("'%s' is not a service a password is kept for"
								% service)
	return {'service': service, 'host': host, 'user': user}

def label (service, host, user):
	"what the item is called in a keyring manager, so a person can find it"
	return "PyGtk Posting %s - %s on %s" % (service, user, host)

def postgres_host (host, port):
	'''the host a database password is kept under. The port is part of it,
	so two clusters on one machine keep separate passwords.'''
	return "%s:%s" % (host, port)

def password (service, host, user):
	'''The stored password. Raises CredentialError when there is none here or
	the keyring will not give it up.

	This blocks, and on a locked keyring it blocks until the prompt the secret
	service puts up has been answered: call it from a worker thread, never
	from the main loop.'''
	secret = _secret()
	attrs = attributes(service, host, user)
	try:
		stored = secret.password_lookup_sync(schema(), attrs, None)
	except GLib.Error as e:
		raise CredentialError("The login keyring would not give up the %s "
								"password for %s:\n%s" % (service, user,
								e.message))
	if stored is None:
		raise CredentialError("No %s password for %s has been saved on this "
								"computer.\n\n%s"
								% (service, user, MISSING_HINTS[service]))
	return stored

def store_password (service, host, user, secret_text):
	"Save a password that has already been shown to work. Blocks, as above."
	secret = _secret()
	attrs = attributes(service, host, user)
	try:
		secret.password_store_sync(schema(), attrs, secret.COLLECTION_DEFAULT,
									label(service, host, user), secret_text,
									None)
	except GLib.Error as e:
		raise CredentialError("The %s password could not be saved in the login "
								"keyring:\n%s" % (service, e.message))

def clear_password (service, host, user):
	'''Forget a stored password. Returns whether there was one. Blocks, as
	above.'''
	secret = _secret()
	try:
		return secret.password_clear_sync(schema(),
								attributes(service, host, user), None)
	except GLib.Error as e:
		raise CredentialError("The %s password could not be removed from the "
								"login keyring:\n%s" % (service, e.message))

def have_password (service, host, user):
	'''Whether a password for this service is stored on this workstation,
	without unlocking anything, without reading the secret and without putting
	up a prompt - SearchFlags.NONE opts out of all three, which is what makes
	this safe to ask from the main loop. False for a keyring that is locked or
	missing, because the question being asked is whether sending can be
	attempted at all.'''
	if Secret is None or host == '' or user == '':
		return False
	try:
		service_proxy = Secret.Service.get_sync(Secret.ServiceFlags.OPEN_SESSION,
												None)
		items = service_proxy.search_sync(schema(),
								attributes(service, host, user),
								Secret.SearchFlags.NONE, None)
	except (GLib.Error, CredentialError):
		return False
	return len(items) > 0

def locked (service, host, user):
	'''Whether the item holding this password is locked, so the difference
	between "never entered here" and "entered here, keyring locked" can be
	said out loud. False when there is no item to be locked.'''
	if Secret is None:
		return False
	try:
		service_proxy = Secret.Service.get_sync(Secret.ServiceFlags.OPEN_SESSION,
												None)
		items = service_proxy.search_sync(schema(),
								attributes(service, host, user),
								Secret.SearchFlags.NONE, None)
	except (GLib.Error, CredentialError):
		return False
	return any(item.get_locked() for item in items)
