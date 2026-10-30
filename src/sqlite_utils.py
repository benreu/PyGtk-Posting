# sqlite_utils.py
#
# Copyright (C) 2020 - Reuben Rissler
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

import os, apsw
import constants, credentials


def get_apsw_connection():
	if constants.installed == False:
		pref_file = os.path.join(os.getcwd(), 
											'local_settings')
	else:
		pref_file = os.path.join(constants.preferences_path, 
											'local_settings')
	make_private(pref_file)
	return apsw.Connection(pref_file)

def make_private (path):
	'''Readable by its owner only. The file used to be created 0644, readable
	by every account on the machine, while it held the database password in
	plain text. A new one is created 0600 here; an old one is narrowed to it.
	SQLite gives its journal the same mode as the file.'''
	try:
		fd = os.open(path, os.O_CREAT | os.O_RDONLY, 0o600)
		try:
			if os.fstat(fd).st_mode & 0o077:
				os.fchmod(fd, 0o600)
		finally:
			os.close(fd)
	except OSError as e:
		print("sqlite_utils: could not make %s private: %s" % (path, e))

def move_passwords_to_keyring(cursor):
	'''Move the database passwords this file used to keep in plain text into
	the login keyring (see credentials.py), and blank them here.

	A password is blanked only once the keyring has taken it, because it may be
	the only copy there is. When the keyring cannot be reached - no
	gir1.2-secret-1, no desktop session, the unlock prompt declined - nothing
	more is touched, the plain text keeps working, and the next start tries
	again. Where two rows name the same server and user with different
	passwords, the default connection's wins: it is the one in use, and a
	stale one would only be asked for at the next connect anyway.

	Returns how many passwords were moved.'''
	rows = list(cursor.execute("SELECT host, port, user, password "
								"FROM postgres_conn"))
	rows += list(cursor.execute("SELECT server, port, user, password "
								"FROM db_connections ORDER BY id DESC"))
	moved = set()
	for host, port, user, password in rows:
		if password in ('', 'None') or (host, port, user) in moved:
			continue
		try:
			credentials.store_password('postgres',
										credentials.postgres_host(host, port),
										user, password)
		except credentials.CredentialError as e:
			print("sqlite_utils: database passwords stay in local_settings "
					"until the login keyring can take them: %s" % e)
			break
		cursor.execute("UPDATE postgres_conn SET password = '' "
						"WHERE host = ? AND port = ? AND user = ?",
						(host, port, user))
		cursor.execute("UPDATE db_connections SET password = '' "
						"WHERE server = ? AND port = ? AND user = ?",
						(host, port, user))
		moved.add((host, port, user))
	if moved:
		# an overwritten value stays readable in the file's free pages until
		# the file is rebuilt
		cursor.execute("VACUUM")
	return len(moved)

def create_apsw_tables(cursor):
	cursor.execute("PRAGMA foreign_keys=on;")
	cursor.execute("CREATE TABLE IF NOT EXISTS postgres_conn "
										"(id INTEGER PRIMARY KEY, "
										"user TEXT NOT NULL, "
										"password TEXT NOT NULL, "
										"host TEXT NOT NULL, "
										"port TEXT NOT NULL, "
										"db_name TEXT NOT NULL, "
										"active BOOLEAN NOT NULL, "
										"mobile BOOLEAN NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS settings "
										"(setting TEXT UNIQUE NOT NULL,"
										"value TEXT NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS product_edit "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"size INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS product_overview "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"size INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS contact_overview "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"size INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS keybindings "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"keybinding TEXT NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS resource_calendar "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"size INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS open_invoices "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"value INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS unpaid_invoices "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"value INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS vendor_history "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"size INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS product_search "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"value INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS correspondence "
										"(widget_id TEXT UNIQUE NOT NULL, "
										"value INTEGER NOT NULL)")
	cursor.execute("CREATE TABLE IF NOT EXISTS db_connections "
										"(id INTEGER PRIMARY KEY, "
										"name TEXT, "
										"server TEXT NOT NULL, "
										"port TEXT NOT NULL, "
										"user TEXT NOT NULL, "
										"password TEXT NOT NULL, "
										"db_name TEXT NOT NULL, "
										"standard BOOLEAN NOT NULL, "
										"mobile BOOLEAN NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO db_connections VALUES "
					"('1', 'name', 'localhost', '5432', "
					"'postgres', 'None', 'None', 'False', 'False')")
	# the password columns are kept, so an older Posting can still read this
	# file, and hold '' for every connection whose password is in the keyring

def update_apsw_tables(cursor):
	cursor.execute("INSERT OR IGNORE INTO postgres_conn VALUES "
					"('1', 'postgres', 'None', "
					"'localhost', '5432', 'None', 'False', 'False')")
	cursor.execute("CREATE TABLE IF NOT EXISTS db_connections "
										"(id INTEGER PRIMARY KEY, "
										"name TEXT, "
										"server TEXT NOT NULL, "
										"port TEXT NOT NULL, "
										"user TEXT NOT NULL, "
										"password TEXT NOT NULL, "
										"db_name TEXT NOT NULL, "
										"standard BOOLEAN NOT NULL, "
										"mobile BOOLEAN NOT NULL)")
	cursor.execute("INSERT OR IGNORE INTO settings VALUES "
					"('postgres_bin_path', '/usr/bin')")
	cursor.execute("INSERT OR IGNORE INTO settings VALUES "
					"('backup_path', '')")
	cursor.execute("INSERT OR IGNORE INTO product_edit VALUES "
					"('window_width', 900)")
	cursor.execute("INSERT OR IGNORE INTO product_edit VALUES "
					"('window_height', 500)")
	# product window layout
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('window_width', 850)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('window_height', 500)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('ext_name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('description_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('barcode_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('unit_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('weight_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('tare_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('manufacturer_sku_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('expense_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('inventory_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('revenue_account_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('sellable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('purchasable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('manufactured_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('job_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_overview VALUES "
					"('stocked_column', 25)")
	# contact window layout
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('window_width', 850)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('window_height', 500)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('ext_name_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('address_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('city_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('state_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('zip_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('fax_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('phone_column', 125)")
	cursor.execute("INSERT OR IGNORE INTO contact_overview VALUES "
					"('email_column', 125)")
	# keybindings
	cursor.execute("INSERT OR IGNORE INTO keybindings VALUES "
					"('Main window', 'F9')")
	# resource calendar window layout
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('pane1', 500)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('pane2', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('show_details_checkbutton', 1)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('row_height_value', 3)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('row_width_value', 10)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('edit_window_width', 600)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('edit_window_height', 200)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('subject_column', 200)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('qty_column', 50)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('type_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('contact_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO resource_calendar VALUES "
					"('category_column', 100)")
	# open invoices window layout
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('window_width', 550)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('window_height', 400)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('sort_column', 0)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('sort_type', 0)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('number_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('invoice_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('contact_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('date_created_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO open_invoices VALUES "
					"('items_column', 100)")
	# unpaid invoices window layout
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('window_width', 500)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('window_height', 400)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('sort_column', 0)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('sort_type', 0)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('number_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('invoice_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('customer_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('date_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO unpaid_invoices VALUES "
					"('amount_column', 100)")
	# vendor history window layout
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('window_width', 600)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('window_height', 400)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('date_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('invoice_name_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('description_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('amount_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('paid_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('posted_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('qty_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('product_name_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('product_ext_name_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('remark_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('price_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('ext_price_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('order_number_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('po_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('po_date_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO vendor_history VALUES "
					"('vendor_column', 100)")
	# correspondence window layout
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('window_width', 900)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('window_height', 600)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('paned_position', 300)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('date_column', 160)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('direction_column', 70)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('contact_column', 180)")
	cursor.execute("INSERT OR IGNORE INTO correspondence VALUES "
					"('subject_column', 260)")
	# product search window layout
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('window_width', 500)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('window_height', 400)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('product_name_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('ext_name_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('barcode_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('vendor_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('order_number_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('vendor_number_column', 100)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('stock_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('sellable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('purchasable_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('manufactured_column', 25)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('sort_column', 0)")
	cursor.execute("INSERT OR IGNORE INTO product_search VALUES "
					"('sort_type', 0)")
