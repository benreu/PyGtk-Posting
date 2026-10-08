# shipping_carriers.py
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

from gi.repository import Gtk
from db_connection import DB
from constants import ui_directory

UI_FILE = ui_directory + "/shipping_carriers.ui"

class ShippingCarriersGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.shipping_carrier_store = self.builder.get_object('shipping_carrier_store')
		self.populate_carrier_store ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		pass

	def populate_carrier_store (self):
		self.shipping_carrier_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name, standard "
							"FROM shipping_carriers "
							"WHERE deleted = False ORDER BY name")
		for row in cursor.fetchall():
			self.shipping_carrier_store.append(row)
		cursor.close()
		DB.rollback()

	def new_clicked (self, button):
		iter_ = self.shipping_carrier_store.append([0, 'New carrier', False])
		self.builder.get_object('treeview-selection1').select_iter(iter_)

	def carrier_combo_changed(self, combo):
		self.builder.get_object('button2').set_sensitive(True)

	def delete_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		current_carrier_id = model[path][0]
		cursor = DB.cursor()
		try:
			cursor.execute("DELETE FROM shipping_carriers "
								"WHERE id = %s", (current_carrier_id,))
			DB.rollback()
			cursor.execute("UPDATE shipping_carriers "
								"SET deleted = True WHERE id = %s",
								(current_carrier_id,))
		except Exception as e:
			DB.rollback()
			self.builder.get_object('label3').set_label(str(e))
			dialog = self.builder.get_object('dialog1')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				carrier_id = self.builder.get_object('combobox1').get_active_id()
				cursor.execute("UPDATE contact_shipping_addresses "
									"SET shipping_carrier_id = %s "
									"WHERE shipping_carrier_id = %s",
									(carrier_id, current_carrier_id))
				cursor.execute("UPDATE shipping_carriers "
									"SET deleted = True WHERE id = %s",
									(current_carrier_id,))
		cursor.close()
		DB.commit()
		self.builder.get_object('button2').set_sensitive(False)
		self.populate_carrier_store ()

	def name_edited (self, text_renderer, path, text):
		iter_ = self.shipping_carrier_store.get_iter(path)
		self.shipping_carrier_store[path][1] = text
		self.save (iter_)

	def default_toggled (self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		cursor = DB.cursor()
		for row in self.shipping_carrier_store:
			if row.path == selected_path:
				row[2] = True
				cursor.execute("UPDATE shipping_carriers "
									"SET standard = True "
									"WHERE id = (%s)",[row[0]])
			else:
				row[2] = False
				cursor.execute("UPDATE shipping_carriers "
									"SET standard = False "
									"WHERE id = %s",[row[0]])
		cursor.close()
		DB.commit()

	def save (self, iter_):
		row_id = self.shipping_carrier_store[iter_][0]
		name = self.shipping_carrier_store[iter_][1]
		cursor = DB.cursor()
		if row_id == 0:
			cursor.execute("INSERT INTO shipping_carriers "
								"(name) VALUES (%s) "
								"RETURNING id",
								(name,))
			row_id = cursor.fetchone()[0]
			self.shipping_carrier_store[iter_][0] = row_id
		else:
			cursor.execute("UPDATE shipping_carriers "
								"SET (name, date_edited) = (%s, CURRENT_DATE) "
								"WHERE id = %s",
								(name, row_id))
		cursor.close()
		DB.commit()
