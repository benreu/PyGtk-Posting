import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase  # pins Gtk to 3.0, so it is imported first
from gi.repository import Gtk

class UnitsWindowTest(DBTestCase):
	def setUp(self):
		super().setUp()
		import units
		self.units = units
		self.gui = units.UnitsGUI()

	def names(self):
		return [row[1] for row in self.gui.unit_store]

	def new_unit(self, name, standard = False):
		'''committed, because the window rolls back: delete_clicked probes with
		a real DELETE and throws the answer away, and save () rolls back a name
		the database refused'''
		unit_id = self.one("INSERT INTO units (name, standard) "
							"VALUES (%s, %s) RETURNING id", (name, standard))
		self.DB.commit()
		self.gui.populate_unit_store ()
		return str(unit_id)

	def path_of(self, unit_id):
		for row in self.gui.unit_store:
			if row[0] == str(unit_id):
				return str(row.path)
		self.fail('unit %s not listed' % unit_id)

	def select(self, unit_id):
		selection = self.gui.builder.get_object('treeview-selection1')
		selection.select_path(self.path_of(unit_id))

	def deleted(self, unit_id):
		return self.one("SELECT deleted FROM units WHERE id = %s", (unit_id,))

	def test_store_lists_only_the_live_units(self):
		unit_id = self.new_unit('Reel')
		self.assertIn('Reel', self.names())
		self.cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
							(unit_id,))
		self.DB.commit()
		self.gui.populate_unit_store ()
		self.assertNotIn('Reel', self.names())

	def test_naming_a_new_row_inserts_it(self):
		self.gui.new_clicked(None)
		path = str(len(self.gui.unit_store) - 1)
		self.assertEqual(self.gui.unit_store[path][0], self.units.UNSAVED)
		self.gui.name_edited(None, path, 'Reel')
		unit_id = self.gui.unit_store[path][0]
		self.assertNotEqual(unit_id, self.units.UNSAVED)
		self.assertEqual(self.one("SELECT name FROM units WHERE id = %s",
									(unit_id,)), 'Reel')

	def test_renaming_a_unit_updates_it(self):
		unit_id = self.new_unit('Before')
		self.gui.name_edited(None, self.path_of(unit_id), 'After')
		self.assertEqual(self.one("SELECT name FROM units WHERE id = %s",
									(unit_id,)), 'After')

	def test_a_duplicate_name_is_refused_and_the_row_reverts(self):
		'''units.name is UNIQUE, which the lookup tables this window is modelled
		on are not, so this is the one path the template did not have to handle'''
		unit_id = self.new_unit('Reel')
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.name_edited(None, self.path_of(unit_id), 'Piece')
		show_message.assert_called_once()
		self.assertEqual(self.one("SELECT name FROM units WHERE id = %s",
									(unit_id,)), 'Reel')
		self.assertIn('Reel', self.names())

	def test_a_duplicate_name_on_a_new_row_leaves_nothing_behind(self):
		before = self.one("SELECT count(*) FROM units")
		self.gui.new_clicked(None)
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.name_edited(None, str(len(self.gui.unit_store) - 1), 'Piece')
		show_message.assert_called_once()
		self.assertEqual(self.one("SELECT count(*) FROM units"), before)

	def test_making_a_unit_standard_clears_the_others(self):
		unit_id = self.new_unit('Reel')
		self.gui.default_toggled(None, self.path_of(unit_id))
		self.assertEqual(self.one("SELECT standard FROM units WHERE id = %s",
									(unit_id,)), True)
		self.assertEqual(self.one("SELECT count(*) FROM units "
									"WHERE standard = True"), 1)

	def test_an_unsaved_row_cannot_be_made_standard(self):
		'''it has no id to carry the flag, and clearing the others on its behalf
		would leave every product INSERT path with no unit to resolve'''
		before = self.one("SELECT id FROM units WHERE standard = True")
		self.gui.new_clicked(None)
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.default_toggled(None, str(len(self.gui.unit_store) - 1))
		show_message.assert_called_once()
		self.assertEqual(self.one("SELECT id FROM units WHERE standard = True"),
							before)

	def test_an_unsaved_row_is_dropped_rather_than_deleted(self):
		before = self.one("SELECT count(*) FROM units")
		self.gui.new_clicked(None)
		rows = len(self.gui.unit_store)
		self.gui.builder.get_object('treeview-selection1').select_path(
									str(rows - 1))
		self.gui.delete_clicked(None)
		self.assertEqual(len(self.gui.unit_store), rows - 1)
		self.assertEqual(self.one("SELECT count(*) FROM units"), before)

	def test_an_unused_unit_is_retired(self):
		unit_id = self.new_unit('Reel')
		self.select(unit_id)
		self.gui.delete_clicked(None)
		self.assertEqual(self.deleted(unit_id), True)
		self.assertNotIn('Reel', self.names())

	def test_the_standard_unit_cannot_be_deleted(self):
		unit_id = self.one("SELECT id::text FROM units WHERE standard = True")
		self.gui.populate_unit_store ()
		self.select(unit_id)
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.delete_clicked(None)
		show_message.assert_called_once()
		self.assertEqual(self.deleted(unit_id), False)

	def use_unit(self, unit_id):
		self.cursor.execute("UPDATE products SET unit = %s WHERE id = 19",
							(unit_id,))
		self.DB.commit()

	def answer_dialog(self, response, pick = None):
		'''the reassign store is filled only once the FK error has been caught,
		so the choice has to be made from inside run ()'''
		def run(dialog):
			if pick != None:
				self.gui.builder.get_object('combobox1').set_active_id(pick)
			return response
		return mock.patch('gi.repository.Gtk.Dialog.run', new = run)

	def test_a_used_unit_moves_its_products_then_retires(self):
		unit_id = self.new_unit('Reel')
		target = self.one("SELECT id::text FROM units WHERE standard = True")
		self.use_unit(unit_id)
		self.select(unit_id)
		with self.answer_dialog(Gtk.ResponseType.ACCEPT, target):
			self.gui.delete_clicked(None)
		self.assertEqual(str(self.one("SELECT unit FROM products "
										"WHERE id = 19")), target)
		self.assertEqual(self.deleted(unit_id), True)

	def test_a_cancelled_delete_leaves_the_unit_and_its_products_alone(self):
		unit_id = self.new_unit('Reel')
		self.use_unit(unit_id)
		self.select(unit_id)
		with self.answer_dialog(Gtk.ResponseType.CANCEL):
			self.gui.delete_clicked(None)
		self.assertEqual(self.deleted(unit_id), False)
		self.assertEqual(str(self.one("SELECT unit FROM products "
										"WHERE id = 19")), unit_id)

	def test_the_unit_being_retired_is_not_offered_as_its_own_replacement(self):
		unit_id = self.new_unit('Reel')
		self.use_unit(unit_id)
		self.select(unit_id)
		with self.answer_dialog(Gtk.ResponseType.CANCEL):
			self.gui.delete_clicked(None)
		offered = [row[0] for row in self.gui.builder.get_object('reassign_store')]
		self.assertNotIn(unit_id, offered)
		self.assertNotEqual(offered, [])

	def parent_iter(self, unit_id):
		for row in self.gui.builder.get_object('parent_store'):
			if row[0] == str(unit_id):
				return row.iter
		self.fail('unit %s is not offered in the combo' % unit_id)

	def blank_parent_iter(self):
		"""the leading row, which is how a relationship is cleared"""
		return self.gui.builder.get_object('parent_store')[0].iter

	def set_parent(self, unit_id, parent_id):
		self.gui.parent_combo_changed(None, self.path_of(unit_id),
										self.parent_iter(parent_id))

	def named(self, name):
		return self.one("SELECT id::text FROM units WHERE name = %s", (name,))

	def relationship(self, unit_id):
		"""(parent name, ratio) as stored"""
		self.cursor.execute("SELECT p.name, u.parent_qty FROM units AS u "
							"LEFT JOIN units AS p ON p.id = u.parent_id "
							"WHERE u.id = %s", (unit_id,))
		return self.cursor.fetchone()

	def test_the_seeded_abbreviations_and_ratios_landed(self):
		self.assertEqual(self.one("SELECT abbreviation FROM units "
									"WHERE name = 'Piece'"), 'pc')
		self.assertEqual(self.relationship(self.named('Foot')),
							('Inch', Decimal('12')))
		self.assertEqual(self.relationship(self.named('Hour')),
							('Minute', Decimal('60')))

	def test_an_abbreviation_is_saved_trimmed(self):
		unit_id = self.new_unit('Reel')
		self.gui.abbreviation_edited(None, self.path_of(unit_id), '  rl  ')
		self.assertEqual(self.one("SELECT abbreviation FROM units WHERE id = %s",
									(unit_id,)), 'rl')

	def test_a_relationship_is_saved(self):
		unit_id = self.new_unit('Reel')
		self.set_parent(unit_id, self.named('Inch'))
		self.gui.parent_qty_edited(None, self.path_of(unit_id), '250')
		self.assertEqual(self.relationship(unit_id), ('Inch', Decimal('250')))

	def test_naming_a_parent_with_no_ratio_means_one_of_it(self):
		"""unit_parent_qty_together wants both or neither, so the window has to
		supply the half the user did not"""
		unit_id = self.new_unit('Reel')
		self.set_parent(unit_id, self.named('Inch'))
		self.assertEqual(self.relationship(unit_id), ('Inch', Decimal('1')))

	def test_clearing_the_parent_clears_the_ratio_with_it(self):
		unit_id = self.new_unit('Reel')
		self.set_parent(unit_id, self.named('Inch'))
		self.gui.parent_combo_changed(None, self.path_of(unit_id),
										self.blank_parent_iter())
		self.assertEqual(self.relationship(unit_id), (None, None))

	def test_a_ratio_without_a_parent_is_refused(self):
		unit_id = self.new_unit('Reel')
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.parent_qty_edited(None, self.path_of(unit_id), '12')
		show_message.assert_called_once()
		self.assertEqual(self.relationship(unit_id), (None, None))

	def test_a_ratio_of_none_is_refused(self):
		unit_id = self.new_unit('Reel')
		self.set_parent(unit_id, self.named('Inch'))
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.parent_qty_edited(None, self.path_of(unit_id), '0')
		show_message.assert_called_once()
		self.assertEqual(self.relationship(unit_id), ('Inch', Decimal('1')))

	def test_a_ratio_that_is_not_a_number_is_refused(self):
		unit_id = self.new_unit('Reel')
		self.set_parent(unit_id, self.named('Inch'))
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.parent_qty_edited(None, self.path_of(unit_id), 'twelve')
		show_message.assert_called_once()
		self.assertEqual(self.relationship(unit_id), ('Inch', Decimal('1')))

	def test_a_unit_cannot_be_measured_in_itself(self):
		unit_id = self.new_unit('Reel')
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.parent_combo_changed(None, self.path_of(unit_id),
											self.parent_iter(unit_id))
		show_message.assert_called_once()
		self.assertEqual(self.relationship(unit_id), (None, None))

	def test_a_cycle_is_refused(self):
		"""Foot is measured in Inch, so Inch cannot be measured in Foot. A CHECK
		cannot see past its own row, so would_cycle is what catches this"""
		inch, foot = self.named('Inch'), self.named('Foot')
		self.assertEqual(self.relationship(foot)[0], 'Inch') # precondition
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.parent_combo_changed(None, self.path_of(inch),
											self.parent_iter(foot))
		show_message.assert_called_once()
		self.assertEqual(self.relationship(inch), (None, None))

	def test_a_unit_another_is_measured_in_cannot_be_deleted(self):
		"""the probe DELETE would fail on the self FK too, but the dialog it
		opens offers to move products, which would not mend the child unit"""
		inch = self.named('Inch')
		self.select(inch)
		with mock.patch.object(self.gui, 'show_message') as show_message:
			self.gui.delete_clicked(None)
		show_message.assert_called_once()
		self.assertIn('Foot', show_message.call_args[0][0])
		self.assertEqual(self.deleted(inch), False)

	def test_closing_tells_whoever_opened_it(self):
		told = []
		gui = self.units.UnitsGUI(lambda: told.append(True))
		gui.destroy(gui.window)
		self.assertEqual(told, [True])

class ProductEditUnitComboTest(DBTestCase):
	'''the combo used to be a hardcoded Glade list of ids 1-9'''

	def open_editor(self):
		import product_edit_main
		return product_edit_main.ProductEditMainGUI()

	def combo_units(self, gui):
		'''GtkComboBoxText's model is (text, id)'''
		model = gui.get_object('comboboxtext1').get_model()
		return {row[1]: row[0] for row in model}

	def new_unit(self, name = 'Reel'):
		unit_id = self.one("INSERT INTO units (name) VALUES (%s) "
							"RETURNING id", (name,))
		self.DB.commit()
		return unit_id

	def test_combo_is_filled_from_the_units_table(self):
		unit_id = self.new_unit()
		self.assertEqual(self.combo_units(self.open_editor()).get(str(unit_id)),
							'Reel')

	def test_a_retired_unit_is_left_out(self):
		unit_id = self.new_unit()
		self.cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
							(unit_id,))
		self.DB.commit()
		self.assertNotIn(str(unit_id), self.combo_units(self.open_editor()))

	def test_a_new_product_defaults_to_the_standard_unit(self):
		'''products.unit is NOT NULL and Glade no longer pre-selects unit 1, so
		without this a new product cannot be saved at all'''
		standard = self.one("SELECT id::text FROM units WHERE standard = True")
		gui = self.open_editor()
		self.assertEqual(gui.get_object('comboboxtext1').get_active_id(),
							standard)

	def test_a_retired_unit_still_shows_on_the_product_holding_it(self):
		unit_id = self.new_unit()
		self.cursor.execute("UPDATE products SET unit = %s WHERE id = 19",
							(unit_id,))
		self.cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
							(unit_id,))
		self.DB.commit()
		gui = self.open_editor()
		gui.select_product(19)
		combo = gui.get_object('comboboxtext1')
		self.assertEqual(combo.get_active_id(), str(unit_id))
		self.assertEqual(combo.get_active_text(), 'Reel')

	def test_saving_a_product_on_a_retired_unit_keeps_it(self):
		'''the silent corruption this guards: a unit missing from the combo
		leaves nothing selected, and the save writes whatever is'''
		unit_id = self.new_unit()
		self.cursor.execute("UPDATE products SET unit = %s WHERE id = 19",
							(unit_id,))
		self.cursor.execute("UPDATE units SET deleted = True WHERE id = %s",
							(unit_id,))
		self.DB.commit()
		gui = self.open_editor()
		gui.select_product(19)
		with mock.patch.object(gui, 'save_product_terms_prices'), \
				mock.patch.object(gui.window, 'destroy'):
			gui.save_clicked()
		self.assertEqual(self.one("SELECT unit FROM products WHERE id = 19"),
							unit_id)

	def test_the_detail_label_shows_the_abbreviation_and_the_ratio(self):
		gui = self.open_editor()
		foot = self.one("SELECT id::text FROM units WHERE name = 'Foot'")
		gui.get_object('comboboxtext1').set_active_id(foot)
		self.assertEqual(gui.get_object('unit_detail_label').get_label(),
							'ft \u00b7 1 Foot = 12 Inch')

	def test_the_detail_label_is_just_the_abbreviation_without_a_ratio(self):
		gui = self.open_editor()
		piece = self.one("SELECT id::text FROM units WHERE name = 'Piece'")
		gui.get_object('comboboxtext1').set_active_id(piece)
		self.assertEqual(gui.get_object('unit_detail_label').get_label(), 'pc')

	def test_the_detail_label_survives_an_empty_combo(self):
		"""populate_unit_combo's remove_all () fires changed with nothing
		selected, which must not raise"""
		gui = self.open_editor()
		gui.get_object('comboboxtext1').remove_all()
		self.assertEqual(gui.get_object('unit_detail_label').get_label(), '')

if __name__ == '__main__':
	unittest.main()
