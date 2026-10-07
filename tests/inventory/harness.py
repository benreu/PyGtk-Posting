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
	puts an IO watch on the database socket. Windows only connect and disconnect'''
	def connect(self, *args):
		return 1
	def disconnect(self, *args):
		pass

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
"""
# the update also widens purchase_order_items.expense_account to bigint, which is
# left out here: it rewrites the table, and no test uses an account number big
# enough to need it

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

	def on_hand(self, product_id):
		return self.one("SELECT COALESCE(SUM(qty_in - qty_out), 0) "
						"FROM inventory_transactions WHERE product_id = %s",
						(product_id,))
