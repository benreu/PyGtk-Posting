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

UI_FILE = "src/reports/product_account_relationship.ui"

class ProductAccountRelationshipGUI:
	def __init__(self, main):

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		
		self.product_text = ''
		self.account_text = ''
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.product_account_store = self.builder.get_object('product_account_store')
		self.filtered_store = self.builder.get_object('product_account_filter')
		self.filtered_store.set_visible_func(self.filter_func)
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.populate_product_account_store ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		product_id = model[path][0]
		import product_hub 
		product_hub.ProductHubGUI(self.main, product_id)

	def account_search_changed (self, entry):
		self.account_text = entry.get_text()
		self.filtered_store.refilter()
		
	def product_search_changed (self, entry):
		self.product_text = entry.get_text()
		self.filtered_store.refilter()

	def filter_func (self, model, tree_iter, r):
		if self.product_text in model[tree_iter][1].lower():
			if self.account_text in model[tree_iter][2].lower():
				if self.account_text in model[tree_iter][3].lower():
					if self.account_text in model[tree_iter][4].lower():
						return True
		return False

	def populate_product_account_store (self):
		self.cursor.execute("SELECT p.id, p.name, "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.default_expense_account), ''), "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.revenue_account), ''), "
							"COALESCE((SELECT name FROM gl_accounts "
							"WHERE number = p.inventory_account), '') "
							"FROM products AS p ORDER BY p.name")
		for row in self.cursor.fetchall():
			product_id = row[0]
			product_name = row[1]
			expense_account = row[2]
			revenue_account = row[3]
			inventory_account = row[4]
			self.product_account_store.append([product_id, product_name, 
											expense_account, revenue_account, 
											inventory_account])


			


							