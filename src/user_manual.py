# user_manual.py
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

# Every window's help page, opened in yelp. A page is named by its file in
# help/C/pygtk-posting without the .page; tests/help/test_help.py checks that
# each name given here exists and that every window binds F1.

import os, subprocess
from gi.repository import Gtk, Gdk
import constants


def show (page, parent = None):
	# constants.help_dir, not an import of help_dir: it is only filled in by
	# set_directories (), which may run after this module is imported
	path = os.path.join(constants.help_dir, page + ".page")
	try:
		subprocess.Popen(["yelp", path])
	except FileNotFoundError:
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(parent)
		dialog.set_markup("Help is read with yelp, which is not installed."
							"\n\nInstall it with:\nsudo apt install yelp")
		dialog.run()
		dialog.destroy()

def bind_f1 (window, page):
	"F1 anywhere in window opens page"
	accel_group = Gtk.AccelGroup()
	accel_group.connect(Gdk.KEY_F1, 0, Gtk.AccelFlags.VISIBLE,
						lambda *args: show(page, window) or True)
	window.add_accel_group(accel_group)
