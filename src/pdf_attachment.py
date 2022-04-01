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
gi.require_version('Vte', '2.91')
gi.require_version('EvinceView', '3.0')
from gi.repository import Gtk, GLib, GObject, Gdk
from gi.repository import Vte, EvinceView, EvinceDocument
from multiprocessing import Queue, Process
from queue import Empty
from subprocess import call
import os, sane

UI_FILE = "src/pdf_attachment.ui"

def sizeof_file(num, suffix='B'):
	"https://stackoverflow.com/questions/1094841/"
	for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
		if abs(num) < 1024.0:
			return "%3.1f %s%s" % (num, unit, suffix)
		num /= 1024.0
	return "%.1f %s%s" % (num, 'Yi', suffix)

class PdfAttachmentWindow (Gtk.Builder):
	device = None
	__gsignals__ = { 
	'pdf_optimized': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ())
	}
	"""the pdf_optimized signal is used to send a message to the parent 
		window that the pdf is now optimized"""
	def __init__ (self, parent_window):
		
		self.parent_window = parent_window
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		
		self.terminal = Vte.Terminal()
		self.terminal.show()
		self.terminal.set_scroll_on_output(True)
		self.terminal.connect("child-exited", self.terminal_child_exited)
		self.get_object('scrolledwindow3').add(self.terminal)

		self.data_queue = Queue()
		self.scanner_store = self.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		
		GLib.timeout_add(100, self.populate_scanners)
		style_provider = Gtk.CssProvider()
		css_data = b'''
		#red-background {
		background-color: #FF2A2A;
		}
		'''
		style_provider.load_from_data(css_data)
		Gtk.StyleContext.add_provider_for_screen(
							Gdk.Screen.get_default(), 
							style_provider,
							Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
		
		EvinceDocument.init()
		self.view = EvinceView.View()
		self.get_object('pdf_view_scrolled_window').add(self.view)
		
		self.window = self.get_object("window")
		self.window.set_transient_for(parent_window)
		self.window.show_all()

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
		v_adjust = self.get_object('v_adjustment').get_value()
		try:
			f = "file://" + self.file
			doc = EvinceDocument.Document.factory_get_document(f)
			self.get_object('button8').set_sensitive (True)
			self.get_object('notify_revealer').set_reveal_child(False)
		except Exception as e: # show in app error notify bar
			print (e)
			self.get_object('error_label').set_text(str(e))
			self.get_object('notify_revealer').set_reveal_child(True)
			self.get_object('button8').set_sensitive (False)
			return
		# create model to load the pdf from after validating the pdf
		self.model = EvinceView.DocumentModel()
		self.model.set_document(doc)
		self.view.set_model(self.model)
		GLib.idle_add(self.get_object('v_adjustment').set_value, v_adjust)

	def get_pdf (self):
		with open (self.file, 'rb') as f:
			pdf_data = f.read()
		return pdf_data
	
	def destroy (self, window):
		if self.device:
			self.device.close()

	def cancel_clicked (self, button):
		self.window.destroy ()

	def attach_clicked (self, button):
		self.emit("pdf_optimized")
		self.window.destroy ()

	def original_file_clicked (self, button):
		if not button.get_active():
			return
		self.file = '/tmp/original.pdf'
		self.view_file ()

	def optimized_file_clicked (self, button):
		if not button.get_active():
			return
		self.file = '/tmp/optimized.pdf'
		self.view_file ()
	
	def notify_close_button_clicked (self, button):
		self.get_object('notify_revealer').set_reveal_child(False)

	def scanner_combo_changed (self, combo):
		if self.device:
			self.device.close()
		self.device = sane.open(combo.get_active_id())
		self.get_object('scan_button').set_sensitive (True)

	def filechooser_file_set (self, chooser):
		file_name = chooser.get_filename()
		if os.path.exists('/tmp/original.pdf'):
			os.remove('/tmp/original.pdf')
		call(["cp", file_name, '/tmp/original.pdf'])
		self.optimize_file()

	def optimize_file (self):
		if os.path.exists('/tmp/optimized.pdf'):
			os.remove('/tmp/optimized.pdf')
		self.terminal.reset(True, True)
		self.spinner = self.get_object('spinner1')
		self.spinner.start()
		self.spinner.set_visible(True)
		commands = ['gs',
					'-sDEVICE=pdfwrite',
					'-dCompatibilityLevel=1.4',
					'-dPDFSETTINGS=/screen',
					'-dNOPAUSE',
					'-dBATCH',
					'-sOutputFile=/tmp/optimized.pdf',
					'/tmp/original.pdf']
		self.terminal.spawn_sync(   Vte.PtyFlags.DEFAULT,
									'/usr/bin',
									commands,
									[],
									GLib.SpawnFlags.DO_NOT_REAP_CHILD,
									None,
									None,
									)

	def terminal_child_exited (self, terminal, error):
		self.spinner.stop()
		self.spinner.set_visible(False)
		orig_size = os.path.getsize('/tmp/original.pdf')
		new_size = os.path.getsize('/tmp/optimized.pdf')
		label = self.get_object('label20')
		if error > 0: # optimizing failed, may not be fatal, so we continue
			self.file = '/tmp/original.pdf'
			label.set_visible(True)
			label.show()
			self.get_object('optimized_file_radiobutton').set_sensitive(False)
			self.get_object('original_file_radiobutton').set_active(True)
		else: # optimizing is fine, decide which file is smaller
			self.get_object('optimized_file_radiobutton').set_sensitive(True)
			label.set_visible(False)
			if orig_size > new_size:
				self.file = '/tmp/optimized.pdf'
				self.get_object('optimized_file_radiobutton').set_active(True)
			else:
				self.file = '/tmp/original.pdf'
				self.get_object('original_file_radiobutton').set_active(True)
		self.get_object('label_before').set_text(sizeof_file(orig_size))
		self.get_object('label_after').set_text(sizeof_file(new_size))
		self.get_object('stack_switcher').set_sensitive (True)
		self.get_object('stack1').set_visible_child_name('page1')
		self.view_file ()
		self.parent_window.present()

	def scan_clicked (self, button):
		document = self.device.scan()
		document.save('/tmp/original.pdf')
		self.optimize_file ()




