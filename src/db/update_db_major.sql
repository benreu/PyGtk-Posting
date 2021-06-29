/* update_db_major.sql

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

--version 0.5.0; not used
ALTER TABLE terms_and_discounts DROP COLUMN IF EXISTS markup_percent; 
--reserved keyword
DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='employee_info' AND column_name='current')
  THEN
      ALTER TABLE payroll.employee_info RENAME COLUMN current TO active;
  END IF;
END $$;
--clarify ambiguity
DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='employee_info' AND column_name='payment_frequency')
  THEN
      ALTER TABLE payroll.employee_info RENAME COLUMN payment_frequency TO payments_per_year;
  END IF;
END $$;
--0.6.0
ALTER TABLE IF EXISTS purchase_order_line_items RENAME TO purchase_order_items;
ALTER TABLE IF EXISTS job_sheet_line_items RENAME TO job_sheet_items;
--0.7.0
CREATE TABLE IF NOT EXISTS product_assembly_versions (
	id bigserial primary key,
	product_id bigint NOT NULL REFERENCES products ON UPDATE RESTRICT ON DELETE RESTRICT,
	version_name varchar NOT NULL,
	assembly_notes varchar NOT NULL DEFAULT '',
	date_created date NOT NULL DEFAULT now(),
	date_ended date,
	active boolean NOT NULL DEFAULT True
	);
INSERT INTO product_assembly_versions (product_id, version_name, assembly_notes) SELECT pai.manufactured_product_id, 'Version A', p.assembly_notes FROM product_assembly_items AS pai JOIN products AS p ON p.id = pai.manufactured_product_id WHERE pai.manufactured_product_id NOT IN (SELECT product_id FROM product_assembly_versions GROUP BY product_id) GROUP BY manufactured_product_id, p.assembly_notes ORDER BY manufactured_product_id;
INSERT INTO product_assembly_versions (product_id, version_name, assembly_notes) SELECT mp.product_id, 'Version A', p.assembly_notes FROM manufacturing_projects AS mp JOIN products AS p ON p.id = mp.product_id WHERE mp.product_id NOT IN (SELECT product_id FROM product_assembly_versions GROUP BY product_id) GROUP BY product_id, p.assembly_notes ORDER BY product_id;
ALTER TABLE product_assembly_items ADD COLUMN IF NOT EXISTS version_id bigint;
ALTER TABLE public.product_assembly_items 
	DROP CONSTRAINT IF EXISTS product_assembly_items_version_id_fkey, 
	ADD CONSTRAINT product_assembly_items_version_id_fkey 
	FOREIGN KEY (version_id)
	REFERENCES public.product_assembly_versions (id) ON UPDATE RESTRICT ON DELETE RESTRICT;
UPDATE product_assembly_items SET version_id = pav.id FROM (SELECT id, product_id FROM product_assembly_versions) AS pav WHERE product_assembly_items.manufactured_product_id = pav.product_id AND version_id IS NULL;
ALTER TABLE product_assembly_items ALTER COLUMN version_id SET NOT NULL;
ALTER TABLE manufacturing_projects ADD COLUMN IF NOT EXISTS version_id bigint;
ALTER TABLE public.manufacturing_projects 
	DROP CONSTRAINT IF EXISTS manufacturing_projects_version_id_fkey, 
	ADD CONSTRAINT manufacturing_projects_version_id_fkey 
	FOREIGN KEY (version_id)
	REFERENCES public.product_assembly_versions (id) ON UPDATE RESTRICT ON DELETE RESTRICT;
UPDATE manufacturing_projects SET version_id = pav.id FROM (SELECT id, product_id FROM product_assembly_versions) AS pav WHERE manufacturing_projects.product_id = pav.product_id AND version_id IS NULL;
ALTER TABLE manufacturing_projects ALTER COLUMN version_id SET NOT NULL;
CREATE TABLE IF NOT EXISTS public.manufacturing_items (
	id bigserial primary key,
	manufacturing_project_id integer REFERENCES manufacturing_projects ON UPDATE RESTRICT ON DELETE RESTRICT,
	qty smallint NOT NULL,
	product_id integer NOT NULL,
	remark character varying NOT NULL DEFAULT '',
	cost numeric (12, 2) NOT NULL,
	ext_cost numeric (12, 2) NOT NULL,
	deleted boolean NOT NULL DEFAULT False
	);


