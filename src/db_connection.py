# db_connection.py
#
# Copyright (C) 2026 - Reuben Rissler
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

from gi.repository import GLib, GObject, Gtk
import time, psycopg2
import sqlite_utils

DEFAULT_CONNECT_TIMEOUT = 5
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BACKOFF_SECONDS = 2
RECONNECT_BACKOFF_CAP = 30
MIN_DIALOG_VISIBLE_SECONDS = 0.6

DB = None
DB_PROCESS_ID = 0
db_name = None
mobile = False
broadcaster = None
reconnect_status = None
ACCOUNTS = None


def is_connection_lost(exc, real_conn):
	# both a dropped connection and a FOR UPDATE NOWAIT lock raise OperationalError
	if isinstance(exc, psycopg2.InterfaceError):
		return True
	if isinstance(exc, psycopg2.OperationalError):
		if getattr(exc, 'pgcode', None) == '55P03':  # lock_not_available
			return False
		return real_conn is None or real_conn.closed != 0
	return False


def _fetch_params(sqlite, row_id):
	cursor = sqlite.cursor()
	if row_id == None:
		rows = cursor.execute("SELECT host, port, user, password, db_name, mobile "
								"FROM postgres_conn")
	else:
		rows = cursor.execute("SELECT server, port, user, password, db_name, mobile "
								"FROM db_connections WHERE id = ?", (row_id,))
	host = port = user = password = database = mobile = None
	for row in rows:
		host, port, user, password, database, mobile = row
	cursor.close()
	params = {
		'dbname': database,
		'host': host,
		'user': user,
		'password': password,
		'port': port,
		'connect_timeout': DEFAULT_CONNECT_TIMEOUT,
	}
	return params, mobile == 'True'


def get_db_params(row_id):
	import constants
	if getattr(constants, 'sqlite_connection', None) == None:
		sqlite = sqlite_utils.get_apsw_connection()
		cursor = sqlite.cursor()
		sqlite_utils.create_apsw_tables(cursor)
		sqlite_utils.update_apsw_tables(cursor)
		sqlite.close()  # unlock file after updating
		sqlite = sqlite_utils.get_apsw_connection()
		constants.sqlite_connection = sqlite
	return _fetch_params(constants.sqlite_connection, row_id)


class DBCursor:
	# created fresh on every DB.cursor() call, never cached - nothing here goes stale on reconnect

	def __init__(self, parent, real_cursor):
		self._parent = parent
		self._real = real_cursor

	def execute(self, *args, **kwargs):
		try:
			return self._real.execute(*args, **kwargs)
		except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
			if is_connection_lost(e, self._parent._real):
				self._parent.reconnect()
			raise

	def executemany(self, *args, **kwargs):
		try:
			return self._real.executemany(*args, **kwargs)
		except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
			if is_connection_lost(e, self._parent._real):
				self._parent.reconnect()
			raise

	def __getattr__(self, name):
		return getattr(self._real, name)


class DBConnection:
	# assigned once to the module-level DB global and never reassigned - identity
	# stays stable so every `from db_connection import DB` site keeps working
	# across a reconnect()

	def __init__(self, row_id):
		self._row_id = row_id
		self._real = None
		self._listeners = []
		self._reconnecting = False
		self._in_reconnect_call = False
		self.db_name = None
		self.mobile = False
		self._connect()

	def _connect(self):
		params, mobile = get_db_params(self._row_id)
		self.db_name = params['dbname']
		self.mobile = mobile
		self._real = psycopg2.connect(**params)

	def register_reconnect_listener(self, fn):
		self._listeners.append(fn)

	def _notify(self, event, attempt=None, max_attempts=None):
		for fn in list(self._listeners):
			try:
				fn(event, attempt, max_attempts)
			except Exception as e:
				print("db_connection: reconnect listener error: %s" % e)

	def _pump(self, seconds):
		# lets the main loop paint the "Reconnecting..." dialog and animate its
		# spinner during an otherwise-blocking wait. Safe to do only because
		# cursor()/commit()/rollback() refuse to touch self._real while
		# self._reconnecting is set, so anything re-entered here during the
		# pump fails cleanly instead of hitting a stale/closed connection.
		ctx = GLib.MainContext.default()
		end = time.monotonic() + seconds
		while time.monotonic() < end:
			while ctx.pending():
				ctx.iteration(False)
			time.sleep(0.05)

	def reconnect(self):
		# guards the whole call, including the 'reconnected' notify below, so a
		# listener whose own DB use fails right after reconnecting (eg. LISTEN
		# in Broadcast._listen()) can't recursively kick off a second full
		# reconnect cycle - it just fails and waits for the next real trigger
		if self._in_reconnect_call:
			return False
		self._in_reconnect_call = True
		try:
			if self._reconnecting:
				return False
			self._reconnecting = True
			success = False
			try:
				try:
					if self._real is not None:
						self._real.close()
				except Exception:
					pass
				delay = RECONNECT_BACKOFF_SECONDS
				for attempt in range(MAX_RECONNECT_ATTEMPTS):
					self._notify('reconnecting', attempt + 1, MAX_RECONNECT_ATTEMPTS)
					self._pump(0.05)  # force the dialog to paint/update the try count
					try:
						self._connect()
						success = True
						break
					except psycopg2.OperationalError as e:
						print("db_connection: reconnect attempt %d/%d failed: %s"
								% (attempt + 1, MAX_RECONNECT_ATTEMPTS, e))
						self._pump(delay)
						delay = min(delay * 2, RECONNECT_BACKOFF_CAP)
			finally:
				self._reconnecting = False
			# notify only after _reconnecting is back to False, so 'reconnected'
			# listeners (eg. Broadcast._on_reconnect re-issuing LISTEN) can use
			# DB.cursor() again instead of hitting the reconnecting guard
			if success:
				self._notify('reconnected')
				return True
			else:
				self._notify('reconnect_failed')
				self._show_connection_picker()
				return False
		finally:
			self._in_reconnect_call = False

	def _show_connection_picker(self):
		from db import database_tools
		database_tools.GUI(True)

	def cursor(self, *args, **kwargs):
		if self._reconnecting:
			raise psycopg2.OperationalError("database connection is reconnecting")
		if self._real is None or self._real.closed != 0:
			self.reconnect()
		return DBCursor(self, self._real.cursor(*args, **kwargs))

	def commit(self):
		if self._reconnecting:
			raise psycopg2.OperationalError("database connection is reconnecting")
		try:
			self._real.commit()
		except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
			if is_connection_lost(e, self._real):
				self.reconnect()
			raise
		# a trigger's pg_notify on a table we're LISTENing to gets delivered back
		# to us as part of this same commit's response, with no later socket-
		# readable event to wake Broadcast.on_db_readable - drain it now so
		# windows relying on eg. invoices_changed refresh for our own writes too
		if broadcaster is not None:
			broadcaster.process_notifies()

	def rollback(self):
		if self._reconnecting:
			return
		try:
			self._real.rollback()
		except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
			if is_connection_lost(e, self._real):
				self.reconnect()
				return
			raise

	def __getattr__(self, name):
		return getattr(self._real, name)


def start_broadcaster():
	global broadcaster, ACCOUNTS, reconnect_status
	import accounts as ACCOUNTS
	broadcaster = Broadcast()
	reconnect_status = ReconnectStatusDialog()
	DB.register_reconnect_listener(reconnect_status.on_reconnect_event)


class Broadcast(GObject.GObject):
	__gsignals__ = {
		'products_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
		'contacts_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
		'clock_entries_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
		'invoices_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
		'purchase_orders_changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
		'job_sheets_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
		'documents_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
		'loans_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
		'resources_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
		'admin_changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
		'shutdown': (GObject.SignalFlags.RUN_FIRST, None, ())
	}

	def __init__(self):
		global DB_PROCESS_ID
		GObject.GObject.__init__(self)
		self.io_watch_id = GLib.io_add_watch(
			DB.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_db_readable
		)
		self.connect("shutdown", self.on_shutdown)
		self._listen()
		DB_PROCESS_ID = DB.get_backend_pid()
		DB.register_reconnect_listener(self._on_reconnect)

	def _listen(self):
		c = DB.cursor()
		c.execute("LISTEN products;"
				  "LISTEN contacts;"
				  "LISTEN accounts;"
				  "LISTEN time_clock_entries;"
				  "LISTEN invoices;"
				  "LISTEN purchase_orders;"
				  "LISTEN job_sheets;"
				  "LISTEN documents;"
				  "LISTEN loans;"
				  "LISTEN resources;")
		c.close()
		DB.commit()

	def _on_reconnect(self, event, attempt=None, max_attempts=None):
		global DB_PROCESS_ID
		if event != 'reconnected':
			return
		try:
			GLib.source_remove(self.io_watch_id)
		except Exception:
			pass
		self.io_watch_id = GLib.io_add_watch(
			DB.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_db_readable
		)
		self._listen()
		DB_PROCESS_ID = DB.get_backend_pid()

	def on_shutdown(self, broadcaster):
		GLib.source_remove(self.io_watch_id)

	def on_db_readable(self, source, condition):
		if condition & (GLib.IO_HUP | GLib.IO_ERR) or DB.closed == 1:
			GLib.idle_add(DB.reconnect)
			return False
		self.process_notifies()
		return True

	def process_notifies(self):
		# commits on our own LISTENing connection deliver self-notifies
		# synchronously as part of the commit's response, with no later
		# socket-readable event to wake on_db_readable - so this also gets
		# called directly from DBConnection.commit() to drain those.
		try:
			DB.poll()
			while DB.notifies:
				notify = DB.notifies.pop(0)
				if notify.channel == "products":
					self.emit('products_changed')
				elif notify.channel == "contacts":
					self.emit('contacts_changed')
				elif notify.channel == "accounts":
					ACCOUNTS.populate_accounts()
				elif notify.channel == "time_clock_entries":
					self.emit('clock_entries_changed')
				elif notify.channel == "invoices":
					invoice_id = notify.payload
					self.emit("invoices_changed", int(invoice_id),
							  notify.pid != DB_PROCESS_ID)
				elif notify.channel == "purchase_orders":
					po_id = notify.payload
					if notify.pid != DB_PROCESS_ID:
						self.emit("purchase_orders_changed", int(po_id))
				elif notify.channel == "job_sheets":
					job_sheet_id = notify.payload
					self.emit("job_sheets_changed", int(job_sheet_id),
							  notify.pid != DB_PROCESS_ID)
				elif notify.channel == "documents":
					document_id = notify.payload
					self.emit("documents_changed", int(document_id),
							  notify.pid != DB_PROCESS_ID)
				elif notify.channel == "loans":
					loan_id = notify.payload
					self.emit("loans_changed", int(loan_id),
							  notify.pid != DB_PROCESS_ID)
				elif notify.channel == "resources":
					resource_id = notify.payload
					self.emit("resources_changed", int(resource_id),
							  notify.pid != DB_PROCESS_ID)
		except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
			# the connection died while handling a background notification - DB has
			# already reconnected (or is reconnecting) via the cursor that hit this;
			# there's no user action to retry here, so just skip this refresh
			print("db_connection: on_db_readable: %s" % e)


class ReconnectStatusDialog:
	def __init__(self):
		self.dialog = None
		self.attempt_label = None
		self._shown_at = None

	def on_reconnect_event(self, event, attempt=None, max_attempts=None):
		if event == 'reconnecting':
			self._show(attempt, max_attempts)
		else:
			self._hide()

	def _show(self, attempt=None, max_attempts=None):
		if self.dialog == None:
			self.dialog = Gtk.MessageDialog(
				transient_for = None,
				modal = True,
				message_type = Gtk.MessageType.INFO,
				buttons = Gtk.ButtonsType.NONE
			)
			self.dialog.set_title("Reconnecting to database...")
			self.attempt_label = Gtk.Label()
			self.dialog.get_message_area().pack_start(self.attempt_label, False, False, 0)
			spinner = Gtk.Spinner()
			spinner.set_size_request(32, 32)
			self.dialog.get_message_area().pack_start(spinner, False, False, 6)
			spinner.start()
			self.dialog.show_all()
			self._shown_at = time.monotonic()
		if attempt != None and max_attempts != None:
			self.attempt_label.set_text("Attempt %d of %d" % (attempt, max_attempts))

	def _hide(self):
		if self.dialog == None:
			return
		# a reconnect that succeeds on the first attempt can close this within
		# milliseconds of opening it, which reads as a window flashing on screen -
		# hold it open for a minimum stretch so it's actually visible
		elapsed = time.monotonic() - self._shown_at
		remaining = MIN_DIALOG_VISIBLE_SECONDS - elapsed
		if remaining > 0:
			ctx = GLib.MainContext.default()
			end = time.monotonic() + remaining
			while time.monotonic() < end:
				while ctx.pending():
					ctx.iteration(False)
				time.sleep(0.05)
		self.dialog.destroy()
		self.dialog = None
		self.attempt_label = None
		self._shown_at = None


def connect(row_id):
	global DB, db_name, mobile
	try:
		db = DBConnection(row_id)
	except psycopg2.OperationalError as e:
		print(e.args[0])
		db_name = 'False'
		return False
	DB = db
	db_name = db.db_name
	mobile = db.mobile
	start_broadcaster()
	import accounts
	def _populate_accounts_safely():
		try:
			accounts.populate_accounts()
		except (psycopg2.OperationalError, psycopg2.InterfaceError):
			pass  # DB dropped/reconnecting right as this ran - nothing to do
		return False
	GLib.idle_add(_populate_accounts_safely)
	return True
