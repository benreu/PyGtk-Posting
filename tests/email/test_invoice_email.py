# test_invoice_email.py
#
# Emailing an invoice and a document from the windows that post them. Posting
# opens a compose window with the document attached rather than sending
# anything itself: what gets written to a customer is theirs to word, and an
# invoice posted to the wrong contact can still be caught there.
#
# What this replaced attached a pdf from a /tmp path keyed on the document's
# name - so two windows open on one customer overwrote each other's attachment
# - and skipped the send silently when the contact had no address, after the
# invoice had already posted. Nothing here can reach a mail server: the
# compose window is mocked in every test.

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

PDF = b'%PDF-1.4 the bytes that were posted'


class InvoiceEmailTest (MailTestCase):

	REAL_CUSTOMERS = ("SELECT c.id FROM contacts AS c "
						"JOIN customer_markup_percent AS m "
							"ON m.id = c.markup_percent_id "
						"WHERE (c.deleted, c.customer) = (False, True) "
						"ORDER BY c.id LIMIT 2")

	def setUp (self):
		super().setUp()
		self.cursor.execute(self.REAL_CUSTOMERS)
		(self.customer_id,), (self.other_customer_id,) = self.cursor.fetchall()
		# the user works in this copy, so the preference holds whatever they
		# last chose; the tests that read it set it themselves
		self.cursor.execute("UPDATE settings SET email_when_possible = True")
		self.cursor.execute("UPDATE contacts SET email = 'alvin@example.com' "
							"WHERE id = %s", (self.customer_id,))
		self.cursor.execute("UPDATE contacts SET email = '' WHERE id = %s",
							(self.other_customer_id,))
		self.customer_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.customer_id,))
		self.invoice_id = self.one("INSERT INTO invoices (customer_id, name, "
									"pdf_data) VALUES (%s, %s, %s) "
									"RETURNING id",
									(self.customer_id, 'Invoice_1234',
										memoryview(PDF)))
		self.DB.commit()
		import email_window
		self.compose = mock.patch.object(email_window, 'EmailGUI').start()
		self.message = mock.patch.object(emailing, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		import invoice_window
		self.gui = invoice_window.InvoiceGUI(self.invoice_id)
		self.settle()

	def settle (self):
		"let the window's idle callbacks run; load_settings is one of them"
		while Gtk.events_pending():
			Gtk.main_iteration()

	def menuitem (self):
		return self.gui.builder.get_object('email_invoice_menuitem')

	def opened (self):
		"the compose window's arguments"
		self.assertTrue(self.compose.called, 'no message was opened')
		return self.compose.call_args.kwargs


class AddressTest (InvoiceEmailTest):

	def test_a_customer_with_an_address_can_be_emailed (self):
		self.assertTrue(self.menuitem().get_sensitive())
		self.assertTrue(self.menuitem().get_active())
		self.assertEqual(self.gui.builder.get_object('entry_email').get_text(),
							'alvin@example.com')

	def test_a_customer_with_no_address_cannot (self):
		# this is the case that used to post the invoice and then quietly do
		# nothing, so nobody found out until the customer asked
		self.gui.customer_selected(self.other_customer_id)
		self.assertFalse(self.menuitem().get_sensitive())
		self.assertFalse(self.menuitem().get_active())
		self.assertIn('no email address', self.menuitem().get_tooltip_text())

	def test_choosing_a_customer_who_has_one_puts_it_back (self):
		self.gui.customer_selected(self.other_customer_id)
		self.gui.customer_selected(self.customer_id)
		self.assertTrue(self.menuitem().get_sensitive())
		self.assertTrue(self.menuitem().get_active())
		self.assertIsNone(self.menuitem().get_tooltip_text())

	def test_the_setting_still_decides_when_there_is_an_address (self):
		self.cursor.execute("UPDATE settings SET email_when_possible = False")
		self.DB.commit()
		import invoice_window
		gui = invoice_window.InvoiceGUI(self.invoice_id)
		self.settle()
		item = gui.builder.get_object('email_invoice_menuitem')
		self.assertTrue(item.get_sensitive())
		self.assertFalse(item.get_active())


class PostedInvoiceTest (InvoiceEmailTest):

	def invoice (self, total = 12.34):
		invoice = mock.Mock()
		invoice.total = total
		return invoice

	def test_nothing_is_sent_without_being_looked_at_first (self):
		# the whole point: posting opens a message, it does not send one
		self.gui.email_posted_invoice(self.invoice())
		self.assertTrue(self.compose.called)

	def test_the_attachment_is_the_posted_pdf_not_a_tmp_file (self):
		self.gui.email_posted_invoice(self.invoice())
		attachments = self.opened()['attachments']
		self.assertEqual(attachments, [('Invoice_1234.pdf', PDF)])

	def test_it_opens_addressed_to_the_customer (self):
		self.gui.email_posted_invoice(self.invoice())
		self.assertEqual(self.opened()['to'], 'alvin@example.com')
		# the combo's ids are text, so that is what the window carries
		self.assertEqual(str(self.opened()['contact_id']),
							str(self.customer_id))

	def test_the_subject_names_the_invoice (self):
		self.gui.email_posted_invoice(self.invoice())
		self.assertEqual(self.opened()['subject'], 'Invoice Invoice_1234')

	def test_the_body_is_filled_in_ready_to_be_edited (self):
		self.gui.email_posted_invoice(self.invoice(total = 12.34))
		body = self.opened()['body']
		self.assertIn('$12.34', body)
		self.assertIn(self.customer_name, body)

	def test_it_is_tied_to_the_invoice_for_mail_links (self):
		self.gui.email_posted_invoice(self.invoice())
		self.assertEqual(self.opened()['link'],
							('invoice_id', self.invoice_id))

	def test_no_address_opens_nothing (self):
		self.cursor.execute("UPDATE contacts SET email = '' WHERE id = %s",
							(self.customer_id,))
		self.DB.commit()
		self.gui.builder.get_object('entry_email').set_text('')
		self.assertFalse(self.gui.email_posted_invoice(self.invoice()))
		self.assertFalse(self.compose.called)

	def test_an_invoice_with_no_stored_pdf_opens_nothing (self):
		self.cursor.execute("UPDATE invoices SET pdf_data = NULL WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		self.assertFalse(self.gui.email_posted_invoice(self.invoice()))
		self.assertFalse(self.compose.called)


class DocumentEmailTest (MailTestCase):

	def setUp (self):
		super().setUp()
		self.contact_id = self.one("SELECT id FROM contacts "
									"WHERE deleted = False ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE contacts SET email = 'alvin@example.com' "
							"WHERE id = %s", (self.contact_id,))
		self.contact_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.contact_id,))
		self.document_type_id = self.one("SELECT id FROM document_types "
											"ORDER BY id LIMIT 1")
		self.document_id = self.one("INSERT INTO documents "
									"(contact_id, name, dated_for, "
									"date_created, document_type_id, pdf_data) "
									"VALUES (%s, %s, CURRENT_DATE, "
									"CURRENT_DATE, %s, %s) "
									"RETURNING id",
									(self.contact_id, 'Quo_9_abc_Oct_21_2026',
										self.document_type_id, memoryview(PDF)))
		self.DB.commit()
		import email_window
		self.compose = mock.patch.object(email_window, 'EmailGUI').start()
		self.message = mock.patch.object(emailing, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		import documents_window
		self.gui = documents_window.DocumentGUI()
		self.gui.contact_id = self.contact_id
		self.gui.document_id = self.document_id
		self.gui.document_name = 'Quo_9_abc_Oct_21_2026'
		self.gui.document_type = 'Quote'

	def opened (self):
		self.assertTrue(self.compose.called, 'no message was opened')
		return self.compose.call_args.kwargs

	def test_the_attachment_is_the_posted_pdf (self):
		self.gui.email_posted_document()
		self.assertEqual(self.opened()['attachments'],
							[('Quo_9_abc_Oct_21_2026.pdf', PDF)])

	def test_the_subject_is_the_document_type (self):
		self.gui.email_posted_document()
		self.assertEqual(self.opened()['subject'], 'Quote')

	def test_a_quote_opens_for_a_note_to_be_added (self):
		# a quote is rarely sent bare, which is why it opens rather than goes
		self.gui.email_posted_document()
		self.assertEqual(self.opened()['to'], 'alvin@example.com')
		self.assertIn('quote', self.opened()['body'])

	def test_a_blank_address_is_said_out_loud_not_skipped (self):
		self.cursor.execute("UPDATE contacts SET email = '' WHERE id = %s",
							(self.contact_id,))
		self.DB.commit()
		self.assertFalse(self.gui.email_posted_document())
		self.assertFalse(self.compose.called)
		self.assertTrue(self.message.called)
		said = self.message.call_args.args[2]
		self.assertIn('posted', said)
		self.assertIn('no email address', said)


if __name__ == '__main__':
	unittest.main()
