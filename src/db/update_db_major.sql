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
    WHERE table_name='employee_info' and column_name='current')
  THEN
      ALTER TABLE payroll.employee_info RENAME COLUMN current TO active;
  END IF;
END $$;
--clarify ambiguity
DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='employee_info' and column_name='payment_frequency')
  THEN
      ALTER TABLE payroll.employee_info RENAME COLUMN payment_frequency TO payments_per_year;
  END IF;
END $$;
--0.6.0
ALTER TABLE IF EXISTS purchase_order_line_items RENAME to purchase_order_items;


