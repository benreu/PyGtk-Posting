# test_address_normalization.py
#
# The 0.7.30 address work: the BEFORE INSERT OR UPDATE trigger that keeps
# city, state, zip and country tidy, the log trigger rewrite that adding the
# country column depended on, and the three editors that write those columns.
#
# harness has to be imported first: the editors do `from db_connection import
# DB`, which copies the connection by value.

import os, sys, unittest

sys.path.insert(0, os.path.dirname(__file__))

import harness
from gi.repository import Gtk

import contact_edit_main as cem
import contact_edit_individual as cei
import contact_edit_shipping_address as cesa


def minor_update_block (version):
	'''the statement update_db_minor.sql ships for one version marker, so the
	test cannot drift from what is actually applied to a database. execute_file
	splits that file on a double dash, which is why a body may not contain one'''
	from constants import sql_dir
	path = os.path.join(sql_dir, 'update_db_minor.sql')
	with open(path) as sql_file:
		commands = sql_file.read().split("--")
	for command in commands:
		if command.startswith(version):
			assert "--" not in command, 'the block would be split in two'
			return "--" + command # execute_file puts back what the split ate
	raise AssertionError('no %s block in update_db_minor.sql' % version)


class TestMigrationBlock(harness.DBTestCase):
	'''the shipped SQL, run against the real copy and rolled back with the test'''

	def test_block_is_one_chunk_with_a_label(self):
		block = minor_update_block('0.7.30')
		self.assertTrue(block.startswith('--0.7.30\n'))
		self.assertNotIn('--', block[2:])

	def test_leaves_no_dirty_row_behind_and_rerunning_changes_nothing(self):
		block = minor_update_block('0.7.30')
		self.cursor.execute(block)
		dirty = ("SELECT count(*) FROM %s WHERE city <> btrim(city) "
					"OR state <> btrim(state) OR zip <> btrim(zip) "
					"OR country <> btrim(country) "
					"OR (state ~ '^[A-Za-z]{2}$' AND state <> upper(state))")
		for table in ('public.contacts', 'public.contact_individuals',
						'public.contact_shipping_addresses', 'public.company_info'):
			self.cursor.execute(dirty % table)
			self.assertEqual(self.cursor.fetchone()[0], 0,
								'%s still holds an unnormalized row' % table)
		# the audit rows the backfill wrote are the only ones the re-run may add
		self.cursor.execute("SELECT count(*) FROM log.contacts")
		before = self.cursor.fetchone()[0]
		self.cursor.execute(block)
		self.cursor.execute("SELECT count(*) FROM log.contacts")
		self.assertEqual(self.cursor.fetchone()[0], before,
							'the block is not idempotent')

	def test_fixes_the_misspelled_city(self):
		self.cursor.execute("SELECT count(*) FROM contacts "
								"WHERE lower(btrim(city)) = 'canadaigua'")
		if self.cursor.fetchone()[0] == 0:
			self.skipTest('this copy has no canadaigua row to fix')
		self.cursor.execute(minor_update_block('0.7.30'))
		self.cursor.execute("SELECT count(*) FROM contacts "
								"WHERE lower(btrim(city)) = 'canadaigua'")
		self.assertEqual(self.cursor.fetchone()[0], 0)


class TestNormalizingTrigger(harness.DBTestCase):

	def new_contact(self, city, state, zip_code, country = 'USA'):
		self.cursor.execute("SELECT c.id FROM contacts AS c "
							"WHERE (c.deleted, c.customer) = (False, True) "
							"ORDER BY c.id LIMIT 1")
		self.cursor.execute("INSERT INTO contacts (name, markup_percent_id, "
								"terms_and_discounts_id, city, state, zip, country) "
							"SELECT 'test address', "
								"(SELECT id FROM customer_markup_percent ORDER BY id LIMIT 1), "
								"(SELECT id FROM terms_and_discounts ORDER BY id LIMIT 1), "
								"%s, %s, %s, %s RETURNING id, city, state, zip, country",
							(city, state, zip_code, country))
		return self.cursor.fetchone()

	def test_trims_and_collapses_whitespace(self):
		row = self.new_contact('  Keuka   Park  ', ' ny ', ' 14478 ', ' usa ')
		self.assertEqual(row[1:], ('Keuka Park', 'NY', '14478', 'usa'))

	def test_uppercases_a_two_letter_state_only(self):
		self.assertEqual(self.new_contact('Penn Yan', 'ky', '14527')[2], 'KY')
		# a province name is not a state code and must survive untouched
		self.assertEqual(self.new_contact('Brampton', 'Ontario', 'L6T 5G7')[2],
							'Ontario')

	def test_keeps_a_canadian_postal_code_and_a_zip_plus_four(self):
		self.assertEqual(self.new_contact('Brampton', 'Ontario', ' L6T 5G7 ')[3],
							'L6T 5G7')
		self.assertEqual(self.new_contact('Hamilton', 'NJ', ' 08691-2343 ')[3],
							'08691-2343')

	def test_never_case_folds_a_city(self):
		'''initcap would turn these into Mcleansville and City Of Industry'''
		self.assertEqual(self.new_contact('McLeansville', 'NC', '27301')[1],
							'McLeansville')
		self.assertEqual(self.new_contact('City of Industry', 'CA', '91744')[1],
							'City of Industry')

	def test_an_update_is_normalized_too(self):
		contact_id = self.new_contact('Geneva', 'NY', '14456')[0]
		self.cursor.execute("UPDATE contacts SET (city, state, zip) = "
								"(' Himrod ', ' ny ', ' 14842 ') WHERE id = %s "
							"RETURNING city, state, zip", (contact_id,))
		self.assertEqual(self.cursor.fetchone(), ('Himrod', 'NY', '14842'))

	def test_the_other_three_tables_are_normalized(self):
		contact_id = self.new_contact('Geneva', 'NY', '14456')[0]
		self.cursor.execute("INSERT INTO contact_individuals "
								"(name, city, state, zip, contact_id) "
							"VALUES ('x', ' Stanley ', ' ny ', ' 14561 ', %s) "
							"RETURNING city, state, zip", (contact_id,))
		self.assertEqual(self.cursor.fetchone(), ('Stanley', 'NY', '14561'))
		self.cursor.execute("INSERT INTO contact_shipping_addresses "
								"(description, city, state, zip, contact_id) "
							"VALUES ('x', ' Dundee ', ' ny ', ' 14837 ', %s) "
							"RETURNING city, state, zip", (contact_id,))
		self.assertEqual(self.cursor.fetchone(), ('Dundee', 'NY', '14837'))
		self.cursor.execute("UPDATE company_info SET (city, state, zip) = "
								"(' Penn  Yan ', ' ny ', ' 14527 ') "
							"RETURNING city, state, zip")
		self.assertEqual(self.cursor.fetchone(), ('Penn Yan', 'NY', '14527'))


class TestContactAuditLog(harness.DBTestCase):
	'''log.save_contact_trigger used to be a positional INSERT ... SELECT NEW.*,
	which the country column broke outright'''

	def test_insert_is_logged_with_normalized_values(self):
		self.cursor.execute("INSERT INTO contacts (name, markup_percent_id, "
								"terms_and_discounts_id, city, state, zip) "
							"SELECT 'test audit', "
								"(SELECT id FROM customer_markup_percent ORDER BY id LIMIT 1), "
								"(SELECT id FROM terms_and_discounts ORDER BY id LIMIT 1), "
								"' Branchport ', ' ny ', ' 14418 ' RETURNING id")
		contact_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT city, state, zip, country, date_edited "
							"FROM log.contacts WHERE id = %s", (contact_id,))
		row = self.cursor.fetchone()
		self.assertIsNotNone(row, 'the insert was not logged at all')
		self.assertEqual(row[:4], ('Branchport', 'NY', '14418', 'USA'))
		self.assertIsNotNone(row[4], 'date_edited was not filled in')

	def test_update_is_logged(self):
		self.cursor.execute("SELECT id FROM contacts WHERE deleted = False "
							"ORDER BY id LIMIT 1")
		contact_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT count(*) FROM log.contacts WHERE id = %s",
							(contact_id,))
		before = self.cursor.fetchone()[0]
		self.cursor.execute("UPDATE contacts SET city = ' Dresden ' WHERE id = %s",
							(contact_id,))
		self.cursor.execute("SELECT count(*) FROM log.contacts WHERE id = %s",
							(contact_id,))
		self.assertEqual(self.cursor.fetchone()[0], before + 1)
		self.cursor.execute("SELECT city FROM log.contacts WHERE id = %s "
							"ORDER BY date_edited DESC LIMIT 1", (contact_id,))
		self.assertEqual(self.cursor.fetchone()[0], 'Dresden')


class FakeContactOverview:
	def __init__(self, contact_id = 0):
		self.window = Gtk.Window()
		self.contact_id = contact_id
		self.repopulated = 0

	def populate_contact_individuals(self):
		self.repopulated += 1

	def populate_contact_shipping_addresses(self):
		self.repopulated += 1


class TestEditorsCarryCountry(harness.DBTestCase):
	'''all three editors read and write the new column, and a new record starts
	on the default rather than writing an empty string over it'''

	def test_contact_editor_defaults_a_new_contact_to_usa(self):
		gui = cem.ContactEditMainGUI()
		self.assertEqual(gui.get_object('country_entry').get_text(), 'USA')

	def test_contact_editor_loads_the_stored_country(self):
		self.cursor.execute("UPDATE contacts SET country = 'Canada' "
							"WHERE id = (SELECT min(id) FROM contacts "
										"WHERE deleted = False) RETURNING id")
		contact_id = self.cursor.fetchone()[0]
		self.DB.commit() # a savepoint release; the editor reads it back
		gui = cem.ContactEditMainGUI(contact_id)
		self.assertEqual(gui.get_object('country_entry').get_text(), 'Canada')

	def test_individual_editor_defaults_to_usa(self):
		gui = cei.ContactEditIndividualGUI(FakeContactOverview())
		self.assertEqual(gui.get_object('country_entry').get_text(), 'USA')

	def test_shipping_editor_defaults_to_usa(self):
		gui = cesa.ContactEditShippingAddressGUI(FakeContactOverview())
		self.assertEqual(gui.builder.get_object('country_entry').get_text(), 'USA')

	def test_shipping_editor_copies_country_from_billing(self):
		self.cursor.execute("SELECT id FROM contacts "
							"WHERE (deleted, customer) = (False, True) "
								"AND address != '' AND city != '' "
							"ORDER BY id LIMIT 1")
		row = self.cursor.fetchone()
		if row is None:
			self.skipTest('no contact with a billing address')
		contact_id = row[0]
		self.cursor.execute("UPDATE contacts SET country = 'Canada' WHERE id = %s",
							(contact_id,))
		self.DB.commit()
		gui = cesa.ContactEditShippingAddressGUI(FakeContactOverview(contact_id))
		gui.contact_id = contact_id # what new_shipping_address_clicked does
		gui.copy_billing_address_clicked(None)
		self.assertEqual(gui.builder.get_object('country_entry').get_text(),
							'Canada')


class TestZipCompletion(harness.DBTestCase):
	'''the completion the three editors now share'''

	def test_store_is_filled_from_contacts(self):
		import zip_completion
		gui = cem.ContactEditMainGUI()
		store = gui.get_object('zip_code_store')
		self.assertGreater(len(store), 0)
		# every suggestion is already normalized, which is the point of 0.7.30
		for row in store:
			zip_code, city, state = row[0], row[1], row[2]
			self.assertEqual(city, city.strip())
			self.assertEqual(state, state.strip())
			self.assertEqual(zip_code, zip_code.strip())

	def test_a_known_zip_prefills_city_and_state(self):
		self.cursor.execute("SELECT zip, city, state FROM contacts "
							"WHERE deleted = False AND zip != '' AND city != '' "
							"GROUP BY zip, city, state ORDER BY zip LIMIT 1")
		row = self.cursor.fetchone()
		if row is None:
			self.skipTest('no contact with a zip and city')
		zip_code, city, state = row
		for module, gui, city_entry, state_entry in (
				(cem, cem.ContactEditMainGUI(), 'entry5', 'entry6'),
				(cei, cei.ContactEditIndividualGUI(FakeContactOverview()),
					'entry5', 'entry6')):
			gui.get_object('entry4').set_text(zip_code)
			gui.zip_activated(gui.get_object('entry4'))
			self.assertEqual(gui.get_object(city_entry).get_text(), city,
								'%s did not prefill the city' % module.__name__)
			self.assertEqual(gui.get_object(state_entry).get_text(), state)

		gui = cesa.ContactEditShippingAddressGUI(FakeContactOverview())
		gui.builder.get_object('entry3').set_text(zip_code)
		gui.zip_activated(gui.builder.get_object('entry3'))
		self.assertEqual(gui.builder.get_object('entry4').get_text(), city)
		self.assertEqual(gui.builder.get_object('entry5').get_text(), state)

	def test_an_unknown_zip_leaves_the_entries_alone(self):
		gui = cem.ContactEditMainGUI()
		gui.get_object('entry5').set_text('Geneva')
		gui.get_object('entry4').set_text('00000')
		gui.zip_activated(gui.get_object('entry4'))
		self.assertEqual(gui.get_object('entry5').get_text(), 'Geneva')


if __name__ == '__main__':
	unittest.main()
