# zip_completion.py
#
# Copyright (C) 2026 - Reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

'''The zip code entry completion shared by the three address editors.

   The suggestions are whatever the contacts table already holds, so the list
   needs nothing maintained and grows as addresses are entered. That used to
   mean a typo spread itself, which is why contacts.city, state and zip are
   normalized by a trigger now (see the 0.7.30 block in update_db_minor.sql);
   with the column clean, GROUP BY collapses the repeats and the list converges.

   A zip can legitimately cover more than one locality, 14478 being both Bluff
   Point and Keuka Park, so the prefill picks one and the user can overwrite it.
'''

from db_connection import DB


def populate_store (store):
	'''fill a three column store with the distinct zip, city, state triples'''
	store.clear()
	cursor = DB.cursor()
	cursor.execute("SELECT zip, city, state FROM contacts "
						"WHERE deleted = False "
						"GROUP BY zip, city, state "
						"ORDER BY zip, city")
	for row in cursor.fetchall():
		store.append(row)
	cursor.close()

def city_state_for_zip (zip_code):
	'''a (city, state) tuple for this zip, or None when it is not in use yet'''
	cursor = DB.cursor()
	cursor.execute("SELECT city, state FROM contacts "
						"WHERE (deleted, zip) = (False, %s) "
						"GROUP BY city, state LIMIT 1", (zip_code,))
	row = cursor.fetchone()
	cursor.close()
	return row
