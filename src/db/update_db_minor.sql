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
