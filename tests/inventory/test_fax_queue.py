# test_fax_queue.py
#
# Faxes printed from any program. BRFAX holds every job, and fax_queue
# collects each held job, once, into one Send fax window, so pages printed
# from several programs go as one fax once a number is entered and Send is
# pressed; the held originals are then canceled. The scheduler is a fake here
# (FakeConnection), the conversion is the real cupsfilter, and faxing.send is
# mocked in every test that could send: nothing reaches a real queue.

import os, sys, shutil, subprocess, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import faxing # first: it asks for the Poppler version
from gi.repository import Gtk
import cups
import fax_queue
from test_faxing import pdf_text

CANCELED = 7 # IPP job-state


def numbered_pdf (path, pages):
	"pages that say which they are, so a page range can be checked"
	import weasyprint
	html = ''.join('<p style="page-break-after: always">PAGE %d</p>' % n
					for n in range(1, pages + 1))
	weasyprint.HTML(string = html).write_pdf(path)
	return path


class FakeConnection:
	'''the scheduler, as far as fax_queue and faxing.cancel_jobs ask it'''

	def __init__(self):
		self.jobs = {} # job id: attributes
		self.documents = {} # job id: [(path, document-format)]
		self.canceled = []

	def hold(self, job_id, documents, queue = 'BRFAX', state = fax_queue.HELD,
				**attrs):
		attrs.update({'job-state': state,
						'job-printer-uri': 'ipp://localhost/printers/' + queue,
						'number-of-documents': len(documents)})
		self.jobs[job_id] = attrs
		self.documents[job_id] = documents

	def getJobs(self, which_jobs, my_jobs, requested_attributes):
		return {job_id: {'job-state': attrs['job-state'],
						'job-printer-uri': attrs['job-printer-uri']}
				for job_id, attrs in self.jobs.items()
				if attrs['job-state'] < CANCELED}

	def getJobAttributes(self, job_id):
		return dict(self.jobs[job_id])

	def getDocument(self, printer_uri, job_id, number):
		# a temporary copy, as pycups gives: fax_queue deletes it
		path, document_format = self.documents[job_id][number - 1]
		handle, copy = tempfile.mkstemp()
		os.close(handle)
		shutil.copyfile(path, copy)
		return {'file': copy, 'document-format': document_format}

	def cancelJob(self, job_id):
		self.canceled.append(job_id)
		self.jobs[job_id]['job-state'] = CANCELED

	hold_default = 'indefinite' # what the queue does with a job sent unheld

	def getPrinterAttributes(self, name, requested_attributes):
		return {'job-hold-until-default': self.hold_default}


@unittest.skipUnless(os.path.exists(fax_queue.PPD) and
						shutil.which('cupsfilter'),
						"needs Brother's fax PPD and cupsfilter")
class FaxQueueTest(harness.DBTestCase):

	def setUp(self):
		super().setUp()
		self.directory = tempfile.mkdtemp(prefix = 'test_fax_queue_')
		self.addCleanup(shutil.rmtree, self.directory, True)
		self.manual = numbered_pdf(os.path.join(self.directory, 'manual.pdf'), 3)
		self.conn = FakeConnection()
		mock.patch.object(cups, 'Connection', return_value = self.conn).start()
		self.message = mock.patch.object(faxing, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		self.watcher = fax_queue.Watcher()
		self.addCleanup(shutil.rmtree, self.watcher.directory, True)
		self.addCleanup(self.close_window)

	def close_window(self):
		# destroy (), not the close button: that would ask about held jobs
		if self.watcher.gui is not None:
			self.watcher.gui.window.destroy()

	def hold_manual(self, job_id, **attrs):
		self.conn.hold(job_id, [(self.manual, 'application/pdf')], **attrs)

	def rows(self):
		return [(row[1], row[2], row[3])
				for row in self.watcher.gui.document_store]

	def test_a_held_print_opens_the_fax_window_with_its_pages(self):
		self.hold_manual(5, **{'document-name-supplied': 'manual.pdf'})
		self.watcher.poll()
		self.assertIsNotNone(self.watcher.gui)
		self.assertEqual(self.rows(), [('manual.pdf', 3, 5)])
		self.assertEqual(self.conn.canceled, []) # held until Send

	def test_the_pages_chosen_when_printing_are_the_pages_faxed(self):
		# lp -P and some dialogs send the whole file and leave the range to CUPS
		self.hold_manual(5, **{'page-ranges': [(1, 1), (3, 3)]})
		self.hold_manual(6, **{'page-ranges': (2, 2)})
		self.watcher.poll()
		first, second = [row[0] for row in self.watcher.gui.document_store]
		self.assertEqual([text.strip() for text in pdf_text(first)],
							['PAGE 1', 'PAGE 3'])
		self.assertEqual([text.strip() for text in pdf_text(second)],
							['PAGE 2'])

	def test_later_prints_join_the_same_fax_and_each_comes_once(self):
		self.hold_manual(5, **{'page-ranges': (1, 1)})
		self.watcher.poll()
		gui = self.watcher.gui
		self.hold_manual(6, **{'page-ranges': (3, 3)})
		self.watcher.poll()
		self.watcher.poll()
		self.assertIs(self.watcher.gui, gui)
		self.assertEqual([row[2] for row in self.rows()], [5, 6])

	def test_only_jobs_held_on_the_fax_queue_are_taken(self):
		self.hold_manual(5, queue = 'Brother-MFC-9330CDW')
		self.hold_manual(6, state = 3) # pending, not held
		self.watcher.poll()
		self.assertIsNone(self.watcher.gui)

	def test_postscript_prints_are_converted(self):
		postscript = os.path.join(self.directory, 'manual.ps')
		subprocess.run(['pdftops', self.manual, postscript], check = True)
		self.conn.hold(5, [(postscript, 'application/postscript')])
		self.watcher.poll()
		self.assertEqual(self.rows()[0][1], 3)

	def send(self, number = '13155551234'):
		sent = []
		def send(path, dial, title):
			sent.append((faxing.page_count(path), dial))
			return 'BRFAX-90'
		gui = self.watcher.gui
		gui.get_object('cover_check').set_active(False)
		gui.get_object('number_entry').set_text(number)
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing, 'send', side_effect = send):
			gui.send_clicked(None)
		return sent

	def test_send_faxes_every_print_as_one_then_cancels_them(self):
		self.hold_manual(5)
		self.hold_manual(6, **{'page-ranges': (2, 2)})
		self.watcher.poll()
		paths = [row[0] for row in self.watcher.gui.document_store]
		self.assertEqual(self.send(), [(4, '13155551234')]) # one call
		self.assertEqual(self.conn.canceled, [5, 6])
		self.assertEqual(len(self.watcher.gui.document_store), 0)
		self.assertFalse(any(os.path.exists(path) for path in paths))
		self.watcher.poll() # canceled now, so nothing comes back
		self.assertEqual(len(self.watcher.gui.document_store), 0)

	def test_a_failed_send_cancels_nothing(self):
		self.hold_manual(5)
		self.watcher.poll()
		gui = self.watcher.gui
		gui.get_object('number_entry').set_text('13155551234')
		with mock.patch.object(faxing, 'queue_available', return_value = True), \
				mock.patch.object(faxing, 'send',
							side_effect = faxing.FaxError('lp: busy')):
			gui.send_clicked(None)
		self.assertEqual(self.conn.canceled, [])
		self.assertEqual(len(gui.document_store), 1)

	def test_removing_a_print_cancels_it(self):
		self.hold_manual(5)
		self.hold_manual(6)
		self.watcher.poll()
		gui = self.watcher.gui
		gui.get_object('document_selection').select_path(0)
		gui.remove_clicked(None)
		self.assertEqual(self.conn.canceled, [5])
		self.assertEqual([row[2] for row in self.rows()], [6])

	def test_closing_asks_before_canceling_the_prints(self):
		self.hold_manual(5)
		self.watcher.poll()
		gui = self.watcher.gui
		with mock.patch.object(gui, 'ask_to_discard',
								return_value = False) as ask:
			gui.close_clicked(None)
			self.assertTrue(gui.window_delete_event(gui.window, None))
		ask.assert_called_with(1)
		self.assertIs(self.watcher.gui, gui) # still open
		self.assertEqual(self.conn.canceled, [])
		with mock.patch.object(gui, 'ask_to_discard', return_value = True):
			gui.close_clicked(None)
		self.assertEqual(self.conn.canceled, [5])
		self.assertIsNone(self.watcher.gui)

	def test_a_print_canceled_from_the_queue_leaves_the_fax(self):
		self.hold_manual(5)
		self.hold_manual(6)
		self.watcher.poll()
		self.conn.jobs[5]['job-state'] = CANCELED # by hand, in the print queue
		self.watcher.poll()
		self.assertEqual([row[2] for row in self.rows()], [6])
		self.assertEqual(self.conn.canceled, [])

	def test_an_unreadable_print_is_reported_once(self):
		self.hold_manual(5)
		with mock.patch.object(self.conn, 'getDocument',
								side_effect = cups.IPPError(1, 'Forbidden')):
			self.watcher.poll()
			self.watcher.poll()
		self.assertEqual(self.message.call_count, 1)
		self.assertIn('BRFAX-5', self.message.call_args[0][2])
		self.assertIsNone(self.watcher.gui)
		self.assertEqual(self.conn.canceled, []) # left for the user

	def test_a_closed_window_is_replaced_by_the_next_print(self):
		self.hold_manual(5)
		self.watcher.poll()
		with mock.patch.object(self.watcher.gui, 'ask_to_discard',
								return_value = True):
			self.watcher.gui.close_clicked(None)
		self.hold_manual(6)
		self.watcher.poll()
		self.assertEqual([row[2] for row in self.rows()], [6])

	def test_a_window_that_fails_to_open_does_not_stop_the_watching(self):
		self.hold_manual(5)
		with mock.patch.object(self.watcher, 'window',
								side_effect = AttributeError('broken')):
			self.assertTrue(self.watcher.poll()) # the timeout stays
		self.hold_manual(6)
		self.watcher.poll()
		self.assertEqual([row[2] for row in self.rows()], [6])

	def test_a_scheduler_that_is_down_is_tried_again(self):
		with mock.patch.object(cups, 'Connection', side_effect = RuntimeError):
			self.assertTrue(self.watcher.poll())
		self.assertIsNone(self.watcher.gui)


class HoldNoticeTest(harness.DBTestCase):
	'''a job printed to a queue that does not hold it completes undialed and
	nothing else says so, so the Send fax window shows the command to run'''

	def setUp(self):
		super().setUp()
		self.conn = FakeConnection()
		mock.patch.object(cups, 'Connection', return_value = self.conn).start()
		self.addCleanup(mock.patch.stopall)

	def window(self):
		import fax_window
		gui = fax_window.FaxGUI()
		self.addCleanup(gui.window.destroy)
		return gui

	def test_queue_holds_jobs(self):
		self.assertTrue(fax_queue.queue_holds_jobs())
		self.conn.hold_default = 'no-hold'
		self.assertFalse(fax_queue.queue_holds_jobs())
		with mock.patch.object(cups, 'Connection', side_effect = RuntimeError):
			self.assertTrue(fax_queue.queue_holds_jobs()) # unknown: say nothing

	def test_the_command_is_shown_only_while_the_queue_does_not_hold(self):
		self.assertFalse(self.window().get_object('hold_infobar').get_revealed())
		self.conn.hold_default = 'no-hold'
		gui = self.window()
		self.assertTrue(gui.get_object('hold_infobar').get_revealed())
		self.assertIn(fax_queue.HOLD_COMMAND,
						gui.get_object('hold_label').get_label())

	def test_both_help_buttons_open_the_fax_page(self):
		import fax_window
		gui = self.window()
		with mock.patch.object(fax_window.subprocess, 'Popen') as popen:
			gui.help_clicked(None)
			gui.get_object('hold_infobar').response(Gtk.ResponseType.HELP)
		self.assertEqual(popen.call_count, 2)
		for call in popen.call_args_list:
			self.assertEqual(call[0][0][0], 'yelp')
			self.assertTrue(call[0][0][1].endswith('/fax.page'))

	def test_the_fax_page_is_there_and_names_the_command(self):
		import constants, xml.dom.minidom
		path = os.path.join(constants.help_dir, 'fax.page')
		xml.dom.minidom.parse(path) # well formed, or yelp shows nothing
		with open(path) as f:
			self.assertIn(fax_queue.HOLD_COMMAND, f.read())


class CancelJobsTest(unittest.TestCase):

	def test_one_job_already_gone_does_not_stop_the_rest(self):
		conn = mock.Mock()
		conn.cancelJob.side_effect = [cups.IPPError(1, 'gone'), None]
		with mock.patch.object(cups, 'Connection', return_value = conn):
			faxing.cancel_jobs([5, 6])
		self.assertEqual([c[0][0] for c in conn.cancelJob.call_args_list],
							[5, 6])

	def test_no_scheduler_does_not_raise(self):
		with mock.patch.object(cups, 'Connection', side_effect = RuntimeError):
			faxing.cancel_jobs([5])


if __name__ == '__main__':
	unittest.main()
