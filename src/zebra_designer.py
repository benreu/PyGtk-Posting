# zebra_designer.py
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

'''The visual label designer, editing the templates stored in the database.

Unlike every other window in Posting this one has no .ui file. It is the
LinuxZPL designer, tracked as a git submodule at src/linuxzpl, which builds its
widgets in code. Only the parts that reach for a file are replaced here, so
that opening and saving go to settings.zebra_templates instead of to the disk.

The submodule is a whole application, not a library: Posting uses its zplcore
engine and its gtkui frontend, and ignores the Qt frontend and the test suite
(create_deb.py skips both when building the .deb).
'''

import os, sys
from gi.repository import Gtk

# The designer imports itself absolutely, as "from zplcore import ...", so its
# own directory goes on the path rather than its imports being rewritten. That
# keeps following upstream a matter of moving the submodule pin. It is done
# here rather than at Posting start-up so zplcore and gtkui only appear once
# the designer is opened, and appended rather than inserted so the submodule
# root cannot shadow Posting's own modules.
_ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'linuxzpl')
if not os.path.isdir(os.path.join(_ENGINE, 'zplcore')):
	raise ImportError("The label designer is missing. It lives in the LinuxZPL "
			"submodule; from the Posting source directory run:\n\n"
			"    git submodule update --init src/linuxzpl")
if _ENGINE not in sys.path:
	sys.path.append(_ENGINE)

from gtkui.window import ZPLViewerWindow
from zplcore import parser as zpl_parser
from zplcore import workflow

from db_connection import DB
import zebra


class ZebraDesignerGUI (ZPLViewerWindow):

	def __init__ (self, template_id = None):
		self.template_id = None
		self.template_name = None
		self.label_type = zebra.PRODUCT
		ZPLViewerWindow.__init__(self)
		self.set_title("Zebra label designer")
		if template_id != None:
			self.load_template(template_id)
		else:
			self.update_title()

	###########################################################################
	# printer

	def _load_settings (self):
		'''Take the printer from Posting, falling back to the designer's own.

		Called from ZPLViewerWindow.__init__ before the label size is derived
		from the dpi, which is why this is the hook rather than assigning to
		printer_address afterwards.
		'''
		ZPLViewerWindow._load_settings(self)
		cursor = DB.cursor()
		# host, not host::text: the column is inet, and casting to text brings
		# the netmask with it ("10.1.2.3/32"), which is not a hostname.
		cursor.execute("SELECT host, port FROM settings.zebra_printers "
						"ORDER BY id LIMIT 1")
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		if row != None:
			self.printer_address = row[0]
			self.printer_port = row[1]

	###########################################################################
	# opening

	def load_template (self, template_id):
		"Open a stored template on the canvas."
		try:
			content = zebra.fetch_template(template_id)
			name, label_type = self.template_details(template_id)
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			return
		self.template_id = template_id
		self.template_name = name
		self.label_type = label_type
		self.open_document(content, name)

	def template_details (self, template_id):
		for row_id, name, label_type in zebra.list_templates():
			if row_id == template_id:
				return name, label_type
		raise zebra.ZebraError("The label template no longer exists.")

	def open_document (self, content, name):
		'''Put ZPL on the canvas. The half of load_zpl_file that is not file I/O.

		warn_unsupported is what stops a template quietly losing commands the
		designer cannot model: it names them before any editing is invested.
		'''
		document, loaded_dpi = zpl_parser.parse_zpl(content, self.renderer)
		self.design_canvas.set_document(document)
		self.current_zpl_content = content
		self.current_filepath = None
		self.label_width = document.label_width
		self.label_height = document.label_height
		rescaled = self._offer_dpi_rescale(loaded_dpi)
		self.label_width = self.design_canvas.label_width
		self.label_height = self.design_canvas.label_height
		self.design_canvas.queue_draw()
		self.unsaved_changes = False
		self._reset_history()
		self.update_title()
		opened = "Opened: %s" % name
		self.update_status("%s - %s" % (opened, rescaled) if rescaled else opened)
		workflow.warn_unsupported(content, self._warn_unsupported)

	def on_load_file_clicked (self, widget):
		"Open one of the stored templates instead of a file."
		if not self.check_unsaved_changes():
			return
		templates = zebra.list_templates()
		if templates == []:
			self.show_error_dialog("There are no label templates yet. "
									"Design one and save it.")
			return
		dialog = Gtk.Dialog(title="Open label template", parent=self, flags=0)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		dialog.set_default_response(Gtk.ResponseType.OK)
		store = Gtk.ListStore(int, str, str)
		for row in templates:
			store.append(list(row))
		treeview = Gtk.TreeView(model = store)
		for index, title in ((1, "Name"), (2, "Type")):
			treeview.append_column(
				Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text = index))
		treeview.connect("row-activated",
			lambda t, p, c: dialog.response(Gtk.ResponseType.OK))
		scroll = Gtk.ScrolledWindow()
		scroll.set_size_request(400, 300)
		scroll.add(treeview)
		dialog.get_content_area().pack_start(scroll, True, True, 0)
		dialog.show_all()
		selection = treeview.get_selection()
		if self.template_id != None:
			for row in store:
				if row[0] == self.template_id:
					selection.select_iter(row.iter)
		response = dialog.run()
		model, treeiter = selection.get_selected()
		dialog.destroy()
		if response == Gtk.ResponseType.OK and treeiter != None:
			self.load_template(model[treeiter][0])

	def on_new_clicked (self, widget = None):
		"A blank label, no longer attached to a stored template."
		ZPLViewerWindow.on_new_clicked(self, widget)
		self.template_id = None
		self.template_name = None
		self.update_title()

	###########################################################################
	# saving

	def save_file_or_ask_for_filename (self):
		'''Save to the database. True means saved.

		The return value matters: workflow.unsaved_changes_gate reads a false
		one as "abort", which is what keeps a failed save from silently
		discarding the work it was asked to protect.
		'''
		content = self.document_content()
		if content == None:
			return False
		if self.template_id == None:
			return self.save_dialog()
		return self.store_template(self.template_name, self.label_type,
									content, self.template_id)

	def save_dialog (self):
		"Save As: ask for a name and a label type, then store it."
		content = self.document_content()
		if content == None:
			return False
		name, label_type = self.ask_name_and_type()
		if name == None:
			return False
		template_id = None
		for row_id, existing, _type in zebra.list_templates():
			if existing == name:
				if row_id == self.template_id:
					template_id = row_id
					break
				if not self.confirm_overwrite(name):
					return False
				template_id = row_id
				break
		return self.store_template(name, label_type, content, template_id)

	def store_template (self, name, label_type, content, template_id):
		try:
			self.template_id = zebra.save_template(name, label_type, content,
													template_id)
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			self.update_status("Save failed")
			return False
		self.template_name = name
		self.label_type = label_type
		self.unsaved_changes = False
		self.update_title()
		self.update_status("Saved: %s" % name)
		return True

	def document_content (self):
		"The canvas as ZPL, or None with the user already told why not."
		try:
			content = self.design_canvas.to_zpl()
		except Exception as e:
			self.show_error_dialog("Failed to generate ZPL: %s" % e)
			return None
		if not content.strip() or content == "^XA\n^XZ":
			self.show_error_dialog("No content to save")
			return None
		return content

	def ask_name_and_type (self):
		"Prompt for a template name and label type, or (None, None)."
		dialog = Gtk.Dialog(title="Save label template", parent=self, flags=0)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
		dialog.set_default_response(Gtk.ResponseType.OK)
		entry = Gtk.Entry()
		entry.set_activates_default(True)
		if self.template_name != None:
			entry.set_text(self.template_name)
		combo = Gtk.ComboBoxText()
		for label_type in (zebra.PRODUCT, zebra.SERIAL):
			combo.append(label_type, "%s (%s placeholder%s)"
				% (label_type, zebra.PLACEHOLDER_COUNT[label_type],
					'' if zebra.PLACEHOLDER_COUNT[label_type] == 1 else 's'))
		combo.set_active_id(self.label_type)
		grid = Gtk.Grid(row_spacing = 4, column_spacing = 6, border_width = 6)
		grid.attach(Gtk.Label(label = "Name", halign = Gtk.Align.END), 0, 0, 1, 1)
		grid.attach(entry, 1, 0, 1, 1)
		grid.attach(Gtk.Label(label = "Label type", halign = Gtk.Align.END), 0, 1, 1, 1)
		grid.attach(combo, 1, 1, 1, 1)
		dialog.get_content_area().pack_start(grid, True, True, 0)
		dialog.show_all()
		while True:
			if dialog.run() != Gtk.ResponseType.OK:
				dialog.destroy()
				return None, None
			name = entry.get_text().strip()
			if name != '':
				label_type = combo.get_active_id()
				dialog.destroy()
				return name, label_type
			self.show_error_dialog("The template needs a name.")

	def confirm_overwrite (self, name):
		dialog = Gtk.MessageDialog(parent = self, flags = 0,
									message_type = Gtk.MessageType.QUESTION,
									buttons = Gtk.ButtonsType.NONE,
									text = 'Replace "%s"?' % name)
		dialog.format_secondary_text("A template of that name already exists. "
										"Saving replaces it for every client.")
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							"Replace", Gtk.ResponseType.OK)
		response = dialog.run()
		dialog.destroy()
		return response == Gtk.ResponseType.OK

	###########################################################################
	# nothing here reads or writes a .zpl on disk

	def save_zpl_file (self, filepath, content):
		raise NotImplementedError("templates are stored in the database")

	def load_zpl_file (self, filepath):
		raise NotImplementedError("templates are stored in the database")

	###########################################################################

	def update_title (self):
		name = self.template_name or "Untitled"
		title = "%s - Zebra label designer" % name
		self.set_title(title)
		titlebar = self.get_titlebar()
		if titlebar != None:
			titlebar.set_title(title)
			titlebar.set_subtitle(self.label_type)
