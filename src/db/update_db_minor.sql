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
CREATE TABLE IF NOT EXISTS public.shipping_info (id serial PRIMARY KEY, tracking_number varchar NOT NULL, reason varchar, invoice_id bigint REFERENCES invoices ON DELETE RESTRICT ON UPDATE RESTRICT, CONSTRAINT shipment_reason_not_null CHECK (reason IS NOT NULL OR invoice_id IS NOT NULL));
ALTER TABLE public.shipping_info ADD UNIQUE (invoice_id); 
ALTER TABLE public.shipping_info ADD UNIQUE (tracking_number); 
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


