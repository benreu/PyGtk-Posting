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
_conn = None
try:
	_conn = connect()
	db_connection.DB = FakeDB(_conn)
except unittest.SkipTest:
	pass

Gtk.Widget.show_all = lambda self: None # no windows on the user's display
Gtk.Window.present = lambda self: None

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
"""
# the update also widens purchase_order_items.expense_account to bigint, and
# purchase_order_items.received from smallint to integer, both left out here:
# each rewrites the table, and that rewrite is rolled back with every test, so
# it would be paid again in every setUp. No test uses an account number or a
# received count big enough to need either.
# Left out for the same reason: the unique index on
# (count_summary_id, product_id). The statements above are no-ops once they have
# run, but a CREATE INDEX on inventory_transactions is a real index build on a
# large table, and this runs in every setUp. The cost is that the tests exercise
# close_count's own idempotence guard rather than the database's backstop.
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
		statement is a no-op once it has'''
		self.cursor.execute(PENDING_SCHEMA)

	def tearDown(self):
		if _conn is not None:
			self.cursor.close()
			self.DB.real_rollback()

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
