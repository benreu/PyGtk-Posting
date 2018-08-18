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

UI_FILE = "src/db/version.ui"


def check_db_version (main, version):

	from db import database_tools
	d = database_tools.GUI(main.db)
	d.window.hide()
	while Gtk.events_pending():
		Gtk.main_iteration()
	d.upgrade_old_version()
	window = main.window
	builder = Gtk.Builder()
	builder.add_from_file(UI_FILE)
	for dialog in (['db_major_upgrade', 'db_newer_dialog', 'db_minor_upgrade']):
		builder.get_object(dialog).set_transient_for(window)
	db = main.db
	c = db.cursor()
	c.execute("SELECT "
				"major_version::text, "	
				"minor_version::text, "
				"version "
				"FROM settings")
	for row in c.fetchall():
		major_db_version = row[0]
		minor_db_version = row[1]
		old_version = row[2]
	#if old_version < '132':
	#	raise Exception("Please upgrade to version 0.4.0 before continuing")
	major_posting_version = version[2:3]
	minor_posting_version = version[4:5]
	if major_db_version < major_posting_version:  # major version upgrade 
		dialog = builder.get_object('db_major_upgrade')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			d.update_tables_major ()
			d.update_tables_minor ()
			c.execute("UPDATE settings "
						"SET (major_version, minor_version) = (%s, %s)", 
						(major_posting_version, minor_posting_version))
		else:
			GLib.idle_add(Gtk.main_quit)
	elif major_db_version > major_posting_version:  # major version behind
		dialog = builder.get_object('db_newer_dialog')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.DELETE_EVENT:
			GLib.idle_add(Gtk.main_quit)
	elif minor_db_version < minor_posting_version:   # minor version upgrade
		dialog = builder.get_object('db_minor_upgrade')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			d.update_tables_minor ()
			c.execute("UPDATE settings "
						"SET minor_version = %s", (minor_posting_version,))
		else:
			GLib.idle_add(Gtk.main_quit)
	elif minor_db_version > minor_posting_version:  # minor version behind
		dialog = builder.get_object('db_newer_dialog')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.DELETE_EVENT:
			GLib.idle_add(Gtk.main_quit)
	d.window.destroy()
	c.close()
	db.commit()







