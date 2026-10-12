# products_to_reorder.py
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

from gi.repository import Gtk
from db_connection import DB
from constants import ui_directory

UI_FILE = ui_directory + "/reports/products_to_reorder.ui"


class ProductsToReorderGUI (Gtk.Builder):
	def __init__ (self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.store = self.get_object("products_to_reorder_store")
		self.populate_reorder_store ()
		self.window = self.get_object("window")
		self.window.show_all()

	def populate_reorder_store (self):
		'''a product is listed once its stock has fallen to the floor somebody
		set for it. min_inventory is a per product column with no location of
		its own, so what it is weighed against is the company's whole stock,
		the same figure the product list shows. A floor of zero is the default
		nobody has touched, so those products are not a list of anything'''
		self.store.clear()
		c = DB.cursor()
		c.execute("SELECT p.id, "
						"p.name, "
						"p.ext_name, "
						"oh.qty, "
						"p.min_inventory, "
						"p.reorder_qty, "
						"COALESCE(vpn.vendor_id, 0), "
						"COALESCE(v.name, ''), "
						"'' "
					"FROM products AS p "
					"JOIN LATERAL (SELECT COALESCE(SUM(it.qty_in - it.qty_out), 0) "
							"AS qty FROM inventory_transactions AS it "
							"WHERE it.product_id = p.id) AS oh ON True "
					# the vendor the product is usually bought from, which is
					# the one the order would go to
					"LEFT JOIN LATERAL (SELECT vendor_id "
							"FROM vendor_product_numbers "
							"WHERE product_id = p.id AND deleted = False "
							"ORDER BY id LIMIT 1) AS vpn ON True "
					"LEFT JOIN contacts AS v ON v.id = vpn.vendor_id "
					"WHERE (p.deleted, p.stock, p.purchasable) = "
						"(False, True, True) "
					"AND p.min_inventory > 0 "
					"AND oh.qty <= p.min_inventory "
					"ORDER BY p.name, p.ext_name")
		for row in c.fetchall():
			self.store.append(row)
		c.close()
		DB.rollback()

	def reload_clicked (self, button):
		self.populate_reorder_store ()

	def product_hub_activated (self, menuitem):
		model, path = self.get_object('reorder_selection').get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_hub
		product_hub.ProductHubGUI(product_id)

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def add_to_po_clicked (self, button):
		'''ordering goes the way the manufacturing project window orders a
		part: onto the vendor's open order if there is one, else onto a new
		draft. The quantity ordered is the reorder quantity, what the product
		is meant to be bought in, not the shortfall against the floor'''
		selection = self.get_object('reorder_selection')
		model, paths = selection.get_selected_rows()
		if not paths:
			return
		import purchase_order_window
		for path in paths:
			tree_iter = model.get_iter(path)
			product_id = model[tree_iter][0]
			product_name = model[tree_iter][1]
			order_qty = model[tree_iter][5]
			vendor_id = model[tree_iter][6]
			if vendor_id == 0:
				self.show_message("'%s' has no vendor, so there is nowhere to "
									"order it from. Give it a vendor product "
									"number first." % product_name)
				continue
			if order_qty <= 0:
				self.show_message("'%s' has no reorder quantity set, so there "
									"is nothing to order." % product_name)
				continue
			po_id = purchase_order_window.find_or_create_open_po(vendor_id)
			existing = purchase_order_window.find_po_item(po_id, product_id)
			if existing:
				po_item_id, existing_qty = existing
				new_qty = existing_qty + order_qty
				if not self.confirm_update_po_item(product_name, existing_qty,
													new_qty):
					continue
				purchase_order_window.update_po_item_qty(po_item_id, new_qty)
			else:
				purchase_order_window.add_manufacturing_item_to_po(po_id,
													product_id, order_qty)
			model[tree_iter][8] = "Added"

	def confirm_update_po_item (self, product_name, existing_qty, new_qty):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.QUESTION,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup("%s is already on this vendor's purchase order "
							"(qty %s).\nUpdate the existing line to qty %s "
							"instead of adding a new one?"
							% (product_name, existing_qty, new_qty))
		response = dialog.run()
		dialog.destroy()
		return response == Gtk.ResponseType.YES

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
