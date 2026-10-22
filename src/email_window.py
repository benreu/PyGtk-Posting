# email_window.py
#
# Copyright (C) 2026 - reuben
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

'''A message to a contact, with any files attached, sent through Posting's
own mail account.

This is the one place mail is composed rather than generated: the invoice and
document windows send a document they already have, and nothing is typed. The
button that opens this used to run thunderbird -compose with nothing but an
address, which left the message outside Posting entirely - no record that it
was sent, and no account of whether it went.'''

from gi.repository import Gtk
import os
from db_connection import DB
from constants import ui_directory
import emailing

UI_FILE = ui_directory + "/email_window.ui"


class EmailGUI (Gtk.Builder):

	def __init__ (self, contact_id = None, to = '', subject = '', body = '',
					attachments = (), link = None):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.contact_store = self.get_object('contact_store')
		self.attachment_store = self.get_object('attachment_store')
		# what the record this message is about is, when the window was opened
		# for one; a message typed from scratch works it out from the contact
		self.link = link
		self.held = {}
		completion = self.get_object('contact_completion')
		completion.set_match_func(self.contact_match_func)
		self.populate_contact_store()
		self.get_object('to_entry').set_text(to or '')
		self.get_object('subject_entry').set_text(subject)
		self.get_object('body_textview').get_buffer().set_text(body)
		for name, data in attachments:
			self.hold(name, data)
		if contact_id != None:
			self.get_object('contact_combo').set_active_id(str(contact_id))
		self.window = self.get_object('window')
		self.window.show_all()
		self.show_account()
		self.update_buttons()

	def show_account (self):
		'''Say which account this goes out from, or that there is none. A
		window that looks ready to send but cannot is worse than one that says
		so before anything is typed.'''
		acct = emailing.account()
		if acct == None:
			self.get_object('status_label').set_label(
											emailing.missing_account_message())
		else:
			self.get_object('status_label').set_label("From %s"
						% emailing.address(acct.from_name, acct.from_address))

	def populate_contact_store (self):
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, email FROM contacts "
						"WHERE deleted = False AND email <> '' ORDER BY name")
		for row in cursor.fetchall():
			self.contact_store.append(row)
		cursor.close()
		DB.rollback()

	def contact_match_func (self, completion, key, iter_):
		for text in key.split():
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def contact_match_selected (self, completion, model, iter_):
		self.get_object('contact_combo').set_active_id(model[iter_][0])

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		if contact_id == None:
			return # typed into the entry, not chosen from the list
		for row in self.contact_store:
			if row[0] == contact_id:
				self.get_object('to_entry').set_text(row[2])
				break
		self.update_buttons()

	def to_entry_changed (self, entry):
		self.update_buttons()

	def update_buttons (self):
		to = self.get_object('to_entry').get_text()
		self.get_object('send_button').set_sensitive(
												emailing.valid_address(to))

	def add_clicked (self, button):
		dialog = Gtk.FileChooserDialog(title = "Choose files to attach",
										action = Gtk.FileChooserAction.OPEN)
		dialog.set_transient_for(self.window)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
		dialog.set_select_multiple(True)
		result = dialog.run()
		paths = dialog.get_filenames()
		dialog.destroy()
		if result != Gtk.ResponseType.ACCEPT:
			return
		for path in paths:
			try:
				size = os.path.getsize(path)
			except OSError as e:
				emailing.show_message(self.window, Gtk.MessageType.ERROR,
										"%s could not be read:\n%s"
										% (os.path.basename(path), e))
				continue
			self.attachment_store.append([path, os.path.basename(path),
											"%s Kb" % (size // 1000)])

	def hold (self, name, data):
		'''Attach something that is already in hand rather than on disk. A
		posted invoice comes out of invoices.pdf_data and there is no file
		anywhere to point the window at.'''
		self.held[name] = data
		self.attachment_store.append(['', name, "%s Kb" % (len(data) // 1000)])

	def remove_clicked (self, button):
		model, tree_iter = self.get_object('attachment_selection').get_selected()
		if tree_iter != None:
			model.remove(tree_iter)

	def attachments (self):
		'''The attachments as (filename, bytes). Read now rather than when
		each was chosen, so a file edited in between goes as it stands.'''
		files = []
		for row in self.attachment_store:
			if row[0] == '':
				files.append((row[1], self.held[row[1]]))
			else:
				with open(row[0], 'rb') as attachment:
					files.append((row[1], attachment.read()))
		return files

	def contact_name (self):
		contact_id = self.get_object('contact_combo').get_active_id()
		for row in self.contact_store:
			if row[0] == contact_id:
				return row[1]
		return ''

	def send_clicked (self, button):
		to = self.get_object('to_entry').get_text().strip()
		body_buffer = self.get_object('body_textview').get_buffer()
		body = body_buffer.get_text(body_buffer.get_start_iter(),
									body_buffer.get_end_iter(), False)
		try:
			attachments = self.attachments()
		except OSError as e:
			emailing.show_message(self.window, Gtk.MessageType.ERROR,
									"An attachment could not be read:\n%s" % e)
			return
		link = self.link
		if link == None:
			contact_id = self.get_object('contact_combo').get_active_id()
			link = ('contact_id', int(contact_id)) if contact_id else None
		button.set_sensitive(False)
		self.get_object('status_label').set_label("Sending...")
		started = emailing.send_and_report(self.window,
						[emailing.address(self.contact_name(), to)],
						self.get_object('subject_entry').get_text(), body,
						attachments = attachments, link = link,
						on_done = self.sent)
		if not started:
			# nothing was sent and the reason has been shown, so on_done never
			# ran: put the button back, or the window sits there unusable
			self.not_sent()

	def sent (self, error):
		'''The message went, so there is nothing left in this window to do
		with it. A message that did not go stays exactly as it was typed:
		closing on a failure would throw away what somebody had written, to
		be retyped before it could be tried again.'''
		if error == None:
			self.window.destroy()
		else:
			self.not_sent()

	def not_sent (self):
		self.get_object('send_button').set_sensitive(True)
		self.show_account()

	def close_clicked (self, button):
		self.window.destroy()
