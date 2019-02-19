# export_to_pdf.py
#
# Copyright (C) 2019 - house
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
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, GLib, Gio
from gi.repository import EvinceView, EvinceDocument, PangoCairo, Pango
import cairo
import main

UI_FILE = main.ui_directory + "/reports/export_to_pdf.ui"

class ExportToPdfGUI(Gtk.Builder):
	landscape = False
	def __init__ (self, treeview):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.treeview = treeview
		self.store = treeview.get_model()
		
		EvinceDocument.init()
		self.view = EvinceView.View()
		self.get_object('pdf_view_scrolled_window').add(self.view)
		self.window = self.get_object('window')
		self.window.show_all()
		self.generate_pdf ()

	def delete_event (self, window, event):
		window.hide()
		return True

	def generate_pdf(self):
		if type(self.store) is type(Gtk.TreeStore()):
			self.create_from_treestore()
		elif type(self.store) is type(Gtk.ListStore()):
			self.create_from_liststore()
		else: # should not be reached
			raise Exception("Invalid treestore model!")
		self.window.present()
			
	def create_from_treestore (self):
		for i in self.store:
			print (self.treeview.row_expanded(i.path))
			
	def create_from_liststore (self):
		border = 25
		columns = list()
		for column in self.treeview.get_columns():
			if column.get_visible():
				specs = list()
				cell_area = column.get_area()
				renderer = cell_area.get_cells()[0]
				specs.append(cell_area.attribute_get_column(renderer, "text"))
				specs.append(renderer.get_property("ellipsize"))
				xalign = renderer.get_property("xalign")
				if xalign == 1.0:
					xalign = Pango.Alignment.RIGHT
				else:
					xalign = Pango.Alignment.LEFT
				specs.append(xalign)
				specs.append(column.get_width())
				columns.append(specs)
		pdf_width = self.treeview.get_allocated_width() + (border * 2)
		if pdf_width > 792: # greater than 11 inches
			pdf_height = 612 * (float(pdf_width) / 792) 
			# scale pdf height according to width oversize
			self.landscape = True
		elif pdf_width > 612: # greater than 8.5 inches
			pdf_width = 792
			pdf_height = 612
			self.landscape = True
		else: # less than 8.5 inches
			pdf_width = 612
			pdf_height = 792
		rectangle = self.treeview.get_cell_area(0, None)
		surface = cairo.PDFSurface("/tmp/pdf_export.pdf", pdf_width, pdf_height)
		cr = cairo.Context(surface)
		cr.set_source_rgb(0, 0, 0)
		cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
									cairo.FONT_WEIGHT_NORMAL)
		cr.set_font_size(11)
		y = border
		for index, row in enumerate(self.store):
			x = border
			for specs in columns:
				layout = PangoCairo.create_layout(cr)
				desc = Pango.font_description_from_string("Sans 9")
				layout.set_font_description(desc)
				text = str(row[specs[0]])
				length = len(text)
				layout.set_text(text, length)
				layout.set_ellipsize(specs[1])
				layout.set_alignment(specs[2])
				layout.set_width(specs[3] * Pango.SCALE)
				layout.set_height(-1)
				cr.move_to(x, y)
				PangoCairo.show_layout(cr, layout)
				x += specs[3] + 10
			y += rectangle.height 
			if (y + border) > pdf_height:
				cr.show_page()
				y = border
		surface.finish()
		with open("/tmp/pdf_export.pdf",'rb') as f:
			self.bytes = f.read()
		GLib.idle_add(self.load_pdf)

	def print_pdf_clicked (self, button):
		import printing
		print_op = printing.Setup()
		pdf_data = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes(self.bytes))
		print_op.set_print_bytes(pdf_data)
		if self.landscape:
			setup = Gtk.PageSetup()
			setup.set_orientation(Gtk.PageOrientation.LANDSCAPE)
			print_op.set_default_page_setup(setup)
		print_op.print_dialog(self.window)

	def save_pdf_clicked (self, button):
		file_dialog = self.get_object("file_dialog")
		response = file_dialog.run()
		file_dialog.hide()
		if response == Gtk.ResponseType.ACCEPT:
			filename = file_dialog.get_filename()
			if not filename.endswith('.pdf'):
				filename = filename + ".pdf"
			with open(filename,'wb') as f:
				f.write (self.bytes)

	def load_pdf (self):
		self.model = EvinceView.DocumentModel()
		doc = EvinceDocument.Document.factory_get_document("file:///tmp/pdf_export.pdf")
		self.model.set_document(doc)
		self.view.set_model(self.model)

