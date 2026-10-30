# email_message.py
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

'''The wording an invoice is emailed with.

It used to be four lines in invoice_window that only editing the source could
change, so every customer got the same message and a business whose payment
terms or sign-off read differently had no way to say so.

What is typed here is a template, not the finished message: {customer},
{invoice}, {total} and {company} are filled in for each invoice, and the
message still opens in the compose window afterwards to be edited or added
to before it goes. This sets where every one of them starts.'''

from gi.repository import Gtk, GLib
from db_connection import DB
from constants import ui_directory
import emailing
import user_manual

UI_FILE = ui_directory + "/email_message.ui"

# what the preview stands in with, so the tokens can be seen working without
# needing a real invoice to hand
SAMPLE = {'customer': 'Alvin Miller', 'invoice': '1234', 'total': '$486.20',
			'company': 'this company'}


class EmailMessageGUI (Gtk.Builder):

	def __init__ (self, name = 'invoice'):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.name = name
		self.loading = False
		self.get_object('token_label').set_label(
				'\n'.join("{%s}   %s" % (token, meaning)
							for token, meaning in emailing.TOKEN_HELP))
		self.load()
		self.window = self.get_object('window')
		user_manual.bind_f1(self.window, "email_message")
		self.window.show_all()

	def load (self):
		subject, body = emailing.message_template(self.name)
		self.show_message(subject, body)

	def show_message (self, subject, body):
		'''Put a message in the form without it counting as an edit - the
		preview follows every keystroke, and loading is not one.'''
		self.loading = True
		self.get_object('subject_entry').set_text(subject)
		self.get_object('body_textview').get_buffer().set_text(body)
		self.loading = False
		self.update_preview()

	def typed (self):
		"the message as it stands in the form, as (subject, body)"
		body_buffer = self.get_object('body_textview').get_buffer()
		return (self.get_object('subject_entry').get_text(),
				body_buffer.get_text(body_buffer.get_start_iter(),
										body_buffer.get_end_iter(), False))

	def message_changed (self, widget):
		if not self.loading:
			self.update_preview()

	def update_preview (self):
		'''Show the subject as a real invoice would carry it. A token typed
		wrong is left standing in the preview rather than silently dropped,
		which is how a {custmer} gets noticed here instead of in somebody's
		inbox.'''
		subject, body = self.typed()
		self.get_object('preview_label').set_label(
						"Subject on a real invoice:  %s"
						% emailing.fill_template(subject, SAMPLE))

	def save_clicked (self, button):
		subject, body = self.typed()
		cursor = DB.cursor()
		# the row is seeded by the upgrade, but a database somebody emptied
		# still has to be able to save
		cursor.execute("INSERT INTO settings.email_messages "
							"(name, subject, body) VALUES (%s, %s, %s) "
							"ON CONFLICT (name) DO UPDATE SET "
							"(subject, body) = (EXCLUDED.subject, "
							"EXCLUDED.body)",
							(self.name, subject, body))
		cursor.close()
		DB.commit()
		self.window.destroy()

	def restore_clicked (self, button):
		'''Put the standard wording back in the form. Not saved until Save is
		pressed, so this can be looked at and thought better of.'''
		subject, body = emailing.DEFAULT_MESSAGES.get(self.name, ('', ''))
		self.show_message(subject, body)

	def close_clicked (self, button):
		self.window.destroy()
