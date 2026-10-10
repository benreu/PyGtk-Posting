# product_name_cleanup.py
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

from gi.repository import Gtk, Gdk
from db_connection import DB
from constants import ui_directory, PRODUCT_LOCK_CLASSID
import product_name_rules

UI_FILE = ui_directory + "/admin/product_name_cleanup.ui"

AUTO_COLOR = Gdk.RGBA(0, 0, 0, 1)
REVIEW_COLOR = Gdk.RGBA(0.6, 0.35, 0, 1)   #amber: a real finding, but check it

class ProductNameCleanupGUI ():
	def __init__ (self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.fix_store = self.builder.get_object('fix_store')
		self.rule_store = self.builder.get_object('rule_store')
		self.word_order_store = self.builder.get_object('word_order_store')
		self.duplicate_store = self.builder.get_object('duplicate_store')
		self.populating = False

		self.window = self.builder.get_object('window')
		self.window.show_all()
		self.load()

	def destroy (self, widget):
		pass

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

	####################### opting in

	def load (self):
		'''Nothing is scanned until this database has rules. The rules table is
		created on request rather than by the version upgrade, so a database
		can adopt this whenever it suits.'''
		infobar = self.builder.get_object('setup_infobar')
		if not product_name_rules.installed():
			infobar.show()
			self.set_tabs_sensitive(False)
			return
		infobar.hide()
		self.set_tabs_sensitive(True)
		self.sync_rules()
		self.ruleset = product_name_rules.load_rules()
		self.populate_rule_store()
		self.scan()

	def sync_rules (self):
		'''Re-run the install script on a database that has opted in already.

		This feature sits outside the version upgrade mechanism on purpose, so
		opening this window is the only moment a later release has to hand a
		database rules that did not exist when it opted in. The script is
		idempotent and inserts nothing over an existing row, so this neither
		revives a rule somebody deactivated nor undoes an edit made in the
		rules tab. A database whose user cannot alter the table still works
		with the rules it has, which is why this reports and carries on.'''
		try:
			product_name_rules.install()
		except Exception as e:
			DB.rollback()
			self.show_message("The rules table could not be brought up to "
								"date, so rules added by a later release may "
								"be missing:\n\n%s" % e)

	def set_tabs_sensitive (self, sensitive):
		self.builder.get_object('notebook').set_sensitive(sensitive)

	def setup_clicked (self, button):
		try:
			product_name_rules.install()
		except Exception as e:
			DB.rollback()
			self.show_message("Could not create the rules table:\n\n%s" % e)
			return
		self.load()

	####################### scanning

	def scan (self):
		'''One pass over the catalog, filling the three report stores.'''
		self.fix_store.clear()
		self.word_order_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name FROM products "
							"WHERE deleted = False ORDER BY name")
		rows = cursor.fetchall()
		cursor.close()
		DB.rollback()
		auto_names = self.ruleset.auto_rule_names()
		for product_id, name in rows:
			auto_labels = list()
			for finding in self.ruleset.findings(name):
				if finding.kind == product_name_rules.AUTO_SAFE:
					if finding.label not in auto_labels:
						auto_labels.append(finding.label)
				elif finding.kind == product_name_rules.REVIEW:
					#what this one rule alone would do, on top of the auto
					#safe fixes, so the row stands on its own
					suggested = self.ruleset.apply(name,
												auto_names + [finding.rule])
					self.fix_store.append([product_id, name, suggested,
											finding.label, finding.rule,
											False, True, REVIEW_COLOR])
				elif finding.kind == product_name_rules.REPORT:
					self.word_order_store.append([product_id, name])
			if auto_labels:
				#one row for the whole auto safe subset: they are mechanical,
				#so there is nothing to choose between them
				self.fix_store.append([product_id, name,
										self.ruleset.normalize(name),
										', '.join(auto_labels), '',
										True, True, AUTO_COLOR])
		self.populate_duplicate_store()
		self.update_fix_summary()

	def populate_duplicate_store (self):
		self.duplicate_store.clear()
		cursor = DB.cursor()
		cursor.execute("WITH collision AS "
							"(SELECT lower(btrim(regexp_replace("
								"name, '\\s+', ' ', 'g'))) AS key "
							"FROM products WHERE deleted = False "
							"GROUP BY key HAVING count(*) > 1) "
						"SELECT p.id, p.name, c.key FROM products AS p "
						"JOIN collision AS c "
							"ON c.key = lower(btrim(regexp_replace("
								"p.name, '\\s+', ' ', 'g'))) "
						"WHERE p.deleted = False "
						"ORDER BY c.key, p.id")
		for row in cursor.fetchall():
			self.duplicate_store.append(row)
		cursor.close()
		DB.rollback()

	def update_fix_summary (self):
		selected = len([row for row in self.fix_store if row[5] == True])
		products = len(set([row[0] for row in self.fix_store if row[5] == True]))
		label = self.builder.get_object('fix_summary_label')
		label.set_label("%s of %s suggestions selected, "
						"affecting %s products"
						% (selected, len(self.fix_store), products))
		self.builder.get_object('apply_button').set_sensitive(selected > 0)

	####################### the fixes tab

	#The current name column is editable with no "edited" handler connected on
	#purpose. It is editable only so the cell can be clicked into: a text
	#cursor is the only way to see where a name actually ends, which is the
	#whole question with a trailing or a doubled space. With nothing listening,
	#Gtk discards whatever is typed and the cell redraws from the store, so the
	#column cannot rename anything. Renaming goes through the Fix column and
	#the Apply button. Do not connect a handler here.

	def apply_renderer_toggled (self, cell_renderer, path):
		self.fix_store[path][5] = not cell_renderer.get_active()
		self.update_fix_summary()

	def refresh_clicked (self, button):
		'''Re-read the rules and scan again. The Rules tab already rescans
		when it saves an edit, but the rules can also change from another
		session or straight from SQL, and the products themselves move under
		this window, so there has to be a way to ask again. Goes through
		load() rather than scan() so a database that has had the rules set up
		elsewhere since this window opened stops offering the setup bar.'''
		self.load()

	def select_all_clicked (self, button):
		for row in self.fix_store:
			if row[6] == True:
				row[5] = True
		self.update_fix_summary()

	def unselect_all_clicked (self, button):
		for row in self.fix_store:
			row[5] = False
		self.update_fix_summary()

	def apply_clicked (self, button):
		'''Applies exactly the rules that are ticked, per product. A product
		can have both an auto safe row and a review row, so the rules are
		gathered first and the name is rewritten once.'''
		auto_names = self.ruleset.auto_rule_names()
		wanted = dict()
		original = dict()
		for row in self.fix_store:
			if row[5] != True:
				continue
			product_id = row[0]
			original[product_id] = row[1]
			rules = wanted.setdefault(product_id, list())
			if row[4] == '':
				rules += auto_names
			else:
				rules.append(row[4])
		locked_out = list()
		cursor = DB.cursor()
		for product_id, rules in wanted.items():
			name = original[product_id]
			new_name = self.ruleset.apply(name, rules)
			if new_name == name:
				continue
			cursor.execute("SELECT pg_try_advisory_lock(%s, %s)",
							(PRODUCT_LOCK_CLASSID, product_id))
			if cursor.fetchone()[0] == False:
				#somebody else has this product open; skip it rather than
				#overwrite the name under them
				locked_out.append(name)
				continue
			cursor.execute("UPDATE products SET name = %s WHERE id = %s",
							(new_name, product_id))
			cursor.execute("SELECT pg_advisory_unlock(%s, %s)",
							(PRODUCT_LOCK_CLASSID, product_id))
		cursor.close()
		DB.commit()
		if locked_out:
			self.show_message("These products are being edited by somebody "
								"else and were left alone:\n\n%s"
								% '\n'.join(locked_out))
		self.scan()

	####################### the rules tab

	def populate_rule_store (self):
		self.populating = True
		self.rule_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name, rule_type, kind, label, variants, "
							"canonical, sort_order, active "
							"FROM product_name_rules "
							"WHERE deleted = False "
							"ORDER BY sort_order, name")
		for row in cursor.fetchall():
			self.rule_store.append(row)
		cursor.close()
		DB.rollback()
		self.populating = False
		self.builder.get_object('rule_summary_label').set_label(
						"%s rules" % len(self.rule_store))

	def rule_changed (self, path):
		'''Save the edited row, then rescan so the Fixes tab shows what the
		rule actually does before anything is applied.'''
		if self.populating == True:
			return
		row = self.rule_store[path]
		cursor = DB.cursor()
		try:
			if row[0] == 0:
				cursor.execute("INSERT INTO product_name_rules "
									"(name, rule_type, kind, label, variants, "
									"canonical, sort_order, active) "
									"VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
									"RETURNING id",
									(row[1], row[2], row[3], row[4], row[5],
									row[6], row[7], row[8]))
				row[0] = cursor.fetchone()[0]
			else:
				cursor.execute("UPDATE product_name_rules SET "
									"(name, rule_type, kind, label, variants, "
									"canonical, sort_order, active) = "
									"(%s, %s, %s, %s, %s, %s, %s, %s) "
									"WHERE id = %s",
									(row[1], row[2], row[3], row[4], row[5],
									row[6], row[7], row[8], row[0]))
		except Exception as e:
			DB.rollback()
			cursor.close()
			self.show_message("Could not save the rule:\n\n%s" % e)
			self.populate_rule_store()
			return
		cursor.close()
		DB.commit()
		self.ruleset = product_name_rules.load_rules()
		self.scan()

	def rule_name_edited (self, cell_renderer, path, text):
		self.rule_store[path][1] = text
		self.rule_changed(path)

	def rule_type_edited (self, cell_renderer, path, text):
		self.rule_store[path][2] = text
		self.rule_changed(path)

	def rule_kind_edited (self, cell_renderer, path, text):
		self.rule_store[path][3] = text
		self.rule_changed(path)

	def rule_label_edited (self, cell_renderer, path, text):
		self.rule_store[path][4] = text
		self.rule_changed(path)

	def rule_variants_edited (self, cell_renderer, path, text):
		self.rule_store[path][5] = text
		self.rule_changed(path)

	def rule_canonical_edited (self, cell_renderer, path, text):
		self.rule_store[path][6] = text
		self.rule_changed(path)

	def rule_sort_order_edited (self, cell_renderer, path, text):
		try:
			self.rule_store[path][7] = int(text)
		except ValueError:
			return
		self.rule_changed(path)

	def rule_active_toggled (self, cell_renderer, path):
		self.rule_store[path][8] = not cell_renderer.get_active()
		self.rule_changed(path)

	def new_rule_clicked (self, button):
		'''Appended with id 0 and saved on the first edit, the same way the
		other lookup table editors in this app do it.'''
		order = 0
		for row in self.rule_store:
			order = max(order, row[7])
		iter_ = self.rule_store.append([0, 'new_rule', 'unit', 'auto',
										'Unit case', '', '', order + 10, True])
		self.builder.get_object('rule_selection').select_iter(iter_)

	def delete_rule_clicked (self, button):
		'''Soft deleted, never removed: the seed in db/product_name_rules.sql
		is idempotent on name, so a hard delete would come back the next time
		anybody ran the setup.'''
		model, iter_ = self.builder.get_object('rule_selection').get_selected()
		if iter_ == None:
			return
		rule_id = model[iter_][0]
		if rule_id != 0:
			cursor = DB.cursor()
			cursor.execute("UPDATE product_name_rules SET "
								"(active, deleted) = (False, True) "
								"WHERE id = %s", (rule_id,))
			cursor.close()
			DB.commit()
		self.populate_rule_store()
		self.ruleset = product_name_rules.load_rules()
		self.scan()

	####################### the report tabs

	#Neither of these tabs suggests a fix, because reordering a name or
	#choosing between two collisions is a judgement call. What the user needs
	#instead is the history: which of the two products the invoices and orders
	#actually point at, and whether a brand first name is the one in use. So
	#both lists open the product hub on the row that was picked. The id is
	#column 0 of both stores.

	def _popup_product_hub (self, menu_id, event):
		if event.button == 3:
			self.builder.get_object(menu_id).popup_at_pointer()

	def _open_product_hub (self, selection_id):
		selection = self.builder.get_object(selection_id)
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		import product_hub
		product_hub.ProductHubGUI(model[paths[0]][0])

	def duplicate_treeview_button_release_event (self, treeview, event):
		self._popup_product_hub('duplicate_menu', event)

	def duplicate_product_hub_activated (self, menuitem):
		self._open_product_hub('duplicate_selection')

	def word_order_treeview_button_release_event (self, treeview, event):
		self._popup_product_hub('word_order_menu', event)

	def word_order_product_hub_activated (self, menuitem):
		self._open_product_hub('word_order_selection')

	def page_switched (self, notebook, page, page_number):
		pass
