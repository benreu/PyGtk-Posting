# test_correspondence_window.py
#
# Reading what has been sent. Posting recorded every message it sent from
# 0.7.37 on, but the only way to read those rows was the SQL window, so in
# practice the record of what had been sent to a customer was still whatever
# was in the Sent folder of whichever workstation sent it.
#
# A message is found by the links recorded when it was sent, never by matching
# an email address, and the hardest thing here is the test that says so: two
# contacts sharing an address must not see each other's mail.
#
# Nothing here reaches a mail server, and nothing opens a pdf viewer:
# subprocess.Popen is mocked in every test that could.

import os, sys, unittest
from unittest import mock

# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

import harness
from mail_schema import MailTestCase
from gi.repository import Gtk

import correspondence_window


class CorrespondenceTestCase (MailTestCase):
	'''Three recorded messages: two to one customer, one of them about an
	invoice, and one to somebody else. Dates are days apart so that newest
	first means something.'''

	def setUp (self):
		MailTestCase.setUp(self)
		self.cursor.execute("DELETE FROM mail_links")
		self.cursor.execute("DELETE FROM mail_messages")
		self.cursor.execute("INSERT INTO settings.mail_accounts "
							"(name, active, from_address) VALUES "
							"('test', False, 'us@example.com') RETURNING id")
		self.account_id = self.cursor.fetchone()[0]
		self.cursor.execute("SELECT i.id, i.name, i.customer_id, c.name "
							"FROM invoices AS i "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE i.pdf_data IS NOT NULL "
							"ORDER BY i.id LIMIT 1")
		row = self.cursor.fetchone()
		if row == None:
			self.skipTest('no invoice with a saved pdf in this copy')
		(self.invoice_id, self.invoice_name,
			self.customer_id, self.customer_name) = row
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE deleted = False AND id <> %s "
							"ORDER BY id LIMIT 1", (self.customer_id,))
		self.other_id, self.other_name = self.cursor.fetchone()

		self.invoice_message = self.message('Invoice %s' % self.invoice_name,
							'Your invoice is attached.', days = 1,
							attached = True,
							links = [('invoice_id', self.invoice_id),
										('contact_id', self.customer_id)])
		self.question = self.message('A question', 'When can we expect it?',
							days = 2,
							links = [('contact_id', self.customer_id)])
		self.other_message = self.message('Somebody else', 'Not yours.',
							days = 3, links = [('contact_id', self.other_id)])
		self.DB.commit()

	def message (self, subject, body, days = 1, attached = False, links = (),
					to = 'them@example.com'):
		self.cursor.execute("INSERT INTO mail_messages (account_id, outgoing, "
								"date_sent, subject, body_text, to_addresses, "
								"has_attachments, from_address) "
							"VALUES (%s, True, now() - %s * interval '1 day', "
								"%s, %s, %s, %s, 'us@example.com') "
							"RETURNING id",
							(self.account_id, days, subject, body, to,
								attached))
		message_id = self.cursor.fetchone()[0]
		for column, record_id in links:
			self.cursor.execute("INSERT INTO mail_links (mail_messages_id, %s) "
								"VALUES (%%s, %%s)" % column,
								(message_id, record_id))
		return message_id

	def open (self, contact_id = None):
		gui = correspondence_window.CorrespondenceGUI(contact_id)
		self.addCleanup(gui.window.destroy)
		return gui

	def listed (self, gui):
		"the message ids in the list, in the order they are shown"
		return [row[0] for row in gui.get_object('message_sort')]

	def settle (self):
		while Gtk.events_pending():
			Gtk.main_iteration()


class TheListTest (CorrespondenceTestCase):

	def test_everything_sent_is_shown_when_no_contact_is_chosen (self):
		# the window is one customer's correspondence and the company's
		# outbox depending on this
		gui = self.open()
		self.assertEqual(set(self.listed(gui)),
							{self.invoice_message, self.question,
								self.other_message})

	def test_newest_first (self):
		gui = self.open()
		self.assertEqual(self.listed(gui)[0], self.invoice_message)

	def test_a_contact_shows_only_that_contact (self):
		gui = self.open(self.customer_id)
		self.assertEqual(set(self.listed(gui)),
							{self.invoice_message, self.question})

	def test_another_contacts_mail_is_not_shown (self):
		gui = self.open(self.customer_id)
		self.assertNotIn(self.other_message, self.listed(gui))

	def test_two_contacts_sharing_an_address_do_not_see_each_others_mail (self):
		# the whole reason the link is recorded rather than worked out from
		# the address. contacts.email is not unique, is not trimmed and is not
		# case folded on write, so an address match would sooner or later put
		# one customer's mail under another's name
		self.cursor.execute("UPDATE contacts SET email = 'shared@example.com' "
							"WHERE id IN (%s, %s)",
							(self.customer_id, self.other_id))
		self.DB.commit()
		gui = self.open(self.other_id)
		self.assertEqual(self.listed(gui), [self.other_message])

	def test_clearing_the_contact_shows_everything_again (self):
		gui = self.open(self.customer_id)
		gui.clear_clicked(None)
		self.assertEqual(len(self.listed(gui)), 3)

	def test_a_message_linked_to_nothing_is_still_in_the_company_list (self):
		# an address typed in with no contact chosen. It went out, so it is
		# part of the record even though nothing says who it was about
		stranger = self.message('To a stranger', 'Hello', days = 1)
		self.DB.commit()
		self.assertIn(stranger, self.listed(self.open()))

	def test_a_message_outside_the_dates_is_left_out (self):
		old = self.message('Last year', 'Long ago', days = 400,
							links = [('contact_id', self.customer_id)])
		self.DB.commit()
		gui = self.open(self.customer_id)
		self.assertNotIn(old, self.listed(gui))

	def test_widening_the_dates_brings_it_back (self):
		old = self.message('Last year', 'Long ago', days = 400,
							links = [('contact_id', self.customer_id)])
		self.DB.commit()
		gui = self.open(self.customer_id)
		from datetime import datetime, timedelta
		gui.start_calendar.set_date(datetime.today() - timedelta(days = 500))
		self.assertIn(old, self.listed(gui))

	def test_an_end_date_of_today_means_up_to_now (self):
		# a window left open overnight would otherwise stop showing mail at
		# midnight, and go on refreshing itself for messages it had decided
		# not to show. Real mail also carries clocks that are ahead
		later = self.message('Clock is fast', 'From the future', days = -1,
								links = [('contact_id', self.customer_id)])
		self.DB.commit()
		self.assertIn(later, self.listed(self.open(self.customer_id)))

	def test_an_end_date_in_the_past_is_still_a_cut (self):
		gui = self.open(self.customer_id)
		from datetime import datetime, timedelta
		gui.end_calendar.set_date(datetime.today() - timedelta(days = 2))
		self.assertNotIn(self.invoice_message, self.listed(gui))

	def test_the_contact_is_named_rather_than_addressed (self):
		gui = self.open(self.customer_id)
		shown = [row[4] for row in gui.get_object('message_sort')]
		self.assertIn(self.customer_name, shown)

	def test_a_message_about_nobody_falls_back_to_the_address (self):
		self.message('To a stranger', 'Hello', days = 1,
						to = 'stranger@example.com')
		self.DB.commit()
		shown = [row[4] for row in self.open().get_object('message_sort')]
		self.assertIn('stranger@example.com', shown)

	def test_an_attachment_is_marked (self):
		gui = self.open(self.customer_id)
		marks = dict((row[0], row[6]) for row in gui.get_object('message_sort'))
		self.assertEqual(marks[self.invoice_message], 'Yes')
		self.assertEqual(marks[self.question], '')

	def test_how_many_there_are_is_said (self):
		gui = self.open(self.customer_id)
		self.assertIn('2', gui.get_object('status_label').get_label())

	def test_a_contact_with_no_correspondence_is_told_so (self):
		gui = self.open(self.other_id)
		gui.contact_id = -1
		gui.populate_messages()
		self.assertIn('Nothing has been emailed',
						gui.get_object('status_label').get_label())

	def test_an_empty_list_with_older_mail_says_to_widen_the_dates (self):
		# the window opens on the last year, and an imported archive is
		# mostly older than that: without this the whole of it looks like
		# nothing at all
		self.message('From the archive', 'Long ago', days = 4000,
						links = [('contact_id', self.customer_id)])
		self.DB.commit()
		gui = self.open(self.customer_id)
		from datetime import datetime, timedelta
		# a window with nothing in it: the fixtures are one to three days old
		# and the archived one is far older
		gui.start_calendar.set_date(datetime.today() - timedelta(days = 200))
		gui.end_calendar.set_date(datetime.today() - timedelta(days = 100))
		said = gui.get_object('status_label').get_label()
		self.assertIn('oldest message here', said)
		self.assertIn('widen the dates', said)


class SearchTest (CorrespondenceTestCase):

	def search (self, gui, text):
		'''Type in the search box. GtkSearchEntry holds search-changed back
		for a moment of its own accord, which is right for the window and no
		use here, so it is emitted rather than waited for.'''
		entry = gui.get_object('search_entry')
		entry.set_text(text)
		entry.emit('search-changed')

	def test_the_subject_is_searched (self):
		gui = self.open()
		self.search(gui, 'question')
		self.assertEqual(self.listed(gui), [self.question])

	def test_the_contact_is_searched_too (self):
		gui = self.open()
		self.search(gui, self.other_name.lower())
		self.assertIn(self.other_message, self.listed(gui))

	def test_clearing_the_search_shows_everything (self):
		gui = self.open()
		self.search(gui, 'question')
		self.search(gui, '')
		self.assertEqual(len(self.listed(gui)), 3)

	def test_a_search_that_matches_nothing_shows_nothing (self):
		gui = self.open()
		self.search(gui, 'no such thing anywhere')
		self.assertEqual(self.listed(gui), [])


class TheMessageTest (CorrespondenceTestCase):

	def select (self, gui, message_id):
		model = gui.get_object('message_sort')
		for row in model:
			if row[0] == message_id:
				gui.get_object('message_treeview').set_cursor(row.path)
				return
		self.fail('%s is not in the list' % message_id)

	def body (self, gui):
		buffer_ = gui.get_object('body_buffer')
		return buffer_.get_text(buffer_.get_start_iter(),
								buffer_.get_end_iter(), False)

	def links (self, gui):
		return [(row[0], row[1]) for row in gui.get_object('link_store')]

	def test_choosing_a_message_shows_what_was_written (self):
		gui = self.open(self.customer_id)
		self.select(gui, self.question)
		self.assertEqual(self.body(gui), 'When can we expect it?')

	def test_choosing_another_message_replaces_it (self):
		gui = self.open(self.customer_id)
		self.select(gui, self.question)
		self.select(gui, self.invoice_message)
		self.assertEqual(self.body(gui), 'Your invoice is attached.')

	def test_what_the_message_was_about_is_listed (self):
		gui = self.open(self.customer_id)
		self.select(gui, self.invoice_message)
		self.assertIn(('Contact', self.customer_name), self.links(gui))
		self.assertIn(('Invoice', self.invoice_name), self.links(gui))

	def test_a_message_about_only_a_contact_lists_only_that (self):
		gui = self.open(self.customer_id)
		self.select(gui, self.question)
		self.assertEqual(self.links(gui), [('Contact', self.customer_name)])

	def test_nothing_is_selected_to_begin_with (self):
		gui = self.open(self.customer_id)
		self.assertEqual(self.body(gui), '')
		self.assertFalse(gui.get_object('open_button').get_sensitive())


class OpenTheDocumentTest (CorrespondenceTestCase):

	def setUp (self):
		CorrespondenceTestCase.setUp(self)
		self.popen = mock.patch.object(correspondence_window.subprocess,
										'Popen').start()
		self.addCleanup(mock.patch.stopall)

	def choose (self, gui, kind):
		for row in gui.get_object('link_store'):
			if row[0] == kind:
				gui.get_object('link_treeview').set_cursor(row.path)
				return
		self.fail('no %s link' % kind)

	def selected (self, gui, message_id):
		model = gui.get_object('message_sort')
		for row in model:
			if row[0] == message_id:
				gui.get_object('message_treeview').set_cursor(row.path)
				return
		self.fail('%s is not in the list' % message_id)

	def test_an_invoice_can_be_opened (self):
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Invoice')
		self.assertTrue(gui.get_object('open_button').get_sensitive())

	def test_a_contact_cannot_be_opened (self):
		# a contact is a real link - it is how this window finds the message
		# at all - but a contact is not a document
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Contact')
		self.assertFalse(gui.get_object('open_button').get_sensitive())

	def test_what_opens_is_the_pdf_that_was_attached (self):
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Invoice')
		gui.open_clicked(None)
		path = self.popen.call_args.args[0][1]
		self.cursor.execute("SELECT pdf_data FROM invoices WHERE id = %s",
							(self.invoice_id,))
		with open(path, 'rb') as written:
			self.assertEqual(written.read(), bytes(self.cursor.fetchone()[0]))

	def test_it_is_handed_to_the_desktop (self):
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Invoice')
		gui.open_clicked(None)
		self.assertEqual(self.popen.call_args.args[0][0], 'xdg-open')

	def test_an_invoice_with_no_saved_pdf_says_so_and_opens_nothing (self):
		self.cursor.execute("UPDATE invoices SET pdf_data = NULL WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Invoice')
		with mock.patch.object(gui, 'show_message') as said:
			gui.open_clicked(None)
		self.assertFalse(self.popen.called)
		self.assertIn('nothing to open', said.call_args.args[0])

	def test_a_slash_in_the_name_does_not_make_a_directory (self):
		self.cursor.execute("UPDATE invoices SET name = 'a/b' WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui = self.open(self.customer_id)
		self.selected(gui, self.invoice_message)
		self.choose(gui, 'Invoice')
		gui.open_clicked(None)
		self.assertTrue(os.path.exists(self.popen.call_args.args[0][1]))


class RefreshTest (CorrespondenceTestCase):
	'''A send on another workstation shows up here without the window being
	reopened, which is the whole point of the row being in the database
	rather than in somebody's Sent folder.'''

	def test_a_send_arms_a_refresh (self):
		gui = self.open()
		harness.db_connection.broadcaster.emit('mail_messages_changed')
		self.assertIsNotNone(gui.refresh_timeout)

	def test_a_flurry_of_sends_arms_only_one (self):
		# the sync will notify once per committed slice, two dozen times in a
		# minute during the first one, and each would rebuild the store
		gui = self.open()
		harness.db_connection.broadcaster.emit('mail_messages_changed')
		armed = gui.refresh_timeout
		for _ in range(5):
			harness.db_connection.broadcaster.emit('mail_messages_changed')
		self.assertEqual(gui.refresh_timeout, armed)

	def test_the_refresh_brings_in_what_was_sent (self):
		gui = self.open()
		new = self.message('Just sent', 'Hot off the press', days = 0,
							links = [('contact_id', self.customer_id)])
		self.DB.commit()
		harness.db_connection.broadcaster.emit('mail_messages_changed')
		gui.refresh_due()
		self.assertIn(new, self.listed(gui))

	def test_a_refresh_leaves_the_message_being_read_selected (self):
		gui = self.open(self.customer_id)
		model = gui.get_object('message_sort')
		for row in model:
			if row[0] == self.question:
				gui.get_object('message_treeview').set_cursor(row.path)
		self.message('Just sent', 'Hot', days = 0,
						links = [('contact_id', self.customer_id)])
		self.DB.commit()
		gui.populate_messages()
		self.assertEqual(gui.message_id, self.question)

	def test_a_renamed_contact_is_picked_up (self):
		gui = self.open()
		harness.db_connection.broadcaster.emit('contacts_changed')
		self.assertTrue(len(gui.contact_store) > 0)

	def test_destroying_the_window_disconnects_it (self):
		# a handler left connected is called with a destroyed window the next
		# time anything sends
		gui = self.open()
		gui.destroy(gui.window)
		self.assertEqual(gui.handler_ids, [])
		self.assertEqual(harness.db_connection.broadcaster.connected(
											'mail_messages_changed'), [])

	def test_destroying_the_window_disarms_a_pending_refresh (self):
		# a timeout left armed repopulates a store that is gone
		gui = self.open()
		harness.db_connection.broadcaster.emit('mail_messages_changed')
		self.assertIsNotNone(gui.refresh_timeout)
		gui.destroy(gui.window)
		self.assertIsNone(gui.refresh_timeout)


class ContactHistoryTabTest (CorrespondenceTestCase):
	'''The same correspondence as a tab in the contact history window, which
	is where somebody looking at a customer already is.'''

	def open_history (self):
		from reports import contact_history
		gui = contact_history.ContactHistoryGUI()
		self.addCleanup(gui.get_object('window1').destroy)
		gui.get_object('combobox1').set_active_id(str(self.customer_id))
		self.settle()
		return gui

	def test_the_contacts_messages_are_listed (self):
		gui = self.open_history()
		listed = [row[0] for row in gui.get_object('correspondence_store')]
		self.assertEqual(set(listed),
							{self.invoice_message, self.question})

	def test_another_contacts_mail_is_not_in_it (self):
		gui = self.open_history()
		listed = [row[0] for row in gui.get_object('correspondence_store')]
		self.assertNotIn(self.other_message, listed)

	def test_newest_first (self):
		gui = self.open_history()
		store = gui.get_object('correspondence_store')
		self.assertEqual(store[0][0], self.invoice_message)

	def test_the_tab_says_how_many (self):
		gui = self.open_history()
		self.assertIn('(2)', gui.get_object('label12').get_label())

	def test_an_empty_tab_is_not_shouted_about (self):
		gui = self.open_history()
		gui.contact_id = -1
		gui.populate_correspondence()
		self.assertEqual(gui.get_object('label12').get_label(),
							'Correspondence')

	def test_the_page_is_what_report_hub_requires (self):
		# report_hub_clicked does scrolled_window.get_child () and assumes a
		# treeview; the Documents placeholder in this notebook already breaks
		# that, and this tab must not be the second one
		gui = self.open_history()
		notebook = gui.get_object('notebook1')
		page = notebook.get_nth_page(9)
		self.assertIsInstance(page, Gtk.ScrolledWindow)
		self.assertIsInstance(page.get_child(), Gtk.TreeView)

	def test_opening_a_row_hands_it_to_the_correspondence_window (self):
		gui = self.open_history()
		with mock.patch.object(correspondence_window,
								'CorrespondenceGUI') as window:
			gui.correspondence_row_activated(None, None, None)
		self.assertEqual(window.call_args.args[0], self.customer_id)


class WindowLayoutTest (CorrespondenceTestCase):

	def test_the_remembered_size_is_applied (self):
		gui = self.open()
		self.assertTrue(gui.window.get_size()[0] > 0)

	def test_the_layout_can_be_saved_and_read_back (self):
		gui = self.open()
		gui.get_object('paned').set_position(275)
		gui.save_window_layout_activated(None)
		again = self.open()
		self.assertEqual(again.get_object('paned').get_position(), 275)


if __name__ == '__main__':
	unittest.main()
