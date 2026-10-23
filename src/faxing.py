# faxing.py
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

'''Faxing through the Brother MFC's PC-FAX queue.

Brother's CUPS filter never asks for a number. It reads one from the job's
fax-number= option, and a job without one - which is what every print dialog
sends - completes in CUPS with nothing dialed. So no fax goes through
Gtk.PrintOperation: each one is an lp job that carries its own number, the way
Brother's own brpcfax command sends them.

A completed job only means the fax machine took the pages into its memory.
Busy lines, redials and failed calls are known to the machine alone, on its
transmission report, so nothing here can say that a fax arrived.'''

import gi
gi.require_version('Poppler', '0.18')
from gi.repository import Gtk, GLib, Poppler
import re, subprocess, traceback

FAX_QUEUE = "BRFAX"
# the driver's own number check passes digits and commas (a comma is a pause)
# and nothing else, and its PPD allows 32 characters
NUMBER = re.compile(r'^[0-9][0-9,]{0,31}$')


class FaxError (Exception):
	pass


def dialable (text):
	'''The number to dial for what a fax column holds, or '' when it does not
	hold exactly one North American number. The column is free text ("585 554
	6779", "Toms#315 694 0123", "1 336 697 3100") and the filter cuts a number
	at its first space, so "585 554 6779" sent as typed would dial 585.'''
	digits = re.sub(r'[^0-9]', '', text or '')
	if len(digits) == 10:
		return '1' + digits
	if len(digits) == 11 and digits.startswith('1'):
		return digits
	return ''

def valid_number (number):
	return NUMBER.match(number) is not None

def display (number):
	"13155551234 as 1 (315) 555-1234, for people to read; anything else as is"
	if len(number) == 11 and number.isdigit():
		return "1 (%s) %s-%s" % (number[1:4], number[4:7], number[7:])
	return number

def queue_available ():
	try:
		result = subprocess.run(["lpstat", "-e"], capture_output = True,
								text = True, timeout = 10)
	except (OSError, subprocess.SubprocessError):
		return False
	return FAX_QUEUE in result.stdout.split()

def page_count (pdf_path):
	document = Poppler.Document.new_from_file(GLib.filename_to_uri(pdf_path))
	return document.get_n_pages()

def send (pdf_path, number, title):
	'''Queue pdf_path to be faxed to number and return the CUPS job id. lp has
	read the file by the time it returns, so the caller may delete it.'''
	if not valid_number(number):
		raise FaxError("%s is not a number the fax driver can dial" % number)
	# the title travels through Brother's shell scripts unquoted in places
	title = re.sub(r'[^A-Za-z0-9_.-]+', '_', title)
	try:
		# no-hold: the queue holds every job that arrives without a number so
		# that fax_queue can ask for one, and this one already has it
		result = subprocess.run(["lp", "-d", FAX_QUEUE, "-t", title,
								"-o", "fax-number=" + number,
								"-o", "Quality=FINE",
								"-o", "PageSize=Letter",
								"-o", "job-hold-until=no-hold",
								pdf_path],
								capture_output = True, text = True, timeout = 60)
	except (OSError, subprocess.SubprocessError) as e:
		raise FaxError(str(e))
	if result.returncode != 0:
		raise FaxError(result.stderr.strip() or result.stdout.strip())
	match = re.search(r'request id is (\S+)', result.stdout)
	return match.group(1) if match else ''

def cancel_jobs (job_ids):
	'''Cancel held print jobs whose pages have been faxed or discarded. One
	already gone - canceled from the print queue, say - is not an error, and
	nothing here may raise: it runs after a fax has been sent, and a failure
	must not leave the window looking unsent.'''
	if not job_ids:
		return
	try:
		import cups
		conn = cups.Connection()
	except Exception:
		traceback.print_exc()
		return
	for job_id in job_ids:
		try:
			conn.cancelJob(job_id)
		except Exception:
			traceback.print_exc()

def missing_queue_message ():
	return ("There is no fax queue named %s on this computer.\n\n"
			"Install Brother's fax driver (brmfcfaxdrv) and add a queue "
			"named %s for the fax machine, or share the queue from a "
			"computer that has one." % (FAX_QUEUE, FAX_QUEUE))

def queued_message (job, number):
	return ("Queued on the fax machine as %s, to %s.\n\n"
			"Posting only knows the fax machine took it. The machine's "
			"transmission report says whether the fax went through."
			% (job, display(number)))

def show_message (parent, message_type, text):
	dialog = Gtk.MessageDialog(message_type = message_type,
								buttons = Gtk.ButtonsType.CLOSE)
	dialog.set_transient_for(parent)
	dialog.set_markup(GLib.markup_escape_text(text))
	dialog.run()
	dialog.destroy()


DONT_FAX = 1 # the response of FaxDialog's "Don't fax" button


class FaxDialog (Gtk.Dialog):
	'''Asks before anything is dialed: who it goes to, the number as it is on
	file, and the number that will be dialed, which can be corrected here.

	number is what to offer instead of the stored number, for a number already
	chosen; can_stop adds a "Don't fax" button for taking that choice back.
	pdf_path is left out when the document does not exist yet, which drops the
	page count.'''

	def __init__ (self, parent, contact_name, stored_number, pdf_path = None,
					number = None, send_label = "Send fax", can_stop = False):
		Gtk.Dialog.__init__(self, title = "Send fax", transient_for = parent,
							modal = True)
		if can_stop:
			self.add_button("Don't fax", DONT_FAX)
		self.add_button("Cancel", Gtk.ResponseType.CANCEL)
		self.send_button = self.add_button(send_label, Gtk.ResponseType.OK)
		self.set_default_response(Gtk.ResponseType.OK)

		grid = Gtk.Grid(row_spacing = 6, column_spacing = 12, border_width = 10)
		self.get_content_area().pack_start(grid, True, True, 0)
		self.number_entry = Gtk.Entry(activates_default = True)
		self.number_entry.connect('changed', self.number_changed)
		self.number_entry.set_text(number if number is not None
										else dialable(stored_number))
		rows = [("To", Gtk.Label(label = contact_name or '')),
				("On file", Gtk.Label(label = stored_number or '(no fax number)')),
				("Dial", self.number_entry)]
		if pdf_path is not None:
			rows.append(("Pages", Gtk.Label(label = str(page_count(pdf_path)))))
		for row, (caption, widget) in enumerate(rows):
			grid.attach(Gtk.Label(label = caption, xalign = 1), 0, row, 1, 1)
			widget.set_halign(Gtk.Align.FILL if widget is self.number_entry
												else Gtk.Align.START)
			grid.attach(widget, 1, row, 1, 1)
		note = Gtk.Label(label = "Digits and commas only; a comma is a pause.\n"
								"Long distance numbers start with 1.",
						xalign = 0)
		note.get_style_context().add_class('dim-label')
		grid.attach(note, 0, len(rows), 2, 1)
		self.number_changed(self.number_entry)

	def number_changed (self, entry):
		self.send_button.set_sensitive(valid_number(entry.get_text()))

	def get_number (self):
		'''the number to dial, '' for "Don't fax", or None when the user
		canceled'''
		self.show_all()
		response = self.run()
		number = self.number_entry.get_text()
		self.destroy()
		if response == DONT_FAX:
			return ''
		return number if response == Gtk.ResponseType.OK else None


def send_and_report (parent, pdf_path, number, title):
	'''queue an already confirmed number and say how it went. Returns the job
	id, or None if nothing was sent'''
	try:
		job = send(pdf_path, number, title)
	except FaxError as e:
		show_message(parent, Gtk.MessageType.ERROR,
						"The fax was not sent:\n%s" % e)
		return None
	show_message(parent, Gtk.MessageType.INFO, queued_message(job, number))
	return job

def fax_pdf (parent, pdf_path, title, contact_name = '', stored_number = ''):
	'''One document from start to finish: check for the queue, confirm the
	number, queue it and say so. Returns the job id, or None if nothing was
	sent.'''
	if not queue_available():
		show_message(parent, Gtk.MessageType.ERROR, missing_queue_message())
		return None
	number = FaxDialog(parent, contact_name, stored_number,
						pdf_path).get_number()
	if not number:
		return None
	return send_and_report(parent, pdf_path, number, title)
