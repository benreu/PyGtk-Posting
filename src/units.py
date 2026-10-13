# units.py
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
from decimal import Decimal, InvalidOperation
from db_connection import DB
from constants import ui_directory

UI_FILE = ui_directory + "/units.ui"

#the id column is a string, because the reassign combo takes it as its
#id_column and GtkComboBox only reads a string there. A row that has not been
#inserted yet carries this instead of an id.
UNSAVED = '0'

#Every unit list is grouped by what the unit measures, and inside a group the
#smallest comes first -- inches before feet -- which the recorded ratios already
#say: a unit with no parent is its category's base and counts as one, anything
#else is the product of the ratios up its chain. Deriving it means the order can
#never disagree with the ratio, and recording "Yard = 3 Foot" is the whole of
#slotting a yard in after a foot. The depth cap is because a cycle is wrong data
#the database does not refuse, a CHECK being unable to see past its own row, and
#an uncapped recursion over one would never return.
UNIT_FACTOR = """
			WITH RECURSIVE chain (id, next_id, factor, depth) AS (
					SELECT id, parent_id, COALESCE(parent_qty, 1), 1 FROM units
				UNION ALL
					SELECT c.id, u.parent_id,
							c.factor * COALESCE(u.parent_qty, 1), c.depth + 1
						FROM chain AS c JOIN units AS u ON u.id = c.next_id
						WHERE c.depth < 10)
			SELECT id, max(factor) AS factor FROM chain GROUP BY id
"""
UNIT_ORDER = "ORDER BY u.category, f.factor, u.name"

def qty_text (value):
	'''parent_qty is numeric(12,4), so it comes back as 12.0000 where the grid
	should read 12. format () rather than str () because Decimal.normalize turns
	10 into 1E+1'''
	if value == None:
		return ''
	return format(Decimal(value).normalize(), 'f')

class UnitsGUI:
	def __init__(self, parent_callback = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		#whoever opened this window gets told once it is closed, so a combo
		#that was filled from the units table can be filled again
		self.parent_callback = parent_callback

		self.unit_store = self.builder.get_object('unit_store')
		self.populate_unit_store ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		if self.parent_callback != None:
			self.parent_callback ()

	def populate_unit_store (self):
		self.unit_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT u.id::text, u.name, u.standard, u.abbreviation, "
							"u.parent_qty, "
							"COALESCE(p.name, ''), COALESCE(p.id::text, ''), "
							"u.category "
							"FROM units AS u "
							"LEFT JOIN units AS p ON p.id = u.parent_id "
							"JOIN (" + UNIT_FACTOR + ") AS f ON f.id = u.id "
							"WHERE u.deleted = False " + UNIT_ORDER)
		for row in cursor.fetchall():
			self.unit_store.append([row[0], row[1], row[2], row[3],
									qty_text(row[4]), row[5], row[6], row[7]])
		cursor.close()
		DB.rollback()
		self.populate_parent_store ()
		self.populate_category_store ()

	def populate_parent_store (self):
		'''the model behind the "Of unit" combo column. The leading blank row is
		how a relationship is cleared. A column has one model for every row, so
		it cannot leave out the unit being edited: parent_combo_changed is what
		refuses a unit as its own parent'''
		store = self.builder.get_object('parent_store')
		store.clear()
		store.append(['', '—'])
		cursor = DB.cursor()
		cursor.execute("SELECT u.id::text, u.name FROM units AS u "
							"JOIN (" + UNIT_FACTOR + ") AS f ON f.id = u.id "
							"WHERE u.deleted = False " + UNIT_ORDER)
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

	def populate_category_store (self):
		'''the categories already in use, so they keep being spelled the same
		way. The renderer carries an entry too, which is how a new one is made'''
		store = self.builder.get_object('category_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT DISTINCT category FROM units "
							"WHERE deleted = False AND category != '' "
							"ORDER BY category")
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

	def new_clicked (self, button):
		iter_ = self.unit_store.append([UNSAVED, 'New unit', False, '',
										'', '', '', ''])
		self.builder.get_object('treeview-selection1').select_iter(iter_)

	def unit_combo_changed (self, combo):
		self.builder.get_object('button2').set_sensitive(True)

	def name_edited (self, text_renderer, path, text):
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][1] = text
		self.save (iter_)

	def abbreviation_edited (self, text_renderer, path, text):
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][3] = text.strip()
		self.save (iter_)

	def category_edited (self, renderer, path, text):
		"""typed, or picked from the list and then committed"""
		self.set_category (path, text)

	def category_combo_changed (self, combo, path, tree_iter):
		"""picked from the list. The renderer has an entry, so which of the two
		signals arrives depends on how the choice was made; both land here, and
		writing the same category twice costs nothing"""
		store = self.builder.get_object('category_store')
		self.set_category (path, store[tree_iter][0])

	def set_category (self, path, text):
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][7] = text.strip()
		self.save (iter_)

	def parent_qty_edited (self, spin_renderer, path, text):
		if self.unit_store[path][6] == '':
			#parent_qty without a parent is what unit_parent_qty_together
			#refuses, and a number on its own says nothing anyway
			self.show_message ("Choose the unit this one is measured in first.")
			return
		try:
			qty = Decimal(text)
		except InvalidOperation:
			self.show_message ("'%s' is not a number." % text)
			return
		if qty <= 0:
			self.show_message ("A unit cannot be worth none of another one.")
			return
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][4] = qty_text(qty)
		self.save (iter_)

	def parent_combo_changed (self, combo, path, tree_iter):
		parent_store = self.builder.get_object('parent_store')
		parent_id = parent_store[tree_iter][0]
		parent_name = parent_store[tree_iter][1]
		unit_id = self.unit_store[path][0]
		if parent_id != '' and unit_id != UNSAVED:
			if parent_id == unit_id:
				self.show_message ("A unit cannot be measured in itself.")
				return
			if self.would_cycle (unit_id, parent_id):
				self.show_message ("'%s' is already measured in '%s', so this "
									"would run in a circle."
									% (parent_name, self.unit_store[path][1]))
				return
		iter_ = self.unit_store.get_iter(path)
		self.unit_store[path][6] = parent_id
		if parent_id == '':
			self.unit_store[path][5] = ''
			self.unit_store[path][4] = ''
		else:
			self.unit_store[path][5] = parent_name
		self.save (iter_)

	def would_cycle (self, unit_id, parent_id):
		'''walk up from the proposed parent: if this unit turns up on the way,
		the relationship runs in a circle. A CHECK cannot see past its own row,
		so the database only refuses a unit that is its own parent and this has
		to catch the longer way round. The seen set is in case the table already
		holds a cycle, put there through the SQL window'''
		cursor = DB.cursor()
		seen = set()
		walker = parent_id
		cycles = False
		while walker != None and walker not in seen:
			if walker == str(unit_id):
				cycles = True
				break
			seen.add(walker)
			cursor.execute("SELECT parent_id::text FROM units WHERE id = %s",
							(walker,))
			row = cursor.fetchone()
			walker = row[0] if row != None else None
		cursor.close()
		DB.rollback()
		return cycles

	def save (self, iter_):
		row_id = self.unit_store[iter_][0]
		name = self.unit_store[iter_][1]
		abbreviation = self.unit_store[iter_][3]
		category = self.unit_store[iter_][7]
		parent_id = self.unit_store[iter_][6] or None
		parent_qty = self.unit_store[iter_][4] or None
		#unit_parent_qty_together wants both or neither: naming a parent with no
		#ratio yet means one of it, and clearing the parent clears the ratio
		if parent_id == None:
			parent_qty = None
		elif parent_qty == None:
			parent_qty = '1'
		self.unit_store[iter_][4] = qty_text(parent_qty)
		cursor = DB.cursor()
		try:
			if row_id == UNSAVED:
				cursor.execute("INSERT INTO units "
									"(name, abbreviation, category, "
									"parent_id, parent_qty) "
									"VALUES (%s, %s, %s, %s, %s) "
									"RETURNING id::text",
									(name, abbreviation, category,
									parent_id, parent_qty))
				self.unit_store[iter_][0] = cursor.fetchone()[0]
			else:
				cursor.execute("UPDATE units SET "
									"(name, abbreviation, category, parent_id, "
									"parent_qty, date_edited) = "
									"(%s, %s, %s, %s, %s, CURRENT_DATE) "
									"WHERE id = %s",
									(name, abbreviation, category, parent_id,
									parent_qty, row_id))
		except Exception as e:
			#units.name is UNIQUE, which the lookup tables this window is
			#modelled on are not, so a repeated name aborts the transaction.
			#Reloading is what puts the row back to what is actually stored,
			#rather than leaving one on screen that was never written.
			DB.rollback()
			cursor.close()
			self.show_message ("That unit could not be saved, which probably "
								"means another unit already has that name.",
								str(e))
			self.populate_unit_store ()
			return
		cursor.close()
		DB.commit()
		self.populate_parent_store ()
		self.populate_category_store ()

	def default_toggled (self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		if self.unit_store[selected_path][0] == UNSAVED:
			#there is no row yet to carry the flag, and the other units must
			#not be cleared on behalf of one that does not exist: every product
			#INSERT path resolves its unit through this flag
			self.show_message ("Give this unit a name before making it the "
								"standard one.")
			return
		cursor = DB.cursor()
		for row in self.unit_store:
			if row.path == selected_path:
				row[2] = True
				cursor.execute("UPDATE units SET standard = True "
									"WHERE id = %s", (row[0],))
			else:
				row[2] = False
				cursor.execute("UPDATE units SET standard = False "
									"WHERE id = %s", (row[0],))
		cursor.close()
		DB.commit()

	def delete_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		current_unit_id = model[path][0]
		if current_unit_id == UNSAVED:
			self.unit_store.remove(self.unit_store.get_iter(path[0]))
			return
		if model[path][2] == True:
			#new products take their unit from the standard flag, so it has to
			#stay on a unit that is still there to be named
			self.show_message ("That is the standard unit. Make a different "
								"unit standard before deleting this one.")
			return
		child = self.one_child_of (current_unit_id)
		if child != None:
			#parent_id is ON DELETE RESTRICT too, so the probe below would fail
			#on this as well, and the dialog it opens offers to move products,
			#which would do nothing for a unit measured in this one
			self.show_message ("'%s' is measured in this unit, so it cannot be "
								"deleted. Clear that relationship first."
								% child)
			return
		cursor = DB.cursor()
		try:
			#products.unit is ON DELETE RESTRICT, so this asks the database
			#whether anything is using the unit and throws the answer away. A
			#unit that is in use can only ever be retired, never removed, since
			#the products overview still joins units to show its name.
			cursor.execute("DELETE FROM units WHERE id = %s",
								(current_unit_id,))
			DB.rollback()
			cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
								(current_unit_id,))
		except Exception as e:
			DB.rollback()
			self.builder.get_object('label3').set_label(str(e))
			self.populate_reassign_store (current_unit_id)
			dialog = self.builder.get_object('dialog1')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				unit_id = self.builder.get_object('combobox1').get_active_id()
				if unit_id != None:
					cursor.execute("UPDATE products SET unit = %s "
										"WHERE unit = %s",
										(unit_id, current_unit_id))
					cursor.execute("UPDATE units SET deleted = True "
										"WHERE id = %s", (current_unit_id,))
		cursor.close()
		DB.commit()
		self.builder.get_object('button2').set_sensitive(False)
		self.populate_unit_store ()

	def one_child_of (self, unit_id):
		'''the name of some live unit measured in this one, or None'''
		cursor = DB.cursor()
		cursor.execute("SELECT name FROM units "
							"WHERE parent_id = %s AND deleted = False LIMIT 1",
							(unit_id,))
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		return row[0] if row != None else None

	def populate_reassign_store (self, current_unit_id):
		'''the dialog gets its own store rather than sharing the treeview's,
		because the unit being retired cannot stand in for itself and a row
		that has not been inserted yet has no id to move the products onto'''
		store = self.builder.get_object('reassign_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT u.id::text, u.name FROM units AS u "
							"JOIN (" + UNIT_FACTOR + ") AS f ON f.id = u.id "
							"WHERE u.deleted = False AND u.id != %s "
							+ UNIT_ORDER, (current_unit_id,))
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

	def show_message (self, message, secondary = None):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		if secondary != None:
			dialog.format_secondary_text (secondary)
		dialog.run()
		dialog.destroy()
