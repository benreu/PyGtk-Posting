# pdf_attachment.py
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

import gi
gi.require_version('EvinceView', '3.0')
from gi.repository import Gtk, GObject
from gi.repository import EvinceView
from gi.repository import EvinceDocument
from multiprocessing import Queue, Process
from queue import Empty
from subprocess import Popen, PIPE, STDOUT, call
import os, sane

UI_FILE = "src/pdf_attachment.ui"

class Dialog :
	device = None
	def __init__ (self, parent_window):
		
		self.parent_window = parent_window
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		dialog = self.builder.get_object("scan_dialog")
		dialog.set_transient_for(parent_window)

		self.data_queue = Queue()
		self.scanner_store = self.builder.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GObject.timeout_add(100, self.populate_scanners)
		
		EvinceDocument.init()
		self.view = EvinceView.View()
		self.builder.get_object('pdf_view_scrolled_window').add(self.view)

		self.dialog = self.builder.get_object('scan_dialog')

	def populate_scanners(self):
		try:
			devices = self.data_queue.get_nowait()
			for scanner in devices:
				device_id = scanner[0]
				device_manufacturer = scanner[1]
				name = scanner[2]
				given_name = scanner[3]
				self.scanner_store.append([str(device_id), device_manufacturer,
											name, given_name])
		except Empty:
			return True
		
	def get_scanners(self):
		sane.init()
		devices = sane.get_devices()
		self.data_queue.put(devices)

	def view_file (self):
		self.model = EvinceView.DocumentModel()
		doc = EvinceDocument.Document.factory_get_document("file:///tmp/opt.pdf")
		self.model.set_document(doc)
		self.view.set_model(self.model)
		self.builder.get_object('button8').set_sensitive (True)
		self.builder.get_object('stack1').set_visible_child_name('view_page')
		self.dialog.show_all()
		self.parent_window.present()

	def get_pdf (self):
		return self.pdf_data
	
	def run (self):
		result = self.dialog.run()
		self.pdf_data = None
		if result == Gtk.ResponseType.ACCEPT:
			self.load_file_from_disk()
		self.dialog.hide()
		if self.device:
			self.device.close()
		return result

	def scanner_combo_changed (self, combo):
		if self.device:
			self.device.close()
		self.device = sane.open(combo.get_active_id())
		self.builder.get_object('scan_button').set_sensitive (True)

	def filechooser_file_set (self, chooser):
		if os.path.exists("/tmp/opt.pdf"):
			os.remove("/tmp/opt.pdf")
		self.spinner = self.builder.get_object('spinner1')
		self.spinner.start()
		self.spinner.set_visible(True)
		self.result_buffer = self.builder.get_object('pdf_opt_result_buffer')
		self.result_buffer.set_text('', -1)
		self.sw = self.builder.get_object('scrolledwindow3')
		self.file_name = chooser.get_filename()
		p = Popen(['./src/pdf_opt/pdfsizeopt', self.file_name, '/tmp/opt.pdf'], 
														stdout = PIPE,
														stderr = STDOUT,
														stdin = PIPE)
		self.io_id = GObject.io_add_watch(p.stdout, GObject.IO_IN, self.optimizer_thread)
		GObject.io_add_watch(p.stdout, GObject.IO_HUP, self.thread_finished)

	def thread_finished (self, stdout, condition):
		GObject.source_remove(self.io_id)
		stdout.close()
		button = self.builder.get_object('button8')
		self.spinner.stop()
		self.spinner.set_visible(False)
		label = self.builder.get_object('label20')
		if os.path.exists("/tmp/opt.pdf"):
			label.set_visible(False)
			button.set_label("Attach")
		else:
			label.set_visible(True)
			label.show()
			button.set_label("Attach without optimization")
			call(["cp", self.file_name, "/tmp/opt.pdf"])
		self.view_file ()

	def optimizer_thread (self, stdout, condition):
		line = stdout.readline()
		line = line.decode(encoding="utf-8", errors="strict")
		adj = self.sw.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())
		iter_ = self.result_buffer.get_end_iter()
		self.result_buffer.insert(iter_, line, -1)
		return True

	def scan_clicked (self, button):
		if os.path.exists("/tmp/opt.pdf"):
			os.remove("/tmp/opt.pdf")
		document = self.device.scan()
		document.save("/tmp/opt.pdf")
		self.view_file ()

	def load_file_from_disk (self):
		with open("/tmp/opt.pdf",'rb') as f:
			self.pdf_data = f.read ()

	


		
