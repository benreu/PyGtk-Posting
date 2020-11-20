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

ALTER TABLE time_clock_projects ADD COLUMN IF NOT EXISTS resource_id bigint UNIQUE;
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
ALTER TABLE credit_memo_items ADD COLUMN IF NOT EXISTS gl_entry_id bigint;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'credit_memo_items_gl_entry_id_fkey' )
	THEN
		ALTER TABLE public.credit_memo_items
		ADD CONSTRAINT credit_memo_items_gl_entry_id_fkey FOREIGN KEY (gl_entry_id)
		REFERENCES public.gl_entries (id) MATCH SIMPLE
		ON UPDATE RESTRICT ON DELETE RESTRICT;
	END IF;
END$$; 
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
ALTER TABLE incoming_invoices ADD COLUMN IF NOT EXISTS gl_entry_id bigint;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'incoming_invoices_gl_entry_id_fkey' )
	THEN
		ALTER TABLE public.incoming_invoices
		ADD CONSTRAINT incoming_invoices_gl_entry_id_fkey FOREIGN KEY (gl_entry_id)
		REFERENCES public.gl_entries (id) MATCH SIMPLE
		ON UPDATE RESTRICT ON DELETE RESTRICT;
	END IF;
END$$; 
CREATE TABLE IF NOT EXISTS incoming_invoices_gl_entry_expenses_ids (id bigserial PRIMARY KEY, gl_entry_expense_id bigint NOT NULL REFERENCES gl_entries ON DELETE RESTRICT ON UPDATE RESTRICT, incoming_invoices_id bigint NOT NULL REFERENCES incoming_invoices ON DELETE RESTRICT ON UPDATE RESTRICT);
--version 0.5.8
ALTER TABLE public.purchase_order_line_items DROP CONSTRAINT IF EXISTS purchase_order_line_items_expense_account_fkey;
ALTER TABLE public.purchase_order_line_items ADD CONSTRAINT purchase_order_line_items_expense_account_fkey FOREIGN KEY (expense_account) REFERENCES public.gl_accounts ("number") MATCH SIMPLE ON UPDATE CASCADE ON DELETE RESTRICT;
--version 0.5.9
ALTER TABLE incoming_invoices ADD COLUMN IF NOT EXISTS gl_transaction_id bigint;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'incoming_invoices_gl_transaction_id_fkey' )
	THEN
		ALTER TABLE public.incoming_invoices
		ADD CONSTRAINT incoming_invoices_gl_transaction_id_fkey FOREIGN KEY (gl_transaction_id)
		REFERENCES public.gl_transactions (id) MATCH SIMPLE
		ON UPDATE NO ACTION ON DELETE RESTRICT;
	END IF;
END$$; 
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
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS incoming_invoice_id bigint;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'shipping_info_incoming_invoice_id_fkey' )
	THEN
		ALTER TABLE public.shipping_info
		ADD CONSTRAINT shipping_info_incoming_invoice_id_fkey FOREIGN KEY (incoming_invoice_id)
		REFERENCES public.incoming_invoices (id) MATCH SIMPLE
		ON UPDATE NO ACTION ON DELETE RESTRICT;
	END IF;
END$$; 
--version 0.5.13
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS date_shipped date DEFAULT now();
ALTER TABLE shipping_info ADD COLUMN IF NOT EXISTS contact_id bigint;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'shipping_info_contact_id_fkey' )
	THEN
		ALTER TABLE public.shipping_info
		ADD CONSTRAINT shipping_info_contact_id_fkey FOREIGN KEY (contact_id)
		REFERENCES public.contacts (id) MATCH SIMPLE
		ON UPDATE NO ACTION ON DELETE RESTRICT;
	END IF;
END$$; 
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
ALTER TABLE payroll.employee_info ALTER COLUMN payments_per_year SET DEFAULT 24;
ALTER TABLE payroll.employee_info ALTER COLUMN payments_per_year SET NOT NULL;
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
	UPDATE payroll.employee_info SET active = False 
		WHERE (id, active) = (SELECT NEW.id, True);
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
	IF OLD.active = False THEN 
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
ON payroll.employee_info (employee_id, active)
WHERE active = True;
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
--version 0.5.21
ALTER TABLE resources ADD COLUMN IF NOT EXISTS sort int DEFAULT 0;
UPDATE resources SET sort = 0 WHERE sort IS NULL;
ALTER TABLE resources ALTER COLUMN sort SET NOT NULL;
--version 0.5.22
CREATE TABLE IF NOT EXISTS public.units (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL);
INSERT INTO units (name) VALUES ('Piece'), ('Hour'), ('Minute'), ('Foot'), ('Inch'), ('Ounce'), ('Pound'), ('Ton'), ('Acre') ON CONFLICT (name) DO NOTHING;
ALTER TABLE products ALTER COLUMN unit TYPE int using unit::integer;
DO $$
BEGIN
	IF NOT EXISTS (SELECT constraint_schema, constraint_name 
		FROM information_schema.constraint_column_usage 
		WHERE constraint_schema = 'public'
		AND constraint_name = 'products_units_fkey' )
	THEN
		ALTER TABLE public.products
		ADD CONSTRAINT products_units_fkey FOREIGN KEY (unit)
		REFERENCES public.units (id) MATCH SIMPLE
		ON UPDATE RESTRICT ON DELETE RESTRICT;
	END IF;
END$$; 
-- 0.5.23
CREATE OR REPLACE FUNCTION complete_search(search_text text)
RETURNS table(schemaname text, tablename text, columnname text, rowfound text, rowctid text)
AS $$ 
BEGIN
  FOR schemaname,tablename,columnname IN
      SELECT c.table_schema,c.table_name,c.column_name
      FROM information_schema.columns c
      JOIN information_schema.tables t ON
        (t.table_name=c.table_name AND t.table_schema=c.table_schema)
      WHERE c.table_schema <> 'pg_catalog'
        AND c.table_schema <> 'information_schema'
        AND c.data_type <> 'bytea' 
        AND t.table_type='BASE TABLE'
  LOOP
    RETURN QUERY EXECUTE format('SELECT %L, %L, %L, %I::text, ctid::text FROM %I.%I WHERE cast(%I as text) ~* %L', 
       schemaname,
       tablename,
       columnname,
       columnname,
       schemaname,
       tablename,
       columnname,
       search_text
    ) USING schemaname,tablename,columnname;
 END LOOP;
END; 
$$ language plpgsql;
-- 0.5.24
CREATE UNIQUE INDEX IF NOT EXISTS products_markup_prices_unique
ON public.products_markup_prices (product_id, markup_id);
--0.5.25
ALTER TABLE purchase_order_line_items ADD COLUMN IF NOT EXISTS sort int DEFAULT 0;
UPDATE purchase_order_line_items SET sort = 0 WHERE sort IS NULL;
ALTER TABLE purchase_order_line_items ALTER COLUMN sort SET NOT NULL;
ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS sort int DEFAULT 0;
UPDATE invoice_items SET sort = 0 WHERE sort IS NULL;
ALTER TABLE invoice_items ALTER COLUMN sort SET NOT NULL;
--0.5.26
ALTER TABLE incoming_invoices_gl_entry_expenses_ids ADD COLUMN IF NOT EXISTS remark varchar DEFAULT '';
UPDATE incoming_invoices_gl_entry_expenses_ids SET remark = '' WHERE remark IS NULL;
ALTER TABLE incoming_invoices_gl_entry_expenses_ids ALTER COLUMN remark SET NOT NULL;
--0.5.27 update complete_search function
SELECT 1;
--0.5.28
ALTER TABLE settings ALTER COLUMN finance_rate TYPE numeric(12,6);
--0.5.29
CREATE OR REPLACE FUNCTION public.customer_product_price (_customer_id bigint, _product_id bigint, OUT _price numeric(12, 2)) RETURNS numeric(12, 2)
    LANGUAGE plpgsql
    AS 
$BODY$ 
	DECLARE _cost numeric(12, 2); _markup_percent numeric(12, 2); 
	BEGIN 
	SELECT pmp.price INTO _price FROM products_markup_prices AS pmp 
		JOIN contacts AS c ON c.markup_percent_id = pmp.markup_id
		WHERE (c.id, pmp.product_id) = (_customer_id, _product_id); 
	IF NOT FOUND THEN 
		SELECT cost INTO _cost FROM products WHERE id = _product_id;
		SELECT markup_percent INTO _markup_percent FROM customer_markup_percent AS cmp
		JOIN contacts AS c ON c.markup_percent_id = cmp.id 
		WHERE c.id = _customer_id;
		SELECT _cost * _markup_percent / 100 INTO _price; 
	END IF; 
	RETURN; 
	END ;
$BODY$ ;

ALTER TABLE public.invoice_items ALTER COLUMN qty SET DEFAULT 1;

--0.5.30
ALTER TABLE contact_individuals ADD COLUMN IF NOT EXISTS ext_name varchar DEFAULT '';
UPDATE contact_individuals SET ext_name = '' WHERE ext_name IS NULL;
ALTER TABLE contact_individuals ALTER COLUMN ext_name SET NOT NULL;
ALTER TABLE contact_individuals ADD COLUMN IF NOT EXISTS notes varchar DEFAULT '';
UPDATE contact_individuals SET notes = '' WHERE notes IS NULL;
ALTER TABLE contact_individuals ALTER COLUMN notes SET NOT NULL;
--0.5.31
UPDATE document_items SET remark = '' WHERE remark IS NULL;
ALTER TABLE public.document_items ALTER COLUMN remark SET NOT NULL;
--0.5.32
ALTER TABLE public.resources ALTER COLUMN diary DROP DEFAULT;
--0.5.33
CREATE TABLE IF NOT EXISTS public.resource_types (id serial PRIMARY KEY, name varchar NOT NULL UNIQUE);
ALTER TABLE resources ADD COLUMN IF NOT EXISTS resource_type_id bigint REFERENCES resource_types ON DELETE RESTRICT;
ALTER TABLE resources ADD COLUMN IF NOT EXISTS qty bigint;
--0.5.34
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS gl_transaction_payment_id bigint REFERENCES gl_transactions ON DELETE RESTRICT;

WITH cte AS (SELECT 
			po.amount_due AS amount, 
			po.invoice_description,
			po.id AS po_id, 
			po.date_created,
			po.date_paid,
			ge.date_inserted AS ge_date,
			ge.gl_transaction_id AS gl_transaction_id,
			ge.transaction_description,
			ge.id AS ge_id,
			ge.check_number
	FROM purchase_orders AS po 
	JOIN gl_entries AS ge ON ge.amount = po.amount_due 
		AND po.invoice_description = ge.transaction_description
		AND credit_account IS NOT NULL
	WHERE gl_transaction_payment_id IS NULL) ,
cte2 AS (SELECT * FROM cte AS c_outer WHERE 
	(SELECT COUNT(po_id) FROM cte AS c_inner 
	WHERE c_inner.po_id = c_outer.po_id) = 1)
UPDATE purchase_orders SET gl_transaction_payment_id = cte2.gl_transaction_id FROM cte2 
	WHERE purchase_orders.id = cte2.po_id RETURNING cte2.*; 

WITH cte AS (SELECT
            po.amount_due AS amount,
            po.invoice_description,
            po.id AS po_id,
            po.date_created,
            po.date_paid,
            ge.date_inserted AS ge_date,
            ge.gl_transaction_id AS gl_transaction_id,
            ge.transaction_description,
            ge.id AS ge_id,
            check_number
    FROM purchase_orders AS po
    JOIN gl_entries AS ge ON ge.amount = po.amount_due
        AND credit_account IS NOT NULL
        AND date_reconciled IS NOT NULL
        AND check_number IS NOT NULL
    WHERE gl_transaction_payment_id IS NULL) ,
cte2 AS (SELECT * FROM cte AS c_outer WHERE
    (SELECT COUNT(po_id) FROM cte AS c_inner
    WHERE c_inner.po_id = c_outer.po_id) = 1)
UPDATE purchase_orders SET gl_transaction_payment_id = cte2.gl_transaction_id FROM cte2
    WHERE purchase_orders.id = cte2.po_id RETURNING cte2.*; 
--0.5.35
ALTER TABLE job_sheet_line_items ALTER COLUMN product_id SET NOT NULL;
UPDATE job_sheet_line_items SET qty = 1 WHERE qty IS NULL;
ALTER TABLE job_sheet_line_items ALTER COLUMN qty SET NOT NULL;
ALTER TABLE job_sheet_line_items ALTER COLUMN qty SET DEFAULT 1;
UPDATE job_sheet_line_items SET remark = '' WHERE remark IS NULL;
ALTER TABLE job_sheet_line_items ALTER COLUMN remark SET NOT NULL;
ALTER TABLE job_sheet_line_items ALTER COLUMN remark SET DEFAULT '';
--0.5.36
ALTER TABLE manufacturing_projects ADD COLUMN IF NOT EXISTS date_created date;
UPDATE manufacturing_projects SET date_created = tcp.start_date FROM (SELECT id, start_date FROM time_clock_projects) AS tcp WHERE manufacturing_projects.time_clock_projects_id = tcp.id AND manufacturing_projects.date_created IS NULL;
ALTER TABLE manufacturing_projects ALTER COLUMN date_created SET DEFAULT now();
ALTER TABLE manufacturing_projects ALTER COLUMN date_created SET NOT NULL;
--0.5.37
CREATE OR REPLACE FUNCTION public.invoice_item_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS 
$BODY$  
	BEGIN 
		IF NEW.invoice_id != OLD.invoice_id
			THEN PERFORM pg_notify('invoices', OLD.invoice_id::text);
		END IF; 
		PERFORM pg_notify('invoices', NEW.invoice_id::text); 
		RETURN NEW; 
	END;
$BODY$ ;
--CREATE FUNCTION public.invoice_item_inserted
CREATE OR REPLACE FUNCTION public.invoice_item_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS 
$BODY$  
	BEGIN 
		PERFORM pg_notify('invoices', NEW.invoice_id::text); 
		RETURN NEW; 
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'invoice_item_update_trigger') THEN
		CREATE TRIGGER invoice_item_update_trigger AFTER UPDATE ON public.invoice_items 
		FOR EACH ROW WHEN (OLD.* <> NEW.*) EXECUTE PROCEDURE public.invoice_item_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'invoice_item_insert_trigger') THEN
		CREATE TRIGGER invoice_item_insert_trigger AFTER INSERT ON public.invoice_items 
		FOR EACH ROW EXECUTE PROCEDURE public.invoice_item_inserted();
	END IF;
END
$$;
CREATE OR REPLACE FUNCTION public.purchase_order_item_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS 
$BODY$  
	BEGIN 
		IF NEW.purchase_order_id != OLD.purchase_order_id
			THEN PERFORM pg_notify('purchase_orders', OLD.purchase_order_id::text);
		END IF; 
		PERFORM pg_notify('purchase_orders', NEW.purchase_order_id::text); 
		RETURN NEW; 
	END;
$BODY$ ;
--CREATE FUNCTION public.purchase_order_item_inserted
CREATE OR REPLACE FUNCTION public.purchase_order_item_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS 
$BODY$  
	BEGIN 
		PERFORM pg_notify('purchase_orders', NEW.purchase_order_id::text); 
		RETURN NEW; 
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'purchase_order_item_update') THEN
		CREATE TRIGGER purchase_order_item_update AFTER UPDATE ON public.purchase_order_items 
		FOR EACH ROW WHEN (OLD.* <> NEW.*) EXECUTE PROCEDURE public.purchase_order_item_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'purchase_order_item_insert') THEN
		CREATE TRIGGER purchase_order_item_insert AFTER INSERT ON public.purchase_order_items 
		FOR EACH ROW EXECUTE PROCEDURE public.purchase_order_item_inserted();
	END IF;
END
$$;



