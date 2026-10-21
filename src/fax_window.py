# fax_window.py
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

from gi.repository import Gtk, GLib
from datetime import date
import os, shutil, subprocess, tempfile
from db_connection import DB
from constants import ui_directory, template_dir
import faxing

UI_FILE = ui_directory + "/fax_window.ui"


class Item(object):
	pass


class FaxGUI (Gtk.Builder):
	'''Faxes any PDFs, behind an optional cover sheet, to a contact or to a
	number typed in. Everything goes as one pdf in one job, so the fax machine
	dials once and the pages arrive together.'''

	def __init__(self):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.contact_store = self.get_object('contact_store')
		self.document_store = self.get_object('document_store')
		completion = self.get_object('contact_completion')
		completion.set_match_func(self.contact_match_func)
		self.populate_contact_store()
		self.window = self.get_object('window')
		self.window.show_all()
		self.update_pages()

	def populate_contact_store (self):
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, fax FROM contacts "
						"WHERE deleted = False AND fax <> '' ORDER BY name")
		for row in cursor.fetchall():
			self.contact_store.append(row)
		cursor.close()
		DB.rollback()

	def contact_match_func (self, completion, key, iter_):
		for text in key.split():
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def contact_match_selected (self, completion, model, iter_):
		self.get_object('contact_combo').set_active_id(model[iter_][0])

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		if contact_id is None:
			return # typed into the entry, not chosen
		for row in self.contact_store:
			if row[0] == contact_id:
				self.get_object('attention_entry').set_text(row[1])
				self.get_object('number_entry').set_text(faxing.dialable(row[2]))
				self.get_object('on_file_label').set_label("On file: %s" % row[2])
				break

	def number_entry_changed (self, entry):
		self.update_buttons()

	def add_clicked (self, button):
		dialog = Gtk.FileChooserDialog(title = "Choose documents to fax",
										action = Gtk.FileChooserAction.OPEN)
		dialog.set_transient_for(self.window)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
		dialog.set_select_multiple(True)
		pdf_filter = Gtk.FileFilter()
		pdf_filter.set_name("PDF documents")
		pdf_filter.add_mime_type("application/pdf")
		pdf_filter.add_pattern("*.pdf")
		dialog.add_filter(pdf_filter)
		result = dialog.run()
		paths = dialog.get_filenames()
		dialog.destroy()
		if result != Gtk.ResponseType.ACCEPT:
			return
		for path in paths:
			try:
				pages = faxing.page_count(path)
			except GLib.Error as e:
				faxing.show_message(self.window, Gtk.MessageType.ERROR,
									"%s could not be read as a PDF:\n%s" %
									(os.path.basename(path), e.message))
				continue
			self.document_store.append([path, os.path.basename(path), pages])
		self.update_pages()

	def remove_clicked (self, button):
		model, tree_iter = self.get_object('document_selection').get_selected()
		if tree_iter is not None:
			model.remove(tree_iter)
			self.update_pages()

	def cover_toggled (self, check_button):
		self.get_object('cover_grid').set_sensitive(check_button.get_active())
		self.update_pages()

	def document_pages (self):
		return sum(row[2] for row in self.document_store)

	def update_pages (self):
		pages = self.document_pages()
		if self.get_object('cover_check').get_active():
			text = "%s pages of documents, and the cover sheet" % pages
		else:
			text = "%s pages" % pages
		self.get_object('pages_label').set_label(text)
		self.update_buttons()

	def has_pages (self):
		return (self.document_pages() > 0 or
				self.get_object('cover_check').get_active())

	def update_buttons (self):
		number = self.get_object('number_entry').get_text()
		self.get_object('preview_button').set_sensitive(self.has_pages())
		self.get_object('send_button').set_sensitive(self.has_pages() and
											faxing.valid_number(number))

	def render_cover (self, directory):
		cursor = DB.cursor()
		company = Item()
		cursor.execute("SELECT name, street, city, state, zip, phone, fax, "
						"email FROM company_info")
		for row in cursor.fetchall():
			(company.name, company.street, company.city, company.state,
				company.zip, company.phone, company.fax, company.email) = row
		# today here, not the server's CURRENT_DATE, which runs on UTC
		cursor.execute("SELECT format_date(%s)", (date.today(),))
		fax = Item()
		fax.date = cursor.fetchone()[0]
		cursor.close()
		DB.rollback()  # before the render: WeasyPrint must not hold a snapshot open

		fax.attention = self.get_object('attention_entry').get_text()
		fax.number = faxing.display(self.get_object('number_entry').get_text())
		fax.subject = self.get_object('subject_entry').get_text()
		note_buffer = self.get_object('note_textview').get_buffer()
		fax.note = note_buffer.get_text(note_buffer.get_start_iter(),
										note_buffer.get_end_iter(), False)

		from jinja2 import Environment, FileSystemLoader
		import weasyprint

		env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
		template = env.get_template('fax_cover.html')
		# a long note can push the sheet onto a second page, which changes
		# the page count printed on it, so render until the two agree
		cover_pages = 1
		for attempt in range(3):
			fax.pages = self.document_pages() + cover_pages
			document = weasyprint.HTML(string=template.render(
										fax=fax, company=company)).render()
			if len(document.pages) == cover_pages:
				break
			cover_pages = len(document.pages)
		path = os.path.join(directory, "cover.pdf")
		document.write_pdf(path)
		return path

	def build_pdf (self, directory):
		'''The cover sheet and every document as one pdf in directory, so the
		machine dials once'''
		paths = [row[0] for row in self.document_store]
		if self.get_object('cover_check').get_active():
			paths.insert(0, self.render_cover(directory))
		fax_pdf = os.path.join(directory, "fax.pdf")
		if len(paths) == 1:
			shutil.copyfile(paths[0], fax_pdf)
			return fax_pdf
		try:
			subprocess.run(["pdfunite"] + paths + [fax_pdf], check = True,
							capture_output = True, text = True)
		except subprocess.CalledProcessError as e:
			raise faxing.FaxError("The documents could not be put together:\n%s"
									% e.stderr.strip())
		except OSError as e:
			raise faxing.FaxError("pdfunite (poppler-utils) is needed to put "
									"the documents together:\n%s" % e)
		return fax_pdf

	def preview_clicked (self, button):
		# left in /tmp like every other preview, so the viewer can keep it open
		directory = tempfile.mkdtemp(prefix = "posting_fax_")
		try:
			path = self.build_pdf(directory)
		except (faxing.FaxError, OSError) as e:
			faxing.show_message(self.window, Gtk.MessageType.ERROR, str(e))
			return
		subprocess.Popen(["xdg-open", path])

	def send_clicked (self, button):
		if not faxing.queue_available():
			faxing.show_message(self.window, Gtk.MessageType.ERROR,
								faxing.missing_queue_message())
			return
		number = self.get_object('number_entry').get_text()
		attention = self.get_object('attention_entry').get_text()
		directory = tempfile.mkdtemp(prefix = "posting_fax_")
		try:
			job = faxing.send(self.build_pdf(directory), number,
								"Fax_" + (attention or number))
		except (faxing.FaxError, OSError) as e:
			faxing.show_message(self.window, Gtk.MessageType.ERROR,
								"The fax was not sent:\n%s" % e)
			return
		finally:
			shutil.rmtree(directory, ignore_errors = True)
		self.get_object('status_label').set_label("%s  %s" %
						(GLib.DateTime.new_now_local().format("%-I:%M %p"),
						faxing.queued_message(job, number)))
		self.clear()

	def clear (self):
		'''ready for the next fax, and no second press of Send can repeat this
		one: with no number Send is insensitive'''
		self.document_store.clear()
		self.get_object('contact_combo_entry').set_text('')
		for entry in ('attention_entry', 'number_entry', 'subject_entry'):
			self.get_object(entry).set_text('')
		self.get_object('on_file_label').set_label('')
		self.get_object('note_textview').get_buffer().set_text('')
		self.update_pages()

	def close_clicked (self, button):
		self.window.destroy()
