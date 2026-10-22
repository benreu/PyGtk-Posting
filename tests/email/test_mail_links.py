# test_mail_links.py
#
# What a message is about. Until there were links, a sent message was a row in
# a flat log: the compose window knew which customer and which invoice it was
# for and threw both away, so the record of what had been sent to a customer
# could not be asked for by customer.
#
# The table is shaped by two rules that these pin down. Exactly one target per
# row, so a message about an invoice is two rows and each answers one
# question; and one row per message per target, so attaching twice is still
# one link.
#
# Nothing here reaches a mail server.

import os, sys, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
import mail_schema
from mail_schema import MailTestCase


class LinkTestCase (MailTestCase):
	'''A recorded message and the records it could be about. The invoice and
	purchase order are real rows out of the restore copy rather than made up,
	because the foreign keys are the point.'''

	def setUp (self):
		MailTestCase.setUp(self)
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active) VALUES ('test', False) RETURNING id")
		account_id = self.cursor.fetchone()[0]
		self.cursor.execute("INSERT INTO mail_messages "
							"(account_id, outgoing, subject) "
							"VALUES (%s, True, 'Invoice 1234') RETURNING id",
							(account_id,))
		self.message_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT id, customer_id FROM invoices "
							"ORDER BY id LIMIT 1")
		self.invoice_id, self.contact_id = self.cursor.fetchone()
		self.cursor.execute("SELECT id FROM purchase_orders ORDER BY id LIMIT 1")
		self.purchase_order_id = self.cursor.fetchone()[0]

	def link (self, column, record_id, message_id = None):
		self.cursor.execute("INSERT INTO mail_links (mail_messages_id, %s) "
							"VALUES (%%s, %%s) RETURNING id" % column,
							(message_id or self.message_id, record_id))
		return self.cursor.fetchone()[0]

	def links (self, message_id = None):
		self.cursor.execute("SELECT contact_id, invoice_id, purchase_order_id "
							"FROM mail_links WHERE mail_messages_id = %s "
							"ORDER BY id",
							(message_id or self.message_id,))
		return self.cursor.fetchall()


class ExactlyOneTargetTest (LinkTestCase):

	def test_a_link_to_one_record (self):
		self.link('contact_id', self.contact_id)
		self.assertEqual(self.links(),
							[(self.contact_id, None, None)])

	def test_a_link_to_nothing_is_refused (self):
		# a row pointing at no record is not a record of anything
		with self.assertRaises(harness.psycopg2.errors.CheckViolation):
			self.cursor.execute("INSERT INTO mail_links (mail_messages_id) "
								"VALUES (%s)", (self.message_id,))

	def test_a_link_to_two_records_at_once_is_refused (self):
		# the invoice and the customer are two questions, so they are two
		# rows; one row answering both could not be read as either
		with self.assertRaises(harness.psycopg2.errors.CheckViolation):
			self.cursor.execute("INSERT INTO mail_links (mail_messages_id, "
								"contact_id, invoice_id) VALUES (%s, %s, %s)",
								(self.message_id, self.contact_id,
									self.invoice_id))

	def test_a_link_to_all_three_is_refused (self):
		with self.assertRaises(harness.psycopg2.errors.CheckViolation):
			self.cursor.execute("INSERT INTO mail_links (mail_messages_id, "
								"contact_id, invoice_id, purchase_order_id) "
								"VALUES (%s, %s, %s, %s)",
								(self.message_id, self.contact_id,
									self.invoice_id, self.purchase_order_id))

	def test_an_emailed_invoice_is_two_rows (self):
		# what the send path really writes, and the shape the correspondence
		# window reads: findable under the invoice and under the customer
		self.link('invoice_id', self.invoice_id)
		self.link('contact_id', self.contact_id)
		self.assertEqual(self.links(), [(None, self.invoice_id, None),
										(self.contact_id, None, None)])

	def test_a_purchase_order_is_a_target_too (self):
		self.link('purchase_order_id', self.purchase_order_id)
		self.assertEqual(self.links(),
							[(None, None, self.purchase_order_id)])


class OneLinkPerTargetTest (LinkTestCase):

	def test_the_same_contact_twice_is_refused (self):
		self.link('contact_id', self.contact_id)
		with self.assertRaises(harness.psycopg2.errors.UniqueViolation):
			self.link('contact_id', self.contact_id)

	def test_the_same_invoice_twice_is_refused (self):
		self.link('invoice_id', self.invoice_id)
		with self.assertRaises(harness.psycopg2.errors.UniqueViolation):
			self.link('invoice_id', self.invoice_id)

	def test_an_invoice_link_is_not_a_duplicate_contact_link (self):
		# the indexes are partial for this reason. A plain unique index on
		# (mail_messages_id, contact_id) would see the invoice row as another
		# row with contact_id NULL, and NULLs being distinct to it, would
		# admit the duplicates it claimed to prevent
		self.link('invoice_id', self.invoice_id)
		self.link('contact_id', self.contact_id)
		self.link('purchase_order_id', self.purchase_order_id)
		self.assertEqual(len(self.links()), 3)

	def test_two_invoices_on_one_message_are_both_kept (self):
		# one unique row per invoice, not one invoice per message: a message
		# can carry two invoices and be about both
		self.cursor.execute("SELECT id FROM invoices ORDER BY id LIMIT 2")
		first, second = [row[0] for row in self.cursor.fetchall()]
		self.link('invoice_id', first)
		self.link('invoice_id', second)
		self.assertEqual(len(self.links()), 2)

	def test_the_same_contact_on_two_messages (self):
		self.cursor.execute("INSERT INTO mail_messages (outgoing) "
							"VALUES (True) RETURNING id")
		other = self.cursor.fetchone()[0]
		self.link('contact_id', self.contact_id)
		self.link('contact_id', self.contact_id, other)
		self.assertEqual(len(self.links()), 1)
		self.assertEqual(len(self.links(other)), 1)


class LinkLifetimeTest (LinkTestCase):

	def test_deleting_the_message_takes_its_links (self):
		self.link('invoice_id', self.invoice_id)
		self.link('contact_id', self.contact_id)
		self.cursor.execute("DELETE FROM mail_messages WHERE id = %s",
							(self.message_id,))
		self.assertEqual(self.links(), [])

	def test_deleting_a_linked_invoice_is_refused (self):
		# correspondence is not silently orphaned. Nothing in this program
		# deletes an invoice, so this costs nothing and says what it means
		self.link('invoice_id', self.invoice_id)
		with self.assertRaises(harness.psycopg2.errors.ForeignKeyViolation):
			self.cursor.execute("DELETE FROM invoices WHERE id = %s",
								(self.invoice_id,))

	def test_who_linked_it_fills_itself_in (self):
		# there is no logged in user in this program, so the Postgres role the
		# workstation connected as is as much as can honestly be recorded
		self.link('contact_id', self.contact_id)
		self.cursor.execute("SELECT linked_by, date_linked IS NOT NULL "
							"FROM mail_links WHERE mail_messages_id = %s",
							(self.message_id,))
		linked_by, dated = self.cursor.fetchone()
		self.assertNotEqual(linked_by, '')
		self.assertTrue(dated)


class ContactMergeTest (LinkTestCase):
	'''Merging duplicate contacts really deletes one of them, against a
	RESTRICT link. The merger reassigns a hardcoded list of tables first, and
	this is what notices when that list has not been taught about a new one.

	This drives the real merge_clicked rather than a copy of its SQL.'''

	def setUp (self):
		LinkTestCase.setUp(self)
		# terms_and_discounts_id and markup_percent_id are the two columns
		# of contacts that are NOT NULL with no default, so the pair is made
		# by copying them off an existing contact
		self.loser = self.new_contact('Merge Loser')
		self.winner = self.new_contact('Merge Winner')
		self.DB.commit()
		from admin import duplicate_contact
		self.gui = duplicate_contact.DuplicateContactGUI()
		self.gui.search = 'email'
		store = self.gui.builder.get_object('duplicate_contact_store')
		store.clear()
		for contact_id, name in ((self.winner, 'Merge Winner'),
									(self.loser, 'Merge Loser')):
			store.append([contact_id, name, '', '', '', '', '', '', '',
							'merge@example.com'])
		model = self.gui.builder.get_object('duplicate_contact_sort')
		selection = self.gui.builder.get_object('treeview-selection2')
		selection.select_path(0)        # the winner is the chosen row
		self.gui.paths = [model[1].path] # the loser is in self.paths

	def new_contact (self, name):
		self.cursor.execute("INSERT INTO contacts (name, email, "
								"terms_and_discounts_id, markup_percent_id) "
							"SELECT %s, 'merge@example.com', "
								"terms_and_discounts_id, markup_percent_id "
							"FROM contacts WHERE id = %s RETURNING id",
							(name, self.contact_id))
		return self.cursor.fetchone()[0]

	def test_the_correspondence_follows_the_surviving_contact (self):
		self.link('contact_id', self.loser)
		self.gui.merge_clicked(None)
		self.cursor.execute("SELECT contact_id FROM mail_links "
							"WHERE mail_messages_id = %s", (self.message_id,))
		self.assertEqual(self.cursor.fetchall(), [(self.winner,)])

	def test_a_message_linked_to_both_ends_up_linked_once (self):
		# the delete in front of the update is not optional: the unique index
		# would refuse the second of the two rows, and an UPDATE cannot carry
		# ON CONFLICT
		self.link('contact_id', self.loser)
		self.link('contact_id', self.winner)
		self.gui.merge_clicked(None)
		self.cursor.execute("SELECT contact_id FROM mail_links "
							"WHERE mail_messages_id = %s", (self.message_id,))
		self.assertEqual(self.cursor.fetchall(), [(self.winner,)])

	def test_the_losing_contact_is_really_gone (self):
		self.link('contact_id', self.loser)
		self.gui.merge_clicked(None)
		self.cursor.execute("SELECT count(*) FROM contacts WHERE id = %s",
							(self.loser,))
		self.assertEqual(self.cursor.fetchone()[0], 0)

	def test_a_merge_with_no_correspondence_still_works (self):
		self.gui.merge_clicked(None)
		self.cursor.execute("SELECT count(*) FROM contacts WHERE id = %s",
							(self.loser,))
		self.assertEqual(self.cursor.fetchone()[0], 0)


class ShippedLinkSchemaTest (MailTestCase):
	'''The table is defined in two places that must not drift: the --0.7.38
	block, which is what an upgraded database gets, and mail_schema's copy,
	which every test in this folder runs against. This runs the shipped SQL
	rather than a copy of it.'''

	def block (self):
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'db', 'update_db_minor.sql')
		with open(path) as sql_file:
			sql = sql_file.read()
		start = sql.index('--0.7.38')
		rest = sql.find('\n--0.7.', start + 1)
		return sql[start:] if rest == -1 else sql[start:rest]

	def shape (self, sql):
		self.cursor.execute("DROP TABLE IF EXISTS public.mail_links")
		self.cursor.execute(sql)
		self.DB.commit()
		self.cursor.execute("SELECT column_name, data_type, is_nullable, "
								"column_default "
							"FROM information_schema.columns "
							"WHERE (table_schema, table_name) = "
								"('public', 'mail_links') "
							"ORDER BY ordinal_position")
		columns = self.cursor.fetchall()
		self.cursor.execute("SELECT indexdef FROM pg_indexes "
							"WHERE (schemaname, tablename) = "
								"('public', 'mail_links') ORDER BY indexname")
		indexes = self.cursor.fetchall()
		self.cursor.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
							"WHERE conrelid = 'public.mail_links'::regclass "
							"ORDER BY conname")
		return columns, indexes, self.cursor.fetchall()

	def test_the_suite_is_run_against_the_table_that_ships (self):
		shipped = self.shape(self.block())
		tested = self.shape(mail_schema.PENDING_MAIL_LINK_SCHEMA)
		self.assertEqual(tested[0], shipped[0])
		self.assertEqual(tested[1], shipped[1])
		self.assertEqual(tested[2], shipped[2])

	def test_an_upgrade_leaves_a_table_that_is_already_there_alone (self):
		# this file re-runs from the top on every upgrade, so every statement
		# in it has to be a no-op the second time - the CHECK included, which
		# is why it is dropped by name before being added
		self.shape(self.block())
		self.cursor.execute("INSERT INTO mail_messages (outgoing) "
							"VALUES (True) RETURNING id")
		message_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT id FROM invoices ORDER BY id LIMIT 1")
		invoice_id = self.cursor.fetchone()[0]
		self.cursor.execute("INSERT INTO mail_links (mail_messages_id, "
							"invoice_id) VALUES (%s, %s) RETURNING id",
							(message_id, invoice_id))
		link_id = self.cursor.fetchone()[0]
		self.cursor.execute(self.block())
		self.DB.commit()
		self.cursor.execute("SELECT invoice_id FROM mail_links WHERE id = %s",
							(link_id,))
		self.assertEqual(self.cursor.fetchone()[0], invoice_id)

	def test_every_target_is_a_bigint (self):
		# files.contact_id is a smallint against a bigserial contacts.id and
		# stops working at contact 32,768; nothing here repeats that
		self.shape(self.block())
		self.cursor.execute("SELECT column_name, data_type "
							"FROM information_schema.columns "
							"WHERE (table_schema, table_name) = "
								"('public', 'mail_links') "
							"AND column_name LIKE '%\\_id'")
		for column, kind in self.cursor.fetchall():
			self.assertEqual(kind, 'bigint', column)

	def test_the_jobs_seam_is_written_down (self):
		# the next kind of record is one ADD COLUMN and one term in the CHECK,
		# and the comment has to say so where somebody will find it
		self.assertIn('job', self.block().lower())


if __name__ == '__main__':
	unittest.main()
