# serial_numbers.py
#
# Copyright (C) 2020 - reuben
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
import os, subprocess
import barcode_generator, zebra, admin_utils
from db_connection import DB
from constants import ui_directory, template_dir, MANUFACTURING_SERIAL_LOCK_CLASSID

UI_FILE = ui_directory + "/manufacturing/serial_numbers.ui"

class Item (object):
	pass

class SerialNumbersGUI(Gtk.Builder):
	lock_acquired = False
	def __init__(self, parent, manufacturing_id, serials_required):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.parent = parent
		self.manufacturing_id = manufacturing_id
		self.serials_required = serials_required
		self.window = self.get_object('window')
		cursor = DB.cursor()
		cursor.execute("SELECT pg_try_advisory_lock(%s, %s)",
							(MANUFACTURING_SERIAL_LOCK_CLASSID, manufacturing_id))
		locked = cursor.fetchone()[0]
		cursor.close()
		if not locked:
			DB.rollback()
			error = "Somebody else is working on serial numbers"
			self.show_message (error)
			self.window.destroy()
			return
		self.lock_acquired = True
		self.window.show_all()
		self.populate_serial_numbers()
		self.populate_printers()

	def window_destroy (self, widget):
		self.parent.populate_projects()
		if self.lock_acquired:
			cursor = DB.cursor()
			cursor.execute("SELECT pg_advisory_unlock(%s, %s)",
								(MANUFACTURING_SERIAL_LOCK_CLASSID,
								self.manufacturing_id))
			cursor.close()
			self.lock_acquired = False
		DB.commit()

	def populate_system_labels(self):
		store = self.get_object('serial_template_store')
		zebra.populate_odt_store(store, 'serial*.odt')

	def populate_zebra_labels(self):
		store = self.get_object('serial_template_store')
		zebra.populate_template_store(store, zebra.SERIAL)

	def populate_printers(self):
		store = self.get_object('printer_store')
		store.clear()
		store.append(['0', 'System', 'None', 0])
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, host, port "
						"FROM settings.zebra_printers")
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()

	def populate_serial_numbers (self):
		store = self.get_object('serial_number_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, serial_number "
							"FROM serial_numbers "
							"WHERE manufacturing_id = %s ",
							(self.manufacturing_id,))
		for row in cursor.fetchall():
			store.append(row)
		cursor.execute("SELECT p.id, p.serial_number "
							"FROM products AS p "
							"JOIN manufacturing_projects AS mp "
							"ON mp.product_id = p.id "
							"WHERE mp.id = %s",
							(self.manufacturing_id,))
		for row in cursor.fetchall():
			self.product_id = row[0]
			serial_start = row[1]
		cursor.close()
		self.get_object('serial_number_adjustment').set_lower(serial_start)
		self.get_object('serial_number_spinbutton').set_value(serial_start)
		self.serials_generated = len(store)
		if self.serials_required == self.serials_generated:
			self.get_object('generate_box').set_sensitive(False)
		else:
			self.get_object('generate_box').set_sensitive(True)
		end = serial_start + (self.serials_required - self.serials_generated)
		self.get_object('serial_end_label').set_label(str(end))
		
	def printer_combo_changed (self, combobox):
		printer_id = combobox.get_active_id()
		if printer_id == None:
			return
		if printer_id == '0':
			self.populate_system_labels()
		else:
			self.populate_zebra_labels()

	def printer_template_combo_changed (self, combobox):
		self.get_object('edit_template_button').set_sensitive(
			zebra.selected_template_id(combobox) != None)

	def edit_template_clicked (self, button):
		template_id = zebra.selected_template_id(self.get_object('template_combo'))
		if template_id == None or not admin_utils.check_admin(self.window):
			return
		import zebra_designer
		designer = zebra_designer.edit_template(template_id)
		designer.connect('destroy', self.template_designer_closed, template_id)

	def template_designer_closed (self, designer, template_id):
		# a rename, or a Save as under a new name, should show in the combo.
		# Repopulate the way the printer combo does, since the store is shared
		# with the .odt list, then put the selection back: on the designer's
		# final template if it still has one, else on the one that was open.
		self.printer_combo_changed(self.get_object('printer_combo'))
		zebra.select_template(self.get_object('template_combo'),
								designer.template_id or template_id)

	def reprint_serial_number_clicked (self, button):
		barcode = self.get_object('reprint_spinbutton').get_value_as_int()
		self.print_serial_number(barcode, 1)

	def generate_serial_numbers_clicked (self, button):
		spinbutton = self.get_object('serial_number_spinbutton')
		serial_start = spinbutton.get_value_as_int()
		label_qty = self.get_object('label_qty_spinbutton').get_value_as_int()
		cursor = DB.cursor()
		for i in range(self.serials_required):
			barcode = serial_start + i
			while Gtk.events_pending():
				Gtk.main_iteration()
			self.print_serial_number(barcode, label_qty)
			cursor.execute("INSERT INTO serial_numbers "
							"(product_id, date_inserted, serial_number, "
							"manufacturing_id) "
							"VALUES (%s, CURRENT_DATE, %s, %s)", 
							(self.product_id, barcode, self.manufacturing_id))
		serial = self.serials_required + serial_start
		cursor.execute("UPDATE products SET serial_number = %s "
						"WHERE id = %s", (serial, self.product_id))
		DB.commit()
		cursor.close()
		self.populate_serial_numbers()

	def print_serial_number (self, barcode, label_qty):
		printer_id = self.get_object('printer_combo').get_active_id()
		if printer_id == None:
			return
		template_iter = self.get_object('template_combo').get_active_iter()
		if template_iter == None:
			return
		model = self.get_object('serial_template_store')
		template_id = model[template_iter][0]
		if template_id == 'zpl':
			self.zebra_print_label(barcode, label_qty, model[template_iter][2])
		elif template_id == 'odt':
			self.system_print_label(barcode, label_qty,
					os.path.join(template_dir, model[template_iter][1]))
			
	def zebra_print_label (self, barcode, label_qty, template_id):
		printer_iter = self.get_object('printer_combo').get_active_iter()
		model = self.get_object('printer_store')
		host = model[printer_iter][2]
		port = model[printer_iter][3]
		try:
			zebra.print_label(host, port, template_id, barcode, label_qty)
		except zebra.ZebraError as e:
			self.show_message(str(e))

	def system_print_label (self, barcode, label_qty, template):
		printer_iter = self.get_object('printer_combo').get_active_iter()
		model = self.get_object('printer_store')
		label = Item()
		label.code128 = barcode_generator.makeCode128(str(barcode))
		label.barcode = barcode
		head, template_name = os.path.split(template)
		from py3o.template import Template
		label_file = os.path.join("/tmp", template_name)
		t = Template(template, label_file)
		data = dict(label = label)
		t.render(data)
		for i in range(label_qty):
			subprocess.call(["soffice", "--headless", "-p", label_file])

	def start_serial_number_value_changed (self, spinbutton):
		serial_number = spinbutton.get_value_as_int()
		qty = self.get_object('spinbutton1').get_value_as_int()
		self.get_object('label10').set_label(str(qty + serial_number))
		
	def selection_changed (self, selection):
		model, paths = selection.get_selected_rows()
		if len(paths) > 1:
			self.get_object('menu1').popup_at_pointer()

	def serial_numbers_button_release_event (self, widget, event):
		if event.button == 3:
			self.get_object('menu1').popup_at_pointer()

	def serial_number_treeview_print_clicked (self, menuitem):
		model, paths = self.get_object('treeselection1').get_selected_rows()
		if paths == []:
			return
		for path in paths:
			barcode = model[path][1]
			self.print_serial_number(barcode, 1)

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()



