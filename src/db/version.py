# version.py
#
# Copyright (C) 2018 - reuben
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

from gi.repository import Gtk, GLib
import constants

UI_FILE = constants.ui_directory + "/db/version.ui"


class CheckVersion :
	def __init__ (self, main, version):

		from db import database_tools
		d = database_tools.GUI()
		d.window.hide()
		while Gtk.events_pending():
			Gtk.main_iteration()
		d.upgrade_old_version()
		self.window = main.window
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		for dialog in (['db_major_upgrade', 'db_newer_dialog', 
						'db_minor_upgrade', 'credit_memo_dialog']):
			self.builder.get_object(dialog).set_transient_for(self.window)
		self.db = main.db
		c = self.db.cursor()
		c.execute("SELECT "
					"major_version::text, "	
					"minor_version::text, "
					"version "
					"FROM settings")
		for row in c.fetchall():
			major_db_version = row[0]
			minor_db_version = row[1]
			old_version = row[2]
		upgrade = True
		if major_db_version <= '4' and minor_db_version < '6':
			self.populate_liabilities_store ()
			dialog = self.builder.get_object('credit_memo_dialog')
			response = dialog.run()
			if response == Gtk.ResponseType.ACCEPT:
				account = self.builder.get_object('account_combo').get_active_id()
				c.execute("ALTER TABLE public.gl_account_flow "
							"DROP COLUMN IF EXISTS id; "
							"ALTER TABLE public.gl_account_flow "
							"ADD PRIMARY KEY (function); "
							"INSERT INTO gl_account_flow (function, account) "
							"VALUES ('post_credit_memo', %s)", (account,))
			elif response == Gtk.ResponseType.REJECT:
				upgrade = False
			else:
				upgrade = False
				GLib.idle_add(Gtk.main_quit)
			dialog.hide()
		if major_db_version <= '4' and minor_db_version < '7':
			self.populate_liabilities_store ()
			label = "Select an account to post Credit Memo taxes to.\n"\
					"These are taxes returned that have already been collected.\n"\
					"Some states require these to be declared separately."
			self.builder.get_object('message_label').set_label(label)
			dialog = self.builder.get_object('credit_memo_dialog')
			response = dialog.run()
			if response == Gtk.ResponseType.ACCEPT:
				account = self.builder.get_object('account_combo').get_active_id()
				c.execute("INSERT INTO gl_account_flow (function, account) "
							"VALUES ('credit_memo_returned_taxes', %s)", (account,))
			elif response == Gtk.ResponseType.REJECT:
				upgrade = False
			else:
				upgrade = False
				GLib.idle_add(Gtk.main_quit)
			dialog.hide()
		if upgrade == True:
			self.run_updates (d, version, major_db_version, minor_db_version)
		d.window.destroy()

	def populate_liabilities_store (self):
		c = self.db.cursor()
		store = self.builder.get_object('credit_memo_account_store')
		store.clear()
		c.execute("SELECT number::text, name FROM gl_accounts "
					"WHERE (is_parent, type) = (False, 5)")
		for row in c.fetchall():
			store.append (row)
		c.close()

	def run_updates (self, d, version, major_db_version, minor_db_version):
		c = self.db.cursor()
		major_posting_version = int(version[2:3])
		minor_posting_version = int(version[4:6])
		if int(major_db_version) < major_posting_version:  # major version upgrade 
			dialog = self.builder.get_object('db_major_upgrade')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				d.update_tables_major ()
				d.update_tables_minor ()
				c.execute("UPDATE settings "
							"SET (major_version, minor_version) = (%s, %s)", 
							(major_posting_version, minor_posting_version))
			else:
				self.db.rollback()
				GLib.idle_add(Gtk.main_quit)
		elif int(major_db_version) > major_posting_version:  # major version behind
			dialog = self.builder.get_object('db_newer_dialog')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.DELETE_EVENT:
				GLib.idle_add(Gtk.main_quit)
		elif int(minor_db_version) < minor_posting_version:   # minor version upgrade
			dialog = self.builder.get_object('db_minor_upgrade')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				d.update_tables_minor ()
				c.execute("UPDATE settings "
							"SET minor_version = %s", (minor_posting_version,))
			else:
				self.db.rollback()
				GLib.idle_add(Gtk.main_quit)
		elif int(minor_db_version) > minor_posting_version:  # minor version behind
			dialog = self.builder.get_object('db_newer_dialog')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.DELETE_EVENT:
				GLib.idle_add(Gtk.main_quit)
		c.close()
		self.db.commit()
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()







