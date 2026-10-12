# inventory_transfer.py
#
# Copyright (C) 2026 - Reuben Rissler
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
from db_connection import DB
from constants import ui_directory
from inventory import inventorying

UI_FILE = ui_directory + "/inventory/inventory_transfer.ui"

class InventoryTransferGUI(Gtk.Builder):
	'''move stock the company already owns from one location to another. The
	lines live in transfer_lines_store until they are posted: a move is written by
	the post that moves the stock, so there is no half finished transfer in the
	database to come back to and nothing to clean up if the window is closed'''
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.product_id = None # no product is picked until the combo changes

		self.product_store = self.get_object('transfer_product_store')
		self.lines_store = self.get_object('transfer_lines_store')
		completion = self.get_object('transfer_product_completion')
		completion.set_match_func(self.product_match_func)

		self.populate_stores ()

		self.window = self.get_object('transfer_window')
		self.window.show_all()
		self.set_post_sensitive ()

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def show_message (self, message, secondary = None,
						message_type = Gtk.MessageType.ERROR):
		dialog = Gtk.MessageDialog(message_type = message_type,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup(message)
		if secondary != None:
			# not markup, so a product name with an & in it needs no escaping
			dialog.format_secondary_text(secondary)
		dialog.run()
		dialog.destroy()

	def populate_stores (self):
		'''only a tracked product can hold stock to move, and transfer () refuses
		one that is not tracked, so the picker must not offer a line the post
		would throw back'''
		c = DB.cursor()
		location_store = self.get_object('transfer_location_store')
		source_combo = self.get_object('transfer_source_combo')
		destination_combo = self.get_object('transfer_destination_combo')
		source_id = source_combo.get_active_id()
		destination_id = destination_combo.get_active_id()
		location_store.clear()
		c.execute("SELECT id::text, name FROM locations ORDER BY name")
		for row in c.fetchall():
			location_store.append(row)
		self.product_store.clear()
		c.execute("SELECT id::text, name || ' {' || ext_name || '}' "
					"FROM products "
					"WHERE (deleted, stock, inventory_enabled) "
						"= (False, True, True) "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.product_store.append(row)
		c.close()
		if source_id == None:
			source_combo.set_active(0)
		else:
			source_combo.set_active_id(source_id)
		# the destination is deliberately left unset until it is picked: there is
		# no sensible place to preselect, and the first location is already the
		# source
		if destination_id != None:
			destination_combo.set_active_id(destination_id)
		DB.rollback()

	def transfer_locations_clicked (self, button):
		import locations
		locations.LocationsGUI()

	def transfer_focus_in (self, window, event):
		'''a location added or renamed in the locations window, or a product
		whose tracking was just turned on, is picked up on the way back in. The
		same refresh on focus receive_orders and product_location do'''
		self.populate_stores ()

	def transfer_source_changed (self, combo):
		'''every figure on screen is the stock at the location the move will be
		taken from, so they all have to follow this combo. A line added against
		one source says nothing about what another source holds'''
		self.restate_on_hand ()
		self.set_post_sensitive ()

	def transfer_destination_changed (self, combo):
		self.set_post_sensitive ()

	def source_location_id (self):
		'''the combo hands out a string, while inventorying calls a location id a
		number; transfer () puts it in places where that difference shows'''
		location_id = self.get_object('transfer_source_combo').get_active_id()
		return None if location_id == None else int(location_id)

	def destination_location_id (self):
		location_id = self.get_object(
							'transfer_destination_combo').get_active_id()
		return None if location_id == None else int(location_id)

	def restate_on_hand (self):
		'''both the picker's label and every line's own column, against whatever
		the source combo now names. A source of None is left showing nothing
		rather than handed to on_hand, which reads None as every location: that
		is the company wide figure, and a column headed "on hand at source" is
		the last place to put it. The combo reads None while populate_stores has
		the store cleared, so this is reached with no source on every refresh'''
		source_id = self.source_location_id ()
		label = self.get_object('transfer_on_hand_label')
		if source_id == None:
			for row in self.lines_store:
				row[3] = 0
			label.set_text('no location')
			return
		c = DB.cursor()
		for row in self.lines_store:
			row[3] = inventorying.on_hand (row[0], source_id, c)
		if self.product_id == None:
			label.set_text('no product')
		else:
			qty = inventorying.on_hand (self.product_id, source_id, c)
			label.set_text('%s on hand at source' % qty)
		c.close()
		DB.rollback()

	def transfer_product_match_selected (self, completion, model, iter):
		self.get_object('transfer_product_combo').set_active_id(model[iter][0])

	def transfer_product_combo_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id == None:
			return
		self.product_id = int(product_id)
		self.restate_on_hand ()

	def transfer_add_clicked (self, button):
		source_id = self.source_location_id ()
		if self.product_id == None or source_id == None:
			return
		qty = self.get_object('transfer_qty_spinbutton').get_value_as_int()
		if qty <= 0:
			return
		# a product already listed takes the quantity onto its own line rather
		# than getting a second one. transfer () sums its lines per product
		# anyway, so this is only where that becomes visible to the user
		for row in self.lines_store:
			if row[0] == self.product_id:
				row[1] = row[1] + qty
				break
		else:
			c = DB.cursor()
			c.execute("SELECT name || ' {' || ext_name || '}' FROM products "
						"WHERE id = %s", (self.product_id,))
			name = c.fetchone()[0]
			on_hand = inventorying.on_hand (self.product_id, source_id, c)
			c.close()
			DB.rollback()
			self.lines_store.append([self.product_id, qty, name, on_hand])
		self.get_object('transfer_qty_spinbutton').set_value(1)
		self.set_post_sensitive ()

	def transfer_qty_edited (self, cellrenderertext, path, qty):
		try: # the store column is an integer, so reject anything else up front
			qty = int(qty)
		except ValueError:
			return
		if qty <= 0: # removing a line is what the right click menu is for
			return
		self.lines_store[path][1] = qty

	def transfer_treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			self.get_object('transfer_right_click_menu').popup_at_pointer()

	def transfer_remove_activated (self, menuitem):
		selection = self.get_object('transfer_lines_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		model.remove(model.get_iter(path[0]))
		self.set_post_sensitive ()

	def transfer_product_hub_activated (self, menuitem):
		selection = self.get_object('transfer_lines_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		import product_hub
		product_hub.ProductHubGUI(model[path[0]][0])

	def set_post_sensitive (self):
		'''one place decides whether the move can be posted, and says why not. A
		line asking for more than its on hand column shows is left alone here:
		that check has to run against the stock as it is at posting time, and a
		second authority for it in the window is one that can disagree'''
		source_id = self.source_location_id ()
		destination_id = self.destination_location_id ()
		if source_id == None:
			message = 'Pick a location to move from'
		elif destination_id == None:
			message = 'Pick a location to move to'
		elif source_id == destination_id:
			message = 'The source and the destination are the same location'
		elif len(self.lines_store) == 0:
			message = 'Add a product to move'
		else:
			message = ''
		self.get_object('transfer_status_label').set_text(message)
		self.get_object('transfer_post_button').set_sensitive(message == '')

	def transfer_post_clicked (self, button):
		'''the gate on posting the same lines twice. transfer () creates its own
		header, so every call is a move of its own and the function has nothing to
		recognise a repeat by; the button goes dead here and the lines are cleared
		on the way out, which leaves set_post_sensitive nothing to re enable'''
		button.set_sensitive(False)
		source_id = self.source_location_id ()
		destination_id = self.destination_location_id ()
		notes = self.get_object('transfer_notes_entry').get_text() or None
		moved = sum(row[1] for row in self.lines_store)
		products = len(self.lines_store)
		try:
			inventorying.transfer (self.lines_store, source_id, destination_id,
									notes)
		except Exception as e:
			DB.rollback()
			self.show_message ("The stock was not moved",
								str(e))
			self.set_post_sensitive ()
			return
		DB.commit()
		c = DB.cursor()
		c.execute("SELECT l.name, d.name FROM locations AS l "
					"JOIN locations AS d ON d.id = %s WHERE l.id = %s",
					(destination_id, source_id))
		source_name, destination_name = c.fetchone()
		c.close()
		DB.rollback()
		self.lines_store.clear()
		self.get_object('transfer_notes_entry').set_text('')
		self.restate_on_hand ()
		# the combos are left where they are: the next move is usually between
		# the same two places
		self.set_post_sensitive ()
		self.show_message ("The stock was moved",
							"%s units of %s products moved from %s to %s"
							% (moved, products, source_name, destination_name),
							Gtk.MessageType.INFO)
