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

'''The visual label designer, editing templates on disk or in the database.

Unlike every other window in Posting this one has no .ui file. It is the
LinuxZPL designer, tracked as a git submodule at src/linuxzpl, which builds its
widgets in code. Its File menu is left exactly as upstream wrote it and works
on .zpl files; a Database menu is added beside it for the templates in
settings.zebra_templates, which is where the label windows print from.

A document has one home: a file, a stored template, or neither. The last open
or save decides, and the header bar says which. That single rule is what keeps
the designer's one unsaved-changes flag truthful, since saving anywhere clears
it. File > Save goes to wherever the document lives, so the common path - edit
a stored template, Ctrl+S, close - reaches the database and not a stray
untitled.zpl.

The submodule is a whole application, not a library: Posting uses its zplcore
engine and its gtkui frontend, and ignores the Qt frontend and the test suite
(create_deb.py skips both when building the .deb).
'''

import os, sys
from gi.repository import Gtk, GLib

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

# The window, if any, that has each stored template open. Two windows editing
# one template would be last-save-wins with no warning; the label windows go
# through edit_template() so a second click raises the first window instead.
_open_windows = {}


def edit_template (template_id):
	"The designer window for a stored template, raising one already open."
	window = _open_windows.get(template_id)
	if window != None:
		window.present()
		return window
	return ZebraDesignerGUI(template_id)


class ZebraDesignerGUI (ZPLViewerWindow):

	def __init__ (self, template_id = None):
		self.template_id = None
		self.template_name = None
		self.label_type = zebra.PRODUCT
		self._dirty = False
		ZPLViewerWindow.__init__(self)
		self.database_accels = Gtk.AccelGroup()
		self.add_accel_group(self.database_accels)
		self.build_database_menu()
		self.connect('destroy', self.forget)
		self.update_title()
		self.present()
		if template_id != None:
			self.load_template(template_id)
		elif zebra.list_templates() != []:
			# once the window is on screen, so the picker has something to
			# be transient for; with nothing stored there is nothing to pick
			GLib.idle_add(self.pick_template_on_open)

	def forget (self, widget):
		for stored_id, window in list(_open_windows.items()):
			if window is self:
				del _open_windows[stored_id]

	###########################################################################
	# the dirty flag drives the title, so it is a property here

	@property
	def unsaved_changes (self):
		return self._dirty

	@unsaved_changes.setter
	def unsaved_changes (self, value):
		self._dirty = bool(value)
		self.update_title()

	###########################################################################
	# printer

	def _load_settings (self):
		'''Take the printer from Posting, falling back to the designer's own.

		Called from ZPLViewerWindow.__init__ before the label size is derived
		from the dpi, which is why this is the hook rather than assigning to
		printer_address afterwards. (close_app later writes it back out to the
		designer's own ~/.config/linuxzpl/settings.ini, which is harmless.)
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
	# the Database menu

	def build_database_menu (self):
		'''Beside File, in the same shape: mnemonics, groups, an ellipsis on
		anything that asks first. Save template has no accelerator because
		Ctrl+S already saves to wherever the document lives, and Delete has
		none because it removes the template from every client.
		'''
		menu = Gtk.Menu()
		top = Gtk.MenuItem.new_with_mnemonic("_Database")
		top.set_submenu(menu)
		for label, action, accel in (
				("_Open template…", self.open_template, "<Control><Shift>o"),
				(None, None, None),
				("_Save template", self.save_template, None),
				("Save template _as…", self.save_template_as, None),
				(None, None, None),
				("_Delete template…", self.delete_template, None)):
			if label == None:
				menu.append(Gtk.SeparatorMenuItem())
				continue
			item = Gtk.MenuItem.new_with_mnemonic(label)
			item.connect("activate", action)
			if accel != None:
				key, mods = Gtk.accelerator_parse(accel)
				item.add_accelerator("activate", self.database_accels, key, mods,
										Gtk.AccelFlags.VISIBLE)
			menu.append(item)
			if action == self.delete_template:
				self.delete_item = item
		# upstream keeps its menu bar as a local, so find it where it was
		# packed: the header bar's only child
		bars = [child for child in self.get_titlebar().get_children()
				if isinstance(child, Gtk.MenuBar)]
		if bars != []:
			bars[0].insert(top, 1)
		else:
			bar = Gtk.MenuBar()
			bar.append(top)
			self.get_titlebar().pack_start(bar)
			bar.show_all()
		top.show_all() # the window is already shown, so this is not automatic

	###########################################################################
	# where the document lives

	def home_template (self, template_id, name, label_type):
		"This document now lives in the database, as that template."
		self.template_id = template_id
		self.template_name = name
		self.label_type = label_type
		self.current_filepath = None
		self.register()
		self.update_title()

	def detach (self):
		"No longer a stored template; the name stays, as a Save as prefill."
		self.template_id = None
		self.register()
		self.update_title()

	def register (self):
		for stored_id, window in list(_open_windows.items()):
			if window is self and stored_id != self.template_id:
				del _open_windows[stored_id]
		if self.template_id != None:
			_open_windows[self.template_id] = self

	def update_title (self):
		'''Header title is the name, subtitle is where it lives.

		Runs from the unsaved_changes setter too, which upstream first hits
		inside its own __init__ before the header bar exists.
		'''
		if self.template_id != None:
			name = self.template_name
			where = "%s label template, in the database" % self.label_type
		elif getattr(self, 'current_filepath', None):
			name = os.path.basename(self.current_filepath)
			where = os.path.dirname(self.current_filepath)
		else:
			name = "Untitled"
			where = ""
		if self._dirty:
			name = "*" + name
		self.set_title("%s - Zebra label designer" % name)
		titlebar = self.get_titlebar()
		if titlebar != None:
			titlebar.set_title(name)
			titlebar.set_subtitle(where)
		if hasattr(self, 'delete_item'):
			self.delete_item.set_sensitive(self.template_id != None)

	###########################################################################
	# the file path, left to upstream except for re-homing

	def load_zpl_file (self, filepath):
		ZPLViewerWindow.load_zpl_file(self, filepath)
		# upstream returns None either way; it sets the path only on success
		if self.current_filepath == filepath:
			self.template_name = None
			self.detach()

	def save_zpl_file (self, filepath, content):
		saved = ZPLViewerWindow.save_zpl_file(self, filepath, content)
		if saved:
			self.detach() # saved to disk, so that is where it lives now
		return saved

	def save_file_or_ask_for_filename (self):
		'''File > Save, and the unsaved-changes gate: save to home.

		Upstream's gate calls this and reads a false return as "abort", which
		is what keeps a failed save from discarding the work it protects.
		'''
		if self.template_id != None:
			return self.save_template()
		if self.current_filepath:
			return ZPLViewerWindow.save_file_or_ask_for_filename(self)
		return self.save_template_as()

	def on_new_clicked (self, widget = None):
		ZPLViewerWindow.on_new_clicked(self, widget)
		# Upstream returns None both when the gate cancelled and when it made
		# the new document, so success has to be read off the flag: the gate
		# only asks when dirty, Cancel and a failed Save leave it set, and the
		# New that follows Discard or a successful Save clears it.
		if self.unsaved_changes:
			return
		self.template_name = None
		self.label_type = zebra.PRODUCT
		self.detach()

	###########################################################################
	# opening from the database

	def open_template (self, widget = None):
		"Database > Open template..."
		if not self.check_unsaved_changes():
			return
		if zebra.list_templates() == []:
			self.show_error_dialog("There are no label templates yet. Design "
									"one and save it to the database.")
			return
		template_id = self.choose_template()
		if template_id != None:
			self.load_template(template_id)

	def pick_template_on_open (self):
		"The picker a designer opened on nothing shows first."
		template_id = self.choose_template()
		if template_id != None:
			self.load_template(template_id)
		return False # GLib.idle_add: once

	def choose_template (self):
		"A dialog listing the stored templates; the chosen id, or None."
		dialog = Gtk.Dialog(title="Open label template", parent=self, flags=0)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		dialog.set_default_response(Gtk.ResponseType.OK)
		store = Gtk.ListStore(int, str, str)
		for row in zebra.list_templates():
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
			return model[treeiter][0]
		return None

	def load_template (self, template_id):
		"Open a stored template on the canvas. True when it is showing."
		try:
			content = zebra.fetch_template(template_id)
			name, label_type = self.template_details(template_id)
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			return False
		if not self.open_document(content, name):
			return False
		self.home_template(template_id, name, label_type)
		return True

	def template_details (self, template_id):
		for row_id, name, label_type in zebra.list_templates():
			if row_id == template_id:
				return name, label_type
		raise zebra.TemplateGone("The label template no longer exists.")

	def open_document (self, content, name):
		'''Put ZPL on the canvas: upstream's load_zpl_file without the file.

		Kept step for step with that method, sync_size included - after a
		dpi rescale the widget is otherwise still the old size and the label
		draws clipped. warn_unsupported is what stops a template quietly
		losing commands the designer cannot model: it names them before any
		editing is invested.
		'''
		try:
			document, loaded_dpi = zpl_parser.parse_zpl(content, self.renderer)
			self.design_canvas.set_document(document)
			self.current_zpl_content = content
			self.label_width = document.label_width
			self.label_height = document.label_height
			rescaled = self._offer_dpi_rescale(loaded_dpi)
			self.label_width = self.design_canvas.label_width
			self.label_height = self.design_canvas.label_height
			self.design_canvas.sync_size()
			opened = "Opened: %s" % name
			self.update_status("%s - %s" % (opened, rescaled) if rescaled else opened)
			self.unsaved_changes = False
			self._reset_history()
			workflow.warn_unsupported(content, self._warn_unsupported)
			return True
		except Exception as e:
			self.show_error_dialog("Failed to open %s: %s" % (name, e))
			self.update_status("Error opening template")
			return False

	###########################################################################
	# saving to the database

	def save_template (self, widget = None):
		"Database > Save template: update the row, or Save as if there is none."
		if self.template_id == None:
			return self.save_template_as()
		content = self.document_content()
		if content == None:
			return False
		try:
			return self.store_template(self.template_name, self.label_type,
										content, self.template_id)
		except zebra.TemplateGone as e:
			# another client deleted it: offer to store this copy afresh,
			# rather than failing on the same dead id at every save
			self.show_error_dialog(str(e))
			self.detach()
			return self.save_template_as()
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			self.update_status("Save failed")
			return False

	def save_template_as (self, widget = None):
		"Database > Save template as...: a name and a type, then store it."
		content = self.document_content()
		if content == None:
			return False
		name, label_type = self.ask_name_and_type()
		if name == None:
			return False
		template_id = None
		for row_id, existing, _type in zebra.list_templates():
			if existing == name:
				if row_id != self.template_id and not self.confirm_overwrite(name):
					return False
				template_id = row_id
				break
		try:
			return self.store_template(name, label_type, content, template_id)
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			self.update_status("Save failed")
			return False

	def store_template (self, name, label_type, content, template_id):
		"Write to the database and make that template home. Raises ZebraError."
		stored_id = zebra.save_template(name, label_type, content, template_id)
		self.home_template(stored_id, name, label_type)
		self.unsaved_changes = False
		self.update_status("Saved: %s" % name)
		return True

	def delete_template (self, widget = None):
		"Database > Delete template...: the row goes, the canvas stays."
		if self.template_id == None:
			return
		name = self.template_name
		dialog = Gtk.MessageDialog(parent = self, flags = 0,
									message_type = Gtk.MessageType.WARNING,
									buttons = Gtk.ButtonsType.NONE,
									text = 'Delete "%s"?' % name)
		dialog.format_secondary_text("Every client loses this label template. "
										"The design stays open here, so Save "
										"template as can bring it back.")
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
							Gtk.STOCK_DELETE, Gtk.ResponseType.OK)
		response = dialog.run()
		dialog.destroy()
		if response != Gtk.ResponseType.OK:
			return
		try:
			zebra.delete_template(self.template_id)
		except zebra.ZebraError as e:
			self.show_error_dialog(str(e))
			return
		self.detach()
		self.update_status("Deleted: %s" % name)

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
		prefill = self.template_name
		if prefill == None and self.current_filepath:
			prefill = os.path.splitext(os.path.basename(self.current_filepath))[0]
		if prefill != None:
			entry.set_text(prefill)
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
