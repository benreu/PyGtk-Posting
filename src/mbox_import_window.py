# mbox_import_window.py
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

'''Pointing the mbox importer at a file.

Two buttons rather than one, deliberately. The file this reads holds the only
copy of a decade of mail, and a mail file does not look like anything from
outside, so Look at the file counts what is in it and writes nothing - a
wrong file is then a sentence on screen rather than thousands of rows to
find and undo.

The work is on a worker thread with its own database connection: the Inbox
here is over a gigabyte, and a worker touching the shared connection
segfaults the program rather than raising.'''

from gi.repository import Gtk, GLib
import os, threading
from db_connection import DB, background_connection
from constants import ui_directory
import emailing, mbox_import
import user_manual

UI_FILE = ui_directory + "/mbox_import_window.ui"


class MboxImportGUI (Gtk.Builder):

	def __init__ (self):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.importer = None
		self.working = False
		self.window = self.get_object('window')
		user_manual.bind_f1(self.window, "mail_archive_import")
		self.window.show_all()

	def destroy (self, window):
		# the thread holds its own connection and its own importer, and
		# nothing it does touches this window except through idle_add, which
		# checks the window is still here
		if self.importer != None:
			self.importer.cancelled = True

	############################## the file

	def browse_clicked (self, button):
		dialog = Gtk.FileChooserDialog(title = "Choose a mail file",
										action = Gtk.FileChooserAction.OPEN)
		dialog.set_transient_for(self.window)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
		# where Thunderbird keeps them, since that is what this is for and
		# the directory is hidden
		start = os.path.expanduser('~/.thunderbird')
		if os.path.isdir(start):
			dialog.set_current_folder(start)
		result = dialog.run()
		path = dialog.get_filename()
		dialog.destroy()
		if result == Gtk.ResponseType.ACCEPT and path != None:
			self.get_object('path_entry').set_text(path)

	def path_entry_changed (self, entry):
		path = entry.get_text().strip()
		usable = os.path.isfile(path)
		self.get_object('scan_button').set_sensitive(usable and
														not self.working)
		self.get_object('import_button').set_sensitive(usable and
														not self.working)
		if usable and self.get_object('folder_entry').get_text() == '':
			# the file's own name, which for a Thunderbird folder is what the
			# folder is called
			self.get_object('folder_entry').set_text(os.path.basename(path))

	def folder (self):
		typed = self.get_object('folder_entry').get_text().strip()
		if typed != '':
			return typed
		return os.path.basename(self.get_object('path_entry').get_text().strip())

	############################## saying what happened

	def say (self, text):
		buffer_ = self.get_object('status_buffer')
		buffer_.insert(buffer_.get_end_iter(), text + '\n')
		return False # idle_add: once, never re-armed

	def set_working (self, working):
		self.working = working
		for widget in ('scan_button', 'import_button', 'browse_button',
						'path_entry', 'folder_entry', 'outgoing_check',
						'link_check'):
			self.get_object(widget).set_sensitive(not working)
		if not working:
			self.path_entry_changed(self.get_object('path_entry'))

	def show_progress (self, read, stored):
		self.get_object('progress').set_text("%s read, %s stored"
												% (read, stored))
		# there is no total until the file has been scanned, and scanning it
		# twice to draw a bar would double the slowest part of the work
		self.get_object('progress').pulse()
		return False

	############################## looking

	def scan_clicked (self, button):
		path = self.get_object('path_entry').get_text().strip()
		self.set_working(True)
		self.say("Looking at %s..." % os.path.basename(path))

		def work ():
			try:
				with background_connection() as conn:
					importer = mbox_import.Importer(conn)
					count, earliest, latest = importer.scan(path)
			except Exception as e:
				GLib.idle_add(self.finished, str(e))
				return
			if count == 0:
				GLib.idle_add(self.finished,
								"There are no messages in that file.")
				return
			covering = ''
			if earliest != None:
				covering = ", dated %s to %s" % (earliest, latest)
			GLib.idle_add(self.finished, None,
							"%s messages%s. Press Import to read them in."
							% (count, covering))

		threading.Thread(target = work, daemon = True).start()

	############################## importing

	def import_clicked (self, button):
		path = self.get_object('path_entry').get_text().strip()
		folder = self.folder()
		outgoing = self.get_object('outgoing_check').get_active()
		link = self.get_object('link_check').get_active()
		account_id = self.account_id()
		self.set_working(True)
		self.say("Importing %s..." % os.path.basename(path))

		def progress (read, stored):
			GLib.idle_add(self.show_progress, read, stored)

		def work ():
			try:
				with background_connection() as conn:
					self.importer = mbox_import.Importer(conn, account_id)
					summary = self.importer.run(path, folder, outgoing,
												link, progress)
			except Exception as e:
				GLib.idle_add(self.finished, str(e))
				return
			finally:
				self.importer = None
			GLib.idle_add(self.finished, None, summary.said())

		threading.Thread(target = work, daemon = True).start()

	def account_id (self):
		'''Which mail account these belong to, or None. Read here on the main
		thread, because the worker must not touch the shared connection.'''
		acct = emailing.account()
		return None if acct == None else acct.id

	def finished (self, error, said = None):
		if not self.window.get_realized():
			return False # closed while the thread was running
		self.set_working(False)
		self.get_object('progress').set_fraction(0)
		self.get_object('progress').set_text('')
		if error != None:
			self.say(error)
		else:
			self.say(said)
			# the correspondence window is told, the same way a send tells it
			self.notify()
		return False

	def notify (self):
		cursor = DB.cursor()
		cursor.execute("SELECT pg_notify('mail_messages', '')")
		DB.commit()
		cursor.close()

	def close_clicked (self, button):
		self.window.destroy()
