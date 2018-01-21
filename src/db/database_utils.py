# database_utils.py
#
# Copyright (C) 2016 - reuben
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

from gi.repository import Gtk

PROGRESSBAR = None
COMPLETE_PROGRESS = None

def progressbar (progress):
	global COMPLETE_PROGRESS
	state = float(progress) / COMPLETE_PROGRESS
	PROGRESSBAR.set_fraction(state)
	while Gtk.events_pending():
		Gtk.main_iteration()

def add_new_tables(db, statusbar):
	global COMPLETE_PROGRESS
	statusbar.push(1, "Adding tables ...")
	cursor = db.cursor()
	COMPLETE_PROGRESS = 42.00
	progressbar (1)
	cursor.execute("CREATE TABLE contacts (id serial PRIMARY KEY, name varchar, c_o varchar, address varchar, city varchar, state varchar, zip varchar, fax varchar, phone varchar, email varchar, label varchar, tax_exempt boolean, tax_number varchar, vendor boolean, customer boolean, employee boolean, another_role boolean, organization varchar, custom1 varchar, custom2 varchar, custom3 varchar, custom4 varchar, notes varchar, active boolean, deleted boolean, price_level varchar);")
	progressbar (2)
	cursor.execute("CREATE TABLE tax_rates (id serial PRIMARY KEY, name varchar, rate numeric(12,2), standard boolean);")
	progressbar (3)
	cursor.execute("INSERT INTO tax_rates (name, rate, standard) VALUES ('10 percent', 10.00, True)")
	progressbar (4)
	cursor.execute("CREATE TABLE products (id serial PRIMARY KEY, name varchar, description varchar, barcode varchar, unit varchar, product_groups_id integer, cost numeric(12,2), level_1_price numeric(12,2), level_2_price numeric(12,2), level_3_price numeric(12,2), level_4_price numeric(12,2), tax_rate_id smallint, deleted boolean, sellable boolean, purchasable boolean, min_inventory smallint, reorder_qty smallint, tax_exemptible boolean, manufactured boolean, weight numeric(12,3), tare numeric(12,3));")
	progressbar (5)
	cursor.execute("INSERT INTO products (name, description, barcode, unit, cost, level_1_price, level_2_price, level_3_price , level_4_price, tax_rate_id, deleted, sellable, purchasable, min_inventory, reorder_qty, tax_exemptible, manufactured, weight, tare) VALUES ('Example product', '', '', 1, 10.00, 14.00, 13.00, 12.00 , 11.00, 1, False, True, True, 0, 0, True, False, 0.000, 0.000);")
	progressbar (6)
	cursor.execute("CREATE TABLE vendor_product_numbers (id serial PRIMARY KEY, vendor_id integer, vendor_sku varchar, product_id integer)")
	progressbar (7)
	cursor.execute("CREATE TABLE organizations (id serial PRIMARY KEY, name varchar, address varchar, city varchar, state varchar, zip varchar, fax varchar, phone varchar, email varchar, website varchar, deleteable boolean);")
	progressbar (8)
	cursor.execute("CREATE TABLE invoices (id serial PRIMARY KEY, name varchar, customer_id bigint, paid boolean, canceled boolean, closed boolean, printed boolean, date_paid date, date_printed date, date_created date, deleteable boolean, subtotal numeric(12,2), tax numeric(12,2), total numeric(12,2), pdf_data bytea);")
	progressbar (9)
	cursor.execute("CREATE TABLE invoice_line_items (id serial PRIMARY KEY, barcode varchar, invoice_id bigint, qty numeric(12,2), product varchar, remark varchar, price numeric(12,2), tax numeric(12,2), ext_price numeric(12,2), canceled boolean, tax_description varchar);")
	progressbar (10)
	cursor.execute("CREATE TABLE incoming_invoices (id serial PRIMARY KEY, purchase_order_id bigint, paid boolean, canceled boolean, date_paid date, date_created date, description varchar);")
	progressbar (11)
	cursor.execute("CREATE TABLE purchase_orders (id serial PRIMARY KEY, name varchar, vendor_id bigint, invoiced boolean, canceled boolean, closed boolean, printed boolean, date_paid date, date_printed date, date_created date, deleteable boolean, total numeric(12,2), pdf_data bytea, tax numeric(12,2), shipping numeric(12,2), fee numeric(12,2), surcharge numeric(12,2));")
	progressbar (12)
	cursor.execute("CREATE TABLE purchase_order_line_items (id serial PRIMARY KEY, barcode varchar, purchase_order_id bigint, qty numeric(12,2), product varchar, remark varchar, price numeric(12,6), ext_price numeric(12,2), canceled boolean, received smallint);")
	progressbar (13)
	cursor.execute("CREATE TABLE settings (id serial PRIMARY KEY, last_backup varchar, print_direct boolean, enter_new_line boolean DEFAULT True, enter_save boolean, only_close_zero_statement bool, close_statement smallint, copy_to_print_statement boolean, header_1 varchar, header_2 varchar, header_3 varchar, header_4 varchar, discount_text_1 varchar, discount_text_2 varchar, discount_text_3 varchar, discount_text_4 varchar, email_when_possible boolean, version varchar, time_clock_secure_login boolean );")
	progressbar (14)
	cursor.execute("INSERT INTO settings (header_1, header_2, header_3, header_4, discount_text_1, discount_text_2, discount_text_3, discount_text_4, close_statement, only_close_zero_statement, print_direct, copy_to_print_statement, email_when_possible, version, time_clock_secure_login) VALUES ('Header 1', 'Header 2', 'Header 3', 'Header 4', 'Discount of', 'allowed if paid by', 'for a total of', '', -1, False, False, False, False, '012', False);")
	progressbar (15)
	cursor.execute("CREATE TABLE payments_incoming (id serial PRIMARY KEY, name varchar, date_inserted date, customer_id integer, amount numeric(12,2), reference varchar, comments varchar, credit_account smallint, debit_account smallint, payment_type smallint, payment_text varchar, closed boolean);")
	progressbar (16)
	cursor.execute("CREATE TABLE accounts (id serial PRIMARY KEY, name varchar, type varchar, amount numeric(12,2), deleteable boolean, number integer, parent_number smallint, dependants varchar, is_parent boolean);")
	progressbar (17)
	cursor.executemany("INSERT INTO accounts (name, amount, deleteable, number, parent_number, is_parent) VALUES (%s, %s, %s, %s, %s, True)", [ ("Assets", 0.00, False, 1000, 0), ("Equities", 0.00, False, 2000, 0), ("Expenses", 0.00, False, 3000, 0), ("Revenue", 0.00, False, 4000, 0), ("Liabilities", 0.00, False, 5000, 0)])
	progressbar (18)
	cursor.executemany("INSERT INTO accounts (name, amount, deleteable, number, parent_number, is_parent) VALUES (%s, %s, %s, %s, %s, %s)", [("Accounts Receivable", 0.00, False, 1100, 1000, False), ("Checks to Deposit", 0.00, False, 1200, 1000, False), ("Accounts Payable", 0.00, False, 5100, 5000, False), ("Checking Account", 0.00, False, 1300, 1000, False), ("Cash Drawer", 0.00, False, 1400, 1000, False), ("Taxes", 0.00, False, 5200, 5000, True), ("Sales Tax Collected", 0.00, False, 5210, 5200, False), ("Credit Cards", 0.00, False, 5300, 5000, False), ("Business Revenue", 0.00, False, 4100, 4000, False), ("Cash Income", 0.00, False, 4110, 4100, False), ("Checks Income", 0.00, False, 4120, 4100, False), ("Credit Card Income", 0.00, False, 4130, 4100, False), ("Mastercard", 0.00, False, 5310, 5300, False), ("Visa", 0.00, False, 5320, 5300, False), ("Product Revenue", 0.00, False, 4140, 4100, False)])
	progressbar (19)
	cursor.execute("CREATE TABLE account_flow_settings (id serial PRIMARY KEY, function varchar, account smallint );") # the table where all the money flow signals get hooked up
	progressbar (20)
	cursor.executemany("INSERT INTO account_flow_settings (function, account) VALUES (%s, %s)", [("check_payment", 1200), ("credit_card_payment", 1300),  ("cash_payment", 1400), ("post_purchase_order", 5100), ("sales_tax", 5210), ("post_invoice", 1100), ("credit_card_income", 5100), ("cash_income", 5100), ("check_income", 5100) ])
	progressbar (21)
	cursor.execute("CREATE TABLE checks_incoming (id serial PRIMARY KEY, check_number varchar, deposited boolean, contact varchar, amount numeric(12,2));")
	progressbar (22)
	cursor.execute("CREATE TABLE account_transaction_lines (id serial PRIMARY KEY, account_name varchar, date_inserted date, contact varchar, amount numeric(12,2), debit_account smallint, credit_account smallint, reconciled boolean, canceled boolean);")
	progressbar (23)
	cursor.execute("CREATE TABLE files (id serial PRIMARY KEY, file_data bytea, contact_id smallint, name varchar, date_inserted date);")
	progressbar (24)
	cursor.execute("CREATE TABLE job_types (id serial PRIMARY KEY, name varchar);")
	progressbar (25)
	cursor.execute("CREATE TABLE job_sheets (id serial PRIMARY KEY, contact_id integer, job_type_id integer, job_sequential_number integer, description varchar, total numeric(12,2), date_inserted date, invoiced boolean, completed boolean, time_clock boolean);")
	progressbar (26)
	cursor.execute("CREATE TABLE job_sheet_line_items (id serial PRIMARY KEY, job_id integer, qty numeric(12,2), product_id integer, remarks varchar);")
	progressbar (27)
	cursor.execute("CREATE TABLE company_info (id serial PRIMARY KEY, name varchar, street varchar, city varchar, state varchar, zip varchar, country varchar, phone varchar, fax varchar, email varchar, website varchar, tax_number varchar);")
	progressbar (28)
	cursor.execute("INSERT INTO company_info (name, street, city, state, zip, country, phone, fax, email, website, tax_number) VALUES ('', '', '', '', '', '', '', '', '', '', '')")
	progressbar (29)
	cursor.execute("CREATE TABLE statements (id serial PRIMARY KEY, name varchar, date_inserted date, customer_id smallint, amount numeric(12,2), print_date date, pdf bytea);")
	progressbar (30)
	cursor.execute("CREATE TABLE customer_tax_exemptions (id serial PRIMARY KEY, customer_id integer, exemption_name varchar);")
	progressbar (31)
	cursor.execute ("CREATE TABLE inventory_transactions (id serial PRIMARY KEY, product_id integer, amount integer, reason varchar, date_inserted date);")
	progressbar (32)
	cursor.execute("CREATE TABLE product_location (id serial PRIMARY KEY, product_id integer, rack varchar, cart varchar, shelf varchar, cabinet varchar, drawer varchar, locator_visible boolean);")
	progressbar (33)
	cursor.execute("CREATE TABLE time_clock_entries (id serial PRIMARY KEY, employee varchar, start_time bigint, stop_time bigint, project varchar, state varchar );")
	progressbar (34)
	cursor.execute("CREATE TABLE time_clock_projects (id serial PRIMARY KEY, name varchar, total_time bigint, start_date date, stop_date date, active boolean, permanent boolean, job_sheet_id int);")
	progressbar (35)
	cursor.execute("CREATE TABLE products_manufactured_line_items (id serial PRIMARY KEY, manufactured_product_id integer, qty smallint, assembly_product_id integer, remark varchar, alternative_to_id integer);")
	progressbar (36)
	cursor.execute("CREATE TABLE document_types (id serial PRIMARY KEY, name varchar, text1 varchar, text2 varchar, text3 varchar, text4 varchar, text5 varchar, text6 varchar, text7 varchar, text8 varchar, text9 varchar, text10 varchar, text11 varchar, text12 varchar);")
	progressbar (37)
	cursor.execute("INSERT INTO document_types (name, text1, text2, text3, text4, text5, text6, text7, text8, text9, text10, text11, text12) VALUES ('Quotes', '', '', '', '', '', '', '', '', '', '', '', '')")
	progressbar (38)
	cursor.execute("CREATE TABLE documents (id serial PRIMARY KEY, name varchar, contact_id bigint, invoiced boolean, canceled boolean, closed boolean, printed boolean, date_paid date, date_printed date, date_created date, deleteable boolean, subtotal numeric(12,2), tax numeric(12,2), total numeric(12,2), pdf_data bytea, document_type_id smallint,pending_invoice boolean);")
	progressbar (39)
	cursor.execute("CREATE TABLE documents_line_items (id serial PRIMARY KEY, barcode varchar, document_id bigint, qty numeric(12,2), product_id integer, min numeric(12,2), max numeric(12,2), retailer_id integer, type_1 boolean, type_2 varchar, type_3 varchar, type_4 varchar, priority varchar, remark varchar, price numeric(12,2), tax numeric(12,2), ext_price numeric(12,2), canceled boolean, tax_description varchar, finished numeric(12, 2));")
	progressbar (40)
	cursor.execute("CREATE TABLE document_settings (id serial PRIMARY KEY, column_name varchar, visible boolean, other_name varchar);")
	progressbar (41)
	cursor.executemany("INSERT INTO document_settings (column_name, visible) VALUES (%s, %s)", [("qty", True), ("product", True), ("remarks", True), ("price", True), ("tax", True), ("ext_price", True), ("min", True), ("max", True), ('retailer', True)])
	progressbar (42)
	cursor.execute("CREATE TABLE document_column_settings (id serial PRIMARY KEY, column_name varchar, visible boolean, header_name varchar);")
	progressbar (43)
	cursor.executemany("INSERT INTO document_column_settings (column_name, visible) VALUES (%s, %s)", [("qty", True), ("product", True), ("remarks", True), ("price", True), ("tax", True), ("ext_price", True), ("min", True), ("max", True), ('retailer', True), ("type_1", True), ("type_2", True), ("type_3", True), ("type_4", True), ("priority", True)])
	progressbar (44)
	check_and_update_version (db, statusbar)

def check_and_update_version (db, statusbar):
	global COMPLETE_PROGRESS
	statusbar.push(1, "Upgrading tables ...")
	cursor = db.cursor()
	cursor.execute("SELECT version FROM settings")
	version = cursor.fetchone()[0]
	COMPLETE_PROGRESS = 91.00
	progressbar (1)
	if version <= "016":
		progressbar (16)
		cursor.execute("ALTER TABLE documents_line_items ADD qa_contact_id integer;")
	if version <= "018":
		progressbar (18)
		cursor.execute("ALTER TABLE time_clock_entries ADD employee_id integer;")
		cursor.execute("ALTER TABLE time_clock_entries ADD project_id integer;")
	if version <= "019":
		progressbar (19)
		cursor.execute("ALTER TABLE time_clock_entries ADD invoiced boolean;")
		cursor.execute("ALTER TABLE time_clock_entries ADD employee_paid boolean;")
	if version <= "020":
		progressbar (20)
		cursor.execute("ALTER TABLE products ADD ext_name varchar;")
		cursor.execute("UPDATE products SET ext_name = ''")
	if version <= "021":
		progressbar (21)
		cursor.execute("ALTER TABLE invoice_line_items ADD product_id integer;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD product_id integer;")
	if version <= "022":
		progressbar (22)
		cursor.execute("ALTER TABLE products ADD stock boolean DEFAULT True;")
		cursor.execute("UPDATE products SET stock = True")
	if version <= "023":
		progressbar (23)
		cursor.execute("ALTER TABLE documents ADD invoice_id integer;")
	if version <= "024":
		progressbar (24)
		cursor.execute("ALTER TABLE accounts ADD expense_account boolean;")
		cursor.execute("ALTER TABLE accounts ADD bank_account boolean;")
		cursor.execute("ALTER TABLE accounts ADD credit_card_account boolean;")
		cursor.execute("UPDATE accounts SET credit_card_account = False")
		cursor.execute("UPDATE accounts SET expense_account = False")
		cursor.execute("UPDATE accounts SET bank_account = False")
		cursor.execute("INSERT INTO accounts (name, amount, deleteable, number, parent_number, is_parent, expense_account, bank_account, credit_card_account) VALUES (%s, %s, %s, %s, %s, False, True, False, False)", ("COGS Account", 0.00, False, 3100, 3000 ))
	if version <= "025":
		progressbar (25)
		cursor.execute("ALTER TABLE purchase_order_line_items ADD expense_account smallint;")
	if version <= "026":
		progressbar (26)
		cursor.execute("ALTER TABLE products ADD default_expense_account smallint;")
	if version <= "027":
		progressbar (27)
		cursor.execute("ALTER TABLE settings RENAME enter_save TO refresh_documents_price_on_import;")
		cursor.execute("UPDATE settings SET refresh_documents_price_on_import = False")
	if version <= "028":
		progressbar (28)
		cursor.execute("DROP TABLE account_flow_settings;")
		cursor.execute("CREATE TABLE account_flow_settings (id serial PRIMARY KEY, function varchar, account smallint);") # the table where all the money flow signals get hooked up
		cursor.executemany("INSERT INTO account_flow_settings (function, account) VALUES (%s, %s)", [("check_payment", 1200), ("credit_card_payment", 1300),  ("cash_payment", 1400), ("post_purchase_order", 5100), ("sales_tax", 5210), ("post_invoice", 1100), ("credit_card_income", 4130), ("cash_income", 4110), ("check_income", 4120), ("credit_card_penalty", 3200) ])
		cursor.execute("INSERT INTO accounts (name, amount, deleteable, number, parent_number, is_parent, expense_account, bank_account, credit_card_account) VALUES (%s, %s, %s, %s, %s, False, True, False, False)", ("Credit Card Penalty", 0.00, False, 3200, 3000 ))
	if version <= "029":
		progressbar (29)
		cursor.execute("DROP TABLE document_settings;")
		cursor.execute("ALTER TABLE account_transaction_lines ADD transaction_table varchar;")
		cursor.execute("ALTER TABLE account_transaction_lines ADD transaction_id integer;")
		cursor.execute("ALTER TABLE account_transaction_lines ADD transaction_description varchar;")
	if version <= "030":
		progressbar (30)
		cursor.execute("ALTER TABLE payments_incoming DROP COLUMN customer_id;")
		cursor.execute("ALTER TABLE payments_incoming ADD customer_id integer;")
	if version <= "031":
		progressbar (31)
		cursor.execute("ALTER TABLE payments_incoming ADD check_payment boolean;")
		cursor.execute("ALTER TABLE payments_incoming ADD check_deposited boolean;")
		cursor.execute("ALTER TABLE payments_incoming ADD cash_payment boolean;")
		cursor.execute("ALTER TABLE payments_incoming ADD credit_card_payment boolean;")
	if version <= "032":
		progressbar (32)
		cursor.execute("CREATE TABLE locations (id serial PRIMARY KEY, name varchar);")
		cursor.execute("INSERT INTO locations (name) VALUES ('Warehouse')")
		cursor.execute("ALTER TABLE product_location ADD location_id integer;")
		cursor.execute("UPDATE product_location SET location_id = 1")
	if version <= "033":
		progressbar (33)
		cursor.execute("ALTER TABLE product_location ADD aisle varchar;")
		cursor.execute("UPDATE product_location SET aisle = ''")
		cursor.execute("ALTER TABLE product_location ADD bin varchar;")
		cursor.execute("UPDATE product_location SET bin = ''")
	if version <= "034":
		progressbar (34)
		cursor.execute("ALTER TABLE purchase_orders RENAME deleteable TO received;")
	if version <= "035":
		progressbar (35)
		cursor.execute("ALTER TABLE invoices ADD posted boolean;")
		cursor.execute("ALTER TABLE products ADD inventory_enabled boolean;")
		cursor.execute("UPDATE products SET inventory_enabled = False;")
	if version <= "036":
		progressbar (36)
		cursor.execute("ALTER TABLE inventory_transactions ADD invoice_line_item_id bigint;")
		cursor.execute("ALTER TABLE inventory_transactions ADD location_id integer;")
		cursor.execute("ALTER TABLE inventory_transactions RENAME amount TO qty;")
		cursor.execute("ALTER TABLE vendor_product_numbers ADD vendor_barcode varchar;")
		cursor.execute("UPDATE vendor_product_numbers SET vendor_barcode = ''")
	if version <= "037":
		progressbar (37)
		cursor.execute("ALTER TABLE invoice_line_items ADD imported boolean;")
		cursor.execute("UPDATE invoice_line_items SET imported = False;")
		cursor.execute("UPDATE invoices SET posted = False;")
		cursor.execute("UPDATE invoices SET posted = True WHERE closed = True OR paid = True;")
		cursor.execute("ALTER TABLE job_sheet_line_items RENAME remarks TO remark;")
	if version <= "038":
		progressbar (38)
		cursor.execute("ALTER TABLE statements ADD printed boolean;")
		cursor.execute("UPDATE statements SET printed = False;")
	if version <= "039":
		progressbar (39)
		cursor.execute("CREATE TABLE terms_and_discounts (id serial PRIMARY KEY, name varchar, cash_only boolean, discount_percent integer, pay_in_days smallint, pay_by_day_of_month smallint);")
		cursor.execute("ALTER TABLE contacts ADD terms_and_discounts_id integer REFERENCES terms_and_discounts(id) ON DELETE RESTRICT;")
	if version <= "040":
		progressbar (40)
		cursor.execute("CREATE TABLE manufacturing_projects (id serial PRIMARY KEY, name varchar, product_id integer REFERENCES products ON DELETE RESTRICT, time_clock_projects_id integer REFERENCES time_clock_projects ON DELETE RESTRICT, qty integer, active boolean);")
	if version <= "041":
		progressbar (41)
		cursor.execute("ALTER TABLE invoices ADD FOREIGN KEY (customer_id) REFERENCES contacts(id) ON DELETE RESTRICT;")
	if version <= "042":
		progressbar (42)
		cursor.execute("ALTER TABLE documents ADD FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE purchase_orders ADD FOREIGN KEY (vendor_id) REFERENCES contacts(id) ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE documents_line_items ADD FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE RESTRICT;")
	if version <= "043":
		progressbar (43)
		cursor.execute("ALTER TABLE terms_and_discounts ADD pay_in_days_active boolean;")
		cursor.execute("ALTER TABLE terms_and_discounts ADD pay_by_day_of_month_active boolean;")
		cursor.execute("ALTER TABLE terms_and_discounts ADD standard boolean;")
		cursor.execute("INSERT INTO terms_and_discounts (name, cash_only, discount_percent, pay_in_days_active, pay_in_days, pay_by_day_of_month_active, pay_by_day_of_month, standard) VALUES ('Net 30', False, 5, True, 30, False, 0, True);")
	if version <= "044":
		progressbar (44)
		cursor.execute("ALTER TABLE terms_and_discounts ADD markup_percent integer;")
		cursor.execute("UPDATE terms_and_discounts SET markup_percent = 35;")
	if version <= "045":
		progressbar (45)
		cursor.execute("CREATE TABLE products_terms_prices (id serial PRIMARY KEY, product_id bigint REFERENCES products ON DELETE RESTRICT, term_id bigint REFERENCES terms_and_discounts ON DELETE RESTRICT, price numeric(12,2));")
		cursor.execute("UPDATE contacts SET terms_and_discounts_id = 1")
	if version <= "046":
		progressbar (46)
		cursor.execute("ALTER TABLE accounts ADD income_account boolean DEFAULT False;")
		cursor.execute("ALTER TABLE public.accounts DROP CONSTRAINT accounts_pkey;")
		cursor.execute("""ALTER TABLE public.accounts ADD PRIMARY KEY ("number");""")
		cursor.execute("UPDATE account_transaction_lines SET debit_account = NULL WHERE debit_account = 0")
		cursor.execute("UPDATE account_transaction_lines SET credit_account = NULL WHERE credit_account = 0")
		cursor.execute("ALTER TABLE account_transaction_lines ADD FOREIGN KEY (debit_account) REFERENCES accounts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE account_transaction_lines ADD FOREIGN KEY (credit_account) REFERENCES accounts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE invoice_line_items ADD account_transaction_lines_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE products ADD income_account integer REFERENCES accounts(number) ON DELETE RESTRICT")
		cursor.execute("UPDATE products SET income_account = 4140")
		cursor.execute("ALTER TABLE account_flow_settings ADD FOREIGN KEY (account) REFERENCES accounts ON DELETE RESTRICT;")
	if version <= "047":
		progressbar (47)
		cursor.execute("ALTER TABLE invoices ADD FOREIGN KEY (customer_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE job_sheets ADD FOREIGN KEY (contact_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE job_sheets ADD FOREIGN KEY (job_type_id) REFERENCES job_types ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE job_sheet_line_items ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE job_sheet_line_items RENAME job_id TO job_sheet_id;")
		cursor.execute("ALTER TABLE job_sheet_line_items ADD FOREIGN KEY (job_sheet_id) REFERENCES job_sheets ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE invoice_line_items ADD FOREIGN KEY (invoice_id) REFERENCES invoices ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE invoice_line_items ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("""ALTER TABLE accounts ADD UNIQUE ("number");""")
		cursor.execute("ALTER TABLE documents ADD FOREIGN KEY (document_type_id) REFERENCES document_types ON DELETE RESTRICT;")
		cursor.execute("UPDATE documents_line_items SET qa_contact_id = NULL WHERE qa_contact_id = 0")
		cursor.execute("ALTER TABLE documents_line_items ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE documents_line_items ADD FOREIGN KEY (retailer_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE documents_line_items ADD FOREIGN KEY (qa_contact_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE customer_tax_exemptions ADD FOREIGN KEY (customer_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE files ADD FOREIGN KEY (contact_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE incoming_invoices ADD FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE inventory_transactions ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE inventory_transactions ADD FOREIGN KEY (location_id) REFERENCES locations ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE payments_incoming ADD FOREIGN KEY (debit_account) REFERENCES accounts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE payments_incoming ADD FOREIGN KEY (credit_account) REFERENCES accounts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE product_location ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE product_location ADD FOREIGN KEY (location_id) REFERENCES locations ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE products_manufactured_line_items ADD FOREIGN KEY (manufactured_product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE products_manufactured_line_items ADD FOREIGN KEY (assembly_product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE statements ADD FOREIGN KEY (customer_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE time_clock_entries ADD FOREIGN KEY (employee_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE time_clock_entries ADD FOREIGN KEY (project_id) REFERENCES time_clock_projects ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE vendor_product_numbers ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE vendor_product_numbers ADD FOREIGN KEY (vendor_id) REFERENCES contacts ON DELETE RESTRICT;")
	if version <= "048":
		progressbar (48)
		cursor.execute("ALTER TABLE public.documents RENAME date_paid TO dated_for;")
	if version <= "049":
		progressbar (49)
		cursor.execute("ALTER TABLE public.invoices ADD COLUMN doc_type varchar;")
		cursor.execute("UPDATE public.invoices SET doc_type = 'Invoice';")
	if version <= "050":
		progressbar (50)
		cursor.execute("ALTER TABLE time_clock_entries ADD COLUMN actual_seconds bigint;")
		cursor.execute("ALTER TABLE time_clock_entries ADD COLUMN adjusted_seconds bigint;")
		cursor.execute("UPDATE time_clock_entries SET actual_seconds = stop_time - start_time;")
		cursor.execute("CREATE OR REPLACE FUNCTION update_time_entry_seconds() RETURNS TRIGGER AS $$ "
							"DECLARE seconds integer; "
							"BEGIN "
								"SELECT stop_time - start_time INTO seconds FROM time_clock_entries WHERE id = OLD.id; "
								"UPDATE time_clock_entries SET (actual_seconds, adjusted_seconds) = (seconds, seconds) WHERE id = OLD.id; "
								"RETURN OLD; "
							"END; "
							"$$ LANGUAGE plpgsql;")
	if version <= "051":
		progressbar (51)
		cursor.execute("CREATE TRIGGER start_time_changed_trigger AFTER UPDATE OF start_time ON time_clock_entries FOR EACH ROW EXECUTE PROCEDURE update_time_entry_seconds();")
		cursor.execute("CREATE TRIGGER stop_time_changed_trigger AFTER UPDATE OF stop_time ON time_clock_entries FOR EACH ROW EXECUTE PROCEDURE update_time_entry_seconds();")
		cursor.execute("SELECT id, start_time, stop_time FROM time_clock_entries WHERE state = 'complete'")
		for row in cursor.fetchall():
			row_id = row[0]
			seconds = row[2] - row[1]
			cursor.execute("UPDATE time_clock_entries SET (actual_seconds, adjusted_seconds) = (%s, %s) WHERE id = %s", (seconds, seconds, row_id))
	if version <= "052":
		progressbar (52)
		cursor.execute("CREATE TABLE pay_stubs (id serial PRIMARY KEY, employee_id integer REFERENCES contacts ON DELETE RESTRICT, date_inserted date, regular_hours numeric(12,2), overtime_hours numeric(12,2), cost_sharing_hours numeric(12,2), profit_sharing_hours numeric(12,2), pdf_data bytea);")
		cursor.execute("CREATE TABLE employee_payments (id serial PRIMARY KEY, employee_id integer REFERENCES contacts ON DELETE RESTRICT, date_inserted date, amount_paid numeric(12,2), account_transaction_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT);")
		cursor.execute("CREATE TABLE employee_payments_paystubs_ids (id serial PRIMARY KEY, employee_payment_id integer REFERENCES employee_payments ON DELETE RESTRICT, pay_stub_id integer REFERENCES pay_stubs ON DELETE RESTRICT);")
		cursor.execute("ALTER TABLE time_clock_entries ADD COLUMN pay_stub_id integer REFERENCES pay_stubs ON DELETE RESTRICT;")
	if version <= "053":
		progressbar (53)
		cursor.execute("ALTER TABLE tax_rates ADD COLUMN exemption boolean;")
		cursor.execute("ALTER TABLE tax_rates ADD COLUMN exemption_template_path varchar;")
		cursor.execute("UPDATE tax_rates SET exemption = False;")
		cursor.execute("ALTER TABLE invoice_line_items ADD COLUMN tax_rate_id integer REFERENCES tax_rates ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE tax_rates ADD COLUMN deleted boolean;")
		cursor.execute("UPDATE tax_rates SET deleted = False;")
		cursor.execute("ALTER TABLE customer_tax_exemptions ADD COLUMN tax_rate_id integer REFERENCES tax_rates ON DELETE RESTRICT;")
	if version <= "054":
		progressbar (54)
		cursor.execute("ALTER TABLE invoices ADD COLUMN comments varchar;")
		cursor.execute("ALTER TABLE purchase_orders ADD COLUMN comments varchar;")
		cursor.execute("ALTER TABLE documents ADD COLUMN comments varchar;")
	if version <= "055":
		progressbar (55)
		cursor.execute("ALTER TABLE vendor_product_numbers ADD qty smallint;")
		cursor.execute("ALTER TABLE vendor_product_numbers ADD price numeric (12, 2);")
		cursor.execute("UPDATE vendor_product_numbers SET (qty, price) = (0, 0);")
	if version <= "056":
		progressbar (56)
		cursor.execute("ALTER TABLE invoices ADD COLUMN account_transaction_lines_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE purchase_orders ADD COLUMN account_transaction_lines_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE payments_incoming ADD COLUMN account_transaction_lines_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD COLUMN account_transaction_lines_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
	if version <= "057":
		progressbar (57)
		cursor.execute("ALTER TABLE invoices ADD COLUMN amount_due numeric (12, 2);")
	if version <= "058":
		progressbar (58)
		cursor.execute("INSERT INTO accounts (name, amount, deleteable, number, parent_number, is_parent, expense_account, bank_account, credit_card_account, income_account) VALUES (%s, %s, %s, %s, %s, False, False, False, False, False)", ('Customer Discounts', 0.00, False, 3900, 3000))
		cursor.execute("UPDATE accounts SET is_parent = True WHERE number = %s", (3000, ))
		cursor.execute("INSERT INTO account_flow_settings (function, account) VALUES ('customer_discount', 3900)")
		cursor.execute("UPDATE vendor_product_numbers SET qty = 1 WHERE qty IS NULL")
		cursor.execute("UPDATE vendor_product_numbers SET price = 0.00 WHERE price IS NULL")
	#0.2.0
	if version <= "059":
		progressbar (59)
		cursor.execute("UPDATE vendor_product_numbers SET qty = 0 WHERE qty IS NULL")
		cursor.execute("UPDATE vendor_product_numbers SET price = 0.00 WHERE price IS NULL")
		cursor.execute("UPDATE invoices SET amount_due = total WHERE amount_due IS NULL")
		cursor.execute("ALTER TABLE account_transaction_lines DROP contact;")
		cursor.execute("UPDATE vendor_product_numbers SET (qty, price) = (0, 0) WHERE qty = NULL;")
		cursor.execute("UPDATE tax_rates SET exemption = False WHERE exemption = NULL;")
		cursor.execute("ALTER TABLE account_transaction_lines DROP account_name;")
		cursor.execute("ALTER TABLE payments_incoming DROP name;")
		cursor.execute("ALTER TABLE payments_incoming DROP credit_account;")
		cursor.execute("ALTER TABLE payments_incoming DROP debit_account;")
		cursor.execute("ALTER TABLE payments_incoming DROP payment_type;")
		cursor.execute("DROP TABLE public.checks_incoming;")
		cursor.execute("ALTER TABLE documents_line_items DROP barcode;")
		cursor.execute("ALTER TABLE invoice_line_items DROP barcode;")
		cursor.execute("ALTER TABLE invoice_line_items DROP product;")
		cursor.execute("ALTER TABLE job_sheets DROP job_sequential_number;")
		cursor.execute("ALTER TABLE purchase_order_line_items DROP barcode;")
		cursor.execute("ALTER TABLE purchase_order_line_items DROP product;")
		cursor.execute("ALTER TABLE time_clock_entries DROP project;")
		cursor.execute("ALTER TABLE time_clock_entries DROP employee;")
		cursor.execute("ALTER TABLE contacts ADD COLUMN service_provider BOOLEAN")
		cursor.execute("UPDATE contacts SET service_provider = False")
		cursor.execute("ALTER TABLE contacts ALTER COLUMN service_provider SET NOT NULL")
	if version <= "060":
		progressbar (60)
		cursor.execute("ALTER TABLE account_transaction_lines ALTER COLUMN id TYPE bigint;")
		cursor.execute("ALTER TABLE invoices DROP deleteable;")
		cursor.execute("ALTER TABLE invoices ADD COLUMN account_transaction_lines_tax_id bigint REFERENCES account_transaction_lines ON DELETE RESTRICT;")
		#invoice linking fixes
		cursor.execute("SELECT id FROM invoices WHERE posted = True")
		for row in cursor.fetchall():
			in_id = row[0]
			cursor.execute("SELECT id FROM account_transaction_lines "
				"WHERE (credit_account, transaction_table, transaction_id) = "
				"((SELECT account FROM account_flow_settings "
				"WHERE function = 'post_invoice'), %s, %s)", 
				("invoices", in_id))
			for row in cursor.fetchall():
				transaction_id = row[0]
				cursor.execute("UPDATE invoices SET account_transaction_lines_id = %s WHERE id = %s", (transaction_id, in_id))
			cursor.execute("SELECT id FROM account_transaction_lines "
				"WHERE (credit_account, transaction_table, transaction_id) = "
				"((SELECT account FROM account_flow_settings "
				"WHERE function = 'sales_tax'), %s, %s)", 
				("invoices", in_id))
			for row in cursor.fetchall():
				transaction_id = row[0]
				cursor.execute("UPDATE invoices SET account_transaction_lines_tax_id = %s WHERE id = %s", (transaction_id, in_id))
		#purchase order linking fixes
		cursor.execute("SELECT id FROM purchase_orders WHERE closed = True")
		for row in cursor.fetchall():
			po_id = row[0]
			cursor.execute("SELECT id FROM account_transaction_lines "
				"WHERE (credit_account, transaction_table, transaction_id) = "
				"((SELECT account FROM account_flow_settings "
				"WHERE function = 'post_purchase_order'), %s, %s)", 
				("purchase_orders", po_id))
			for row in cursor.fetchall():
				transaction_id = row[0]
				cursor.execute("UPDATE purchase_orders SET account_transaction_lines_id = %s WHERE id = %s", (transaction_id, po_id))
		#payments incoming linking fixes
		cursor.execute("SELECT id FROM payments_incoming")
		for row in cursor.fetchall():
			pi_id = row[0]
			cursor.execute("SELECT id FROM account_transaction_lines "
					"WHERE (transaction_table, transaction_id) = "
					"(%s, %s)", 
					("payments_incoming", pi_id))
			for row in cursor.fetchall():
				transaction_id = row[0]
				cursor.execute("UPDATE payments_incoming SET account_transaction_lines_id = %s WHERE id = %s", (transaction_id, pi_id))
		#reversed account entries fix
		cursor.execute("SELECT id, debit_account, credit_account FROM account_transaction_lines")
		for row in cursor.fetchall():
			row_id = row[0]
			debit_account = row[1]
			credit_account = row[2]
			cursor.execute("UPDATE account_transaction_lines SET (debit_account, credit_account) = (%s, %s) WHERE id = %s", (credit_account, debit_account, row_id))
		cursor.execute("ALTER TABLE public.payments_incoming ALTER COLUMN id TYPE bigint;")
		cursor.execute("ALTER TABLE public.purchase_orders ADD COLUMN invoice_description varchar;")
		cursor.execute("SELECT purchase_order_id, paid, description FROM incoming_invoices")
		for row in cursor.fetchall():
			po_id = row[0]
			paid = row[1]
			description = row[2]
			cursor.execute("UPDATE purchase_orders SET (invoiced, invoice_description) = (%s, %s) WHERE id = %s", (paid, description, po_id))
		# update purchase_order table
		cursor.execute("ALTER TABLE public.purchase_orders RENAME COLUMN invoiced TO paid;")
		cursor.execute("ALTER TABLE public.incoming_invoices DROP CONSTRAINT incoming_invoices_purchase_order_id_fkey;")
		cursor.execute("ALTER TABLE public.incoming_invoices RENAME COLUMN purchase_order_id TO contact_id;")
		cursor.execute("ALTER TABLE incoming_invoices ADD FOREIGN KEY (contact_id) REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.incoming_invoices ADD COLUMN amount numeric(12, 2);")
		cursor.execute("ALTER TABLE public.accounts ADD COLUMN cash_account boolean DEFAULT False;")
		cursor.execute("TRUNCATE TABLE public.incoming_invoices;")
		cursor.execute("ALTER TABLE public.purchase_orders ADD COLUMN invoiced boolean;")
		cursor.execute("SELECT id, received FROM purchase_orders")
		for row in cursor.fetchall():
			row_id = row[0]
			received = row[1]
			cursor.execute("UPDATE purchase_orders SET invoiced = %s WHERE id = %s", (received, row_id))
		cursor.execute("ALTER TABLE public.products ADD COLUMN expense boolean DEFAULT False;")
		cursor.execute("ALTER TABLE public.account_transaction_lines ADD COLUMN fees_rewards boolean DEFAULT False;")
	if version <= "061":
		progressbar (61)
		cursor.execute("ALTER TABLE purchase_orders ADD COLUMN amount_due numeric (12, 2)")
		cursor.execute("UPDATE purchase_orders SET amount_due = total;")
		cursor.execute("ALTER TABLE public.purchase_orders ALTER COLUMN invoice_description SET DEFAULT '';")
	if version <= "062":
		progressbar (62)
		cursor.execute("ALTER TABLE account_transaction_lines DROP COLUMN canceled;")
		cursor.execute("ALTER TABLE account_transaction_lines DROP COLUMN transaction_table;")
		cursor.execute("ALTER TABLE account_transaction_lines DROP COLUMN transaction_id;")
	if version <= "063":
		progressbar (63)
		cursor.execute("ALTER TABLE account_transaction_lines ADD COLUMN check_number smallint;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD COLUMN order_number varchar;")
		cursor.execute("ALTER TABLE account_transaction_lines ALTER COLUMN reconciled SET DEFAULT False;")
		cursor.execute("UPDATE public.account_transaction_lines SET reconciled = False WHERE reconciled IS NULL")
	if version <= "064":
		progressbar (64)
		cursor.execute("CREATE TABLE resource_tags (id serial PRIMARY KEY, tag varchar, red float, green float, blue float, alpha float);")
		cursor.execute("CREATE TABLE resources (id serial PRIMARY KEY, parent_id integer REFERENCES resources(id) ON DELETE RESTRICT, subject varchar, contact_id integer REFERENCES contacts(id) ON DELETE RESTRICT, timed_seconds bigint, date_created date, dated_for date, tag_id integer REFERENCES resource_tags(id) ON DELETE RESTRICT, notes varchar DEFAULT '');")
		cursor.execute("SELECT purchase_order_line_items.id, product_id, vendor_id FROM purchase_order_line_items JOIN purchase_orders ON purchase_orders.id = purchase_order_line_items.purchase_order_id;")
		for row in cursor.fetchall():
			row_id = row[0]
			product_id = row[1]
			vendor_id = row[2]
			cursor.execute("SELECT vendor_sku FROM vendor_product_numbers WHERE (vendor_id, product_id) = (%s, %s)", (vendor_id, product_id))
			for row in cursor.fetchall():
				order_number = row[0]
				cursor.execute("UPDATE purchase_order_line_items SET order_number = %s WHERE id = %s", (order_number, row_id))
	if version <= "065":
		progressbar (65)
		cursor.execute("ALTER TABLE pay_stubs ADD COLUMN hourly_wage numeric(12, 2);")
	if version <= "066":
		progressbar (66)
		cursor.execute("ALTER TABLE resource_tags ADD COLUMN phone_default boolean DEFAULT False;")
		cursor.execute("ALTER TABLE resource_tags ADD COLUMN finished boolean DEFAULT False;")
		cursor.execute("ALTER TABLE resources ADD COLUMN phone_number varchar;")
	if version <= "067":
		progressbar (67)
		cursor.execute("ALTER TABLE customer_tax_exemptions ADD COLUMN pdf_data bytea;")
		cursor.execute("ALTER TABLE customer_tax_exemptions ADD COLUMN pdf_available boolean DEFAULT False;")
	if version <= "068":
		progressbar (68)
		cursor.execute("ALTER TABLE account_transaction_lines ADD COLUMN contact_id integer REFERENCES contacts ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE account_transaction_lines ADD COLUMN loan_payment boolean DEFAULT False;")
		cursor.execute("ALTER TABLE resources ADD COLUMN diary boolean DEFAULT False;")
		cursor.execute("ALTER TABLE products ADD COLUMN manufacturer_sku varchar DEFAULT '' CHECK (manufacturer_sku IS NOT NULL);")
		cursor.execute("ALTER TABLE products ADD COLUMN kit boolean DEFAULT False;")
	if version <= "069":
		progressbar (69)
		cursor.execute("ALTER TABLE products_manufactured_line_items RENAME TO product_assembly_items;")
	if version <= "070":
		progressbar (70)
		cursor.execute("ALTER TABLE accounts ADD COLUMN start_balance numeric (12, 2) DEFAULT 0.00 CHECK (start_balance IS NOT NULL);")
		cursor.execute("ALTER TABLE documents_line_items RENAME TO document_lines;")
		cursor.execute("ALTER TABLE resources ADD COLUMN call_received_time bigint;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN parent_number TYPE bigint;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN number TYPE bigint;")
		cursor.execute("ALTER TABLE public.account_transaction_lines ALTER COLUMN debit_account TYPE bigint;")
		cursor.execute("ALTER TABLE public.account_transaction_lines ALTER COLUMN credit_account TYPE bigint;")
		cursor.execute("ALTER TABLE public.account_flow_settings ALTER COLUMN account TYPE bigint;")
		cursor.execute("ALTER TABLE accounts ALTER COLUMN type TYPE smallint USING CAST(type as smallint);")
		cursor.execute("UPDATE accounts SET type = 1 WHERE number::text LIKE '1%'")
		cursor.execute("UPDATE accounts SET type = 2 WHERE number::text LIKE '2%'")
		cursor.execute("UPDATE accounts SET type = 3 WHERE number::text LIKE '3%'")
		cursor.execute("UPDATE accounts SET type = 4 WHERE number::text LIKE '4%'")
		cursor.execute("UPDATE accounts SET type = 5 WHERE number::text LIKE '5%'")
	if version <= "071":
		progressbar (71)
		cursor.execute("ALTER TABLE public.account_transaction_lines DROP CONSTRAINT account_transaction_lines_credit_account_fkey;")
		cursor.execute("ALTER TABLE public.account_transaction_lines DROP CONSTRAINT account_transaction_lines_debit_account_fkey;")
		cursor.execute("ALTER TABLE public.account_transaction_lines ADD CONSTRAINT account_transaction_lines_credit_account_fkey FOREIGN KEY (credit_account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.account_transaction_lines ADD CONSTRAINT account_transaction_lines_debit_account_fkey FOREIGN KEY (debit_account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.account_flow_settings DROP CONSTRAINT account_flow_settings_account_fkey;")
		cursor.execute("ALTER TABLE public.account_flow_settings ADD CONSTRAINT account_flow_settings_account_fkey FOREIGN KEY (account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("UPDATE accounts SET parent_number = Null WHERE parent_number = 0;")
		cursor.execute("ALTER TABLE public.accounts ADD CONSTRAINT accounts_parent_number_fkey FOREIGN KEY (parent_number) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
	if version <= "072":
		progressbar (72)
		cursor.execute("ALTER TABLE public.products ADD COLUMN inventory_account bigint REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.products RENAME kit TO job;")
		cursor.execute("ALTER TABLE invoice_line_items DROP tax_description;")
	if version <= "073":
		progressbar (73)
		cursor.execute("ALTER TABLE public.customer_tax_exemptions DROP CONSTRAINT customer_tax_exemptions_customer_id_fkey;")
		cursor.execute("ALTER TABLE customer_tax_exemptions ADD FOREIGN KEY (customer_id) REFERENCES contacts ON DELETE CASCADE;")
		cursor.execute("ALTER TABLE payments_incoming ADD FOREIGN KEY (customer_id) REFERENCES contacts ON DELETE RESTRICT;")
	if version <= "074":
		progressbar (74)
		cursor.execute("TRUNCATE TABLE organizations ;")
		cursor.execute("ALTER TABLE organizations ADD COLUMN contact_id bigint NOT NULL REFERENCES contacts ON DELETE CASCADE;")
		cursor.execute("ALTER TABLE organizations ADD COLUMN role varchar;")
		cursor.execute("ALTER TABLE organizations RENAME TO contact_individuals;")
		cursor.execute("CREATE SCHEMA payroll;")
		cursor.execute("ALTER TABLE public.employee_payments SET SCHEMA payroll;")
		cursor.execute("ALTER TABLE public.employee_payments_paystubs_ids SET SCHEMA payroll;")
		cursor.execute("ALTER TABLE public.pay_stubs SET SCHEMA payroll;")
		cursor.execute("ALTER TABLE public.contacts ADD COLUMN checks_payable_to varchar;")
		cursor.execute("UPDATE public.contacts SET checks_payable_to = '';")
		cursor.execute("CREATE TABLE payroll.employee_info (id serial PRIMARY KEY, employee_id bigint NOT NULL REFERENCES public.contacts ON DELETE RESTRICT, date_created date, born date, social_security varchar, social_security_exempt boolean, on_payroll_since date, wage numeric(12,2), payment_frequency smallint, married boolean, last_updated date, state_withholding_exempt boolean, state_credits smallint, state_extra_withholding numeric(12, 2), fed_withholding_exempt boolean, fed_credits smallint, fed_extra_withholding numeric(12, 2));")
		cursor.execute("CREATE TABLE payroll.tax_table (id serial PRIMARY KEY, tax_term date, s_s_percent numeric(12, 2), s_s_surcharge numeric(12, 2), medicare_percent numeric(12, 2), medicare_surcharge numeric(12, 2), state_standard_reduction numeric(12, 2), state_tax_credit numeric(12, 2), fed_standard_reduction numeric(12, 2), fed_tax_credit numeric(12, 2), unemployment_wage_base numeric(12, 2), unemployment_tax_rate numeric(12, 2), unemployment_surcharge numeric(12, 2), annual_filing_threshhold_941 numeric(12, 2), quarterly_filing_threshhold_941 numeric(12, 2), monthly_deposit_941 numeric(12, 2), daily_deposit_941 numeric(12, 2), active boolean);")
		cursor.execute("ALTER TABLE account_transaction_lines ADD COLUMN date_reconciled date")
		cursor.execute("ALTER TABLE public.products ADD UNIQUE (barcode);")
	if version <= "075":
		progressbar (75)
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN tax_table_id bigint NOT NULL REFERENCES payroll.tax_table;")
		cursor.execute("ALTER TABLE payroll.pay_stubs ALTER COLUMN employee_id SET NOT NULL;")
		cursor.execute("ALTER TABLE payroll.pay_stubs RENAME cost_sharing_hours TO cost_sharing;")
		cursor.execute("ALTER TABLE payroll.pay_stubs RENAME profit_sharing_hours TO profit_sharing;")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN s_s_withheld numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN medicare_withheld numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN state_withheld numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN fed_withheld numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN unemployment_liability numeric(12, 6);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN regular_hrs_total numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN overtime_hrs_total numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN tips_dividends_total numeric(12, 2);")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN gross_payment_amnt numeric(12, 2);")
	if version <= "076":
		progressbar (76)
		cursor.execute("CREATE TABLE payroll.employee_pdf_archive (id serial PRIMARY KEY, employee_id bigint REFERENCES public.contacts ON DELETE RESTRICT, s_s_medicare_exemption_pdf bytea, fed_withholding_pdf bytea, state_withholding_pdf bytea, archived boolean DEFAULT FALSE, date_inserted date);")
		cursor.execute("ALTER TABLE public.purchase_order_line_items ADD CONSTRAINT purchase_order_lines_expense_account_fkey FOREIGN KEY (expense_account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.products DROP CONSTRAINT products_income_account_fkey;")
		cursor.execute("ALTER TABLE public.products ADD CONSTRAINT products_default_expense_account_fkey FOREIGN KEY (default_expense_account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.products ADD CONSTRAINT products_income_account_fkey FOREIGN KEY (income_account) REFERENCES public.accounts (number) MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.product_location DROP CONSTRAINT product_location_product_id_fkey;")
		cursor.execute("ALTER TABLE product_location ADD FOREIGN KEY (product_id) REFERENCES products ON DELETE CASCADE;")
		cursor.execute("ALTER TABLE public.products_terms_prices DROP CONSTRAINT products_terms_prices_product_id_fkey;")
		cursor.execute("ALTER TABLE public.products_terms_prices ADD CONSTRAINT products_terms_prices_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products (id) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE CASCADE;")
		cursor.execute("ALTER TABLE public.document_lines ADD COLUMN s_price numeric(12,4) DEFAULT 0.00;")
		cursor.execute("ALTER TABLE public.document_lines ALTER COLUMN price TYPE numeric(12,4);")
		cursor.execute("ALTER TABLE public.invoice_line_items ALTER COLUMN price TYPE numeric(12,4);")
		cursor.execute("WITH tp AS (SELECT poli.id AS id, vendor_sku AS vs FROM purchase_order_line_items AS poli JOIN purchase_orders ON poli.purchase_order_id = purchase_orders.id JOIN vendor_product_numbers ON vendor_product_numbers.vendor_id = purchase_orders.vendor_id AND vendor_product_numbers.product_id = poli.product_id)  "
		"UPDATE purchase_order_line_items SET order_number = tp.vs FROM tp WHERE purchase_order_line_items.id = tp.id AND purchase_order_line_items.order_number IS NULL; ")
		cursor.execute("ALTER TABLE payroll.tax_table ALTER COLUMN s_s_percent TYPE numeric(12,5);")
		cursor.execute("ALTER TABLE payroll.tax_table ALTER COLUMN medicare_percent TYPE numeric(12,5);")
		cursor.execute("ALTER TABLE payroll.tax_table ALTER COLUMN unemployment_tax_rate TYPE numeric(12,5);")
		cursor.execute("ALTER TABLE payroll.tax_table ALTER COLUMN unemployment_surcharge TYPE numeric(12,5);")
		cursor.execute("DROP TABLE payroll.employee_payments_paystubs_ids;")
		cursor.execute("ALTER TABLE payroll.employee_payments ADD COLUMN pay_stub_id bigint REFERENCES payroll.pay_stubs ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE payroll.employee_info ADD COLUMN current boolean DEFAULT True;")
		cursor.execute("ALTER TABLE payroll.pay_stubs ADD COLUMN employee_info_id bigint NOT NULL REFERENCES payroll.employee_info ON DELETE RESTRICT;")
	if version <= "077":
		progressbar (77)
		cursor.execute("ALTER TABLE contact_individuals ADD COLUMN extension varchar;")
		cursor.execute("ALTER TABLE purchase_orders ADD COLUMN attached_pdf bytea;")
	if version <= "078":
		progressbar (78)
		cursor.execute("ALTER TABLE payments_incoming ADD COLUMN misc_income boolean DEFAULT False;")
		cursor.execute("ALTER TABLE settings DROP COLUMN header_1, DROP COLUMN header_2, DROP COLUMN header_3, DROP COLUMN header_4, DROP COLUMN time_clock_secure_login, DROP COLUMN discount_text_1, DROP COLUMN discount_text_2, DROP COLUMN discount_text_3, DROP COLUMN discount_text_4;")
		cursor.execute("ALTER TABLE public.settings RENAME enter_new_line TO enforce_exact_payment;")
		cursor.execute("UPDATE public.settings SET enforce_exact_payment = True;")
		cursor.execute("ALTER TABLE public.invoices ADD COLUMN statement_id bigint REFERENCES statements ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN expense_account SET DEFAULT False;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN bank_account SET DEFAULT False;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN credit_card_account SET DEFAULT False;")
		cursor.execute("ALTER TABLE public.accounts ALTER COLUMN income_account SET DEFAULT False;")
		cursor.execute("CREATE OR REPLACE FUNCTION public.after_accounts_edited() RETURNS trigger AS $$ "
						"DECLARE table_record accounts%ROWTYPE; "
						"DECLARE parents integer; "
							"BEGIN "
							"FOR table_record IN (SELECT * FROM accounts ) " 
								"LOOP "
								"UPDATE accounts SET is_parent = True WHERE number = table_record.parent_number; "
								"SELECT COUNT (id) FROM accounts WHERE parent_number = table_record.number INTO parents; "
								"IF parents = 0 THEN "
									"UPDATE accounts SET is_parent = False WHERE id = table_record.id; "
								"END  IF; "
								"END LOOP; " 
							"RETURN OLD; " 
						"END; "
						"$$ LANGUAGE plpgsql;")
		cursor.execute("CREATE OR REPLACE FUNCTION public.before_accounts_edited() RETURNS trigger AS $$ "
						"DECLARE counter integer; "
						"BEGIN "
						"SELECT COUNT (id) FROM public.account_transaction_lines WHERE debit_account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in account_transaction_lines', NEW.parent_number; "
							"END IF; "
						"SELECT COUNT (id) FROM public.account_transaction_lines WHERE credit_account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in account_transaction_lines', NEW.parent_number; "
							"END IF; "
						"SELECT COUNT (id) FROM account_flow_settings WHERE account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent-> already used in account_flow_settings', NEW.parent_number; "
							"END IF; "
						"RETURN NEW; "
						"END;"
						"$$ LANGUAGE plpgsql;")
		cursor.execute("CREATE TRIGGER after_accounts_edited "
						"AFTER INSERT OR UPDATE OF number, parent_number "
						"ON public.accounts "
						"FOR EACH STATEMENT "
						"EXECUTE PROCEDURE public.after_accounts_edited();")
		cursor.execute("CREATE TRIGGER before_accounts_edited "
						"BEFORE INSERT OR UPDATE OF number, parent_number "
						"ON public.accounts "
						"FOR EACH ROW "
						"EXECUTE PROCEDURE public.before_accounts_edited();")
	if version <= "079":
		progressbar (79)
		cursor.execute("ALTER TABLE products ADD COLUMN serial_number bigint DEFAULT 0 CHECK(serial_number IS NOT NULL)")
		cursor.execute ("ALTER TABLE public.accounts RENAME TO gl_accounts;")
		cursor.execute ("ALTER TABLE public.account_transaction_lines RENAME TO gl_entries;")
		cursor.execute ("ALTER TABLE public.account_flow_settings RENAME TO gl_account_flow;")
		cursor.execute ("CREATE TABLE gl_transactions (id serial PRIMARY KEY, date_inserted date NOT NULL);")
		cursor.execute ("ALTER TABLE gl_entries ADD COLUMN gl_transaction_id bigint REFERENCES gl_transactions ON DELETE RESTRICT")
		cursor.execute ("ALTER TABLE payments_incoming ADD COLUMN gl_entries_deposit_id bigint REFERENCES gl_entries ON DELETE RESTRICT")
	if version <= "080":
		progressbar (80)
		cursor.execute("ALTER TABLE public.payments_incoming RENAME account_transaction_lines_id TO gl_entries_id;")
		cursor.execute("ALTER TABLE public.purchase_order_line_items RENAME account_transaction_lines_id TO gl_entries_id;")
		cursor.execute("ALTER TABLE public.invoice_line_items RENAME account_transaction_lines_id  TO gl_entries_id;")
		cursor.execute("ALTER TABLE public.invoices RENAME account_transaction_lines_id TO gl_entries_id;")
		cursor.execute("ALTER TABLE public.invoices RENAME account_transaction_lines_tax_id  TO gl_entries_tax_id;")
		cursor.execute("ALTER TABLE public.purchase_orders RENAME account_transaction_lines_id  TO gl_entries_id;")
		cursor.execute("ALTER table public.gl_transactions ADD COLUMN contact_id bigint REFERENCES contacts ON DELETE RESTRICT")
		cursor.execute("ALTER table public.gl_transactions ADD COLUMN loan_payment boolean DEFAULT False")
	if version <= "081":
		progressbar (81)
		cursor.execute("CREATE OR REPLACE FUNCTION public.after_accounts_edited() RETURNS trigger AS $$ "
						"DECLARE table_record gl_accounts%ROWTYPE; "
						"DECLARE parents integer; "
							"BEGIN "
							"FOR table_record IN (SELECT * FROM gl_accounts ) " 
								"LOOP "
								"UPDATE gl_accounts SET is_parent = True WHERE number = table_record.parent_number; "
								"SELECT COUNT (id) FROM gl_accounts WHERE parent_number = table_record.number INTO parents; "
								"IF parents = 0 THEN "
									"UPDATE gl_accounts SET is_parent = False WHERE id = table_record.id; "
								"END  IF; "
								"END LOOP; " 
							"RETURN OLD; " 
						"END; "
						"$$ LANGUAGE plpgsql;")
		cursor.execute("CREATE OR REPLACE FUNCTION public.before_accounts_edited() RETURNS trigger AS $$ "
						"DECLARE counter integer; "
						"BEGIN "
						"SELECT COUNT (id) FROM public.gl_entries WHERE debit_account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in gl_entries', NEW.parent_number; "
							"END IF; "
						"SELECT COUNT (id) FROM public.gl_entries WHERE credit_account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in gl_entries', NEW.parent_number; "
							"END IF; "
						"SELECT COUNT (id) FROM gl_account_flow WHERE account = NEW.parent_number INTO counter; "
							"IF counter > 0 THEN "
								"RAISE EXCEPTION 'Account % is not allowed as a parent-> already used in gl_account_flow', NEW.parent_number; "
							"END IF; "
						"RETURN NEW; "
						"END;"
						"$$ LANGUAGE plpgsql;")
		cursor.execute("DROP TRIGGER after_accounts_edited ON public.gl_accounts;")
		cursor.execute("DROP TRIGGER before_accounts_edited ON public.gl_accounts;")
		cursor.execute("CREATE TRIGGER after_accounts_edited "
						"AFTER INSERT OR UPDATE OF number, parent_number "
						"ON public.gl_accounts "
						"FOR EACH STATEMENT "
						"EXECUTE PROCEDURE public.after_accounts_edited();")
		cursor.execute("CREATE TRIGGER before_accounts_edited "
						"BEFORE INSERT OR UPDATE OF number, parent_number "
						"ON public.gl_accounts "
						"FOR EACH ROW "
						"EXECUTE PROCEDURE public.before_accounts_edited();")
	if version <= "082":
		progressbar (82)
		cursor.execute("ALTER TABLE public.gl_accounts ALTER COLUMN type SET NOT NULL;")
		cursor.execute("SELECT invoices.id, gl_entries_id, gl_entries_tax_id, ge.date_inserted FROM invoices JOIN gl_entries AS ge ON ge.id = invoices.gl_entries_id WHERE gl_entries_id IS NOT NULL")
		for row in cursor.fetchall():
			invoice_id = row[0]
			entries_id = row[1]
			tax_id = row[2]
			date_inserted = row[3]
			cursor.execute("INSERT INTO gl_transactions (date_inserted) VALUES (%s) RETURNING id", (date_inserted,))
			tx_id = cursor.fetchone()[0]
			cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (tx_id, tax_id))
			cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (tx_id, entries_id))
			cursor.execute("SELECT ge.id FROM gl_entries AS ge JOIN invoice_line_items ON invoice_line_items.gl_entries_id = ge.id WHERE invoice_id = %s", (invoice_id,))
			for row in cursor.fetchall():
				ge_id = row[0]
				cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (tx_id, ge_id))
		cursor.execute("SELECT purchase_orders.id, gl_entries_id, ge.date_inserted FROM purchase_orders JOIN gl_entries AS ge ON ge.id = purchase_orders.gl_entries_id WHERE gl_entries_id IS NOT NULL")
		for row in cursor.fetchall():
			po_id = row[0]
			entries_id = row[1]
			date = row[2]
			cursor.execute("INSERT INTO gl_transactions (date_inserted) VALUES (%s) RETURNING id", (date_inserted,))
			tx_id = cursor.fetchone()[0]
			cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (tx_id, entries_id))
			cursor.execute("SELECT ge.id FROM gl_entries AS ge JOIN purchase_order_line_items ON purchase_order_line_items.gl_entries_id = ge.id WHERE purchase_order_id = %s", (po_id,))
			for row in cursor.fetchall():
				ge_id = row[0]
				cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (tx_id, ge_id))
		cursor.execute("SELECT id, date_inserted, contact_id FROM gl_entries WHERE credit_account IS NOT NULL AND debit_account IS NOT NULL AND gl_transaction_id IS NULL AND loan_payment = False")
		for row in cursor.fetchall():
			row_id = row[0]
			date = row[1]
			contact_id = row[2]
			cursor.execute("INSERT INTO gl_transactions (date_inserted, contact_id) VALUES (%s, %s) RETURNING id", (date, contact_id))
			gl_id = cursor.fetchone()[0]
			cursor.execute("UPDATE gl_entries SET gl_transaction_id = %s WHERE id = %s", (gl_id, row_id))
		cursor.execute("UPDATE gl_entries SET credit_account = debit_account WHERE id IN (SELECT gl_entries.id FROM gl_entries JOIN gl_accounts ON gl_accounts.number = gl_entries.debit_account AND type = 4) AND debit_account IS NOT NULL ")
		cursor.execute("UPDATE gl_entries SET debit_account = NULL WHERE id IN (SELECT gl_entries.id FROM gl_entries JOIN gl_accounts ON gl_accounts.number = gl_entries.debit_account AND type = 4) AND debit_account IS NOT NULL ")
		cursor.execute("ALTER TABLE terms_and_discounts ADD COLUMN plus_date smallint DEFAULT 0, ADD COLUMN text1 varchar DEFAULT '', ADD COLUMN text2 varchar DEFAULT '', ADD COLUMN text3 varchar DEFAULT '', ADD COLUMN text4 varchar DEFAULT ''")
	if version <= "083":
		progressbar (83)
		cursor.execute ("ALTER TABLE payments_incoming ADD COLUMN payment_receipt_pdf bytea")
		cursor.execute ("ALTER TABLE payments_incoming DROP COLUMN reference")
		cursor.execute ("ALTER TABLE invoices ADD COLUMN payments_incoming_id bigint REFERENCES payments_incoming ON DELETE RESTRICT")
		cursor.execute ("ALTER TABLE tax_rates ADD COLUMN tax_letter varchar DEFAULT '' CHECK (tax_letter IS NOT NULL)")
		cursor.execute("ALTER TABLE public.products ALTER COLUMN default_expense_account TYPE bigint;")
		cursor.execute("ALTER TABLE public.products ALTER COLUMN income_account TYPE bigint;")
		cursor.execute("ALTER TABLE public.products ALTER COLUMN income_account SET NOT NULL;")
		cursor.execute("ALTER TABLE public.time_clock_entries ADD COLUMN invoice_line_id bigint REFERENCES invoice_line_items ON UPDATE RESTRICT ON DELETE RESTRICT")
		cursor.execute("ALTER TABLE public.products ADD CONSTRAINT products_tax_rate_id FOREIGN KEY (tax_rate_id) REFERENCES public.tax_rates (id) ON UPDATE RESTRICT ON DELETE RESTRICT;")
		cursor.execute("ALTER TABLE public.invoices RENAME closed TO active; ALTER TABLE public.invoices ALTER COLUMN active SET DEFAULT True; ALTER TABLE public.invoices ALTER COLUMN active SET NOT NULL;")
		cursor.execute("UPDATE invoices SET active = True")
	if version <= "084":
		progressbar (84)
		cursor.execute("ALTER TABLE tax_rates ADD COLUMN tax_received_account bigint REFERENCES gl_accounts ON DELETE RESTRICT ON UPDATE RESTRICT")
		cursor.execute("UPDATE tax_rates SET tax_received_account = (SELECT account FROM gl_account_flow WHERE function = 'sales_tax')")
		cursor.execute("UPDATE invoices SET date_paid = date_inserted FROM payments_incoming WHERE payments_incoming.id = invoices.payments_incoming_id;")
	if version <= "085":
		progressbar (85)
		cursor.execute("SELECT id, date_inserted, customer_id FROM payments_incoming")
		for row in cursor.fetchall():
			payment_id = row[0]
			date = row[1]
			customer_id = row[2]
			cursor.execute("(SELECT id, total - amount_due AS discount FROM "
							"(SELECT id, total, amount_due, SUM(amount_due) "
							"OVER (ORDER BY date_created, id) invoice_totals "
							"FROM invoices WHERE (posted, customer_id) "
							"= (True, %s) AND date_paid IS NULL) i "
							"WHERE invoice_totals <= "
							"(SELECT  payment_totals - invoice_totals FROM "
							"(SELECT COALESCE(SUM(amount_due), 0.0)  "
							"AS invoice_totals FROM invoices "
							"WHERE (customer_id, canceled) = (%s, False) AND date_paid IS NOT NULL) i, "
							"(SELECT COALESCE(SUM(amount), 0.0) "
							"AS payment_totals FROM payments_incoming "
							"WHERE (customer_id) = (%s)) p) "
							"ORDER BY id);", (customer_id, 
								customer_id, customer_id))
			for row in cursor.fetchall():
				invoice_id = row[0]
				cursor.execute("UPDATE invoices "
								"SET (payments_incoming_id, date_paid) "
								"= (%s, %s) "
								"WHERE id = %s", 
								(payment_id, date, invoice_id))
	
	if version <= "086":
		progressbar (86)
		cursor.execute("CREATE RULE product_inserted_rule AS ON INSERT TO products DO ALSO NOTIFY products, 'product_inserted'")
		cursor.execute("CREATE RULE product_changed_rule AS ON UPDATE TO products DO ALSO NOTIFY products, 'product_changed'")
		cursor.execute("CREATE RULE contact_inserted_rule AS ON INSERT TO contacts DO ALSO NOTIFY contacts, 'contact_inserted'")
		cursor.execute("CREATE RULE contact_changed_rule AS ON UPDATE TO contacts DO ALSO NOTIFY contacts, 'contact_changed'")
		cursor.execute("ALTER TABLE public.products ALTER COLUMN deleted SET DEFAULT False;")
	if version <= "087":
		progressbar (87)
		cursor.execute("ALTER TABLE products ADD COLUMN catalog boolean DEFAULT False")
		cursor.execute("ALTER TABLE products ADD COLUMN catalog_order integer DEFAULT 0")
		cursor.execute("ALTER TABLE products ADD COLUMN image bytea")
	if version <= "088":
		progressbar (88)
		cursor.execute("CREATE TABLE serial_numbers (id serial PRIMARY KEY, product_id bigint NOT NULL REFERENCES products ON DELETE RESTRICT, date_inserted date NOT NULL, serial_number varchar NOT NULL, invoice_line_item_id bigint REFERENCES invoice_line_items ON DELETE RESTRICT, purchase_order_line_item_id bigint REFERENCES purchase_order_line_items ON DELETE RESTRICT, manufacturing_id bigint REFERENCES manufacturing_projects ON DELETE RESTRICT)")
		cursor.execute("CREATE TABLE serial_number_history (id serial PRIMARY KEY, serial_number_id bigint NOT NULL REFERENCES serial_numbers ON DELETE RESTRICT, description varchar, date_inserted date NOT NULL, contact_id bigint NOT NULL REFERENCES contacts ON DELETE RESTRICT)")
		cursor.execute("ALTER TABLE products ADD COLUMN invoice_serial_numbers boolean DEFAULT False NOT NULL")
	if version <= '089':
		progressbar (89)
		cursor.execute("CREATE SCHEMA settings")
		cursor.execute("CREATE TABLE settings.invoice_columns (id serial PRIMARY KEY, column_id varchar NOT NULL, column_name varchar NOT NULL, visible boolean NOT NULL)")
		cursor.executemany("INSERT INTO settings.invoice_columns (column_id, column_name, visible) VALUES (%s, %s, True)", [('treeviewcolumn1', 'Qty'), ('treeviewcolumn2', 'Product'), ('treeviewcolumn7', 'Ext. name'), ('treeviewcolumn3', 'Remark'), ('treeviewcolumn4', 'Price'), ('treeviewcolumn5', 'Tax'), ('treeviewcolumn6', 'Ext. price')])
		cursor.execute("ALTER TABLE public.purchase_order_line_items ALTER COLUMN purchase_order_id SET NOT NULL")
		cursor.execute("ALTER TABLE public.payments_incoming ADD COLUMN statement_id bigint REFERENCES statements ON DELETE RESTRICT;")
		cursor.execute("UPDATE gl_account_flow SET function = 'sales_tax_canceled' WHERE function = 'sales_tax'")
		cursor.execute("ALTER TABLE settings ADD COLUMN accrual_based boolean DEFAULT False NOT NULL")
	if version <= '090':
		progressbar (90)
		cursor.execute("ALTER TABLE public.payments_incoming ALTER COLUMN closed SET DEFAULT false;")
		cursor.execute("ALTER TABLE public.payments_incoming ADD CONSTRAINT payments_incoming_not_null_check CHECK (closed IS NOT NULL);")
		cursor.execute("ALTER TABLE public.gl_entries ADD CONSTRAINT credit_or_debit_is_not_null CHECK (credit_account IS NOT NULL OR debit_account IS NOT NULL);")
		cursor.execute("CREATE TABLE settings.purchase_order (id serial PRIMARY KEY, qty_prec integer NOT NULL, price_prec integer NOT NULL);")
		cursor.execute("INSERT INTO settings.purchase_order (qty_prec, price_prec) VALUES (0, 2)")
		cursor.execute("ALTER TABLE public.products ALTER COLUMN income_account DROP NOT NULL;")
		cursor.execute("ALTER TABLE public.products ADD CHECK(income_account IS NOT NULL OR expense = True);")
		cursor.execute("ALTER TABLE public.serial_numbers ADD UNIQUE (product_id, serial_number);")
		cursor.execute("CREATE TABLE fiscal_years (id serial PRIMARY KEY, name varchar NOT NULL, start_date date NOT NULL, end_date date NOT NULL, active boolean NOT NULL)")
		cursor.execute("INSERT INTO fiscal_years (name, start_date, end_date, active) VALUES ('2016', '1-1-2016', '12-31-2016', True)")
		cursor.execute("INSERT INTO fiscal_years (name, start_date, end_date, active) VALUES ('2017', '1-1-2017', '12-31-2017', True)")
		cursor.execute("INSERT INTO fiscal_years (name, start_date, end_date, active) VALUES ('2018', '1-1-2018', '12-31-2018', True)")
		cursor.execute("ALTER TABLE settings ADD COLUMN statement_finish_date date")
		cursor.execute("ALTER TABLE public.payments_incoming ALTER COLUMN closed SET DEFAULT False")
		cursor.execute("UPDATE public.payments_incoming SET closed = False WHERE closed IS NULL;")
		cursor.execute("CREATE OR REPLACE FUNCTION payment_info (payments_incoming_id bigint) "
						"RETURNS varchar AS $$ "
						"DECLARE table_record payments_incoming%ROWTYPE; "
						"BEGIN "
						"SELECT * FROM payments_incoming WHERE id = payments_incoming_id INTO table_record; "
						"IF table_record.check_payment = True THEN "
							"RETURN 'Check '::varchar || table_record.payment_text; "
						"ELSEIF table_record.cash_payment = True THEN "
							"RETURN 'Cash '::varchar || table_record.payment_text; "
						"ELSEIF table_record.credit_card_payment = True THEN "
							"RETURN 'Credit card '::varchar || table_record.payment_text; "
						"ELSE RETURN ''; "
						"END IF;"
						"END; "
						"$$ LANGUAGE plpgsql;")
		cursor.execute("ALTER TABLE purchase_order_line_items ADD COLUMN hold boolean DEFAULT False")
		cursor.execute("UPDATE purchase_order_line_items SET hold = False")
		cursor.execute("ALTER TABLE purchase_order_line_items ALTER COLUMN hold SET NOT NULL")
		cursor.execute("CREATE RULE account_inserted_rule AS ON INSERT TO gl_accounts DO ALSO NOTIFY accounts, 'account_inserted'")
		cursor.execute("CREATE RULE account_changed_rule AS ON UPDATE TO gl_accounts DO ALSO NOTIFY accounts, 'account_changed'")
		cursor.execute("ALTER TABLE public.gl_accounts RENAME income_account TO revenue_account;")
		cursor.execute("ALTER TABLE public.products RENAME income_account TO revenue_account;")
	if version <= '091':
		progressbar (91)
		cursor.execute("CREATE TABLE settings.po_columns (id serial PRIMARY KEY, column_id varchar NOT NULL, column_name varchar NOT NULL, visible boolean NOT NULL)")
		cursor.executemany("INSERT INTO settings.po_columns (column_id, column_name, visible) VALUES (%s, %s, True)", [('treeviewcolumn1', 'Qty'), ('treeviewcolumn2', 'Product'), ('treeviewcolumn4', 'Order number'), ('treeviewcolumn8', 'Stock'), ('treeviewcolumn3', 'Ext. name'), ('treeviewcolumn5', 'Remarks'), ('treeviewcolumn6', 'Price'), ('treeviewcolumn7', 'Ext. price'), ('treeviewcolumn12', 'Hold')])
		cursor.execute("WITH gt AS (SELECT * FROM gl_transactions AS gt) UPDATE gl_entries SET date_inserted = gt.date_inserted FROM gt WHERE gl_entries.date_inserted IS NULL AND gt.id = gl_entries.gl_transaction_id")
		cursor.execute("CREATE OR REPLACE FUNCTION public.after_gl_entries_inserted() RETURNS trigger AS $$ "
						"DECLARE new_date date;"
						"BEGIN "
						"IF NEW.date_inserted IS NULL THEN "
						"SELECT date_inserted FROM gl_transactions WHERE gl_transactions.id = NEW.gl_transaction_id INTO new_date; "
						"UPDATE gl_entries SET date_inserted = new_date WHERE id = NEW.id; "
						"END IF; "
						"RETURN NEW; "
						"END;"
						"$$ LANGUAGE plpgsql;")
		cursor.execute("CREATE TRIGGER after_gl_entries_inserted_trigger AFTER INSERT ON gl_entries FOR EACH ROW EXECUTE PROCEDURE after_gl_entries_inserted();")
		cursor.execute("ALTER TABLE gl_accounts DROP COLUMN deleteable")
		cursor.execute("ALTER TABLE gl_accounts DROP COLUMN dependants")
		cursor.execute("ALTER TABLE gl_accounts ADD COLUMN inventory_account boolean DEFAULT False")
		cursor.execute("UPDATE gl_accounts SET inventory_account = False")
		cursor.execute("ALTER TABLE gl_accounts ALTER COLUMN inventory_account SET NOT NULL")
		cursor.execute("DELETE FROM gl_account_flow WHERE function = 'credit_card_penalty'")
		cursor.execute("DELETE FROM gl_account_flow WHERE function = 'credit_card_payment'")
		cursor.execute("ALTER TABLE gl_accounts DROP COLUMN start_balance")
		cursor.execute("ALTER TABLE gl_accounts DROP COLUMN amount")
		cursor.execute("CREATE OR REPLACE RULE default_tax_rate_not_deleteable AS ON DELETE TO public.tax_rates WHERE OLD.standard = TRUE DO INSTEAD NOTHING;")
	if version <= '092':
		progressbar (92)
		cursor.execute("ALTER TABLE contacts RENAME c_o TO ext_name")
		cursor.execute("UPDATE settings SET version = '093'")
	cursor.close()
	db.commit()

def lob_example (db):
	#for notice in self.db.notices:
	#	print notice
	#db lob to file
	'''loaded_lob = db.lobject(oid=101708, mode="rb", )
	r = loaded_lob.read()
	with open("/home/reuben/reuben2.jpg", 'wb') as f:
		f.write(r)'''
	#file to db lob
	'''new_lob = self.db.lobject(mode="wb", new_file="/home/reuben/reuben.jpg")
	new_oid = new_lob.oid
	new_lob.close()
	
	cursor.execute("UPDATE products SET oid = %s WHERE id = %s", (new_oid, id))'''


		
		
