/* insert_basic.sql

 Copyright (C) 2016 - reuben

 This program is free software, you can redistribute it and/or modify
 it under the terms of the GNU Lesser General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY, without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program. If not, see <http://www.gnu.org/licenses/>. */

--Insert gl_accounts parents
INSERT INTO gl_accounts 
	(name, type, number, parent_number) 
VALUES 
	('Assets', 1, 1000, NULL), 
	('Equities', 2, 2000, NULL), 
	('Expenses', 3, 3000, NULL), 
	('Revenue', 4, 4000, NULL), 
	('Liabilities', 5, 5000, NULL)
;
--Insert gl_accounts children
INSERT INTO gl_accounts 
	(name, type, number, parent_number) 
VALUES 
	('Accounts Receivable', 1, 1100, 1000), 
	('Checks to Deposit', 1, 1200, 1000), 
	('Checking Account', 1, 1300, 1000), 
	('Cash Drawer', 1, 1400, 1000),
	('COGS Account', 3, 3100, 3000 ),
	('Credit Card Penalty', 3, 3200, 3000 ),
	('Product Revenue', 4, 4100, 4000),
	('Accounts Payable', 5, 5100, 5000), 
	('Taxes', 5, 5200, 5000),
	('Sales Tax Collected', 5, 5210, 5200),
	('Credit Cards', 5, 5300, 5000),
	('Mastercard', 5, 5310, 5300),
	('Visa', 5, 5320, 5000)
;
--set bank account
UPDATE gl_accounts SET 
	(bank_account, deposits, check_writing) = (True, True, True)
WHERE number = 1300
; 
--set cash account
UPDATE gl_accounts SET 
	cash_account = True
WHERE number = 1400
; 
--set expense account
UPDATE gl_accounts SET 
	expense_account = True
WHERE number = 3100
; 
--set credit card account
UPDATE gl_accounts SET 
	credit_card_account = True
WHERE number = 5310 
; 
--set credit card account 2
UPDATE gl_accounts SET 
	credit_card_account = True
WHERE number = 5320 
; 
--set revenue account
UPDATE gl_accounts SET 
	revenue_account = True
WHERE number = 4100 
; 
--Insert tax rates
INSERT INTO tax_rates 
	(name, rate, standard, tax_letter, tax_received_account) 
VALUES 
	('10 percent', 10.00, True, 't', 5210)
;
--Insert example product
INSERT INTO products 
	(name, description, unit, cost, tax_rate_id, deleted, sellable, purchasable, min_inventory, reorder_qty, tax_exemptible, manufactured, weight, tare, default_expense_account, revenue_account) 
VALUES 
	('Example product', '', 1, 1.00, 1, False, True, True, 0, 0, True, False, 0.000, 0.000, 3100, 4100)
;

--Insert example terms and discounts
INSERT INTO terms_and_discounts 
	(name, cash_only, discount_percent, pay_in_days_active, pay_in_days, pay_by_day_of_month_active, pay_by_day_of_month, standard, markup_percent, plus_date) 
VALUES 
	('Net 30', False, 5, True, 30, False, 0, True, 0, 30)
;
--Insert customer markup percent
INSERT INTO customer_markup_percent 
	(name, markup_percent, standard)
VALUES 
	('Retail', 35, True)
;
--Insert default settings
INSERT INTO settings 
	(print_direct, enforce_exact_payment, refresh_documents_price_on_import, email_when_possible, version, accrual_based, statement_finish_date, cost_decrease_alert, last_backup, backup_frequency_days, statement_day_of_month, date_format, timestamp_format, request_po_attachment, major_version, minor_version) 
VALUES 
	(False, False, False, False, '132', False, now(), 0.25, now(), 7, 1, 'FMMon DD YYYY', 'FMMon DD YYYY HH12:MI:SS AM ', True, 3, 4)
;
--Insert account_flow
INSERT INTO gl_account_flow 
	(function, account) 
VALUES 
	('check_payment', 1200), 
	('credit_card_payment', 1300),  
	('cash_payment', 1400), 
	('post_purchase_order', 5100), 
	('sales_tax', 5210), 
	('post_invoice', 1100)
;
--Insert blank company info
INSERT INTO company_info 
	(name, street, city, state, zip, country, phone, fax, email, website, tax_number) 
VALUES 
	('', '', '', '', '', '', '', '', '', '', '')
;
--Insert example document type
INSERT INTO document_types 
	(name, text1, text2, text3, text4, text5, text6, text7, text8, text9, text10, text11, text12) 
VALUES 
	('Quotes', '', '', '', '', '', '', '', '', '', '', '', '')
;
--Insert default document column settings
INSERT INTO settings.document_columns 
	(column_id, column_name, visible) 
VALUES 
	('treeviewcolumn1', 'Qty', True), 
	('treeviewcolumn2', 'Product', True), 
	('treeviewcolumn7', 'Ext. name', True), 
	('treeviewcolumn8', 'Minimum', True),
	('treeviewcolumn9', 'Maximum', True), 
	('treeviewcolumn10', 'Retailer', True), 
	('treeviewcolumn11', 'Freeze', True), 
	('treeviewcolumn3', 'Remark', True), 
	('treeviewcolumn12', 'Priority', True), 
	('treeviewcolumn4', 'Price', True), 
	('treeviewcolumn13', 'S Price', True), 
	('treeviewcolumn6', 'Ext. price', True)
;
--Insert default invoice column settings
INSERT INTO settings.invoice_columns 
	(column_id, column_name, visible) 
VALUES 
	('treeviewcolumn1', 'Qty', True), 
	('treeviewcolumn2', 'Product', True), 
	('treeviewcolumn7', 'Ext. name', True), 
	('treeviewcolumn3', 'Remark', True), 
	('treeviewcolumn4', 'Price', True), 
	('treeviewcolumn5', 'Tax', True), 
	('treeviewcolumn6', 'Ext. price', True)
;
--Insert default purchase order column settings
INSERT INTO settings.po_columns 
	(column_id, column_name, visible) 
VALUES 	
	('treeviewcolumn1', 'Qty', True), 
	('treeviewcolumn2', 'Product', True), 
	('treeviewcolumn4', 'Order number', True), 
	('treeviewcolumn8', 'Stock', True), 
	('treeviewcolumn3', 'Ext. name', True), 
	('treeviewcolumn5', 'Remarks', True), 
	('treeviewcolumn6', 'Price', True), 
	('treeviewcolumn7', 'Ext. price', True), 
	('treeviewcolumn12', 'Hold', True)
;
--Insert default purchase order precision settings
INSERT INTO settings.purchase_order 
	(qty_prec, price_prec) 
VALUES 
	(0, 2)
;
--Insert example fiscal years
INSERT INTO fiscal_years 
	(name, start_date, end_date, active) 
VALUES
	('2016', '2016-01-01', '2016-12-31', True),
	('2017', '2017-01-01', '2017-12-31', True),
	('2018', '2018-01-01', '2018-12-31', True),
	('2019', '2019-01-01', '2019-12-31', True),
	('2020', '2020-01-01', '2020-12-31', True)
;
--Insert example location
INSERT INTO locations 
	(name) 
VALUES 
	('Warehouse')
;










