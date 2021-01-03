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



