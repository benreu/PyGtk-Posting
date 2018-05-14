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

from gi.repository import Gtk, GObject
from multiprocessing import Queue, Process
from queue import Empty
from subprocess import Popen, PIPE, STDOUT, call
import os, sane

UI_FILE = "src/pdf_attachment.ui"

class Dialog :
	def __init__ (self, parent_window):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		dialog = self.builder.get_object("scan_dialog")
		dialog.set_transient_for(parent_window)
		dialog.set_keep_above(True)

		self.data_queue = Queue()
		self.scanner_store = self.builder.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GObject.timeout_add(100, self.populate_scanners)

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

	def get_pdf (self):
		return self.pdf_data
	
	def run (self):
		dialog = self.builder.get_object('scan_dialog')
		result = dialog.run()
		self.pdf_data = None
		if result == Gtk.ResponseType.ACCEPT:
			if self.attach_origin == 1:
				self.scan_file()
			elif self.attach_origin == 2:
				self.attach_file_from_disk()
			elif self.attach_origin == 3:
				call(["cp", self.file_name, "/tmp/opt.pdf"])
				self.attach_file_from_disk()
		dialog.hide()
		return result

	def scanner_combo_changed (self, combo):
		self.builder.get_object('filechooserbutton1').set_sensitive (False)
		self.attach_origin = 1
		self.builder.get_object('button8').set_sensitive (True)

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
		button.set_sensitive (True)
		self.spinner.stop()
		self.spinner.set_visible(False)
		label = self.builder.get_object('label20')
		if os.path.exists("/tmp/opt.pdf"):
			self.builder.get_object('combobox2').set_sensitive (False)
			self.attach_origin = 2
			label.set_visible(False)
			button.set_label("Attach")
		else:
			label.set_visible(True)
			label.show()
			button.set_label("Attach without optimization")
			self.attach_origin = 3

	def optimizer_thread (self, stdout, condition):
		line = stdout.readline()
		line = line.decode(encoding="utf-8", errors="strict")
		adj = self.sw.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())
		iter_ = self.result_buffer.get_end_iter()
		self.result_buffer.insert(iter_, line, -1)
		return True

	def scan_file (self):
		device_address = self.builder.get_object("combobox2").get_active_id()
		device = sane.open(device_address)
		document = device.scan()
		document.save("/tmp/opt.pdf")
		self.attach_file_from_disk ()

	def attach_file_from_disk (self):
		f = open("/tmp/opt.pdf",'rb')
		self.pdf_data = f.read ()
		f.close()




		