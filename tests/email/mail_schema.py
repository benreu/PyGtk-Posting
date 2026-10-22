# mail_schema.py
#
# The schema the mail tests need, and nothing else needs. It used to sit in
# the shared harness, where every inventory test paid for it and nobody
# reading the harness could tell who it was for.
#
# The three blocks are the DDL of --0.7.35, --0.7.36 and --0.7.37, applied
# inside the test transaction so the suite runs against a copy that has not
# had the upgrade yet and the database is left as it was. Each is asked for
# separately because the three upgrades land one at a time: a copy can have
# the account table and not the messages one.
#
# Unlike the harness's own probes, these are asked from inside the test
# transaction on the first test that wants them, not at import. The harness
# asks its own before FakeDB takes the savepoint every test rolls back to;
# anything asking afterwards would have to give a read transaction back, and
# the rollback that does it would discard that savepoint. The answer is cached
# because the DDL is rolled back with each test, so a copy that was behind
# stays behind.

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..'))

import harness

PROBE = """
SELECT NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE
			(table_schema, table_name) = ('settings', 'mail_accounts')),
	NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE
			(table_schema, table_name) = ('settings', 'email_messages')),
	NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE
			(table_schema, table_name) = ('public', 'mail_messages'))
"""

# 0.7.35, the mail account the Settings page edits and emailing.account () reads.
# There is deliberately no password column here or in the migration: the
# password is in the workstation's login keyring through credentials.py, so
# nothing in this database - or in a dump of it, or in this restore copy - can
# leak it.
#
# The CHECK and the one-active index the migration carries are kept, unlike
# the harness's own blocks, which drop the constraints they can: all three
# tables here are new, so validating a constraint on one scans nothing and
# locks nothing any other test wants, and both of these are what the settings
# page is tested against
PENDING_MAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings.mail_accounts (
	id serial PRIMARY KEY,
	name varchar NOT NULL,
	imap_host varchar NOT NULL DEFAULT '',
	imap_port int NOT NULL DEFAULT 993,
	imap_user varchar NOT NULL DEFAULT '',
	smtp_host varchar NOT NULL DEFAULT '',
	smtp_port int NOT NULL DEFAULT 587,
	smtp_user varchar NOT NULL DEFAULT '',
	smtp_security varchar NOT NULL DEFAULT 'starttls',
	from_name varchar NOT NULL DEFAULT '',
	from_address varchar NOT NULL DEFAULT '',
	sent_folder varchar NOT NULL DEFAULT '',
	active boolean NOT NULL DEFAULT True,
	date_created date NOT NULL DEFAULT now()
);
ALTER TABLE settings.mail_accounts
	DROP CONSTRAINT IF EXISTS mail_accounts_smtp_security_known;
ALTER TABLE settings.mail_accounts
	ADD CONSTRAINT mail_accounts_smtp_security_known
		CHECK (smtp_security IN ('starttls', 'tls', 'none'));
CREATE UNIQUE INDEX IF NOT EXISTS mail_accounts_one_active
	ON settings.mail_accounts (active) WHERE active;
"""

# 0.7.36, the wording an invoice is emailed with. The real migration seeds the
# standard message inside the same guard that creates the table, so that a
# re-run cannot put it back under somebody who rewrote it; the seed is left
# off here because every test that reads a message sets the one it wants, and
# a fixture row nobody asked for is a precondition waiting to be inherited
PENDING_MAIL_MESSAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings.email_messages (
	id serial PRIMARY KEY,
	name varchar NOT NULL UNIQUE,
	subject varchar NOT NULL DEFAULT '',
	body varchar NOT NULL DEFAULT '',
	date_created date NOT NULL DEFAULT now()
);
"""

# 0.7.37, the row saying a message went. The indexes come with it: the
# partial unique one on the server copy is the whole reason the sync can
# insert a slice twice, so a copy of the table without it would be a
# different table from the one that ships. ShippedSchemaTest asserts this
# block and the migration's really do agree
PENDING_MAIL_RECORD_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.mail_messages (
	id bigserial PRIMARY KEY,
	message_id varchar NOT NULL DEFAULT '',
	account_id integer REFERENCES settings.mail_accounts(id)
		ON UPDATE RESTRICT ON DELETE SET NULL,
	folder varchar NOT NULL DEFAULT '',
	uid bigint,
	uidvalidity bigint,
	date_sent timestamptz,
	subject varchar NOT NULL DEFAULT '',
	from_address varchar NOT NULL DEFAULT '',
	from_name varchar NOT NULL DEFAULT '',
	to_addresses varchar NOT NULL DEFAULT '',
	cc_addresses varchar NOT NULL DEFAULT '',
	outgoing boolean NOT NULL DEFAULT False,
	has_attachments boolean NOT NULL DEFAULT False,
	raw_message bytea,
	body_text varchar NOT NULL DEFAULT '',
	date_inserted timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS mail_messages_server_copy
	ON public.mail_messages (account_id, folder, uidvalidity, uid)
	WHERE uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS mail_messages_message_id
	ON public.mail_messages (message_id);
CREATE INDEX IF NOT EXISTS mail_messages_from_address
	ON public.mail_messages (from_address);
CREATE INDEX IF NOT EXISTS mail_messages_date_sent
	ON public.mail_messages (date_sent DESC);
"""

_pending = None # asked once, by the first test that needs these tables


def apply (case):
	'''Bring the mail schema up to what the code expects, inside the test
	transaction so it is rolled back with everything else. Every statement is
	a no-op once the copy has had the upgrade.'''
	global _pending
	if _pending is None:
		case.cursor.execute(PROBE)
		_pending = case.cursor.fetchone()
	blocks = (PENDING_MAIL_SCHEMA, PENDING_MAIL_MESSAGE_SCHEMA,
				PENDING_MAIL_RECORD_SCHEMA)
	for needed, sql in zip(_pending, blocks):
		if needed:
			case.cursor.execute(sql)
	if any(_pending):
		# move the savepoint past the DDL, for the reason apply_pending_schema
		# gives: a window doing the usual DB.rollback () after a read would
		# otherwise undo the tables just created
		case.DB.commit()


class MailTestCase (harness.DBTestCase):
	"a DBTestCase with the mail tables in place"

	def setUp (self):
		harness.DBTestCase.setUp(self)
		apply(self)
