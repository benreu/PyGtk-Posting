# harness.py
#
# Shared setup for the inventory tests. They run against the restore copy
# 'silrep_restore' only, inside one transaction that is rolled back in tearDown,
# so the database is left unchanged. The password is read from the environment.

import os, sys, unittest
import psycopg2

SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
sys.path.insert(0, os.path.abspath(SRC))

import constants
constants.cur_dir = os.path.abspath(os.path.join(SRC, '..'))
constants.set_directories() # ui_directory must point at the checkout

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

TEST_DB = 'silrep_restore' # never point these tests at another database
HOST = '192.168.50.120'

class FakeDB:
	'''psycopg2 connection that never really commits: commit() moves a savepoint
	forward and rollback() returns to it, so the application sees normal
	commit/rollback behaviour while real_rollback() discards the whole test.
	Test setup data must be followed by commit() to survive an application rollback'''
	def __init__(self, conn):
		self.conn = conn
		self.execute("SAVEPOINT test_sp")
	def execute(self, sql):
		cursor = self.conn.cursor()
		cursor.execute(sql)
		cursor.close()
	def cursor(self, *args, **kwargs):
		return self.conn.cursor(*args, **kwargs)
	def commit(self):
		self.execute("RELEASE SAVEPOINT test_sp")
		self.execute("SAVEPOINT test_sp")
	def rollback(self):
		self.execute("ROLLBACK TO SAVEPOINT test_sp")
	def real_rollback(self):
		self.conn.rollback()
		self.execute("SAVEPOINT test_sp")

def connect():
	password = os.environ.get('POSTING_TEST_DB_PASSWORD')
	if password is None:
		raise unittest.SkipTest('POSTING_TEST_DB_PASSWORD not set')
	conn = psycopg2.connect(dbname = TEST_DB, host = HOST, port = 5432,
							user = 'postgres', password = password,
							connect_timeout = 5)
	cursor = conn.cursor()
	cursor.execute("SELECT current_database()")
	assert cursor.fetchone()[0] == TEST_DB
	cursor.close()
	return conn

class FakeBroadcaster:
	'''start_broadcaster () is never called in the tests, and the real Broadcast
	puts an IO watch on the database socket. This stands in for the GObject signal
	machinery only: connect records the handler and returns its id, disconnect
	drops it, and emit calls the ones registered for that signal, with itself as
	the first argument the way GObject would.

	It is not a substitute for a real notification. The suite runs inside one
	transaction that is rolled back, and Postgres holds notifications until commit,
	so no pg_notify is ever delivered here: emit () is how a test plays the part of
	the notification arriving'''
	def __init__(self):
		self.handlers = {} # handler id: (signal, callable)
		self.next_id = 1
	def connect(self, signal, handler):
		handler_id = self.next_id
		self.next_id += 1
		self.handlers[handler_id] = (signal, handler)
		return handler_id
	def disconnect(self, handler_id):
		self.handlers.pop(handler_id, None)
	def emit(self, signal, *args):
		for registered, handler in list(self.handlers.values()):
			if registered == signal:
				handler(self, *args)
	def connected(self, signal):
		return [handler for registered, handler in self.handlers.values()
				if registered == signal]

# db_connection.DB is imported by value everywhere, so it has to be replaced
# before any application module is imported
import db_connection
db_connection.broadcaster = FakeBroadcaster()
# Whether the copy already has everything PENDING_SCHEMA would add. It has to be
# asked once, because the answer cannot be cached by applying the DDL: the block
# runs inside the test transaction, and real_rollback () throws the whole
# transaction away after every test, so anything applied at import time is gone
# before the second test starts. Committing it instead would write the migration
# to the database for real, which is the one thing this harness promises not to
# do -- the application applies migrations, from its own upgrade dialog.
#
# So the DDL stays in setUp, and this is what stops it being paid 600 times over
# on a copy that is already current: each ALTER is a no-op there, but it still
# takes ACCESS EXCLUSIVE on the table, 600 times, against a connection that is
# holding a transaction open. That is lock contention bought for nothing.
SCHEMA_PROBE = """
SELECT NOT (
	EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'settings', 'inventory_capitalized'))
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'inventory_transactions', 'credit_memo_item_id'))
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name, is_nullable) =
		('inventory', 'count_summaries', 'location_id', 'NO'))
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'inventory_transactions', 'count_summary_id'))
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'inventory_transactions', 'transfer_id'))
	AND to_regclass('inventory.transfers') IS NOT NULL
	AND EXISTS (SELECT 1 FROM pg_proc AS p JOIN pg_namespace AS n
		ON n.oid = p.pronamespace
		WHERE (n.nspname, p.proname) = ('inventory', 'count_summary_changed'))
	AND EXISTS (SELECT 1 FROM pg_trigger
		WHERE tgname = 'count_summary_insert_trigger')
	AND EXISTS (SELECT 1 FROM pg_trigger
		WHERE tgname = 'count_summary_update_trigger')
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'units', 'standard'))
	AND EXISTS (SELECT 1 FROM information_schema.columns WHERE
		(table_schema, table_name, column_name) =
		('public', 'units', 'abbreviation')))
"""

_conn = None
_schema_pending = True # until asked; a copy that is behind pays the DDL per test
try:
	_conn = connect()
	# asked here, before FakeDB opens the savepoint every test rolls back to, so
	# giving the probe's read transaction back cannot disturb it
	_probe = _conn.cursor()
	_probe.execute(SCHEMA_PROBE)
	_schema_pending = _probe.fetchone()[0]
	_probe.close()
	_conn.rollback()
	db_connection.DB = FakeDB(_conn)
except unittest.SkipTest:
	pass

Gtk.Widget.show_all = lambda self: None # no windows on the user's display
Gtk.Window.present = lambda self: None

# The windows that remember their own size read it out of the sqlite preferences
# file, which the application bootstraps in get_db_params -- a path these tests
# never take, because they hand psycopg2 the connection themselves. Without it
# local_settings is an empty file with no tables in it and any such window raises
# 'no such table: product_edit' in its constructor. constants.installed is False
# for a checkout, so this is the local_settings next to these tests and never the
# user's own ~/.config/posting. Both calls are idempotent, the same as the
# application's
import sqlite_utils
_sqlite = sqlite_utils.get_apsw_connection()
_sqlite_cursor = _sqlite.cursor()
sqlite_utils.create_apsw_tables(_sqlite_cursor)
sqlite_utils.update_apsw_tables(_sqlite_cursor)
_sqlite.close() # unlock the file, the way get_db_params does

PENDING_SCHEMA = """
ALTER TABLE public.settings
	ADD COLUMN IF NOT EXISTS inventory_capitalized boolean NOT NULL DEFAULT False;
ALTER TABLE public.inventory_transactions
	ADD COLUMN IF NOT EXISTS credit_memo_item_id bigint
		REFERENCES public.credit_memo_items(id)
		ON UPDATE RESTRICT ON DELETE CASCADE;
ALTER TABLE inventory.count_summaries
	ADD COLUMN IF NOT EXISTS location_id integer
		REFERENCES public.locations(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
UPDATE inventory.count_summaries SET location_id =
	(SELECT id FROM locations ORDER BY id LIMIT 1) WHERE location_id IS NULL;
ALTER TABLE inventory.count_summaries ALTER COLUMN location_id SET NOT NULL;
ALTER TABLE public.inventory_transactions
	ADD COLUMN IF NOT EXISTS count_summary_id bigint
		REFERENCES inventory.count_summaries(id)
		ON UPDATE RESTRICT ON DELETE RESTRICT;
CREATE OR REPLACE FUNCTION inventory.count_summary_changed() RETURNS trigger
	LANGUAGE plpgsql
	AS
$BODY$
	BEGIN
		PERFORM pg_notify('inventory_counts', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger
					WHERE tgname = 'count_summary_insert_trigger') THEN
		CREATE TRIGGER count_summary_insert_trigger
		AFTER INSERT ON inventory.count_summaries
		FOR EACH ROW EXECUTE PROCEDURE inventory.count_summary_changed();
	END IF;
	IF NOT EXISTS (SELECT 1 FROM pg_trigger
					WHERE tgname = 'count_summary_update_trigger') THEN
		CREATE TRIGGER count_summary_update_trigger
		AFTER UPDATE ON inventory.count_summaries
		FOR EACH ROW WHEN (
			NEW.name        IS DISTINCT FROM OLD.name OR
			NEW.fiscal_id   IS DISTINCT FROM OLD.fiscal_id OR
			NEW.location_id IS DISTINCT FROM OLD.location_id OR
			NEW.active      IS DISTINCT FROM OLD.active)
		EXECUTE PROCEDURE inventory.count_summary_changed();
	END IF;
END
$$;
CREATE TABLE IF NOT EXISTS inventory.transfers (
	id bigserial primary key,
	date_inserted date NOT NULL DEFAULT now(),
	source_location_id integer NOT NULL REFERENCES public.locations(id)
		ON UPDATE RESTRICT ON DELETE RESTRICT,
	destination_location_id integer NOT NULL REFERENCES public.locations(id)
		ON UPDATE RESTRICT ON DELETE RESTRICT,
	notes text,
	CONSTRAINT transfer_locations_differ
		CHECK (source_location_id <> destination_location_id)
);
ALTER TABLE public.inventory_transactions
	ADD COLUMN IF NOT EXISTS transfer_id bigint
		REFERENCES inventory.transfers(id)
		ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE public.units
	ADD COLUMN IF NOT EXISTS standard boolean DEFAULT false NOT NULL;
ALTER TABLE public.units
	ADD COLUMN IF NOT EXISTS deleted boolean DEFAULT false NOT NULL;
ALTER TABLE public.units
	ADD COLUMN IF NOT EXISTS date_created date DEFAULT now() NOT NULL;
ALTER TABLE public.units
	ADD COLUMN IF NOT EXISTS date_edited date DEFAULT now() NOT NULL;
UPDATE public.units SET standard = True
	WHERE id = (SELECT min(id) FROM public.units)
		AND NOT EXISTS (SELECT 1 FROM public.units WHERE standard = True);
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE
						(table_schema, table_name, column_name) =
						('public', 'units', 'abbreviation'))
		THEN RETURN;
	END IF;

	ALTER TABLE public.units
		ADD COLUMN abbreviation varchar NOT NULL DEFAULT '';
	ALTER TABLE public.units
		ADD COLUMN parent_id integer
			REFERENCES public.units (id) ON UPDATE RESTRICT ON DELETE RESTRICT;
	ALTER TABLE public.units
		ADD COLUMN parent_qty numeric(12,4);
	ALTER TABLE public.units
		ADD CONSTRAINT unit_parent_is_another_unit
			CHECK (parent_id IS NULL OR parent_id <> id);
	ALTER TABLE public.units
		ADD CONSTRAINT unit_parent_qty_together
			CHECK ((parent_id IS NULL) = (parent_qty IS NULL)
							AND (parent_qty IS NULL OR parent_qty > 0));

	EXECUTE $q$
		UPDATE public.units SET abbreviation = v.abbr
			FROM (VALUES ('Piece','pc'), ('Hour','hr'), ('Minute','min'),
						('Foot','ft'), ('Inch','in'), ('Ounce','oz'),
						('Pound','lb'), ('Ton','t'), ('Acre','ac')) AS v(name, abbr)
			WHERE units.name = v.name
		$q$;
	EXECUTE $q$
		UPDATE public.units SET (parent_id, parent_qty) =
				((SELECT id FROM public.units WHERE name = 'Inch'), 12)
			WHERE name = 'Foot'
				AND EXISTS (SELECT 1 FROM public.units WHERE name = 'Inch')
		$q$;
	EXECUTE $q$
		UPDATE public.units SET (parent_id, parent_qty) =
				((SELECT id FROM public.units WHERE name = 'Minute'), 60)
			WHERE name = 'Hour'
				AND EXISTS (SELECT 1 FROM public.units WHERE name = 'Minute')
		$q$;
END
$$;
"""
# the update also widens purchase_order_items.expense_account to bigint, and
# purchase_order_items.received from smallint to integer, both left out here:
# each rewrites the table, and that rewrite is rolled back with every test, so
# it would be paid again in every setUp. No test uses an account number or a
# received count big enough to need either.
# Left out for the same reason: the unique indexes on
# (count_summary_id, product_id) and (transfer_id, product_id, location_id). The
# statements above are no-ops once they have run, but a CREATE INDEX on
# inventory_transactions is a real index build on a large table, and this runs in
# every setUp. The cost is that the tests exercise close_count's own idempotence
# guard, and transfer's own per product aggregation, rather than the database's
# backstop for either. inventory.transfers keeps its CHECK, which is free.
# count_summaries is small enough that its SET NOT NULL does not matter

class DBTestCase(unittest.TestCase):
	def setUp(self):
		if _conn is None:
			self.skipTest('POSTING_TEST_DB_PASSWORD not set')
		self.DB = db_connection.DB
		self.cursor = self.DB.cursor()
		self.apply_pending_schema()

	def apply_pending_schema(self):
		'''bring the schema up to the version the code expects, inside the test
		transaction so it is rolled back with everything else. Postgres keeps DDL
		transactional, so this leaves the database alone while letting the suite
		run against a copy that has not had the update applied yet. Every
		statement is a no-op once it has.

		Skipped outright once SCHEMA_PROBE has said the copy is already current,
		which is the usual case and the difference between taking ACCESS
		EXCLUSIVE on four tables in every setUp and taking none at all'''
		if _schema_pending:
			self.cursor.execute(PENDING_SCHEMA)
			# move the savepoint past the DDL. FakeDB.rollback () returns to
			# test_sp, which was taken at import, so a window doing the usual
			# DB.rollback () after a read would otherwise undo the columns just
			# added and the test would see the old schema. commit () here is
			# still only a savepoint release, so nothing reaches the database:
			# tearDown's real_rollback () discards the DDL with everything else
			self.DB.commit()

	def tearDown(self):
		if _conn is not None:
			self.cursor.close()
			self.DB.real_rollback()
		self.assert_no_windows_shown() # last: it raises, the rollback must happen

	def assert_no_windows_shown(self):
		'''Nothing here may put a window on the user's display. show_all () and
		present () are stubbed at import, but a toplevel carrying visible=True in
		its .ui is shown by GtkBuilder itself, while it parses, before any Python
		in the constructor runs -- so the stubs never see it and the window is on
		screen regardless. This is what notices.

		It hides the offender rather than destroying it, because these windows
		wire their destroy signal to a handler that works on the database:
		product_edit_main's rolls back and drops an advisory lock,
		invoice_window's flushes a comment, purchase_order_window's unlocks the
		order. None of that may run from a teardown. Nothing in the project
		connects hide or unmap, so hiding costs nothing.

		Windows left behind by earlier tests are unmapped and never trip this, so
		a leak is reported once, against the test that caused it'''
		shown = [w for w in Gtk.Window.list_toplevels() if w.get_mapped()]
		for window in shown:
			window.hide()
		if shown:
			self.fail('put on the display: %s' % ', '.join(
						w.get_title() or type(w).__name__ for w in shown))

	def one(self, sql, args = None):
		self.cursor.execute(sql, args)
		return self.cursor.fetchone()[0]

	def new_location(self, name = 'Test location'):
		return self.one("INSERT INTO locations (name) VALUES (%s) RETURNING id",
						(name,))

	def on_hand(self, product_id, location_id = None):
		'''the whole company by default, one location when asked: a count close
		corrects the location its summary names, so most of its tests need both'''
		return self.one("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
						"FROM inventory_transactions WHERE product_id = %s "
						"AND (%s::int IS NULL OR location_id = %s)",
						(product_id, location_id, location_id))
