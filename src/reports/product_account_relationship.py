# product_account_relationship.py
#
# Copyright (C) 2018 - reuben
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/product_account_relationship.ui"

class ProductAccountRelationshipGUI:
	def __init__(self):
		
		self.product_text = ''
		self.expense_text = ''
		self.revenue_text = ''
		self.inventory_text = ''
		self.p_o = None
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.product_account_store = self.builder.get_object('product_account_store')
		self.filtered_store = self.builder.get_object('product_account_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_product_account_store ()

	def destroy (self, widget):
		self.cursor.close()

	def treeview_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.show_external_product_window(model, path)

	def show_external_product_window (self, model, path):
		product_id = model[path][0]
		if self.p_o == None or not self.p_o.window:
			import products_overview
			self.p_o = products_overview.ProductsOverviewGUI(product_id)
		self.p_o.product_id = product_id
		self.p_o.select_product()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_hub 
		product_hub.ProductHubGUI(product_id)

	def expense_search_changed (self, entry):
		self.expense_text = entry.get_text()
		self.filtered_store.refilter()

	def revenue_search_changed (self, entry):
		self.revenue_text = entry.get_text()
		self.filtered_store.refilter()

	def inventory_search_changed (self, entry):
		self.inventory_text = entry.get_text()
		self.filtered_store.refilter()
		
	def product_search_changed (self, entry):
		self.product_text = entry.get_text()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		if self.product_text in model[tree_iter][1].lower():
			if self.expense_text in model[tree_iter][2].lower():
				if self.revenue_text in model[tree_iter][3].lower():
					if self.inventory_text in model[tree_iter][4].lower():
						return True
		return False

	def reload_button_clicked (self, button):
		self.populate_product_account_store ()

	def populate_product_account_store (self):
		self.product_account_store.clear()
		self.cursor.execute("SELECT p.id, p.name, "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.default_expense_account), ''), "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.revenue_account), ''), "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.inventory_account), '') "
							"FROM products AS p ORDER BY p.name")
		for row in self.cursor.fetchall():
			self.product_account_store.append(row)
		DB.rollback()





