# add_files.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GdkPixbuf, Gdk
import os, sys
import apsw, psycopg2, subprocess

#Comment the first line and uncomment the second before installing
#or making the tarball (alternatively, use project variables)
UI_FILE = "src/add_files.ui"
#UI_FILE = "/usr/local/share/pygtk_accounting/ui/pygtk_accounting.ui"

class GUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		
		self.db = db
		self.cursor = self.db.cursor()		
		self.window = self.builder.get_object('window1')			
		self.window.show_all()

	def save_file(self, widget):
		path="/home/reuben/test.pdf"
		f = open(path,'rb')
		dat = f.read()
		binary = psycopg2.Binary(dat)
		self.cursor.execute("INSERT INTO files(file_data) VALUES (%s)", (binary,))
		self.db.commit()


	def open_file(self, widget):
		fula = open("/tmp/ptest.pdf",'wb')
		self.cursor.execute("SELECT file_data FROM files WHERE id = %s", (int(2),))
		file_data = self.cursor.fetchone()[0]
		fula.write(file_data)
		fula.close()
		subprocess.call("xdg-open /tmp/ptest.pdf", shell = True)




		
