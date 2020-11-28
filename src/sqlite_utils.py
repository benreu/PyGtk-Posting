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
import constants


def get_apsw_connection():
	if constants.dev_mode == True:
		pref_file = os.path.join(os.getcwd(), 
											'local_settings')
	else:
		pref_file = os.path.join(constants.preferences_path, 
											'local_settings')
	return apsw.Connection(pref_file)

def create_apsw_tables(cursor):
	cursor.execute("PRAGMA foreign_keys=on;")
	cursor.execute("CREATE TABLE IF NOT EXISTS postgres_conn "
										"(id INTEGER PRIMARY KEY, "
										"user TEXT NOT NULL, "
										"password TEXT NOT NULL, "
										"host TEXT NOT NULL, "
										"port TEXT NOT NULL, "
										"db_name TEXT NOT NULL, "
										"active BOOLEAN NOT NULL)")
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

def update_apsw_tables(cursor):
	cursor.execute("INSERT OR IGNORE INTO postgres_conn VALUES "
					"('1', 'postgres', 'None', "
					"'localhost', '5432', 'None', 'False')")
	cursor.execute("INSERT OR IGNORE INTO settings VALUES "
					"('postgres_bin_path', '/usr/bin')")
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
