-- update_db_minor.sql
--
-- Copyright (C) 2016 - reuben
--
-- This program is free software, you can redistribute it and/or modify
-- it under the terms of the GNU Lesser General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY, without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program. If not, see <http://www.gnu.org/licenses/>.


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
--INSERT INTO resource_tags (tag, red, green, blue, alpha, finished) 
--					VALUES ('To do', 0, 0, 0, 1, False)

ALTER TABLE time_clock_projects ADD COLUMN IF NOT EXISTS resource_id bigint UNIQUE REFERENCES resources ON UPDATE RESTRICT ON DELETE RESTRICT;
-- version 0.4.3
ALTER TABLE credit_memo_items ADD COLUMN IF NOT EXISTS ext_price numeric (12, 2) DEFAULT 0.00;
UPDATE credit_memo_items SET ext_price = (qty * price) WHERE ext_price IS NULL;
ALTER TABLE credit_memo_items ALTER COLUMN ext_price SET NOT NULL;


