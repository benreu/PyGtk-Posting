# complete_search.py
#
# Copyright (C) 2020 - Reuben
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

import psycopg2
from gi.repository import Gtk, GLib
from multiprocessing import Process, Queue
from queue import Empty
from constants import DB, ui_directory

UI_FILE = ui_directory + "/complete_search.ui"

class CompleteSearchGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()
		self.data_queue = Queue()
		self.store = self.get_object('search_store')
		self.treeview = self.get_object('treeview')
		self.window = self.get_object('window')
		self.window.show_all()

	def search_activated (self, entry):
		self.search()

	def search_clicked (self, button):
		self.search()

	def search (self):
		self.search_text = self.get_object('search_entry').get_text()
		self.treeview.set_model(None)
		self.store.clear()
		thread = Process(target=self.get_results)
		thread.start()
		GLib.timeout_add(10, self.show_results)
		self.get_object('search_button').set_sensitive(False)
		spinner = self.get_object("spinner")
		spinner.show()
		spinner.start()

	def get_results(self):
		try:
			self.cursor.execute("SELECT * FROM complete_search(%s)", 
												(self.search_text,))
		except psycopg2.DataError as e:
			DB.rollback()
			self.data_queue.put(e)
			return
		tupl = self.cursor.fetchall()
		self.data_queue.put(tupl)
		DB.rollback()

	def stop_spinner (self):
		spinner = self.get_object("spinner")
		spinner.hide()
		spinner.stop()
		self.get_object('search_button').set_sensitive(True)

	def show_results (self):
		try:
			result = self.data_queue.get_nowait()
			if type(result) == psycopg2.DataError:
				self.show_message(str(result))
				self.stop_spinner()
				return False
			else:
				tupl = result
		except Empty:
			return True
		count = len(tupl)
		for row in tupl:
			self.store.append(row)
			while Gtk.events_pending():
				Gtk.main_iteration()
		self.treeview.set_model(self.store)
		self.get_object('label').set_label(str(count))
		self.get_object('search_button').set_sensitive(True)
		spinner = self.get_object("spinner")
		spinner.hide()
		spinner.stop()
		DB.commit()

	def treeview_row_activated (self, treeview, path, treeviewcolumn):
		schema = self.store[path][0]
		table = self.store[path][1]
		column = self.store[path][2]
		ctid = self.store[path][4]
		self.cursor.execute("SELECT * FROM %s.%s WHERE ctid = '%s'"% 
							(schema, table, ctid))
		for row in self.cursor.fetchall():
			print (row)

	def search_generator_clicked (self, button):
		window = self.get_object('search_generator_window')
		window.show_all()

	def clear_all_clicked (self, button):
		self.get_object('text_store').clear()

	def delete_text_clicked (self, button):
		model, path = self.get_object('word_selection').get_selected_rows()
		if path == []:
			return
		model.remove(model.get_iter(path))

	def add_text_clicked (self, button):
		store = self.get_object('text_store')
		iter_ = store.append([''])
		self.get_object('word_selection').select_iter(iter_)

	def text_edited (self, cellrenderertext, path, text):
		self.get_object('text_store')[path][0] = text

	def generate_clicked (self, button):
		active = self.get_object('search_type_box').get_active_id()
		if active == '0': # ANY partial words
			template = "%s|"
		elif active == '1': # ANY complete words
			template = "^%s$|"
		elif active == '2': # ALL partial words
			template = "(?=.*%s)"
		text = str()
		for row in self.get_object('text_store'):
			text += template % row[0]
		if active == '0' or active == '1': # remove trailing |
			text = "(%s)" % text[0:-1]
		self.get_object('search_entry').set_text(text)

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




