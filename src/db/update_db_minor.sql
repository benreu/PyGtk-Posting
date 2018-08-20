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


ALTER TABLE loans ADD COLUMN IF NOT EXISTS period_amount smallint DEFAULT 1;
UPDATE loans SET period_amount = 1 WHERE period_amount IS NULL;
ALTER TABLE loans ALTER COLUMN period_amount SET NOT NULL;
--version 0.4.1


