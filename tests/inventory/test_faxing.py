# test_faxing.py
#
# Faxing through the Brother MFC's BRFAX queue. Brother's filter reads the
# number from the job's fax-number= option and nothing else: a print dialog
# job arrives without one and completes in CUPS with nothing dialed. So these
# check that every fax leaves as an lp job carrying a number the driver can
# dial, and that nothing here can ever reach the real lp - subprocess.run and
# faxing.send are mocked in every test that could send.

import os, sys, shutil, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import faxing # first: it asks for the Poppler version
from gi.repository import Gtk, GLib, Poppler

# every shape the contacts.fax column holds in silrep_restore, as typed
STORED = {
	'585 554 6779': '15855546779',
	'6072314032': '16072314032',
	'1 336 697 3100': '13366973100',
	'Toms#315 694 0123': '13156940123',
	'Suzanne 315 552 7817': '13155527817',
	'cell 585 555 0100': '15855550100',
	'315 789 8200 fax & office': '13157898200',
}


def write_pdf (path, pages, text = 'page'):
	import weasyprint
	html = '<p style="page-break-after: always">%s</p>' % text * pages
	weasyprint.HTML(string = html).write_pdf(path)
	return path

def pdf_text (path):
	document = Poppler.Document.new_from_file(GLib.filename_to_uri(path))
	return [document.get_page(i).get_text()
			for i in range(document.get_n_pages())]


class DialableTest(unittest.TestCase):

	def test_every_stored_shape_becomes_one_number(self):
		for stored, number in STORED.items():
			self.assertEqual(faxing.dialable(stored), number, stored)
			self.assertTrue(faxing.valid_number(number), number)

	def test_what_is_not_one_number_is_left_to_the_user(self):
		for stored in ('', None, '585 554 6779 / 585 554 6780', '554 6779',
						'9,1 315 555 1234'):
			self.assertEqual(faxing.dialable(stored), '', stored)

	def test_the_driver_takes_digits_and_commas_only(self):
		for number in ('13155551234', '9,13155551234', '1,,3155551234'):
			self.assertTrue(faxing.valid_number(number), number)
		# a space is the worst of these: the filter cuts the number at it
		for number in ('', '1 315 555 1234', '1-315-555-1234', '(315)5551234',
						',13155551234', '1' * 33):
			self.assertFalse(faxing.valid_number(number), number)

	def test_display(self):
		self.assertEqual(faxing.display('13155551234'), '1 (315) 555-1234')
		self.assertEqual(faxing.display('9,13155551234'), '9,13155551234')


class SendTest(unittest.TestCase):

	def run_result(self, returncode = 0, stdout = '', stderr = ''):
		return mock.Mock(returncode = returncode, stdout = stdout,
							stderr = stderr)

	def test_the_number_travels_as_the_fax_number_option(self):
		with mock.patch.object(faxing.subprocess, 'run', return_value =
					self.run_result(stdout = 'request id is BRFAX-1800 '
												'(1 file(s))\n')) as run:
			job = faxing.send('/tmp/x.pdf', '13155551234', 'Invoice_12')
		self.assertEqual(job, 'BRFAX-1800')
		self.assertEqual(run.call_args[0][0],
						["lp", "-d", "BRFAX", "-t", "Invoice_12",
						"-o", "fax-number=13155551234",
						"-o", "Quality=FINE", "-o", "PageSize=Letter",
						"/tmp/x.pdf"])

	def test_the_title_is_made_safe_for_brothers_scripts(self):
		with mock.patch.object(faxing.subprocess, 'run',
								return_value = self.run_result()) as run:
			faxing.send('/tmp/x.pdf', '13155551234', "Fax_Bob's Shop & Co")
		args = run.call_args[0][0]
		self.assertEqual(args[args.index('-t') + 1], 'Fax_Bob_s_Shop_Co')

	def test_an_lp_failure_is_raised_with_its_message(self):
		with mock.patch.object(faxing.subprocess, 'run', return_value =
					self.run_result(1, stderr = 'lp: The printer or class '
												'does not exist.\n')):
			with self.assertRaisesRegex(faxing.FaxError, 'does not exist'):
				faxing.send('/tmp/x.pdf', '13155551234', 'Invoice_12')

	def test_an_undialable_number_never_reaches_lp(self):
		with mock.patch.object(faxing.subprocess, 'run') as run:
			with self.assertRaises(faxing.FaxError):
				faxing.send('/tmp/x.pdf', '315 555 1234', 'Invoice_12')
		run.assert_not_called()

	def test_queue_available(self):
		for stdout, available in (('Brother-MFC-9330CDW\nBRFAX\n', True),
									('BRFAX2\nQL-700\n', False), ('', False)):
			with mock.patch.object(faxing.subprocess, 'run',
						return_value = self.run_result(stdout = stdout)):
				self.assertEqual(faxing.queue_available(), available, stdout)
		with mock.patch.object(faxing.subprocess, 'run', side_effect = OSError):
			self.assertFalse(faxing.queue_available())


class PdfTestCase(unittest.TestCase):

	def setUp(self):
		super().setUp()
		self.directory = tempfile.mkdtemp(prefix = 'test_faxing_')
		self.addCleanup(shutil.rmtree, self.directory, True)
		self.two_pages = write_pdf(os.path.join(self.directory, 'two.pdf'), 2)


class FaxDialogTest(PdfTestCase):
	'''Gtk.Dialog.run () maps the dialog itself, past the show_all stub, so
	run is mocked in every test that gets that far'''

	def dialog(self, stored = '315 555 1234', **kwargs):
		return faxing.FaxDialog(None, 'A customer', stored, self.two_pages,
								**kwargs)

	def test_the_stored_number_is_offered_cleaned_up(self):
		dialog = self.dialog()
		self.assertEqual(dialog.number_entry.get_text(), '13155551234')
		self.assertTrue(dialog.send_button.get_sensitive())
		dialog.destroy()

	def test_a_number_already_chosen_is_offered_instead(self):
		dialog = self.dialog(number = '9,15855546779')
		self.assertEqual(dialog.number_entry.get_text(), '9,15855546779')
		dialog.destroy()

	def test_before_posting_there_is_no_pdf_to_count(self):
		dialog = faxing.FaxDialog(None, 'A customer', '315 555 1234',
									send_label = 'Fax when posted')
		self.assertEqual(dialog.send_button.get_label(), 'Fax when posted')
		dialog.destroy()

	def test_dont_fax_is_offered_only_when_asked_for(self):
		dialog = self.dialog()
		self.assertIsNone(dialog.get_widget_for_response(faxing.DONT_FAX))
		dialog.destroy()
		dialog = self.dialog(can_stop = True)
		self.assertIsNotNone(dialog.get_widget_for_response(faxing.DONT_FAX))
		with mock.patch.object(dialog, 'run', return_value = faxing.DONT_FAX):
			self.assertEqual(dialog.get_number(), '')

	def test_send_waits_for_a_dialable_number(self):
		dialog = self.dialog(stored = '')
		self.assertFalse(dialog.send_button.get_sensitive())
		dialog.number_entry.set_text('9,13155551234')
		self.assertTrue(dialog.send_button.get_sensitive())
		dialog.number_entry.set_text('315 555 1234')
		self.assertFalse(dialog.send_button.get_sensitive())
		dialog.destroy()

	def test_get_number(self):
		dialog = self.dialog()
		dialog.number_entry.set_text('9,13155551234')
		with mock.patch.object(dialog, 'run', return_value = Gtk.ResponseType.OK):
			self.assertEqual(dialog.get_number(), '9,13155551234')
		dialog = self.dialog()
		with mock.patch.object(dialog, 'run',
								return_value = Gtk.ResponseType.CANCEL):
			self.assertIsNone(dialog.get_number())


class FaxPdfTest(PdfTestCase):

	def setUp(self):
		super().setUp()
		self.message = mock.patch.object(faxing, 'show_message').start()
		self.send = mock.patch.object(faxing, 'send',
										return_value = 'BRFAX-9').start()
		self.addCleanup(mock.patch.stopall)

	def test_no_queue_is_said_and_nothing_is_asked(self):
		with mock.patch.object(faxing, 'queue_available', return_value = False), \
				mock.patch.object(faxing, 'FaxDialog') as dialog:
			self.assertIsNone(faxing.fax_pdf(None, self.two_pages, 'T'))
		dialog.assert_not_called()
		self.send.assert_not_called()
		self.assertIn('no fax queue named BRFAX', self.message.call_args[0][2])

	def test_a_confirmed_number_is_sent(self):
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing.FaxDialog, 'get_number',
									return_value = '13155551234'):
			job = faxing.fax_pdf(None, self.two_pages, 'Invoice_5',
									'A customer', '315 555 1234')
		self.assertEqual(job, 'BRFAX-9')
		self.send.assert_called_once_with(self.two_pages, '13155551234',
											'Invoice_5')
		self.assertEqual(self.message.call_args[0][1], Gtk.MessageType.INFO)
		self.assertIn('transmission report', self.message.call_args[0][2])

	def test_cancel_sends_nothing(self):
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing.FaxDialog, 'get_number',
									return_value = None):
			self.assertIsNone(faxing.fax_pdf(None, self.two_pages, 'T'))
		self.send.assert_not_called()
		self.message.assert_not_called()

	def test_a_failed_send_is_said(self):
		self.send.side_effect = faxing.FaxError('lp: no such queue')
		self.assertIsNone(faxing.send_and_report(None, self.two_pages,
													'13155551234', 'T'))
		self.assertEqual(self.message.call_args[0][1], Gtk.MessageType.ERROR)
		self.assertIn('lp: no such queue', self.message.call_args[0][2])


class FaxWindowTest(harness.DBTestCase):

	def setUp(self):
		super().setUp()
		self.directory = tempfile.mkdtemp(prefix = 'test_faxing_')
		self.addCleanup(shutil.rmtree, self.directory, True)
		self.two_pages = write_pdf(os.path.join(self.directory, 'two.pdf'), 2)
		self.contact_id = self.one("SELECT id FROM contacts "
									"WHERE deleted = False ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE contacts SET fax = 'Toms#315 694 0123' "
							"WHERE id = %s", (self.contact_id,))
		self.contact_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.contact_id,))
		self.DB.commit() # the window rolls back after every read
		self.message = mock.patch.object(faxing, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		import fax_window
		self.gui = fax_window.FaxGUI()
		self.addCleanup(self.gui.window.destroy)

	def get(self, widget_id):
		return self.gui.get_object(widget_id)

	def add_document(self, path):
		self.gui.document_store.append([path, os.path.basename(path),
										faxing.page_count(path)])
		self.gui.update_pages()

	def test_only_contacts_with_a_fax_number_are_offered(self):
		count = self.one("SELECT COUNT(*) FROM contacts "
							"WHERE deleted = False AND fax <> ''")
		self.assertEqual(len(self.gui.contact_store), count)
		self.assertTrue(all(row[2] for row in self.gui.contact_store))

	def test_the_lists_show_each_contact_and_its_number(self):
		'''text-column set in a .ui file only says what to match on: unlike
		set_text_column () it adds no renderer, and the popup draws nothing'''
		for widget_id in ('contact_completion', 'contact_combo'):
			cells = self.get(widget_id).get_cells()
			self.assertEqual(len(cells), 2, widget_id)

	def test_choosing_a_contact_fills_in_the_number_to_dial(self):
		self.get('contact_combo').set_active_id(str(self.contact_id))
		self.assertEqual(self.get('attention_entry').get_text(),
							self.contact_name)
		self.assertEqual(self.get('number_entry').get_text(), '13156940123')
		self.assertEqual(self.get('on_file_label').get_label(),
							'On file: Toms#315 694 0123')

	def test_send_needs_a_number_and_a_page(self):
		send = self.get('send_button')
		self.assertFalse(send.get_sensitive())
		self.get('number_entry').set_text('13155551234')
		self.assertTrue(send.get_sensitive()) # the cover sheet alone is a fax
		self.get('cover_check').set_active(False)
		self.assertFalse(send.get_sensitive())
		self.add_document(self.two_pages)
		self.assertTrue(send.get_sensitive())
		self.get('number_entry').set_text('1 315 555 1234')
		self.assertFalse(send.get_sensitive())

	def test_the_cover_sheet_goes_first_and_counts_itself(self):
		self.get('attention_entry').set_text('Accounts payable')
		self.get('number_entry').set_text('13155551234')
		self.get('subject_entry').set_text('Invoice 42')
		self.add_document(self.two_pages)
		pages = pdf_text(self.gui.build_pdf(self.directory))
		self.assertEqual(len(pages), 3)
		for text in ('Accounts payable', '1 (315) 555-1234', 'Invoice 42',
						'3, including this one'):
			self.assertIn(text, pages[0])
		self.assertNotIn('including this one', pages[1])

	def test_a_long_note_counts_every_cover_page(self):
		self.get('number_entry').set_text('13155551234')
		self.get('note_textview').get_buffer().set_text('A long note.\n' * 80)
		self.add_document(self.two_pages)
		pages = pdf_text(self.gui.build_pdf(self.directory))
		self.assertGreater(len(pages), 3) # more than one cover page
		self.assertIn('%s, including this one' % len(pages), pages[0])

	def test_without_a_cover_sheet_only_the_documents_go(self):
		self.get('cover_check').set_active(False)
		self.add_document(self.two_pages)
		self.add_document(write_pdf(os.path.join(self.directory, 'one.pdf'),
									1, 'second document'))
		pages = pdf_text(self.gui.build_pdf(self.directory))
		self.assertEqual(len(pages), 3)
		self.assertIn('second document', pages[2])

	def test_send_queues_one_job_then_clears_the_form(self):
		sent = []
		def send(path, number, title):
			sent.append((faxing.page_count(path), number, title,
						os.path.dirname(path)))
			return 'BRFAX-77'
		self.get('contact_combo').set_active_id(str(self.contact_id))
		self.add_document(self.two_pages)
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing, 'send', side_effect = send):
			self.gui.send_clicked(None)
		self.assertEqual(len(sent), 1)
		pages, number, title, directory = sent[0]
		self.assertEqual((pages, number), (3, '13156940123'))
		self.assertTrue(title.startswith('Fax_'))
		self.assertFalse(os.path.exists(directory)) # the merged pdf is gone
		self.assertIn('BRFAX-77', self.get('status_label').get_label())
		self.assertEqual(len(self.gui.document_store), 0)
		self.assertEqual(self.get('number_entry').get_text(), '')
		self.assertFalse(self.get('send_button').get_sensitive())
		self.message.assert_not_called()

	def test_a_failed_send_keeps_the_form(self):
		self.get('number_entry').set_text('13155551234')
		self.add_document(self.two_pages)
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing, 'send',
							side_effect = faxing.FaxError('lp: no such queue')):
			self.gui.send_clicked(None)
		self.assertIn('lp: no such queue', self.message.call_args[0][2])
		self.assertEqual(len(self.gui.document_store), 1)
		self.assertEqual(self.get('status_label').get_label(), '')

	def test_a_missing_queue_sends_nothing(self):
		self.get('number_entry').set_text('13155551234')
		with mock.patch.object(faxing, 'queue_available', return_value = False), \
				mock.patch.object(faxing, 'send') as send:
			self.gui.send_clicked(None)
		send.assert_not_called()
		self.assertIn('no fax queue', self.message.call_args[0][2])


if __name__ == '__main__':
	unittest.main()
