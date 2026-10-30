# database_restore.py
#
# Copyright (C) 2016 - reuben
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

import gi
gi.require_version('Vte', '2.91')
from gi.repository import Gtk, GLib, Vte
import os
from db_connection import DB
from constants import ui_directory, sql_dir
from sqlite_utils import get_apsw_connection
from db.database_backup import connection_url, password_environment

UI_FILE = ui_directory + "/db/database_restore.ui"

def ask_restore_login (parent, host, port, db_name):
	'''(user, password) to restore with, or None when the user canceled.

	Asked for each restore and never saved. Restoring creates a database,
	which the posting login may not do, so this is usually postgres - whose
	password belongs on no workstation (see POSTGRES_README) and so is not
	taken from the connection form, which is the login Posting runs as.'''
	dialog = Gtk.Dialog(title = "Restore as", transient_for = parent,
						modal = True)
	dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
	restore_button = dialog.add_button("Restore", Gtk.ResponseType.OK)
	dialog.set_default_response(Gtk.ResponseType.OK)
	grid = Gtk.Grid(row_spacing = 6, column_spacing = 12, border_width = 10)
	dialog.get_content_area().pack_start(grid, True, True, 0)
	user_entry = Gtk.Entry(text = 'postgres', activates_default = True,
							width_chars = 28)
	password_entry = Gtk.Entry(activates_default = True, visibility = False,
								width_chars = 28)
	user_entry.connect('changed', lambda entry: restore_button.set_sensitive(
										entry.get_text().strip() != ''))
	rows = [("Database", Gtk.Label(label = db_name, xalign = 0)),
			("Server", Gtk.Label(label = "%s:%s" % (host, port), xalign = 0)),
			("User", user_entry),
			("Password", password_entry)]
	for row, (caption, widget) in enumerate(rows):
		grid.attach(Gtk.Label(label = caption, xalign = 1), 0, row, 1, 1)
		grid.attach(widget, 1, row, 1, 1)
	note = Gtk.Label(label = "A user that may create databases, usually "
							"postgres. Used for this restore only, and not "
							"saved. Once restored, the database is handed to "
							"the posting login.", xalign = 0, wrap = True,
							max_width_chars = 50)
	note.get_style_context().add_class('dim-label')
	grid.attach(note, 0, len(rows), 2, 1)
	dialog.show_all()
	password_entry.grab_focus()
	response = dialog.run()
	login = (user_entry.get_text().strip(), password_entry.get_text())
	dialog.destroy()
	return login if response == Gtk.ResponseType.OK else None

def hand_over_command (bin_path, user, host, port, db_name):
	'''psql running posting_role.sql on the restored database, which makes the
	posting login its owner: the backup records its owners, but the restore
	gives everything to whoever restored it. In the restore window's terminal,
	because the script asks one question there - a password for posting, the
	first time a server has that login at all.'''
	return ["%s/psql" % bin_path, "-X",
			"--file=%s" % os.path.join(sql_dir, 'posting_role.sql'),
			connection_url(user, host, port, db_name)]

def get_postgres_bin_path ():
	sqlite = get_apsw_connection()
	cursor = sqlite.cursor()
	cursor.execute("SELECT value FROM settings "
					"WHERE setting = 'postgres_bin_path'")
	bin_path = cursor.fetchone()[0]
	sqlite.close()
	return bin_path


class RestoreGUI(Gtk.Builder):
	def __init__(self, host, port, user, password, db_name):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.host = host
		self.port = port
		self.user = user
		self.password = password
		self.db_name = db_name
		self.db_name = db_name
		self.bin_path = get_postgres_bin_path ()
		self.terminal = Vte.Terminal()
		self.terminal.set_scroll_on_output(True)
		self.terminal.set_scrollback_lines(-1)
		self.terminal.connect("button-press-event", self.on_button_press)
		self.get_object('restore_scrolled_window').add(self.terminal)
		self.dialog = self.get_object('restore_dialog')
		sqlite = get_apsw_connection()
		cursor = sqlite.cursor()
		cursor.execute("SELECT value FROM settings "
						"WHERE setting = 'backup_path' AND setting != ''")
		for row in cursor.fetchall():
			backup_path = row[0]
			self.dialog.set_current_folder(backup_path)
		sqlite.close()
		result = self.dialog.run()
		if result == Gtk.ResponseType.APPLY:
			self.dialog.hide()
			self.restore_database()
			self.db_file = self.dialog.get_filename()
		self.dialog.destroy()

	def on_button_press(self, widget, event):
		if event.button == 3 and self.terminal.get_has_selection():
			menu = Gtk.Menu()
			copy_item = Gtk.MenuItem(label="Copy")
			copy_item.connect("activate", self.on_copy)
			menu.append(copy_item)
			menu.show_all()
			menu.popup_at_pointer(event)
			return True

	def on_copy(self, widget):
		self.terminal.copy_clipboard_format(Vte.Format.TEXT)
	
	def restore_file_selection_changed (self, filechooser):
		filename = filechooser.get_filename()
		if filename != None:
			self.get_object('status_label').set_label(filename)

	def restore_database(self):
		self.window = self.get_object('restore_window')
		self.window.show_all()
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		create_command = ["%s/psql" % self.bin_path,
							connection_url(self.user, self.host, self.port,
											'postgres'),
							"-c",
							"CREATE DATABASE %s" % self.db_name]
		pty.spawn_async(None,
						create_command,
						password_environment(self.password),
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.create_spawn_callback
						)

	def create_spawn_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.terminal.watch_child(pid)
		self.handler_id = self.terminal.connect("child-exited", self.create_finished_callback)

	def create_finished_callback (self, terminal, error):
		terminal.disconnect(self.handler_id)
		if error != 0:
			self.get_object('status_label').set_label('Create failed!')
			return
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		# --no-owner --no-acl: everything belongs to whoever restores it. The
		# backup records its owners, but the database itself was created above
		# under the restoring login, and without these a backup taken before
		# posting_role.sql would hand its tables to postgres while one taken
		# after fails on every table of a server that has no posting login.
		# This way it is always the same, and hand_over_command, the one step
		# after any restore, sorts out the owners.
		restore_command = ["%s/pg_restore" % self.bin_path, 
							"-v", "--no-owner", "--no-acl",
							"--dbname=%s" % connection_url(self.user, self.host,
														self.port, self.db_name),
							self.db_file]
		pty.spawn_async(None,
						restore_command,
						password_environment(self.password),
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.restore_spawn_callback
						)

	def restore_spawn_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.terminal.watch_child(pid)
		self.handler_id = self.terminal.connect("child-exited", self.restore_finished_callback)

	def restore_finished_callback (self, terminal, error):
		terminal.disconnect(self.handler_id)
		if error != 0:
			self.get_object('status_label').set_label('Restore failed!')
			return
		self.get_object('status_label').set_label("Restored %s, handing it to "
												"the posting login..."
												% self.db_name)
		pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
		self.terminal.set_pty(pty)
		pty.spawn_async(None,
						hand_over_command(self.bin_path, self.user, self.host,
											self.port, self.db_name),
						password_environment(self.password),
						GLib.SpawnFlags.DEFAULT,
						None,
						None,
						-1,
						None,
						self.hand_over_spawn_callback
						)

	def hand_over_spawn_callback (self, pty, task):
		try:
			validity, pid = pty.spawn_finish(task)
		except Exception as e:
			print(e)
			self.show_error_dialog(str(e))
			self.window.destroy()
			return
		self.terminal.watch_child(pid)
		self.handler_id = self.terminal.connect("child-exited", self.hand_over_finished_callback)

	def hand_over_finished_callback (self, terminal, error):
		terminal.disconnect(self.handler_id)
		if error != 0:
			# the data is all there; only the owners are wrong, and the script
			# can be run by hand as POSTGRES_README says
			label = ("Restored %s, but could not hand it to the posting "
					"login. Run posting_role.sql on it." % self.db_name)
		else:
			label = "Successfully restored %s for the posting login" % self.db_name
		self.get_object('status_label').set_label(label)

	def close_clicked (self, button):
		self.window.destroy()

	def window_destroy (self, widget):
		self.dialog.destroy()

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	transient_for = self.window,
									message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE,
									text = error)
		dialog.run()
		dialog.destroy()


