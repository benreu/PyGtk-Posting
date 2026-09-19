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
--0.6.1
ALTER TABLE public.files ALTER COLUMN date_inserted SET DEFAULT now();
--0.6.2
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE TABLE IF NOT EXISTS inventory.count_summaries (
	id bigserial primary key,
	name text NOT NULL,
	fiscal_id bigint NOT NULL REFERENCES fiscal_years,
	date_created date NOT NULL DEFAULT now(),
	date_ended date,
	total_cost numeric(12, 2) NOT NULL DEFAULT 0.00,
	total_retail numeric(12, 2) NOT NULL DEFAULT 0.00,
	active boolean NOT NULL DEFAULT True
);
CREATE TABLE IF NOT EXISTS inventory.count_rows (
	count_summary_id bigint NOT NULL REFERENCES inventory.count_summaries,
	product_id bigint NOT NULL REFERENCES products,
	qty numeric(12, 2) NOT NULL DEFAULT 0.00,
	cost numeric(16, 6) NOT NULL,
	retail numeric(16, 6) NOT NULL,
	date_inserted date NOT NULL DEFAULT now(),
	CONSTRAINT count_summary_id_product_id_unique UNIQUE (count_summary_id, product_id)
);
--CREATE FUNCTION public.product_retail_price
CREATE OR REPLACE FUNCTION public.product_retail_price(
		IN _product_id bigint,
		OUT _price numeric)
	RETURNS numeric(12, 2) 
	LANGUAGE plpgsql AS 
$BODY$ 
	DECLARE _cost numeric(12, 2); _markup_percent numeric(12, 2); 
	BEGIN 
	SELECT price INTO _price FROM products_markup_prices AS pmp 
		JOIN customer_markup_percent AS cmp 
			ON cmp.id = pmp.markup_id 
			AND cmp.standard = True 
		WHERE pmp.product_id = _product_id; 
	IF NOT FOUND THEN 
		SELECT cost INTO _cost FROM products WHERE id = _product_id;
		SELECT markup_percent INTO _markup_percent FROM customer_markup_percent AS cmp
		WHERE standard = True;
		SELECT _cost + (_cost * _markup_percent) / 100 INTO _price; 
	END IF; 
	RETURN; 
	END ;
$BODY$ ;

--CREATE FUNCTION public.customer_product_price
CREATE OR REPLACE FUNCTION public.customer_product_price (
		_customer_id bigint, 
		_product_id bigint, 
		OUT _price numeric)
	RETURNS numeric(12, 2)
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
        SELECT _cost + (_cost * _markup_percent) / 100 INTO _price; 
    END IF; 
    RETURN; 
    END ;
$BODY$ ;
-- 0.6.4
ALTER TABLE loans ADD COLUMN IF NOT EXISTS liability_account bigint REFERENCES gl_accounts ON DELETE RESTRICT ON UPDATE CASCADE;
UPDATE loans SET liability_account = ge.credit_account FROM (SELECT id, credit_account FROM gl_entries) AS ge WHERE loans.gl_entries_id = ge.id AND loans.liability_account IS NULL;
--0.6.5
ALTER TABLE public.time_clock_projects 
	DROP CONSTRAINT time_clock_projects_resource_id_fkey, 
	ADD CONSTRAINT time_clock_projects_resource_id_fkey 
	FOREIGN KEY (resource_id)
	REFERENCES public.resources (id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public.resources 
	DROP CONSTRAINT resources_parent_id_fkey, 
	ADD CONSTRAINT resources_parent_id_fkey 
	FOREIGN KEY (parent_id)
	REFERENCES public.resources (id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public.resources 
	DROP CONSTRAINT resources_resource_type_id_fkey, 
	ADD CONSTRAINT resources_resource_type_id_fkey 
	FOREIGN KEY (resource_type_id)
	REFERENCES public.resource_types (id) ON UPDATE CASCADE ON DELETE RESTRICT;
WITH cte AS 
	(SELECT row_number() OVER (ORDER BY id) AS row_num, id FROM resources ORDER BY id) 
	UPDATE resources AS r SET id = cte.row_num FROM cte WHERE r.id = cte.id ;
CREATE TABLE IF NOT EXISTS resource_ids_tag_ids (
	resource_id bigint NOT NULL REFERENCES resources ON UPDATE CASCADE ON DELETE RESTRICT,
	resource_tag_id bigint NOT NULL REFERENCES resource_tags ON UPDATE CASCADE ON DELETE RESTRICT,
	date_inserted date NOT NULL DEFAULT now(),
	CONSTRAINT resource_id_resource_tag_id_unique UNIQUE (resource_id, resource_tag_id)
	);
SELECT setval('resources_id_seq', (SELECT max(id) FROM resources));
WITH cte AS 
	(SELECT id, tag_id, date_created FROM public.resources WHERE tag_id IS NOT NULL) 
	INSERT INTO resource_ids_tag_ids (resource_id, resource_tag_id, date_inserted) 
	SELECT * FROM cte ON CONFLICT (resource_id, resource_tag_id) DO NOTHING;
ALTER TABLE resources ADD COLUMN IF NOT EXISTS posted boolean;
UPDATE resources SET posted = rt.finished FROM (SELECT id, finished FROM resource_tags WHERE finished = True) AS rt WHERE rt.id = resources.tag_id AND posted != True;
UPDATE resources SET posted = False WHERE posted IS NULL;
UPDATE resources SET posted = True WHERE diary = True;
ALTER TABLE resources ALTER COLUMN posted SET DEFAULT False;
ALTER TABLE resources ALTER COLUMN posted SET NOT NULL;
--0.7.1
CREATE INDEX IF NOT EXISTS gl_entries_gl_transaction_id_idx 
	ON public.gl_entries USING btree (gl_transaction_id);
--0.7.2
ALTER TABLE payments_incoming ADD COLUMN IF NOT EXISTS deposit boolean;
ALTER TABLE payments_incoming ALTER COLUMN deposit SET DEFAULT False;
UPDATE payments_incoming SET deposit = False WHERE deposit IS NULL;
UPDATE payments_incoming SET deposit = True WHERE check_deposited = True;
ALTER TABLE payments_incoming ALTER COLUMN deposit SET NOT NULL;
--0.7.3 CREATE FUNCTION public.payment_type
CREATE OR REPLACE FUNCTION public.payment_type(payments_incoming_id bigint) RETURNS character varying
    LANGUAGE plpgsql
    AS 
$BODY$ 
    DECLARE table_record payments_incoming%ROWTYPE; 
    BEGIN SELECT * FROM payments_incoming WHERE id = payments_incoming_id INTO table_record; 
    IF table_record.check_payment = True THEN 
        RETURN 'Check'::varchar; 
    ELSEIF table_record.cash_payment = True THEN 
        RETURN 'Cash'::varchar; 
    ELSEIF table_record.credit_card_payment = True THEN 
        RETURN 'Credit card'::varchar;
    ELSE RETURN ''''; 
    END IF;
    END;
$BODY$ 
--0.7.4 CREATE FUNCTION public.check_tax_rate_id
CREATE OR REPLACE FUNCTION public.check_tax_rate_id() RETURNS trigger
    LANGUAGE plpgsql
    AS 
$BODY$ 
    BEGIN 
    IF (SELECT tax_exemptible FROM products WHERE id = NEW.product_id) = FALSE OR NEW.tax_rate_id IS NULL OR NEW.tax_rate_id = 0 THEN 
        NEW.tax_rate_id = (SELECT tax_rates.id FROM tax_rates JOIN products ON tax_rates.id = products.tax_rate_id WHERE products.id = NEW.product_id);
    END IF;
    RETURN NEW;
    END;
$BODY$ 
--0.7.5
CREATE TABLE IF NOT EXISTS settings.zebra_printers (
	id serial PRIMARY KEY,
	name varchar NOT NULL,
	host inet NOT NULL,
	port int NOT NULL,
	date_created date NOT NULL DEFAULT now()
);
--0.7.6
CREATE TABLE IF NOT EXISTS invoice_reprints (
	id bigserial primary key,
	invoice_id bigint NOT NULL REFERENCES invoices ON UPDATE CASCADE ON DELETE RESTRICT,
	pdf_data bytea NOT NULL,
	time_printed timestamp with time zone NOT NULL DEFAULT now()
);
--0.7.7
CREATE OR REPLACE FUNCTION public.invoice_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('invoices', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.invoice_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('invoices', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'invoice_update_trigger') THEN
		CREATE TRIGGER invoice_update_trigger AFTER UPDATE ON public.invoices
		FOR EACH ROW WHEN (
			NEW.paid        IS DISTINCT FROM OLD.paid OR
			NEW.canceled    IS DISTINCT FROM OLD.canceled OR
			NEW.posted      IS DISTINCT FROM OLD.posted OR
			NEW.active      IS DISTINCT FROM OLD.active OR
			NEW.amount_due  IS DISTINCT FROM OLD.amount_due OR
			NEW.customer_id IS DISTINCT FROM OLD.customer_id OR
			NEW.dated_for   IS DISTINCT FROM OLD.dated_for OR
			NEW.name        IS DISTINCT FROM OLD.name
		) EXECUTE PROCEDURE public.invoice_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'invoice_insert_trigger') THEN
		CREATE TRIGGER invoice_insert_trigger AFTER INSERT ON public.invoices
		FOR EACH ROW EXECUTE PROCEDURE public.invoice_inserted();
	END IF;
END
$$;
--0.7.8
ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS finance_rate numeric(12,6) NOT NULL DEFAULT 0.00;
INSERT INTO public.gl_accounts (name, type, number, parent_number)
SELECT 'Finance Charge Income', 4, 4200, 4000
WHERE NOT EXISTS (SELECT 1 FROM public.gl_accounts WHERE number = 4200);
INSERT INTO public.gl_account_flow (function, account)
SELECT 'finance_charge_income', 4200
WHERE NOT EXISTS (SELECT 1 FROM public.gl_account_flow WHERE function = 'finance_charge_income');
ALTER TABLE public.invoices ADD COLUMN IF NOT EXISTS finance_rate numeric(12,6);
--0.7.9
ALTER TABLE public.manufacturing_items
	ADD COLUMN IF NOT EXISTS default_product_id integer,
	ADD COLUMN IF NOT EXISTS vendor_id integer,
	ADD COLUMN IF NOT EXISTS purchase_order_item_id bigint,
	ADD COLUMN IF NOT EXISTS from_bom boolean NOT NULL DEFAULT True;

UPDATE public.manufacturing_items
	SET default_product_id = product_id
	WHERE default_product_id IS NULL;

ALTER TABLE public.manufacturing_items
	ALTER COLUMN default_product_id SET NOT NULL;

ALTER TABLE public.manufacturing_items
	DROP CONSTRAINT IF EXISTS manufacturing_items_product_id_fkey,
	ADD CONSTRAINT manufacturing_items_product_id_fkey
		FOREIGN KEY (product_id) REFERENCES public.products (id);

ALTER TABLE public.manufacturing_items
	DROP CONSTRAINT IF EXISTS manufacturing_items_default_product_id_fkey,
	ADD CONSTRAINT manufacturing_items_default_product_id_fkey
		FOREIGN KEY (default_product_id) REFERENCES public.products (id);

ALTER TABLE public.manufacturing_items
	DROP CONSTRAINT IF EXISTS manufacturing_items_vendor_id_fkey,
	ADD CONSTRAINT manufacturing_items_vendor_id_fkey
		FOREIGN KEY (vendor_id) REFERENCES public.contacts (id);

ALTER TABLE public.manufacturing_items
	DROP CONSTRAINT IF EXISTS manufacturing_items_purchase_order_item_id_fkey,
	ADD CONSTRAINT manufacturing_items_purchase_order_item_id_fkey
		FOREIGN KEY (purchase_order_item_id) REFERENCES public.purchase_order_items (id);

/* Guarded because this whole file re-runs from the top on every upgrade,
   and 0.7.12 below drops manufacturing_items.deleted. Without the guard this
   statement fails to parse on any database already at 0.7.12. EXECUTE keeps
   the inner SQL a string, so it is only parsed when the column is really
   there. */
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
				WHERE table_schema = 'public'
					AND table_name = 'manufacturing_items'
					AND column_name = 'deleted') THEN
		EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS manufacturing_items_project_default_product_uq ON public.manufacturing_items (manufacturing_project_id, default_product_id) WHERE deleted = False';
	END IF;
END
$$;
--0.7.10
CREATE OR REPLACE FUNCTION public.purchase_order_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('purchase_orders', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.purchase_order_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('purchase_orders', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'purchase_order_update_trigger') THEN
		CREATE TRIGGER purchase_order_update_trigger AFTER UPDATE ON public.purchase_orders
		FOR EACH ROW WHEN (
			NEW.canceled IS DISTINCT FROM OLD.canceled OR
			NEW.invoiced IS DISTINCT FROM OLD.invoiced OR
			NEW.closed   IS DISTINCT FROM OLD.closed OR
			NEW.received IS DISTINCT FROM OLD.received
		) EXECUTE PROCEDURE public.purchase_order_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'purchase_order_insert_trigger') THEN
		CREATE TRIGGER purchase_order_insert_trigger AFTER INSERT ON public.purchase_orders
		FOR EACH ROW EXECUTE PROCEDURE public.purchase_order_inserted();
	END IF;
END
$$;
CREATE OR REPLACE FUNCTION public.job_sheet_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('job_sheets', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.job_sheet_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('job_sheets', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'job_sheet_update_trigger') THEN
		CREATE TRIGGER job_sheet_update_trigger AFTER UPDATE ON public.job_sheets
		FOR EACH ROW WHEN (
			NEW.invoiced  IS DISTINCT FROM OLD.invoiced OR
			NEW.completed IS DISTINCT FROM OLD.completed
		) EXECUTE PROCEDURE public.job_sheet_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'job_sheet_insert_trigger') THEN
		CREATE TRIGGER job_sheet_insert_trigger AFTER INSERT ON public.job_sheets
		FOR EACH ROW EXECUTE PROCEDURE public.job_sheet_inserted();
	END IF;
END
$$;
CREATE OR REPLACE FUNCTION public.document_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('documents', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.document_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('documents', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'document_update_trigger') THEN
		CREATE TRIGGER document_update_trigger AFTER UPDATE ON public.documents
		FOR EACH ROW WHEN (
			NEW.canceled        IS DISTINCT FROM OLD.canceled OR
			NEW.invoiced        IS DISTINCT FROM OLD.invoiced OR
			NEW.pending_invoice IS DISTINCT FROM OLD.pending_invoice
		) EXECUTE PROCEDURE public.document_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'document_insert_trigger') THEN
		CREATE TRIGGER document_insert_trigger AFTER INSERT ON public.documents
		FOR EACH ROW EXECUTE PROCEDURE public.document_inserted();
	END IF;
END
$$;
CREATE OR REPLACE FUNCTION public.loan_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('loans', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.loan_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('loans', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'loan_update_trigger') THEN
		CREATE TRIGGER loan_update_trigger AFTER UPDATE ON public.loans
		FOR EACH ROW WHEN (
			NEW.last_payment_date IS DISTINCT FROM OLD.last_payment_date OR
			NEW.finished           IS DISTINCT FROM OLD.finished OR
			NEW.period             IS DISTINCT FROM OLD.period OR
			NEW.period_amount      IS DISTINCT FROM OLD.period_amount
		) EXECUTE PROCEDURE public.loan_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'loan_insert_trigger') THEN
		CREATE TRIGGER loan_insert_trigger AFTER INSERT ON public.loans
		FOR EACH ROW EXECUTE PROCEDURE public.loan_inserted();
	END IF;
END
$$;
CREATE OR REPLACE FUNCTION public.resource_updated() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('resources', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
CREATE OR REPLACE FUNCTION public.resource_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS
$BODY$
	BEGIN
		PERFORM pg_notify('resources', NEW.id::text);
		RETURN NEW;
	END;
$BODY$ ;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'resource_update_trigger') THEN
		CREATE TRIGGER resource_update_trigger AFTER UPDATE ON public.resources
		FOR EACH ROW WHEN (
			NEW.posted  IS DISTINCT FROM OLD.posted OR
			NEW.to_do   IS DISTINCT FROM OLD.to_do OR
			NEW.subject IS DISTINCT FROM OLD.subject
		) EXECUTE PROCEDURE public.resource_updated();
	END IF;
END
$$;
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'resource_insert_trigger') THEN
		CREATE TRIGGER resource_insert_trigger AFTER INSERT ON public.resources
		FOR EACH ROW EXECUTE PROCEDURE public.resource_inserted();
	END IF;
END
$$;
--0.7.11
UPDATE public.product_assembly_items SET remark = '' WHERE remark IS NULL;

ALTER TABLE public.product_assembly_items ALTER COLUMN remark SET DEFAULT '';
ALTER TABLE public.product_assembly_items ALTER COLUMN remark SET NOT NULL;
--0.7.12
/* Guarded because this whole file re-runs from the top on every upgrade,
   and the statement three lines below drops manufacturing_items.deleted. On
   the second run the column is gone and this would fail to parse. EXECUTE
   keeps the inner SQL a string, so it is only parsed when the column is
   really there. */
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
				WHERE table_schema = 'public'
					AND table_name = 'manufacturing_items'
					AND column_name = 'deleted') THEN
		EXECUTE 'DELETE FROM public.manufacturing_items WHERE deleted = True';
	END IF;
END
$$;

DROP INDEX IF EXISTS manufacturing_items_project_default_product_uq;

ALTER TABLE public.manufacturing_items DROP COLUMN IF EXISTS deleted;

CREATE UNIQUE INDEX IF NOT EXISTS manufacturing_items_project_default_product_uq
	ON public.manufacturing_items (manufacturing_project_id, default_product_id);
--0.7.13
CREATE TABLE IF NOT EXISTS settings.zebra_templates (
	id serial PRIMARY KEY,
	name varchar NOT NULL UNIQUE,
	label_type varchar NOT NULL DEFAULT 'product',
	template text NOT NULL,
	date_created date NOT NULL DEFAULT now(),
	date_changed timestamp with time zone NOT NULL DEFAULT now(),
	CONSTRAINT zebra_templates_label_type_ck
		CHECK (label_type IN ('product', 'serial'))
);

INSERT INTO settings.zebra_templates (name, label_type, template) VALUES
('Product barcode', 'product', '^XA
^PW182

^FO0,15
^BY2
^A0N,20,20
^BCN,25,Y,N,N,A
^FD%s^FS

^FO0,70
^A0N,40,40
^FB182,4,1,C,0
^FD%s\&^FS

^XZ
'),
('Serial barcode', 'serial', '^XA
^FO45,50^BY3
^A0N,70,70^BCN,100,Y,N,N,A
^FD%s^FS
^XZ
')
ON CONFLICT (name) DO NOTHING;
--0.7.14
CREATE TABLE IF NOT EXISTS public.shipping_carriers (
	id bigserial primary key,
	name character varying NOT NULL,
	standard boolean DEFAULT false NOT NULL,
	deleted boolean DEFAULT false NOT NULL,
	date_created date DEFAULT now() NOT NULL,
	date_edited date DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.contact_shipping_addresses (
	id bigserial primary key,
	contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
	description character varying DEFAULT '' NOT NULL,
	address character varying DEFAULT '' NOT NULL,
	city character varying DEFAULT '' NOT NULL,
	state character varying DEFAULT '' NOT NULL,
	zip character varying DEFAULT '' NOT NULL,
	shipping_carrier_id bigint REFERENCES public.shipping_carriers(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
	standard boolean DEFAULT false NOT NULL,
	deleted boolean DEFAULT false NOT NULL,
	date_created date DEFAULT now() NOT NULL,
	date_edited date DEFAULT now() NOT NULL
);

ALTER TABLE public.invoices ADD COLUMN IF NOT EXISTS shipping_address_id
	bigint REFERENCES public.contact_shipping_addresses(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
