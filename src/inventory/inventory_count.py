# inventory_count.py
# Copyright (C) 2021 reuben 
# 
# inventory_count is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# inventory_count is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
from decimal import Decimal
from pricing import product_retail_price
from db_connection import DB, broadcaster
from constants import ui_directory

UI_FILE = ui_directory + "/inventory/inventory_count.ui"


class InventoryCountGUI(Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.summary_id = None # no count is picked until the combo changes
		self.product_store = self.get_object('product_store')
		self.populate_stores()
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.handler_ids = list()
		for connection in (("inventory_counts_changed",
							self.count_summaries_changed),):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		self.window = self.get_object('window1')
		self.window.show_all()

	def populate_stores (self):
		c = DB.cursor()
		self.product_store.clear()
		c.execute("SELECT id::text, name || ' {' || ext_name || '}' "
							"FROM products WHERE (deleted, stock) = (False, True) "
							"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.product_store.append(row)
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
		c.close()
		DB.rollback()
	
	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)

	def count_summaries_changed (self, broadcaster, summary_id):
		'''some count summary was inserted or changed, here or on another machine.
		Only a close concerns this window, and only of the count it is holding: the
		closing window drops its own summary id before it commits, so the notify it
		causes itself falls through to the repopulate'''
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

	def count_closed_elsewhere (self, name = None):
		'''let go of a count that is no longer open. Reached from the broadcast and
		from a write the database refused, which on a machine that has lost its
		connection is the only warning there is going to be'''
		if name == None:
			c = DB.cursor()
			c.execute("SELECT name FROM inventory.count_summaries WHERE id = %s",
						(self.summary_id,))
			name = c.fetchone()[0]
			c.close()
			DB.rollback()
		self.reset_after_close ()
		self.show_message ("'%s' is closed, so this window has let it go."
							% GLib.markup_escape_text(name),
							"Anything counted into it since it was closed was not "
							"recorded. The count was closed either on another machine "
							"or in another window.",
							Gtk.MessageType.WARNING)

	def reset_after_close (self):
		'''a closed count leaves the combo because populate_stores filters on
		active, but clearing the model raises no usable changed signal, so summary_id
		would still point at it and the next scan would count into a closed count.
		Desensitising the box is what really stops that'''
		self.summary_id = None
		self.populate_stores ()
		self.get_object('widget_box').set_sensitive(False)
		self.get_object('inventory_rows_store').clear()
		self.get_object('missing_barcode_store').clear()

	def widget_focus_in_event (self, widget, event):
		GLib.idle_add(widget.select_region, 0, -1)

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id == None:
			return
		self.process_product(product_id)
		DB.rollback()

	def product_match_selected (self, completion, treemodel, treeiter):
		product_id = treemodel[treeiter][0]
		self.get_object('product_combo').set_active_id(product_id)

	def qty_edited (self, cellrenderertext, path, qty):
		store = self.get_object('inventory_rows_store')
		product_id = store[path][1]
		try: # the store column is an integer, so reject anything else up front
			qty = int(qty)
		except ValueError:
			return
		c = DB.cursor()
		c.execute("UPDATE inventory.count_rows SET qty = %s "
					"WHERE (product_id, count_summary_id) = (%s, %s) "
					"AND EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active)",
					(qty, product_id, self.summary_id, self.summary_id))
		refused = c.rowcount == 0
		c.close()
		DB.commit()
		if refused:
			# the only thing the guard can refuse is a count closed meanwhile, so
			# say so rather than leaving the edit to fail silently
			self.count_closed_elsewhere ()
			return
		store[path][0] = qty
		self.populate_inventory_count ()

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def delete_activated (self, menuitem):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		c = DB.cursor()
		c.execute("DELETE FROM inventory.count_rows "
					"WHERE (count_summary_id, product_id) = (%s, %s) "
					"AND EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active)",
					(self.summary_id, product_id, self.summary_id))
		c.close()
		DB.commit()
		self.populate_inventory_count ()

	def product_hub_activated (self, menuitem):
		model, path = self.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		product_id = model[path][1]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def barcode_entry_activated (self, entry):
		barcode = entry.get_text()
		entry.select_region(0, -1)
		if barcode == "":
			return
		c = DB.cursor()
		c.execute("SELECT id FROM products "
					"WHERE (barcode, deleted) = (%s, False)", (barcode,))
		for row in c.fetchall():
			self.process_product(row[0])
			break
		else:
			store = self.get_object('missing_barcode_store')
			for row in store:
				if row[1] == barcode:
					row[0] += 1
					break
			else:
				store.append([1, barcode])
		c.close()
		DB.rollback()

	def inventory_summaries_combo_changed (self, combobox):
		summary_id = combobox.get_active_id()
		if summary_id != None:
			self.summary_id = summary_id
			self.get_object('widget_box').set_sensitive(True)
			self.populate_inventory_count()

	def process_product(self, product_id):
		c = DB.cursor()
		c.execute("INSERT INTO inventory.count_rows AS cr "
					"(count_summary_id, product_id, qty, cost, retail) "
					"SELECT %s, "
						"%s, "
						"1, "
						"(SELECT cost FROM products WHERE id = %s), "
						"(SELECT product_retail_price(%s)) "
					"WHERE EXISTS (SELECT 1 FROM inventory.count_summaries "
						"WHERE id = %s AND active) "
					"ON CONFLICT (count_summary_id, product_id) "
					"DO UPDATE SET qty = cr.qty + 1 "
					"WHERE (cr.count_summary_id, cr.product_id) = (%s, %s)",
					(self.summary_id, product_id,  product_id, product_id,
					self.summary_id, self.summary_id, product_id))
		refused = c.rowcount == 0
		c.close()
		DB.commit()
		if refused:
			# a closed count is the only thing that proposes no row here, and a
			# scan that quietly counts nothing is worse than being interrupted
			self.count_closed_elsewhere ()
			return
		self.populate_inventory_count ()

	def populate_inventory_count (self):
		store = self.get_object("inventory_rows_store")
		store.clear()
		c = DB.cursor()
		c.execute("SELECT cr.qty, "
					"p.id, "
					"p.name || CASE WHEN p.deleted THEN ' (deleted)' ELSE '' END, "
					"cr.cost, "
					"cr.cost::text, "
					"cr.retail, "
					"cr.retail::text "
					"FROM inventory.count_rows AS cr "
					"JOIN products AS p ON p.id = cr.product_id "
					"WHERE count_summary_id = %s", (self.summary_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()
		self.calculate_totals()

	def inventory_summaries_activated (self, button):
		from inventory import inventory_summaries
		inventory_summaries.InventorySummariesGUI(self)

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

	def close_count_clicked (self, button):
		from inventory import inventorying
		# the combo hands out a string, while everything else calls a summary id
		# a number; close_count puts it in places where that difference shows
		summary_id = int(self.summary_id)
		c = DB.cursor()
		c.execute("SELECT cs.name, COALESCE(l.name, 'no location'), fy.name "
					"FROM inventory.count_summaries AS cs "
					"JOIN fiscal_years AS fy ON fy.id = cs.fiscal_id "
					"LEFT JOIN locations AS l ON l.id = cs.location_id "
					"WHERE cs.id = %s", (summary_id,))
		name, location_name, fiscal_name = c.fetchone()
		# counted against on hand at the same location. A count taken against the
		# wrong location shows up here as the whole of another location's stock
		c.execute("SELECT COALESCE(SUM(TRUNC(cr.qty)::int), 0), "
						"COALESCE((SELECT SUM(it.qty_in - it.qty_out) "
							"FROM inventory_transactions AS it "
							"WHERE it.location_id = cs.location_id), 0), "
						"COUNT(cr.product_id) "
					"FROM inventory.count_summaries AS cs "
					"LEFT JOIN inventory.count_rows AS cr "
						"ON cr.count_summary_id = cs.id "
					"WHERE cs.id = %s GROUP BY cs.id, cs.location_id", (summary_id,))
		counted, on_hand, products = c.fetchone()
		skipped = inventorying.uncorrectable_count_message (summary_id)
		c.close()
		DB.rollback()
		message = ("Correct the stock of every product counted in '%s' "
					"against %s, and close the count?\n\n"
					"Counted: %s units over %s products\n"
					"On hand at %s: %s units\n"
					"Fiscal year: %s\n\n"
					"A product counted at the quantity the books already show is "
					"left alone. A closed count cannot be reopened or counted into "
					"again." %
					(GLib.markup_escape_text(name),
					GLib.markup_escape_text(location_name), counted, products,
					GLib.markup_escape_text(location_name), on_hand,
					GLib.markup_escape_text(fiscal_name)))
		dialog = Gtk.MessageDialog(message_type = Gtk.MessageType.QUESTION,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup(message)
		if skipped != None:
			dialog.format_secondary_text("These counted products cannot be "
											"corrected and will be left alone:\n\n"
											+ self.shorten(skipped))
		result = dialog.run()
		dialog.destroy()
		if result != Gtk.ResponseType.YES:
			return
		try:
			corrected = inventorying.close_count (summary_id)
		except Exception as e:
			DB.rollback()
			self.show_message ("The count was not closed",
								GLib.markup_escape_text(str(e)))
			return
		# the summary id goes before the commit, not after: the commit delivers our
		# own notify synchronously, and a window still holding this id would take it
		# for a close by somebody else and show itself the warning meant for that.
		# Only the id can move, the rest of the reset repopulates and so ends in a
		# rollback, which here would throw the close away
		self.summary_id = None
		DB.commit()
		self.show_message ("Closed '%s'.\n\n%s of %s counted products corrected."
							% (GLib.markup_escape_text(name), corrected, products),
							None if skipped == None else
								("These counted products were left alone:\n\n"
								+ self.shorten(skipped)),
							Gtk.MessageType.INFO if skipped == None
								else Gtk.MessageType.WARNING)
		self.reset_after_close ()

	def shorten (self, message, limit = 20):
		'''a count can hold hundreds of products with no inventory account, and
		naming every one of them makes a dialog nothing can be read in'''
		lines = message.split("\n")
		if len(lines) <= limit:
			return message
		return "\n".join(lines[0:limit] + ["and %s more" % (len(lines) - limit,)])

	def calculate_totals(self):
		c = DB.cursor()
		c.execute("SELECT COALESCE(SUM(qty), 0)::text, "
					"COALESCE(SUM(cost * qty), 0.00)::money, "
					"COALESCE(SUM(retail * qty), 0.00)::money "
					"FROM inventory.count_rows "
					"WHERE count_summary_id = %s", (self.summary_id,))
		product_count, cost, retail = c.fetchone()
		c.close()
		self.get_object('label3').set_label(product_count)
		self.get_object('label7').set_label(cost)
		self.get_object('label5').set_label(retail)
		DB.rollback()






		