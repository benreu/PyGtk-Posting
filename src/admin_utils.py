# admin_dialog.py
#
# Copyright (C) 2020 - reuben
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
from constants import ui_directory

UI_FILE = ui_directory + "/admin_utils.ui"

main_window = None
is_admin = False

def get_admin (prompt = False):
	"check for admin, prompt option to show extra alert for not being admin"
	if is_admin == False:
		if prompt == True:
			pass

def set_admin (value):
	main_class.builder.get_object('menuitem10').set_sensitive(value)
	main_class.builder.get_object('menuitem67').set_sensitive(value)
	main_class.builder.get_object('menuitem21').set_sensitive(value)
	main_class.builder.get_object('menuitem45').set_sensitive(value)
	main_class.builder.get_object('menuitem55').set_sensitive(value)
	main_class.builder.get_object('menuitem50').set_sensitive(value)
	main_class.builder.get_object('menuitem74').set_sensitive(value)
	main_class.builder.get_object('menuitem76').set_sensitive(value)
	main_class.builder.get_object('menuitem64').set_sensitive(value)
	main_class.builder.get_object('menuitem49').set_sensitive(value)
	main_class.builder.get_object('menuitem80').set_sensitive(value)
	if value == True:
		main_class.builder.get_object('menuitem35').set_label("Admin logout")
	else:
		main_class.builder.get_object('menuitem35').set_label("Admin login")
	global is_admin
	is_admin = value

class AdminDialogGUI (Gtk.Builder):
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		if is_admin == True:
			set_admin (False)
		else:
			dialog = self.get_object('admin_dialog')
			dialog.set_transient_for(main_class.window)
			#self.builder.get_object('label21').set_visible(external)
			result = dialog.run()
			dialog.hide()
			text = self.get_object('entry2').get_text().lower()
			self.get_object('entry2').set_text('')
			if result == Gtk.ResponseType.ACCEPT and text == 'admin':
				set_admin (True)

	def password_entry_activated (self, dialog):
		dialog.response(-3)



