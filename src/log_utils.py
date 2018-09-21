# Copyright (C) 2016 reuben 
# 
# pygtk_posting is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# pygtk_posting is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>

import string

log_file = None 

#the log_file variable gets updated in pygtk_posting.py to reflect the actual
#log file path, note that when Anjuta launches the app, this will not work,
#it is primarily used for standard runtime debugging purposes

def remove_gtk_warnings ():
	
	log = open(log_file)
	string = log.read()
	string = string.replace("Gtk-CRITICAL **: gtk_entry_set_text: assertion 'GTK_IS_ENTRY (entry)' failed", "")
	string = string.replace("Gtk-CRITICAL **: gtk_editable_set_position: assertion 'GTK_IS_EDITABLE (editable)' failed", "")
	string = string.replace("Warning: invalid (NULL) pointer instance", "")
	string = string.replace("Warning: g_signal_handler_unblock: assertion 'G_TYPE_CHECK_INSTANCE (instance)' failed", "")
	string = string.replace("(pygtk_posting.py:)", "")
	string = string.replace("Gtk.main()", "")
	log.close()
	return string