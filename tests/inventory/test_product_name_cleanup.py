# test_product_name_cleanup.py
#
# The opt in install, the seed it lays down, and the cleanup window's apply
# path. Everything runs inside the harness transaction, so a table created
# here is discarded with the rollback and silrep_restore keeps no trace of it.
#
# These tests make their own preconditions rather than assuming anything about
# the catalog, in both directions. A database that has already opted in still
# has to exercise the not-installed path, which is why _uninstall drops the
# table inside the transaction; and a catalog whose names have already been
# cleaned up still has to exercise the fix list, which is why _rename puts a
# messy name back. An earlier version of this file asserted counts taken from
# the live catalog and went red the first time somebody pressed Apply.

import os
import unittest
from unittest import mock
import psycopg2
from harness import DBTestCase, HOST, TEST_DB

import product_name_rules

class RulesTestCase(DBTestCase):
	def setUp(self):
		super(RulesTestCase, self).setUp()
		#the compiled ruleset is a module global, so one test must not
		#inherit another's
		product_name_rules._ruleset = None
		self.cursor.execute("SELECT id FROM products WHERE deleted = False "
							"ORDER BY id LIMIT 6")
		self.spare = [row[0] for row in self.cursor.fetchall()]

	def _uninstall(self):
		'''the not opted in state, inside the transaction'''
		self.cursor.execute("DROP TABLE IF EXISTS public.product_name_rules")
		self.DB.commit()
		product_name_rules._ruleset = None

	def _rename(self, index, name):
		'''give a product a name that breaks the convention, so the fix list
		has something in it whatever shape the catalog is in'''
		product_id = self.spare[index]
		self.cursor.execute("UPDATE products SET name = %s WHERE id = %s",
							(name, product_id))
		self.DB.commit()
		return product_id

class InstallTest(RulesTestCase):
	def setUp(self):
		super(InstallTest, self).setUp()
		self._uninstall()

	def test_not_installed_until_asked(self):
		self.assertFalse(product_name_rules.installed())

	def test_no_rules_means_no_normalization(self):
		'''a database that has not opted in stays completely inert'''
		rules = product_name_rules.load_rules()
		self.assertEqual(rules.rules, [])
		self.assertEqual(product_name_rules.normalize('  Relay 12v  '),
						'  Relay 12v  ')
		self.assertEqual(product_name_rules.findings('  Relay 12v  '), [])

	def test_install_creates_and_seeds(self):
		product_name_rules.install()
		self.assertTrue(product_name_rules.installed())
		self.assertEqual(self.one("SELECT count(*) FROM product_name_rules"), 17)

	def test_install_is_idempotent(self):
		product_name_rules.install()
		product_name_rules.install()
		product_name_rules.install()
		self.assertEqual(self.one("SELECT count(*) FROM product_name_rules"), 17)

	def test_install_does_not_revive_a_removed_rule(self):
		'''the seed is ON CONFLICT DO NOTHING on name, so a hard delete would
		come back; soft deleting is what makes a removal stick'''
		product_name_rules.install()
		self.cursor.execute("UPDATE product_name_rules SET "
							"(active, deleted) = (False, True) "
							"WHERE name = 'gauge'")
		self.DB.commit()
		product_name_rules.install()
		self.assertTrue(self.one("SELECT deleted FROM product_name_rules "
								"WHERE name = 'gauge'"))

	def test_an_inactive_rule_is_not_compiled(self):
		product_name_rules.install()
		self.cursor.execute("UPDATE product_name_rules SET active = False "
							"WHERE name = 'microfarads'")
		self.DB.commit()
		rules = product_name_rules.load_rules()
		self.assertNotIn('microfarads', [r.name for r in rules.rules])
		self.assertEqual(rules.normalize('Capacitor 50V 100uf'),
						'Capacitor 50V 100uf')

class SeedParityTest(RulesTestCase):
	'''Pins what db/product_name_rules.sql installs.
	test_product_name_rules.py pins the engine against literal rows; this pins
	the seed, so a drift between the two shows up here.'''

	def setUp(self):
		super(SeedParityTest, self).setUp()
		self.rules = product_name_rules.install()
		self.cursor.execute("SELECT id, name FROM products "
							"WHERE deleted = False")
		self.products = self.cursor.fetchall()

	def test_seed_loads_every_rule(self):
		self.assertEqual(len(self.rules.rules), 17)

	def test_seed_contents(self):
		'''Counting findings across the live catalog was tried first and is no
		use: the moment somebody applies the fixes the catalog is clean and the
		numbers all go to zero, so the seed is pinned by its contents.'''
		seeded = dict((r.name, r) for r in self.rules.rules)
		self.assertEqual(sorted(seeded), sorted([
				'trim', 'double_space', 'volts', 'volts_ac_dc', 'volts_ac',
				'volts_dc', 'amps', 'milliamps', 'microfarads', 'watts',
				'ohms', 'wire_gauge', 'gauge', 'receptacle', 'pin_count',
				'pin_count_exclude', 'brands']))
		for name, canonical in [('volts', 'V'), ('amps', 'A'),
				('milliamps', 'mA'), ('microfarads', 'uF'), ('watts', 'W'),
				('ohms', 'OHM'), ('wire_gauge', 'AWG'), ('gauge', 'GA'),
				('volts_ac', 'VAC'), ('volts_dc', 'VDC'),
				('volts_ac_dc', 'VAC/DC'), ('receptacle', 'Recep'),
				('pin_count', 'pos')]:
			self.assertEqual(seeded[name].canonical, canonical, name)
		self.assertEqual(seeded['receptacle'].kind, 'review')
		self.assertEqual(seeded['pin_count'].kind, 'review')
		self.assertEqual(seeded['brands'].kind, 'report')
		self.assertEqual(seeded['pin_count_exclude'].kind, 'guard')
		self.assertTrue(seeded['volts_ac_dc'].sort_order
						< seeded['volts_ac'].sort_order,
						'the combined token has to be applied first')

	def test_the_seeded_rules_do_the_right_thing(self):
		for before, after in [
				('Capacitor electrolytic 6.3v 100uf',
					'Capacitor electrolytic 6.3V 100uF'),
				('Indicator green 10mm 24vac/dc',
					'Indicator green 10mm 24VAC/DC'),
				('Potentiometer ', 'Potentiometer'),
				('Relay  SPDT', 'Relay SPDT'),
				('Wire stranded 8awg THHN', 'Wire stranded 8AWG THHN'),
				('Resistor 150W 100Ohm', 'Resistor 150W 100OHM'),
				('Breaker 15A 2P', 'Breaker 15A 2P'),
				('Potentiometer Bourns 3006P 10K',
					'Potentiometer Bourns 3006P 10K'),
				('Recep Deutsch DT04-2P', 'Recep Deutsch DT04-2P'),
				]:
			self.assertEqual(self.rules.normalize(before), after, before)

	def test_normalize_is_idempotent_over_the_whole_catalog(self):
		for i, name in self.products:
			once = self.rules.normalize(name)
			self.assertEqual(self.rules.normalize(once), once, name)

	def test_every_rewrite_is_backed_by_a_finding(self):
		'''whatever the catalog holds, a name normalize would change must say
		why, and a name it leaves alone must not claim an auto safe fix'''
		for i, name in self.products:
			auto = [f for f in self.rules.findings(name)
					if f.kind == product_name_rules.AUTO_SAFE]
			if self.rules.normalize(name) != name:
				self.assertTrue(auto, name)
			else:
				self.assertEqual(auto, [], name)

	def test_no_part_number_is_ever_rewritten(self):
		for i, name in self.products:
			if 'ATMEGA' in name or '3386P' in name or 'DCP0' in name:
				self.assertEqual(self.rules.normalize(name), name, name)

	def test_no_pin_count_rewrites_inside_a_part_number(self):
		for i, name in self.products:
			for finding in self.rules.findings(name):
				if finding.rule != 'pin_count':
					continue
				for word in finding.after.split():
					if word in name.split():
						continue
					self.assertNotIn('-', word,
						'%r would rewrite inside a part number' % name)

class CleanupWindowTest(RulesTestCase):
	def setUp(self):
		super(CleanupWindowTest, self).setUp()
		from admin import product_name_cleanup
		self.module = product_name_cleanup

	def _window(self):
		return self.module.ProductNameCleanupGUI()

	def _ready(self):
		'''an installed window, with a product needing a mechanical fix and
		another needing a reviewed one'''
		self.auto_id = self._rename(0, 'Relay widget 12v 5a ')
		self.pin_id = self._rename(1, 'Connector widget 4P friction')
		gui = self._window()
		if product_name_rules.installed():
			gui.load()
		else:
			gui.setup_clicked(None)
		return gui

	def _row_for(self, gui, product_id, rule_name):
		for row in gui.fix_store:
			if row[0] == product_id and row[4] == rule_name:
				return row
		return None

	def test_offers_setup_when_not_installed(self):
		self._uninstall()
		gui = self._window()
		self.assertFalse(gui.builder.get_object('notebook').get_sensitive())

	def test_setup_button_installs_and_scans(self):
		self._uninstall()
		self._rename(0, 'Relay widget 12v 5a ')
		gui = self._window()
		gui.setup_clicked(None)
		self.assertTrue(gui.builder.get_object('notebook').get_sensitive())
		self.assertTrue(len(gui.fix_store) > 0)
		self.assertEqual(len(gui.rule_store), 17)

	def test_auto_rows_ticked_review_rows_not(self):
		gui = self._ready()
		auto = [r for r in gui.fix_store if r[4] == '']
		review = [r for r in gui.fix_store if r[4] != '']
		self.assertTrue(len(auto) > 0)
		self.assertTrue(len(review) > 0)
		self.assertTrue(all(r[5] == True for r in auto))
		self.assertTrue(all(r[5] == False for r in review),
						'a review suggestion must never be ticked by default')

	def test_one_row_per_product_for_the_auto_subset(self):
		'''the mechanical fixes are not individually choosable, so a product
		gets a single auto row no matter how many auto rules it trips'''
		gui = self._ready()
		auto_ids = [r[0] for r in gui.fix_store if r[4] == '']
		self.assertEqual(len(auto_ids), len(set(auto_ids)))
		row = self._row_for(gui, self.auto_id, '')
		self.assertIsNotNone(row)
		self.assertEqual(row[2], 'Relay widget 12V 5A')
		self.assertIn('Whitespace', row[3])
		self.assertIn('Unit case', row[3])

	def test_apply_rewrites_only_the_ticked_rows(self):
		gui = self._ready()
		gui.unselect_all_clicked(None)
		self._row_for(gui, self.auto_id, '')[5] = True
		untouched = self.one("SELECT name FROM products WHERE id = %s",
							(self.pin_id,))
		gui.apply_clicked(None)
		self.assertEqual(self.one("SELECT name FROM products WHERE id = %s",
								(self.auto_id,)), 'Relay widget 12V 5A')
		self.assertEqual(self.one("SELECT name FROM products WHERE id = %s",
								(self.pin_id,)), untouched)

	def test_apply_writes_an_audit_row(self):
		gui = self._ready()
		gui.unselect_all_clicked(None)
		self._row_for(gui, self.auto_id, '')[5] = True
		before = self.one("SELECT count(*) FROM log.products WHERE id = %s",
						(self.auto_id,))
		gui.apply_clicked(None)
		self.assertEqual(self.one("SELECT count(*) FROM log.products "
								"WHERE id = %s", (self.auto_id,)), before + 1)

	def test_accepting_a_review_row_applies_just_that_rule(self):
		gui = self._ready()
		gui.unselect_all_clicked(None)
		row = self._row_for(gui, self.pin_id, 'pin_count')
		self.assertIsNotNone(row, 'expected a pin count suggestion')
		row[5] = True
		gui.apply_clicked(None)
		self.assertEqual(self.one("SELECT name FROM products WHERE id = %s",
								(self.pin_id,)),
						'Connector widget 4pos friction')

	def test_select_all_skips_rows_that_are_not_activatable(self):
		gui = self._ready()
		gui.unselect_all_clicked(None)
		gui.fix_store[0][6] = False
		gui.select_all_clicked(None)
		self.assertFalse(gui.fix_store[0][5],
						'select all must not tick a row it cannot activate')
		self.assertTrue(gui.fix_store[1][5])

	def test_a_product_locked_by_somebody_else_is_skipped(self):
		gui = self._ready()
		gui.unselect_all_clicked(None)
		self._row_for(gui, self.auto_id, '')[5] = True
		before = self.one("SELECT name FROM products WHERE id = %s",
						(self.auto_id,))
		#a second session holds the same advisory lock product_edit_main takes
		other = psycopg2.connect(host = HOST, database = TEST_DB,
								user = 'postgres',
								password = os.environ['POSTING_TEST_DB_PASSWORD'])
		other_cursor = other.cursor()
		other_cursor.execute("SELECT pg_try_advisory_lock(%s, %s)",
							(1, self.auto_id))
		self.assertTrue(other_cursor.fetchone()[0])
		try:
			with mock.patch.object(gui, 'show_message') as show_message:
				gui.apply_clicked(None)
			show_message.assert_called_once()
			self.assertEqual(self.one("SELECT name FROM products "
									"WHERE id = %s", (self.auto_id,)), before)
		finally:
			other_cursor.execute("SELECT pg_advisory_unlock(%s, %s)",
								(1, self.auto_id))
			other_cursor.close()
			other.close()

	def test_duplicates_are_reported(self):
		self._rename(2, 'Widget collision test')
		self._rename(3, 'widget collision test ')
		gui = self._ready()
		keys = [row[2] for row in gui.duplicate_store]
		self.assertEqual(keys.count('widget collision test'), 2)

	def _duplicates(self):
		'''a colliding pair, plus the window showing them'''
		self.keep_id = self._rename(2, 'Widget collision test')
		self.other_id = self._rename(3, 'widget collision test ')
		gui = self._ready()
		rows = [r for r in gui.duplicate_store
				if r[2] == 'widget collision test']
		self.assertEqual(len(rows), 2)
		return gui, rows

	def test_right_click_pops_the_duplicate_menu(self):
		gui, rows = self._duplicates()
		menu = gui.builder.get_object('duplicate_menu')
		with mock.patch.object(menu, 'popup_at_pointer') as popup:
			gui.duplicate_treeview_button_release_event(
						gui.builder.get_object('duplicate_treeview'),
						mock.Mock(button = 3))
		popup.assert_called_once()

	def test_left_click_does_not_pop_the_menu(self):
		gui, rows = self._duplicates()
		menu = gui.builder.get_object('duplicate_menu')
		with mock.patch.object(menu, 'popup_at_pointer') as popup:
			gui.duplicate_treeview_button_release_event(
						gui.builder.get_object('duplicate_treeview'),
						mock.Mock(button = 1))
		popup.assert_not_called()

	def test_product_hub_opens_on_the_selected_duplicate(self):
		gui, rows = self._duplicates()
		gui.builder.get_object('duplicate_selection').select_path(rows[1].path)
		import product_hub
		with mock.patch.object(product_hub, 'ProductHubGUI') as hub:
			gui.duplicate_product_hub_activated(None)
		hub.assert_called_once_with(rows[1][0])

	def test_product_hub_does_nothing_without_a_selection(self):
		gui, rows = self._duplicates()
		gui.builder.get_object('duplicate_selection').unselect_all()
		import product_hub
		with mock.patch.object(product_hub, 'ProductHubGUI') as hub:
			gui.duplicate_product_hub_activated(None)
		hub.assert_not_called()

	def test_word_order_is_reported_without_a_suggestion(self):
		brand_id = self._rename(2, 'O-ring 26x1.5mm Visotron solenoid')
		gui = self._ready()
		self.assertIn(brand_id, [row[0] for row in gui.word_order_store])
		#and a report never turns up as something to fix
		self.assertEqual([r for r in gui.fix_store if r[3] == 'Word order'], [])

	def _word_order(self):
		'''a brand sitting mid name, plus the window reporting it'''
		self.brand_id = self._rename(2, 'O-ring 26x1.5mm Visotron solenoid')
		gui = self._ready()
		rows = [r for r in gui.word_order_store if r[0] == self.brand_id]
		self.assertEqual(len(rows), 1)
		return gui, rows[0]

	def test_right_click_pops_the_word_order_menu(self):
		gui, row = self._word_order()
		menu = gui.builder.get_object('word_order_menu')
		with mock.patch.object(menu, 'popup_at_pointer') as popup:
			gui.word_order_treeview_button_release_event(
						gui.builder.get_object('word_order_treeview'),
						mock.Mock(button = 3))
		popup.assert_called_once()

	def test_left_click_does_not_pop_the_word_order_menu(self):
		gui, row = self._word_order()
		menu = gui.builder.get_object('word_order_menu')
		with mock.patch.object(menu, 'popup_at_pointer') as popup:
			gui.word_order_treeview_button_release_event(
						gui.builder.get_object('word_order_treeview'),
						mock.Mock(button = 1))
		popup.assert_not_called()

	def test_product_hub_opens_on_the_selected_word_order_row(self):
		gui, row = self._word_order()
		gui.builder.get_object('word_order_selection').select_path(row.path)
		import product_hub
		with mock.patch.object(product_hub, 'ProductHubGUI') as hub:
			gui.word_order_product_hub_activated(None)
		hub.assert_called_once_with(self.brand_id)

	def test_word_order_product_hub_does_nothing_without_a_selection(self):
		gui, row = self._word_order()
		gui.builder.get_object('word_order_selection').unselect_all()
		import product_hub
		with mock.patch.object(product_hub, 'ProductHubGUI') as hub:
			gui.word_order_product_hub_activated(None)
		hub.assert_not_called()

	def test_both_report_tabs_use_their_own_menu(self):
		'''the two tabs share the helper but not the menu, so a right click in
		one list cannot act on the other list's selection'''
		gui = self._ready()
		self.assertIsNot(gui.builder.get_object('duplicate_menu'),
						gui.builder.get_object('word_order_menu'))
		self.assertIsNot(gui.builder.get_object('duplicate_selection'),
						gui.builder.get_object('word_order_selection'))

	def test_deactivating_a_rule_drops_its_findings(self):
		uf_id = self._rename(2, 'Capacitor widget 50V 100uf')
		gui = self._ready()
		self.assertIsNotNone(self._row_for(gui, uf_id, ''))
		for row in gui.rule_store:
			if row[1] == 'microfarads':
				path = row.path
				break
		renderer = self.module.Gtk.CellRendererToggle()
		renderer.set_active(True)
		gui.rule_active_toggled(renderer, path)
		self.assertIsNone(self._row_for(gui, uf_id, ''),
						'turning off a rule must drop what it suggested')
		self.assertFalse(self.one("SELECT active FROM product_name_rules "
								"WHERE name = 'microfarads'"))

	def test_refresh_sees_a_rule_changed_from_outside(self):
		'''the Rules tab rescans its own edits, but a rule can change in
		another session or straight from SQL, which is what Refresh is for'''
		uf_id = self._rename(2, 'Capacitor widget 50V 100uf')
		gui = self._ready()
		self.assertIsNotNone(self._row_for(gui, uf_id, ''))
		self.cursor.execute("UPDATE product_name_rules SET active = False "
							"WHERE name = 'microfarads'")
		self.DB.commit()
		gui.refresh_clicked(None)
		self.assertIsNone(self._row_for(gui, uf_id, ''),
						'Refresh must re-read the rules, not just the products')

	def test_refresh_sees_a_product_changed_from_outside(self):
		gui = self._ready()
		late_id = self._rename(2, 'Sensor widget 24v 2a ')
		self.assertIsNone(self._row_for(gui, late_id, ''))
		gui.refresh_clicked(None)
		row = self._row_for(gui, late_id, '')
		self.assertIsNotNone(row)
		self.assertEqual(row[2], 'Sensor widget 24V 2A')

	def test_refresh_picks_up_a_setup_done_elsewhere(self):
		self._uninstall()
		gui = self._window()
		self.assertFalse(gui.builder.get_object('notebook').get_sensitive())
		product_name_rules.install()
		gui.refresh_clicked(None)
		self.assertTrue(gui.builder.get_object('notebook').get_sensitive())

	def test_refresh_resets_what_was_ticked(self):
		'''documented in the button's tooltip: a rescan rebuilds the list, so
		the defaults come back'''
		gui = self._ready()
		gui.unselect_all_clicked(None)
		self.assertFalse(any(row[5] for row in gui.fix_store))
		gui.refresh_clicked(None)
		self.assertTrue(all(row[5] == True
							for row in gui.fix_store if row[4] == ''))

	def test_a_new_rule_is_picked_up(self):
		gui = self._ready()
		gui.new_rule_clicked(None)
		path = gui.rule_store[-1].path
		gui.rule_store[-1][1] = 'kilohms'
		gui.rule_store[-1][5] = 'k'
		gui.rule_store[-1][6] = 'K'
		gui.rule_changed(path)
		self.assertEqual(gui.ruleset.normalize('Resistor 10k 1%'),
						'Resistor 10K 1%')
		self.assertEqual(self.one("SELECT count(*) FROM product_name_rules "
								"WHERE name = 'kilohms'"), 1)

	def test_nothing_listens_for_an_edit_to_the_current_name(self):
		'''The column is editable for viewing only. No "edited" handler is
		connected, so Gtk drops whatever is typed and the cell redraws from
		the store: the column has no way to rename anything. Connecting a
		handler here would give the window a second, unreviewed rename path.'''
		gui = self._window()
		self.assertFalse(hasattr(gui, 'current_name_edited'))
		with open(self.module.UI_FILE) as ui_file:
			ui = ui_file.read()
		renderer = ui.split('id="fix_current_renderer"')[1].split('</object>')[0]
		self.assertNotIn('signal', renderer)
		self.assertIn('editable', renderer)

	def test_current_name_cell_can_be_clicked_into(self):
		'''editable only so a text cursor shows where the name really ends,
		which is the only way to see a trailing or doubled space'''
		gui = self._window()
		self.assertTrue(gui.builder.get_object(
						'fix_current_renderer').get_property('editable'))

	def test_the_other_fix_columns_stay_read_only(self):
		'''the editable cell is a deliberate single exception, not a pattern'''
		gui = self._window()
		for renderer in ['fix_suggested_renderer', 'fix_kind_renderer']:
			self.assertFalse(gui.builder.get_object(renderer).get_property(
							'editable'), renderer)

	def test_a_bad_rule_type_is_refused_not_crashed(self):
		gui = self._ready()
		path = gui.rule_store[0].path
		gui.rule_store[0][2] = 'nonsense'
		with mock.patch.object(gui, 'show_message') as show_message:
			gui.rule_changed(path)
		show_message.assert_called_once()

if __name__ == '__main__':
	unittest.main()
