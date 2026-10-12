# inventory_compare.py
#
# Copyright (C) 2023 - Reuben Rissler
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
from decimal import Decimal
from pricing import product_retail_price
from db_connection import DB, broadcaster
from constants import ui_directory

UI_FILE = ui_directory + "/inventory/inventory_compare.ui"

class InventoryCompareGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.summary_id = None # no count is picked until the combo changes
		#self.product_store = self.get_object('product_store')
		self.populate_stores()
		#product_completion = self.get_object('product_completion')
		#product_completion.set_match_func(self.product_match_func)
		self.handler_ids = list()
		for connection in (("inventory_counts_changed",
							self.count_summaries_changed),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		self.window = self.get_object('window')
		self.window.show_all()

	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def count_summaries_changed (self, broadcaster, summary_id):
		'''only a close of the count being compared concerns this window. The
		previous count it is compared against is picked regardless of active, and
		comparing against last year's closed count is the normal case'''
		if self.summary_id != None and int(self.summary_id) == summary_id:
			c = DB.cursor()
			c.execute("SELECT active, name FROM inventory.count_summaries "
						"WHERE id = %s", (summary_id,))
			active, name = c.fetchone()
			c.close()
			# a handler can run inside somebody else's commit, so the read
			# transaction it opened has to be given back
			DB.rollback()
			if active == False:
				self.count_closed_elsewhere (name)
				return
		self.populate_stores ()

	def count_closed_elsewhere (self, name):
		self.summary_id = None
		self.populate_stores ()
		self.set_widgets_sensitive (False)
		self.get_object('current_inventory_store').clear()
		self.get_object('previous_inventory_store').clear()
		self.get_object('previous_summary_label').set_label('does not exist')
		self.show_message ("'%s' is closed, so this window has let it go."
							% GLib.markup_escape_text(name),
							"A closed count cannot be counted into any further. "
							"It was closed either on another machine or in "
							"another window.")

	def show_message (self, message, secondary = None):
		dialog = Gtk.MessageDialog(message_type = Gtk.MessageType.WARNING,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup(message)
		if secondary != None:
			dialog.format_secondary_text(secondary)
		dialog.run()
		dialog.destroy()

	def populate_stores (self):
		c = DB.cursor()
		store = self.get_object('inventory_summaries_store')
		store.clear()
		c.execute("SELECT cs.id::text, "
					"cs.name || ' (' || COALESCE(l.name, 'no location') || ')' "
					"FROM inventory.count_summaries AS cs "
					"LEFT JOIN locations AS l ON l.id = cs.location_id "
					"WHERE cs.active = True "
					"ORDER BY cs.name")
		for row in c.fetchall():
			store.append(row)
		DB.rollback()

	def inventory_summaries_clicked (self, button):
		from inventory import inventory_summaries
		inventory_summaries.InventorySummariesGUI(self)

	def inventory_summary_changed (self, combobox):
		summary_id = combobox.get_active_id()
		if summary_id == None:
			return
		self.summary_id = summary_id
		self.populate_current_inventory()
		c = DB.cursor()
		# previous summary view
		previous_store = self.get_object("previous_inventory_store")
		previous_store.clear()
		c.execute("SELECT cs.id, cs.name "
					"FROM inventory.count_summaries AS cs "
					"WHERE cs.id = "
						"(SELECT p.id FROM inventory.count_summaries AS p, "
						"inventory.count_summaries AS this "
						"WHERE this.id = %s::bigint "
						"AND (p.date_created, p.id) < (this.date_created, this.id) "
						"ORDER BY p.date_created DESC, p.id DESC LIMIT 1)",
					(summary_id,))
		for row in c.fetchall():
			previous_id, previous_name = row[0], row[1]
			self.get_object('previous_summary_label').set_label(previous_name)
			c = DB.cursor()
			c.execute("SELECT cr.qty, "
						"p.id, "
						"p.name "
						"FROM inventory.count_rows AS cr "
						"JOIN products AS p ON p.id = cr.product_id "
						"WHERE count_summary_id = %s", (previous_id,))
			for row in c.fetchall():
				previous_store.append(row)
			self.set_widgets_sensitive(True)
			break
		else:
			self.get_object('previous_summary_label').set_label('does not exist')
			self.set_widgets_sensitive(False)

	def populate_current_inventory(self):
		current_store = self.get_object("current_inventory_store")
		current_store.clear()
		c = DB.cursor()
		c.execute("SELECT cr.qty, "
					"p.id, "
					"p.name "
					"FROM inventory.count_rows AS cr "
					"JOIN products AS p ON p.id = cr.product_id "
					"WHERE count_summary_id = %s", (self.summary_id,))
		for row in c.fetchall():
			current_store.append(row)

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def delete_activated (self, menuitem):
		selection = self.get_object('current_inventory_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		c = DB.cursor()
		c.execute("DELETE FROM inventory.count_rows "
					"WHERE (count_summary_id, product_id) = (%s, %s) "
					"AND EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active)",
					(self.summary_id, product_id, self.summary_id))
		DB.commit()
		self.populate_current_inventory ()

	def product_hub_activated (self, menuitem):
		selection = self.get_object('current_inventory_selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		import product_hub
		product_hub.ProductHubGUI(product_id)
		
	def copy_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"SELECT %s, "
						"%s, "
						"%s, "
						"(SELECT cost FROM products WHERE id = %s), "
						"(SELECT product_retail_price(%s)) "
					"WHERE EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active) "
					"ON CONFLICT DO NOTHING",
					(self.summary_id, product_id, qty, product_id, product_id,
					self.summary_id))
		DB.commit()
		self.populate_current_inventory()
		
	def update_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"SELECT %s, "
						"%s, "
						"%s, "
						"(SELECT cost FROM products WHERE id = %s), "
						"(SELECT product_retail_price(%s)) "
					"WHERE EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active) "
					"ON CONFLICT (count_summary_id, product_id) "
					"DO UPDATE SET qty = %s "
					"WHERE (cr.count_summary_id, cr.product_id) = (%s, %s)",
					(self.summary_id, product_id, qty, product_id, product_id,
					self.summary_id, qty, self.summary_id, product_id))
		DB.commit()
		self.populate_current_inventory()
		
	def create_inventory_clicked (self, button):
		c = DB.cursor()
		selection = self.get_object('previous_inventory_selection')
		model, rows = selection.get_selected_rows()
		for row in rows:
			qty = model[row][0]
			product_id = model[row][1]
			c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"SELECT %s, "
						"%s, "
						"0, "
						"(SELECT cost FROM products WHERE id = %s), "
						"(SELECT product_retail_price(%s)) "
					"WHERE EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active) "
					"ON CONFLICT DO NOTHING",
					(self.summary_id, product_id, product_id, product_id,
					self.summary_id))
		DB.commit()
		self.populate_current_inventory()

	def set_widgets_sensitive(self, value):
		self.get_object('copy_button').set_sensitive(value)
		self.get_object('update_button').set_sensitive(value)
		self.get_object('create_button').set_sensitive(value)


