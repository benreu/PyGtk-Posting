# test_email_window.py
#
# The compose window - the one place a message is typed rather than generated
# from a document. Nothing here reaches a mail server: send_and_report is
# mocked in every test.

import os, sys, tempfile, unittest
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


class EmailWindowTest (MailTestCase):

	def setUp (self):
		super().setUp()
		self.contact_id = self.one("SELECT id FROM contacts "
									"WHERE deleted = False ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE contacts SET email = 'alvin@example.com' "
							"WHERE id = %s", (self.contact_id,))
		self.contact_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.contact_id,))
		# the user works in this copy and has their own account set up in it,
		# and only one account may be active; cleared inside the test
		# transaction, which is rolled back, so their row survives the run
		self.cursor.execute("DELETE FROM settings.mail_accounts")
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, from_name, from_address, smtp_host, "
							"smtp_user) VALUES "
							"('t', 'Silrep', 'silrep@example.com', "
							"'smtp.example.com', 'silrep@example.com')")
		self.DB.commit()
		self.send = mock.patch.object(emailing, 'send_and_report',
										return_value = True).start()
		self.addCleanup(mock.patch.stopall)
		import email_window
		self.window = email_window

	def open (self, **kwargs):
		gui = self.window.EmailGUI(**kwargs)
		self.addCleanup(gui.window.destroy)
		return gui

	def test_it_opens_with_the_contact_already_chosen (self):
		gui = self.open(contact_id = self.contact_id, to = 'alvin@example.com')
		self.assertEqual(gui.get_object('to_entry').get_text(),
							'alvin@example.com')
		self.assertTrue(gui.get_object('send_button').get_sensitive())

	def test_it_says_which_account_the_message_goes_out_from (self):
		gui = self.open()
		self.assertIn('silrep@example.com',
						gui.get_object('status_label').get_label())

	def test_with_no_account_set_up_it_says_so_instead (self):
		self.cursor.execute("DELETE FROM settings.mail_accounts")
		self.DB.commit()
		gui = self.open()
		self.assertIn('No mail account',
						gui.get_object('status_label').get_label())

	def test_there_is_nothing_to_send_to_until_there_is_an_address (self):
		gui = self.open()
		gui.get_object('to_entry').set_text('')
		self.assertFalse(gui.get_object('send_button').get_sensitive())
		gui.get_object('to_entry').set_text('nobody')
		self.assertFalse(gui.get_object('send_button').get_sensitive())
		gui.get_object('to_entry').set_text('a@b.com')
		self.assertTrue(gui.get_object('send_button').get_sensitive())

	def test_choosing_a_contact_fills_in_their_address (self):
		gui = self.open()
		gui.get_object('contact_combo').set_active_id(str(self.contact_id))
		self.assertEqual(gui.get_object('to_entry').get_text(),
							'alvin@example.com')

	def test_an_attachment_is_read_as_bytes_under_its_own_name (self):
		gui = self.open(contact_id = self.contact_id, to = 'a@b.com')
		with tempfile.NamedTemporaryFile(suffix = '.pdf', delete = False) as f:
			f.write(b'%PDF-1.4 attached')
			path = f.name
		self.addCleanup(os.remove, path)
		gui.attachment_store.append([path, os.path.basename(path), '1 Kb'])
		self.assertEqual(gui.attachments(),
							[(os.path.basename(path), b'%PDF-1.4 attached')])

	def test_sending_hands_over_the_recipient_subject_body_and_link (self):
		gui = self.open(contact_id = self.contact_id, to = 'alvin@example.com')
		gui.get_object('subject_entry').set_text('A question')
		gui.get_object('body_textview').get_buffer().set_text('Hello there')
		gui.send_clicked(gui.get_object('send_button'))
		args, kwargs = self.send.call_args
		self.assertEqual(args[1],
					['%s <alvin@example.com>' % self.contact_name])
		self.assertEqual(args[2], 'A question')
		self.assertEqual(args[3], 'Hello there')
		self.assertEqual(kwargs['link'], ('contact_id', self.contact_id))

	def test_an_address_typed_in_with_no_contact_is_linked_to_nothing (self):
		gui = self.open(to = 'stranger@example.com')
		gui.send_clicked(gui.get_object('send_button'))
		self.assertIsNone(self.send.call_args.kwargs['link'])

	def test_an_attachment_that_vanished_is_reported_and_nothing_is_sent (self):
		gui = self.open(contact_id = self.contact_id, to = 'a@b.com')
		gui.attachment_store.append(['/nonexistent/gone.pdf', 'gone.pdf', '0 Kb'])
		with mock.patch.object(emailing, 'show_message') as shown:
			gui.send_clicked(gui.get_object('send_button'))
		self.assertTrue(shown.called)
		self.assertFalse(self.send.called)


if __name__ == '__main__':
	unittest.main()


class ComposeWindowOutcomeTest (EmailWindowTest):
	'''What the compose window does once the send has been reported. Unlike
	the invoice and document windows, this one holds something a person
	typed, so it only goes away when the message actually went.'''

	def compose (self):
		gui = self.open(contact_id = self.contact_id, to = 'alvin@example.com')
		gui.get_object('subject_entry').set_text('A question')
		gui.get_object('body_textview').get_buffer().set_text('Hello there')
		return gui

	def test_a_message_that_went_takes_its_window_with_it (self):
		gui = self.compose()
		gui.send_clicked(gui.get_object('send_button'))
		on_done = self.send.call_args.kwargs['on_done']
		self.assertEqual(on_done, gui.sent)
		with mock.patch.object(gui.window, 'destroy') as destroy:
			on_done(None)
		self.assertTrue(destroy.called)

	def test_a_message_that_did_not_go_keeps_what_was_typed (self):
		gui = self.compose()
		gui.send_clicked(gui.get_object('send_button'))
		with mock.patch.object(gui.window, 'destroy') as destroy:
			gui.sent(emailing.MailError('the server said no'))
		self.assertFalse(destroy.called)
		self.assertEqual(gui.get_object('subject_entry').get_text(),
							'A question')
		buf = gui.get_object('body_textview').get_buffer()
		self.assertEqual(buf.get_text(buf.get_start_iter(),
										buf.get_end_iter(), False),
							'Hello there')

	def test_a_failed_send_leaves_the_button_usable_again (self):
		gui = self.compose()
		gui.send_clicked(gui.get_object('send_button'))
		self.assertFalse(gui.get_object('send_button').get_sensitive())
		gui.sent(emailing.MailError('the server said no'))
		self.assertTrue(gui.get_object('send_button').get_sensitive())

	def test_nothing_started_also_leaves_the_button_usable (self):
		# send_and_report returning False never runs on_done, so the window
		# has to put itself back together
		self.send.return_value = False
		gui = self.compose()
		gui.send_clicked(gui.get_object('send_button'))
		self.assertTrue(gui.get_object('send_button').get_sensitive())


class HeldAttachmentTest (EmailWindowTest):
	'''A posted invoice is attached from invoices.pdf_data, so there is no
	file anywhere for the window to point at.'''

	def test_something_handed_in_is_attached_without_a_file (self):
		pdf = b'%PDF-1.4 straight out of the column'
		gui = self.open(contact_id = self.contact_id, to = 'a@b.com',
						attachments = [('Invoice_1234.pdf', pdf)])
		self.assertEqual(gui.attachments(), [('Invoice_1234.pdf', pdf)])
		self.assertEqual(len(list(gui.attachment_store)), 1)

	def test_it_is_listed_with_its_name_and_size (self):
		gui = self.open(attachments = [('Invoice_1234.pdf', b'0' * 2000)])
		row = list(gui.attachment_store)[0]
		self.assertEqual(row[1], 'Invoice_1234.pdf')
		self.assertEqual(row[2], '2 Kb')

	def test_removing_it_takes_it_off_the_message (self):
		gui = self.open(attachments = [('Invoice_1234.pdf', b'x')])
		store = gui.attachment_store
		store.remove(store.get_iter_first())
		self.assertEqual(gui.attachments(), [])

	def test_one_from_a_file_and_one_handed_in_both_go (self):
		import tempfile
		with tempfile.NamedTemporaryFile(suffix = '.pdf', delete = False) as f:
			f.write(b'from disk')
			path = f.name
		self.addCleanup(os.remove, path)
		gui = self.open(to = 'a@b.com', attachments = [('held.pdf', b'in hand')])
		gui.attachment_store.append([path, 'disk.pdf', '1 Kb'])
		self.assertEqual(gui.attachments(),
							[('held.pdf', b'in hand'), ('disk.pdf', b'from disk')])

	def test_the_record_it_was_opened_for_wins_over_the_contact (self):
		# an invoice's message belongs to the invoice, not just the customer
		gui = self.open(contact_id = self.contact_id, to = 'a@b.com',
						link = ('invoice_id', 99))
		gui.send_clicked(gui.get_object('send_button'))
		self.assertEqual(self.send.call_args.kwargs['link'],
							('invoice_id', 99))
