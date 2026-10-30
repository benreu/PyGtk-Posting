# test_email_message.py
#
# The wording an invoice is emailed with. It used to be four lines in
# invoice_window that only editing the source could change, so every customer
# got the same message whatever this business's terms or sign-off actually
# are.
#
# The text is a template filled in per invoice. The filling must never raise:
# a stray brace in somebody's wording would otherwise blow up at the moment
# the message is used, long after the window that typed it was closed.

import os, sys, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from mail_schema import MailTestCase
import emailing
from gi.repository import Gtk


class FillTemplateTest (unittest.TestCase):

	def fill (self, text, **values):
		return emailing.fill_template(text, values)

	def test_a_token_is_replaced (self):
		self.assertEqual(self.fill("Hi {customer},", customer = 'Alvin'),
							"Hi Alvin,")

	def test_every_mention_of_one_is_replaced (self):
		self.assertEqual(self.fill("{a} and {a}", a = 'x'), "x and x")

	def test_a_token_nobody_defined_is_left_as_typed (self):
		# left standing rather than dropped, so a misspelling is visible in
		# the preview instead of a hole in somebody's inbox
		self.assertEqual(self.fill("Hi {custmer},", customer = 'Alvin'),
							"Hi {custmer},")

	def test_a_stray_brace_is_not_an_error (self):
		# this is what str.format would raise on, at the moment of sending
		for text in ("Part {1/2} inch", "an { open brace", "a } close brace",
						"{}", "{{customer}}", "100% of {"):
			emailing.fill_template(text, {'customer': 'Alvin'})

	def test_a_dollar_sign_is_just_a_dollar_sign (self):
		# string.Template would have wanted $$ here, and an invoice message is
		# full of amounts
		self.assertEqual(self.fill("You owe $486.20"), "You owe $486.20")

	def test_nothing_to_fill_in_is_left_alone (self):
		self.assertEqual(self.fill("Plain words."), "Plain words.")

	def test_an_empty_message_is_not_an_error (self):
		self.assertEqual(emailing.fill_template('', {}), '')
		self.assertEqual(emailing.fill_template(None, {}), '')

	def test_a_number_is_made_text (self):
		self.assertEqual(self.fill("#{invoice}", invoice = 1234), "#1234")

	def test_the_tokens_the_window_lists_are_the_ones_that_work (self):
		# the help in the window and what is actually filled in have to be the
		# same list, or it documents tokens that do nothing
		listed = [token for token, meaning in emailing.TOKEN_HELP]
		values = dict((token, 'X') for token in listed)
		subject, body = emailing.DEFAULT_MESSAGES['invoice']
		filled = emailing.fill_template(subject + body, values)
		self.assertNotIn('{', filled)


class MessageTemplateTest (MailTestCase):

	def setUp (self):
		super().setUp()
		self.cursor.execute("DELETE FROM settings.email_messages")
		self.DB.commit()

	def store (self, subject, body, name = 'invoice'):
		self.cursor.execute("INSERT INTO settings.email_messages "
							"(name, subject, body) VALUES (%s, %s, %s)",
							(name, subject, body))
		self.DB.commit()

	def test_what_was_saved_is_what_comes_back (self):
		self.store('Your bill {invoice}', 'Dear {customer}')
		self.assertEqual(emailing.message_template('invoice'),
							('Your bill {invoice}', 'Dear {customer}'))

	def test_no_row_falls_back_to_the_standard_wording (self):
		# a database that predates the table, or one somebody emptied, still
		# sends something that reads properly
		self.assertEqual(emailing.message_template('invoice'),
							emailing.DEFAULT_MESSAGES['invoice'])

	def test_an_emptied_message_falls_back_rather_than_sending_nothing (self):
		self.store('', '')
		self.assertEqual(emailing.message_template('invoice'),
							emailing.DEFAULT_MESSAGES['invoice'])

	def test_a_missing_table_still_sends (self):
		with mock.patch.object(harness.db_connection.DB, 'cursor') as cursor:
			cursor.return_value.execute.side_effect = Exception('no table')
			self.assertEqual(emailing.message_template('invoice'),
								emailing.DEFAULT_MESSAGES['invoice'])

	def test_the_filled_message_is_ready_to_open_with (self):
		self.store('Invoice {invoice}', 'Hi {customer}, you owe {total}.')
		subject, body = emailing.filled_message('invoice',
							{'customer': 'Alvin', 'invoice': '1234',
								'total': '$486.20'})
		self.assertEqual(subject, 'Invoice 1234')
		self.assertEqual(body, 'Hi Alvin, you owe $486.20.')


class EmailMessageWindowTest (MailTestCase):

	def setUp (self):
		super().setUp()
		self.cursor.execute("DELETE FROM settings.email_messages")
		self.DB.commit()
		import email_message
		self.module = email_message

	def open (self):
		gui = self.module.EmailMessageGUI()
		self.addCleanup(gui.window.destroy)
		return gui

	def saved (self):
		self.cursor.execute("SELECT subject, body FROM settings.email_messages "
							"WHERE name = 'invoice'")
		return self.cursor.fetchone()

	def test_it_opens_on_the_standard_wording_when_nothing_is_saved (self):
		gui = self.open()
		self.assertEqual(gui.typed(), emailing.DEFAULT_MESSAGES['invoice'])

	def test_it_opens_on_what_was_saved (self):
		self.cursor.execute("INSERT INTO settings.email_messages "
							"(name, subject, body) VALUES "
							"('invoice', 'Bill {invoice}', 'Dear {customer}')")
		self.DB.commit()
		gui = self.open()
		self.assertEqual(gui.typed(), ('Bill {invoice}', 'Dear {customer}'))

	def test_saving_keeps_it (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('Your invoice {invoice}')
		gui.get_object('body_textview').get_buffer().set_text('Thanks.')
		gui.save_clicked(None)
		self.assertEqual(self.saved(), ('Your invoice {invoice}', 'Thanks.'))

	def test_saving_twice_edits_rather_than_adds (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('One')
		gui.save_clicked(None)
		gui = self.open()
		gui.get_object('subject_entry').set_text('Two')
		gui.save_clicked(None)
		self.cursor.execute("SELECT count(*) FROM settings.email_messages")
		self.assertEqual(self.cursor.fetchone()[0], 1)
		self.assertEqual(self.saved()[0], 'Two')

	def test_what_was_saved_is_what_an_invoice_is_opened_with (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('Bill {invoice}')
		gui.get_object('body_textview').get_buffer().set_text(
											'{customer} owes {total}.')
		gui.save_clicked(None)
		subject, body = emailing.filled_message('invoice',
							{'customer': 'Alvin', 'invoice': '77',
								'total': '$10.00'})
		self.assertEqual(subject, 'Bill 77')
		self.assertEqual(body, 'Alvin owes $10.00.')

	def test_the_preview_shows_the_subject_as_it_will_read (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('Invoice {invoice}')
		self.assertIn(self.module.SAMPLE['invoice'],
						gui.get_object('preview_label').get_label())

	def test_a_misspelt_token_stands_out_in_the_preview (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('Invoice {invoce}')
		self.assertIn('{invoce}', gui.get_object('preview_label').get_label())

	def test_the_tokens_are_listed_for_whoever_is_typing (self):
		gui = self.open()
		listed = gui.get_object('token_label').get_label()
		for token, meaning in emailing.TOKEN_HELP:
			self.assertIn('{%s}' % token, listed)

	def test_restoring_puts_the_standard_wording_in_the_form (self):
		gui = self.open()
		gui.get_object('subject_entry').set_text('something else')
		gui.restore_clicked(None)
		self.assertEqual(gui.typed(), emailing.DEFAULT_MESSAGES['invoice'])

	def test_restoring_does_not_save_until_save_is_pressed (self):
		# it can be looked at and thought better of
		self.cursor.execute("INSERT INTO settings.email_messages "
							"(name, subject, body) VALUES "
							"('invoice', 'Mine', 'My wording')")
		self.DB.commit()
		gui = self.open()
		gui.restore_clicked(None)
		self.assertEqual(self.saved(), ('Mine', 'My wording'))


if __name__ == '__main__':
	unittest.main()


class SeededMessageTest (MailTestCase):
	'''The standard wording lives in two places that must not drift: the
	INSERT in --0.7.36, which is what an upgraded database gets, and
	emailing.DEFAULT_MESSAGES, which is what the Restore button puts back and
	what a database with no row falls back to. These run the shipped SQL
	rather than a copy of it.'''

	def block (self):
		"the --0.7.36 block out of the migration, as it will really be run"
		path = os.path.join(os.path.dirname(__file__), '..', '..',
							'src', 'db', 'update_db_minor.sql')
		with open(path) as sql_file:
			sql = sql_file.read()
		start = sql.index('--0.7.36')
		rest = sql.find('\n--0.7.', start + 1)
		return sql[start:] if rest == -1 else sql[start:rest]

	def run_block (self):
		self.cursor.execute(self.block())
		self.DB.commit()

	def seeded (self):
		self.cursor.execute("SELECT subject, body FROM settings.email_messages "
							"WHERE name = 'invoice'")
		return self.cursor.fetchone()

	def setUp (self):
		super().setUp()
		# mail_schema creates the table without the seed, so that every test
		# sets the message it wants; this one wants what the upgrade does
		self.cursor.execute("DROP TABLE IF EXISTS settings.email_messages")
		self.DB.commit()

	def test_an_upgrade_seeds_the_standard_wording (self):
		self.run_block()
		self.assertEqual(self.seeded(), emailing.DEFAULT_MESSAGES['invoice'])

	def test_the_notice_is_the_one_that_was_asked_for (self):
		self.run_block()
		subject, body = self.seeded()
		self.assertIn('CONFIDENTIALITY NOTICE:', body)
		self.assertIn('legally privileged information', body)
		self.assertIn('strictly prohibited.', body)
		self.assertTrue(body.endswith('strictly prohibited.'), body[-40:])

	def test_the_body_keeps_its_blank_lines (self):
		# chr(10) in the SQL, so the paragraphs survive into the message
		self.run_block()
		self.assertEqual(self.seeded()[1].count('\n\n'), 2)

	def test_running_the_upgrade_again_leaves_an_edited_message_alone (self):
		# this file re-runs from the top on every upgrade, and the guard is
		# the only thing standing between somebody's wording and the standard
		# one being put back under them
		self.run_block()
		self.cursor.execute("UPDATE settings.email_messages "
							"SET (subject, body) = ('Mine', 'My wording') "
							"WHERE name = 'invoice'")
		self.DB.commit()
		self.run_block()
		self.assertEqual(self.seeded(), ('Mine', 'My wording'))

	def test_running_it_again_does_not_add_a_second_row (self):
		self.run_block()
		self.run_block()
		self.cursor.execute("SELECT count(*) FROM settings.email_messages")
		self.assertEqual(self.cursor.fetchone()[0], 1)

	def test_the_block_carries_no_stray_comment_marker (self):
		# execute_file splits the whole file on "--" and re-prefixes each
		# piece, so a second one inside a block cuts it in half and the
		# remainder runs as its own statement
		self.assertEqual(self.block().count('--'), 1)
