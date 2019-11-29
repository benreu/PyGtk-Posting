/* update_db_minor.sql

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


--version 0.4.1
ALTER TABLE loans ADD COLUMN IF NOT EXISTS period_amount smallint DEFAULT 1;
UPDATE loans SET period_amount = 1 WHERE period_amount IS NULL;
ALTER TABLE loans ALTER COLUMN period_amount SET NOT NULL;
--version 0.4.2
UPDATE resources SET subject = '' WHERE subject IS NULL;
ALTER TABLE resources ALTER COLUMN subject SET NOT NULL;
ALTER TABLE resources ALTER COLUMN subject SET DEFAULT '';
ALTER TABLE resources ALTER COLUMN diary SET DEFAULT False;
ALTER TABLE resources ALTER COLUMN date_created SET DEFAULT now();
ALTER TABLE resources ALTER COLUMN date_created SET NOT NULL;

ALTER TABLE resource_tags ALTER COLUMN tag SET DEFAULT '';
ALTER TABLE resource_tags ALTER COLUMN red SET DEFAULT 0;
ALTER TABLE resource_tags ALTER COLUMN blue SET DEFAULT 0;
ALTER TABLE resource_tags ALTER COLUMN green SET DEFAULT 0;
ALTER TABLE resource_tags ALTER COLUMN alpha SET DEFAULT 1;

ALTER TABLE resource_tags ALTER COLUMN tag SET NOT NULL;
ALTER TABLE resource_tags ALTER COLUMN red SET NOT NULL;
ALTER TABLE resource_tags ALTER COLUMN blue SET NOT NULL;
ALTER TABLE resource_tags ALTER COLUMN green SET NOT NULL;
ALTER TABLE resource_tags ALTER COLUMN alpha SET NOT NULL;
--INSERT INTO resource_tags (tag, red, green, blue, alpha, finished) VALUES ('To do', 0, 0, 0, 1, False);

ALTER TABLE time_clock_projects ADD COLUMN IF NOT EXISTS resource_id bigint UNIQUE REFERENCES resources ON UPDATE RESTRICT ON DELETE RESTRICT;
-- version 0.4.3
ALTER TABLE credit_memo_items ADD COLUMN IF NOT EXISTS ext_price numeric (12, 2) DEFAULT 0.00;
UPDATE credit_memo_items SET ext_price = (qty * price) WHERE ext_price IS NULL;
ALTER TABLE credit_memo_items ALTER COLUMN ext_price SET NOT NULL;
-- version 0.4.4
ALTER TABLE credit_memo_items ADD COLUMN IF NOT EXISTS deleted boolean DEFAULT False;
UPDATE credit_memo_items SET deleted = False WHERE deleted IS NULL;
ALTER TABLE credit_memo_items ALTER COLUMN deleted SET NOT NULL;
-- version 0.4.5
ALTER TABLE products ADD COLUMN IF NOT EXISTS assembly_notes varchar DEFAULT '';
UPDATE products SET assembly_notes = '' WHERE assembly_notes IS NULL;
ALTER TABLE products ALTER COLUMN assembly_notes SET NOT NULL;
-- version 0.4.6
ALTER TABLE credit_memos ADD COLUMN IF NOT EXISTS dated_for date DEFAULT now();
UPDATE credit_memos SET dated_for = now() WHERE dated_for IS NULL;
ALTER TABLE credit_memos ALTER COLUMN dated_for SET NOT NULL;
ALTER TABLE credit_memos ADD COLUMN IF NOT EXISTS comments varchar DEFAULT '';
UPDATE credit_memos SET comments = '' WHERE comments IS NULL;
ALTER TABLE credit_memos ALTER COLUMN comments SET NOT NULL;
ALTER TABLE credit_memos ADD COLUMN IF NOT EXISTS pdf_data bytea;
--version 0.4.8
CREATE OR REPLACE FUNCTION public.before_accounts_edited()
	RETURNS trigger AS 
$BODY$ 
	DECLARE counter integer; 
	BEGIN 
		SELECT COUNT (id) FROM public.gl_entries WHERE debit_account = NEW.parent_number INTO counter; 
			IF counter > 0 THEN RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in gl_entries', NEW.parent_number; 
		END IF; 
		SELECT COUNT (id) FROM public.gl_entries WHERE credit_account = NEW.parent_number INTO counter; 
			IF counter > 0 THEN RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in gl_entries', NEW.parent_number; 
		END IF; 
		SELECT COUNT (function) FROM public.gl_account_flow WHERE account = NEW.parent_number INTO counter; 
			IF counter > 0 THEN RAISE EXCEPTION 'Account % is not allowed as a parent -> already used in gl_account_flow', NEW.parent_number; 
		END IF; 
	RETURN NEW; 
	END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
--version 0.5.1
ALTER TABLE credit_memo_items ADD COLUMN IF NOT EXISTS gl_entry_id bigint REFERENCES gl_entries ON UPDATE RESTRICT ON DELETE RESTRICT; 
--version 0.5.2
CREATE TABLE IF NOT EXISTS public.shipping_info (id serial PRIMARY KEY, tracking_number varchar NOT NULL UNIQUE, reason varchar, invoice_id bigint UNIQUE REFERENCES invoices ON DELETE RESTRICT ON UPDATE RESTRICT, CONSTRAINT shipment_reason_not_null CHECK (reason IS NOT NULL OR invoice_id IS NOT NULL));
--version 0.5.3
ALTER TABLE files ALTER COLUMN date_inserted SET DEFAULT CURRENT_DATE;
--version 0.5.4
CREATE SCHEMA IF NOT EXISTS log;
CREATE TABLE IF NOT EXISTS log.products (LIKE public.products INCLUDING DEFAULTS, date_edited timestamp NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS log.contacts (LIKE public.contacts INCLUDING DEFAULTS, date_edited timestamp NOT NULL DEFAULT now());

CREATE OR REPLACE FUNCTION log.save_contact_trigger ()
	RETURNS trigger AS 
$BODY$ 
	BEGIN
	INSERT INTO log.contacts SELECT NEW.*;
	RETURN NEW;
	END;
$BODY$
	LANGUAGE plpgsql VOLATILE
	COST 100;

DROP TRIGGER IF EXISTS contact_update ON public.contacts;
CREATE TRIGGER contact_update AFTER UPDATE ON public.contacts FOR EACH ROW WHEN (OLD.* <> NEW.*) EXECUTE PROCEDURE log.save_contact_trigger();
DROP TRIGGER IF EXISTS contact_insert ON public.contacts;
CREATE TRIGGER contact_insert AFTER INSERT ON public.contacts FOR EACH ROW EXECUTE PROCEDURE log.save_contact_trigger();

CREATE OR REPLACE FUNCTION log.save_product_trigger ()
	RETURNS trigger AS 
$BODY$ 
	BEGIN
	INSERT INTO log.products SELECT NEW.*;
	RETURN NEW;
	END;
$BODY$
	LANGUAGE plpgsql VOLATILE
	COST 100;

DROP TRIGGER IF EXISTS product_update ON public.products;
CREATE TRIGGER product_update AFTER UPDATE ON public.products FOR EACH ROW WHEN (OLD.* <> NEW.*) EXECUTE PROCEDURE log.save_product_trigger();
DROP TRIGGER IF EXISTS product_insert ON public.products;
CREATE TRIGGER product_insert AFTER INSERT ON public.products FOR EACH ROW EXECUTE PROCEDURE log.save_product_trigger();
--version 0.5.5
ALTER TABLE log.contacts ALTER COLUMN id DROP DEFAULT;
ALTER TABLE log.products ALTER COLUMN id DROP DEFAULT;
ALTER TABLE log.products ALTER COLUMN barcode DROP DEFAULT;
--version 0.5.6
CREATE TABLE IF NOT EXISTS public.budgets (id serial primary key, name varchar NOT NULL, fiscal_id bigint NOT NULL REFERENCES fiscal_years ON DELETE RESTRICT, total numeric(12,2) NOT NULL, date_created date NOT NULL DEFAULT now(), active boolean NOT NULL DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS public.budget_amounts (id serial primary key, budget_id bigint NOT NULL REFERENCES budgets ON DELETE RESTRICT ON UPDATE RESTRICT, name varchar NOT NULL, amount numeric(12,2) NOT NULL, account bigint NOT NULL REFERENCES gl_accounts ON DELETE RESTRICT ON UPDATE CASCADE, date_created date NOT NULL DEFAULT now());
--version 0.5.7
ALTER TABLE incoming_invoices ADD COLUMN IF NOT EXISTS gl_entry_id bigint REFERENCES gl_entries ON DELETE RESTRICT ON UPDATE RESTRICT;
CREATE TABLE IF NOT EXISTS incoming_invoices_gl_entry_expenses_ids (id bigserial PRIMARY KEY, gl_entry_expense_id bigint NOT NULL REFERENCES gl_entries ON DELETE RESTRICT ON UPDATE RESTRICT, incoming_invoices_id bigint NOT NULL REFERENCES incoming_invoices ON DELETE RESTRICT ON UPDATE RESTRICT);
--version 0.5.8
ALTER TABLE public.purchase_order_line_items DROP CONSTRAINT IF EXISTS purchase_order_line_items_expense_account_fkey;
ALTER TABLE public.purchase_order_line_items ADD CONSTRAINT purchase_order_line_items_expense_account_fkey FOREIGN KEY (expense_account) REFERENCES public.gl_accounts ("number") MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;
--version 0.5.9
ALTER TABLE incoming_invoices ADD COLUMN IF NOT EXISTS gl_transaction_id bigint REFERENCES gl_transactions ON DELETE RESTRICT;
UPDATE incoming_invoices SET gl_transaction_id = ge.gl_transaction_id FROM (SELECT id, gl_transaction_id FROM gl_entries) AS ge WHERE incoming_invoices.gl_entry_id = ge.id AND incoming_invoices.gl_transaction_id IS NULL;
UPDATE incoming_invoices SET gl_transaction_id = ge.gl_transaction_id FROM (SELECT date_inserted, amount, gl_transaction_id FROM gl_entries) AS ge WHERE incoming_invoices.amount = ge.amount AND incoming_invoices.gl_transaction_id IS NULL AND incoming_invoices.date_created = ge.date_inserted ;
--version 0.5.10
ALTER TABLE settings ADD COLUMN IF NOT EXISTS finance_rate decimal(12, 2) DEFAULT 0.00;
UPDATE settings SET finance_rate = 0.00 WHERE finance_rate IS NULL;
ALTER TABLE settings ALTER COLUMN finance_rate SET NOT NULL;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS finance_charge boolean DEFAULT FALSE;
UPDATE invoices SET finance_charge = False WHERE finance_charge IS NULL;
ALTER TABLE invoices ALTER COLUMN finance_charge SET NOT NULL;
--version 0.5.11
ALTER TABLE IF EXISTS public.document_lines RENAME TO document_items;
ALTER TABLE public.document_items ALTER COLUMN document_id SET NOT NULL;
ALTER TABLE public.document_items ALTER COLUMN product_id SET NOT NULL;
ALTER TABLE public.document_items ALTER COLUMN min SET DEFAULT 0.00;
ALTER TABLE public.document_items ALTER COLUMN max SET DEFAULT 100.00;
ALTER TABLE public.document_items ALTER COLUMN qty SET DEFAULT 1.00;
--version 0.5.12
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS incoming_invoice_id bigint REFERENCES incoming_invoices ON DELETE RESTRICT;
--version 0.5.13
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS date_shipped date DEFAULT now();
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS contact_id bigint REFERENCES contacts ON DELETE RESTRICT;
UPDATE shipping_info SET contact_id = c_join.contact_id FROM (SELECT co.id AS contact_id, i.id AS invoice_id FROM contacts AS co JOIN invoices AS i ON i.customer_id = co.id) AS c_join WHERE c_join.invoice_id = shipping_info.invoice_id;
UPDATE shipping_info SET date_shipped = c_join.dated_for FROM (SELECT co.id AS contact_id, i.dated_for AS dated_for, i.id AS invoice_id FROM contacts AS co JOIN invoices AS i ON i.customer_id = co.id) AS c_join WHERE c_join.invoice_id = shipping_info.invoice_id;
ALTER TABLE shipping_info ALTER COLUMN contact_id SET NOT NULL;
--version 0.5.14
ALTER TABLE manufacturing_projects ADD COLUMN IF NOT EXISTS batch_notes varchar DEFAULT '';
UPDATE manufacturing_projects SET batch_notes = '' WHERE batch_notes IS NULL;
ALTER TABLE manufacturing_projects ALTER COLUMN batch_notes SET NOT NULL;
--version 0.5.15
ALTER TABLE payroll.employee_info ADD COLUMN IF NOT EXISTS state_income_status boolean DEFAULT False;
UPDATE payroll.employee_info SET state_income_status = False WHERE state_income_status IS NULL;
ALTER TABLE payroll.employee_info ADD COLUMN IF NOT EXISTS state_credits integer DEFAULT 0;
UPDATE payroll.employee_info SET state_credits = 0 WHERE state_credits IS NULL;
ALTER TABLE payroll.employee_info ADD COLUMN IF NOT EXISTS fed_income_status boolean DEFAULT False;
UPDATE payroll.employee_info SET fed_income_status = False WHERE fed_income_status IS NULL;
ALTER TABLE payroll.employee_info ADD COLUMN IF NOT EXISTS state_withholding_exempt boolean DEFAULT False;
UPDATE payroll.employee_info SET state_withholding_exempt = False WHERE state_withholding_exempt IS NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN state_withholding_exempt SET NOT NULL;
ALTER TABLE payroll.employee_info ADD COLUMN IF NOT EXISTS fed_withholding_exempt boolean DEFAULT False;
UPDATE payroll.employee_info SET fed_withholding_exempt = False WHERE fed_withholding_exempt IS NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_withholding_exempt SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN date_created SET DEFAULT now();
ALTER TABLE payroll.employee_info ALTER COLUMN date_created SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN born SET DEFAULT '1970-1-1';
ALTER TABLE payroll.employee_info ALTER COLUMN born SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN social_security SET DEFAULT '';
ALTER TABLE payroll.employee_info ALTER COLUMN social_security SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN social_security_exempt SET DEFAULT False;
ALTER TABLE payroll.employee_info ALTER COLUMN social_security_exempt SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN wage SET DEFAULT 0.00;
ALTER TABLE payroll.employee_info ALTER COLUMN wage SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN payment_frequency SET DEFAULT 24;
ALTER TABLE payroll.employee_info ALTER COLUMN payment_frequency SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN married SET DEFAULT False;
ALTER TABLE payroll.employee_info ALTER COLUMN married SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN last_updated SET DEFAULT now();
ALTER TABLE payroll.employee_info ALTER COLUMN last_updated SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN state_income_status SET DEFAULT False;
ALTER TABLE payroll.employee_info ALTER COLUMN state_income_status SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN state_credits SET DEFAULT 0;
ALTER TABLE payroll.employee_info ALTER COLUMN state_credits SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN state_extra_withholding SET DEFAULT 0.00;
ALTER TABLE payroll.employee_info ALTER COLUMN state_extra_withholding SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_income_status SET DEFAULT False;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_income_status SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_credits SET DEFAULT 0;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_credits SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_extra_withholding SET DEFAULT 0.00;
ALTER TABLE payroll.employee_info ALTER COLUMN fed_extra_withholding SET NOT NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN on_payroll_since SET DEFAULT now();
UPDATE payroll.employee_info SET on_payroll_since = '1970-1-1' WHERE on_payroll_since IS NULL;
ALTER TABLE payroll.employee_info ALTER COLUMN on_payroll_since SET NOT NULL;
--version 0.5.16
ALTER TABLE IF EXISTS payroll.employee_payments RENAME TO emp_payments;
ALTER TABLE IF EXISTS payroll.employee_pdf_archive RENAME TO emp_pdf_archive;

CREATE OR REPLACE FUNCTION payroll.pay_stubs_employee_info_update_func ()
  RETURNS trigger AS
$func$
BEGIN
	UPDATE payroll.employee_info SET current = False 
		WHERE (id, current) = (SELECT NEW.employee_info_id, True);
	RETURN NEW;
END
$func$  LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS pay_stubs_employee_info_update_trigger ON payroll.pay_stubs;
CREATE TRIGGER pay_stubs_employee_info_update_trigger
AFTER INSERT OR UPDATE ON payroll.pay_stubs
FOR EACH ROW EXECUTE PROCEDURE payroll.pay_stubs_employee_info_update_func() ;

CREATE OR REPLACE FUNCTION payroll.employee_info_update_non_current_error_func ()
	RETURNS trigger AS
$func$
BEGIN
	IF OLD.current = False THEN 
		RAISE EXCEPTION 'Non-current entries in employee_info are not editable';
	END IF;
	RETURN NEW;
END
$func$  LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS employee_info_update_non_current_error_trigger ON payroll.employee_info;
CREATE TRIGGER employee_info_update_non_current_error_trigger
BEFORE UPDATE ON payroll.employee_info
FOR EACH ROW EXECUTE PROCEDURE payroll.employee_info_update_non_current_error_func() ;

CREATE UNIQUE INDEX IF NOT EXISTS employee_info_employee_current_unique
ON payroll.employee_info (employee_id, current)
WHERE current = True;
--version 0.5.17
UPDATE purchase_order_line_items SET order_number = '' WHERE order_number IS NULL;
ALTER TABLE purchase_order_line_items ALTER COLUMN order_number SET DEFAULT '';
ALTER TABLE purchase_order_line_items ALTER COLUMN order_number SET NOT NULL;
--version 0.5.18
ALTER TABLE mailing_lists ADD COLUMN IF NOT EXISTS auto_add boolean DEFAULT False;
UPDATE mailing_lists SET auto_add = False WHERE auto_add IS NULL;
ALTER TABLE mailing_lists ALTER COLUMN auto_add SET NOT NULL;
COMMENT ON COLUMN mailing_lists.auto_add IS 'automatically add these mailing lists when updating or inserting contacts';
CREATE UNIQUE INDEX IF NOT EXISTS mailing_list_register_contact_mailing_list_unique
ON public.mailing_list_register (mailing_list_id, contact_id);
--version 0.5.19
ALTER TABLE job_types ADD COLUMN IF NOT EXISTS current_serial_number int DEFAULT 0;
UPDATE job_types SET current_serial_number = 0 WHERE current_serial_number IS NULL;
ALTER TABLE job_types ALTER COLUMN current_serial_number SET NOT NULL;
--version 0.5.20
ALTER TABLE mailing_list_register ADD COLUMN IF NOT EXISTS printed boolean DEFAULT False;
UPDATE mailing_list_register SET printed = False WHERE printed IS NULL;
ALTER TABLE mailing_list_register ALTER COLUMN printed SET NOT NULL;




