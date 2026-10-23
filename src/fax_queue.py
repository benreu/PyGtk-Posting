# fax_queue.py
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

'''Faxes printed from any program.

Brother's filter dials only a number that arrives as the job's fax-number=
option, and no print dialog sends one, so a job printed to BRFAX completes
with nothing dialed. With the queue set to hold every job

	sudo lpadmin -p BRFAX -o job-hold-until-default=indefinite

a printed job waits on this computer instead. While Posting is open this
finds it, fetches its document and adds it to one Send fax window, and every
job printed after it is added to the same window, so pages from several
prints go as one fax once a number is entered and Send is pressed. The window
sends them as a new job carrying the number (faxing.send asks for it not to
be held) and cancels the held originals.

Jobs printed while Posting is closed wait in the queue and are picked up the
next time it opens.'''

from gi.repository import Gtk, GLib
import cups
import os, subprocess, tempfile, traceback
import faxing

POLL_SECONDS = 2
HELD = 4 # IPP job-state pending-held
# cupsfilter will not run without a PPD, and the stock one it falls back to is
# not installed. Brother's fax PPD is readable by anyone and only supplies the
# page sizes; /etc/cups/ppd/BRFAX.ppd is root's
PPD = "/opt/brother/fax/brmfcfax/cupswrapper/brfax_cups.ppd"


HOLD_COMMAND = ("sudo lpadmin -p %s -o job-hold-until-default=indefinite"
				% faxing.FAX_QUEUE)


def queue_holds_jobs ():
	'''whether the fax queue holds what is printed to it, which faxing from
	other programs needs. True when that cannot be found out - no scheduler,
	no queue - so nobody is told to run a command for a fax that is not there'''
	try:
		attrs = cups.Connection().getPrinterAttributes(faxing.FAX_QUEUE,
							requested_attributes = ['job-hold-until-default'])
	except Exception:
		return True
	return attrs.get('job-hold-until-default') == 'indefinite'

def held_jobs (conn):
	"{job id: printer uri} for this user's jobs held on the fax queue"
	jobs = conn.getJobs(which_jobs = 'not-completed', my_jobs = True,
						requested_attributes = ['job-id', 'job-state',
												'job-printer-uri'])
	return {job_id: attrs['job-printer-uri']
			for job_id, attrs in jobs.items()
			if attrs.get('job-state') == HELD and
			attrs.get('job-printer-uri', '').endswith('/' + faxing.FAX_QUEUE)}

def page_ranges (value):
	'''pycups gives one range as (2, 2) and several as [(1, 1), (3, 3)]; the
	converter wants 2-2 and 1-1,3-3'''
	if not value:
		return ''
	if isinstance(value, tuple):
		value = [value]
	return ','.join('%d-%d' % pair for pair in value)

def fetch_pdf (conn, job_id, printer_uri, directory):
	'''The held job's documents as one Letter pdf in directory, returning
	(path, title). A program may send the whole file and leave page-ranges for
	CUPS to apply - lp -P does - and the document fetched is that whole file,
	so the job's page choices are applied here with the filters CUPS itself
	would use. Not number-up: the converter drops pages laying them out two to
	a sheet, so such a job is faxed a page to a sheet instead.'''
	attrs = conn.getJobAttributes(job_id)
	# CUPS keeps job-name private, even from the owner asking here; the
	# name of the file printed is not
	title = (attrs.get('job-name') or attrs.get('document-name-supplied')
				or "Print job %s" % job_id)
	options = ['-o', 'PageSize=Letter']
	ranges = page_ranges(attrs.get('page-ranges'))
	if ranges:
		options += ['-o', 'page-ranges=' + ranges]
	if attrs.get('page-set') in ('odd', 'even'):
		options += ['-o', 'page-set=' + attrs['page-set']]
	parts = []
	for number in range(1, (attrs.get('number-of-documents') or 1) + 1):
		document = conn.getDocument(printer_uri, job_id, number)
		part = os.path.join(directory, "%s_%s.pdf" % (job_id, number))
		try:
			with open(part, 'wb') as out:
				result = subprocess.run(["cupsfilter", "-p", PPD,
										"-i", document['document-format'],
										"-m", "application/vnd.cups-pdf"]
										+ options + [document['file']],
										stdout = out, stderr = subprocess.PIPE,
										text = True, timeout = 120)
		finally:
			os.remove(document['file'])
		if result.returncode != 0:
			errors = [line for line in result.stderr.splitlines()
						if line.startswith('ERROR')]
			raise faxing.FaxError("The %s document could not be converted:\n%s"
									% (document['document-format'],
									'\n'.join(errors[-3:])))
		parts.append(part)
	path = os.path.join(directory, "%s.pdf" % job_id)
	if len(parts) == 1:
		os.rename(parts[0], path)
	else:
		result = subprocess.run(["pdfunite"] + parts + [path],
								capture_output = True, text = True)
		for part in parts:
			os.remove(part)
		if result.returncode != 0:
			raise faxing.FaxError(result.stderr.strip())
	return path, title


class Watcher:
	'''Finds jobs held on the fax queue and adds each, once, to the Send fax
	window it keeps open for them'''

	def __init__ (self):
		self.seen = set() # added or reported already, never handled twice
		self.gui = None # the Send fax window collecting the jobs
		self.directory = tempfile.mkdtemp(prefix = "posting_fax_jobs_")

	def start (self):
		GLib.timeout_add_seconds(POLL_SECONDS, self.poll)

	def poll (self):
		try:
			conn = cups.Connection()
			jobs = held_jobs(conn)
		except Exception: # the scheduler is restarting or down: next time
			return True
		if self.gui is not None:
			# canceled from the print queue: it is not to be faxed either
			self.gui.drop_held_jobs(set(self.gui.held_job_ids()) - set(jobs))
		for job_id in sorted(jobs):
			if job_id not in self.seen:
				self.seen.add(job_id)
				try:
					self.add_job(conn, job_id, jobs[job_id])
				except Exception:
					# raised out of a timeout callback it would remove the
					# timeout, and every later print would go uncollected
					traceback.print_exc()
		return True

	def add_job (self, conn, job_id, printer_uri):
		try:
			path, title = fetch_pdf(conn, job_id, printer_uri, self.directory)
			pages = faxing.page_count(path)
		except Exception as e:
			traceback.print_exc()
			faxing.show_message(self.gui.window if self.gui else None,
								Gtk.MessageType.ERROR,
								"Print job %s-%s, printed to the fax, could not "
								"be read:\n%s\n\nIt is still waiting in the "
								"print queue; cancel it there."
								% (faxing.FAX_QUEUE, job_id, e))
			return
		self.window().add_held_job(job_id, path, title, pages)

	def window (self):
		if self.gui is None:
			import fax_window
			self.gui = fax_window.FaxGUI()
			self.gui.window.connect('destroy', self.window_destroyed)
		return self.gui

	def window_destroyed (self, window):
		self.gui = None
