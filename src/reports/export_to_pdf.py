# export_to_pdf.py
#
# Copyright (C) 2019 - Reuben Rissler
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
import constants

UI_FILE = constants.ui_directory + "/reports/export_to_pdf.ui"

class ExportToPdfGUI(Gtk.Builder):
	landscape = False
	border_width = 25
	font_desc = "Sans 6"
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

	def delete_event (self, window, event):
		window.hide()
		return True

	def generate_pdf(self):
		self.columns = list() # a list that contains a list of column attributes
		self.column_titles = list()
		for column in self.treeview.get_columns():
			if column.get_visible() and column.get_width() > 0:
				#print (column.get_title())
				specs = list() # the list that holds the column attributes
				cell_area = column.get_area()
				renderer = cell_area.get_cells()[0]
				if type(renderer) != gi.repository.Gtk.CellRendererText:
					print (type(renderer), 'is not supported yet for pdf export')
					continue
				specs.append(cell_area.attribute_get_column(renderer, "text"))
				specs.append(renderer.get_property("ellipsize"))
				xalign = renderer.get_property("xalign")
				if xalign == 1.0:
					xalign = Pango.Alignment.RIGHT
				else:
					xalign = Pango.Alignment.LEFT
				specs.append(xalign)
				specs.append(column.get_width())
				is_expander = self.treeview.get_expander_column() == column
				specs.append(is_expander)
				self.columns.append(specs)
				column_specs = list()
				column_specs.append(column.get_title())
				column_specs.append(column.get_width())
				self.column_titles.append(column_specs)
		pdf_width = self.treeview.get_allocated_width() 
		pdf_width += self.border_width * 2
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
		self.pdf_height = pdf_height
		self.pdf_width = pdf_width
		surface = cairo.PDFSurface("/tmp/pdf_export.pdf", pdf_width, pdf_height)
		self.cr = cairo.Context(surface)
		self.cr.set_source_rgb(0, 0, 0)
		self.cr.set_line_width(1)
		rectangle = self.treeview.get_cell_area(0, None)
		self.row_height = rectangle.height
		# self.y is the current position of the cursor in the document
		self.y = self.border_width 
		self.show_titles ()
		if type(self.store) is type(Gtk.TreeStore()):
			treeiter = self.store.get_iter_first()
			indent = 0
			self.line_axis = list() # a list that contains a list of axises
			self.create_from_treerow(treeiter, indent)
		elif type(self.store) is type(Gtk.ListStore()):
			self.create_from_liststore()
		else: # should not be reached
			print (type(self.store), "is still in testing for pdf export")
			self.create_from_liststore()
			#error = "%s is an invalid treestore model!" % type(self.store)
			#raise Exception(error)
		surface.finish()
		self.window.present()
		with open("/tmp/pdf_export.pdf",'rb') as f:
			self.bytes = f.read()
		GLib.idle_add(self.load_pdf)
			
	def create_from_treerow (self, treeiter, indent):
		"create_from_treerow calls itself for child nodes"
		start_y = self.y
		while treeiter != None:
			x, end_y = self.show_row(treeiter, indent )
			axis = list() # keep track of axises for purpose of page breaks
			axis.append(x)
			axis.append(start_y)
			axis.append(end_y)
			self.line_axis.append(axis) # we need current line axis for page breaks
			if (self.y + self.border_width) > self.pdf_height:
				self.render_page_break()
			if self.store.iter_has_child(treeiter):
				if self.treeview.row_expanded(self.store.get_path(treeiter)):
					childiter = self.store.iter_children(treeiter)
					# enter child node
					self.create_from_treerow (childiter, indent + 20)
					# exit child node and process any other parent nodes
			axis = self.line_axis.pop(-1) # remove axis as we exit the child node (if any)
			x, start_y = axis[0], axis[1] # we use the axis for completing lines
			treeiter = self.store.iter_next(treeiter)
		if x != self.border_width : # render a vertical line for all child nodes
			self.cr.move_to(x, start_y - (self.row_height / 2))
			self.cr.line_to(x, end_y - (self.row_height / 1.5))
			self.cr.stroke()
			
	def show_titles (self):
		x = self.border_width
		for specs in self.column_titles:
			layout = PangoCairo.create_layout(self.cr)
			desc = Pango.font_description_from_string(self.font_desc)
			layout.set_font_description(desc)
			text = str(specs[0])
			layout.set_text(text, len(text))
			layout.set_width(specs[1] * Pango.SCALE) # column_width
			layout.set_height(-1)
			self.cr.move_to(x, self.y)
			PangoCairo.show_layout(self.cr, layout)
			x += specs[1] + 10 # move right by the column width; plus 10 extra?
		self.y += (self.row_height* 2) # add some spacing to the title
			
	def show_row (self, treeiter, indent):
		row = self.store[treeiter] # the row we are displaying
		x = self.border_width + indent 
		start_x = x
		if indent != 0: # show the horizontal line in front of child nodes only
			y = self.y + (self.row_height / 3)
			self.cr.move_to(x, y)
			self.cr.line_to(x + 10, y)
			self.cr.stroke()
		x += 10
		for specs in self.columns:
			layout = PangoCairo.create_layout(self.cr)
			desc = Pango.font_description_from_string(self.font_desc)
			layout.set_font_description(desc)
			text = str(row[specs[0]])
			layout.set_text(text, len(text))
			layout.set_ellipsize(specs[1])
			layout.set_alignment(specs[2])
			layout.set_width(specs[3] * Pango.SCALE) # column_width
			layout.set_height(-1)
			self.cr.move_to(x, self.y)
			PangoCairo.show_layout(self.cr, layout)
			if specs[4]: # expander column; align the rest of the columns
				x -= indent 
			x += specs[3] # move right by the width of the column
		self.y += self.row_height
		return start_x, self.y

	def render_page_break (self):
		"completes vertical lines before finishing the page "
		"and then restarts the lines on the new page"
		for axis in self.line_axis:
			x, start_y = axis[0], axis[1]
			if x == self.border_width:
				continue
			self.cr.move_to(x, start_y - (self.row_height / 3))
			self.cr.line_to(x, self.y + self.row_height ) # end of page
			self.cr.stroke() # paint the line
			axis[1] = 0 # line now starts at beginning of page
		self.cr.show_page() # show existing page and start a new one
		self.y = self.border_width # set the cursor y position to the start
		
	def create_from_liststore (self):
		for index, row in enumerate(self.store):
			x = self.border_width
			for specs in self.columns:
				layout = PangoCairo.create_layout(self.cr)
				desc = Pango.font_description_from_string(self.font_desc)
				layout.set_font_description(desc)
				text = str(row[specs[0]])
				length = len(text)
				layout.set_text(text, length)
				layout.set_ellipsize(specs[1])
				layout.set_alignment(specs[2])
				layout.set_width(specs[3] * Pango.SCALE)
				layout.set_height(-1)
				self.cr.move_to(x, self.y)
				PangoCairo.show_layout(self.cr, layout)
				x += specs[3] + 10
			self.y += self.row_height
			if (self.y + self.border_width) > self.pdf_height:
				self.cr.show_page()
				self.y = self.border_width

	def print_pdf_clicked (self, button):
		import printing
		print_op = printing.Operation()
		print_op.set_parent(self.window)
		pdf_data = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes(self.bytes))
		print_op.set_bytes_to_print(pdf_data)
		if self.landscape:
			setup = Gtk.PageSetup()
			setup.set_orientation(Gtk.PageOrientation.LANDSCAPE)
			print_op.set_default_page_setup(setup)
		print_op.print_dialog()

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

