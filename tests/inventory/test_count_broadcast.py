import unittest
from decimal import Decimal
from harness import DBTestCase
from unittest import mock

import db_connection
from gi.repository import Gtk

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
EXPENSE_ACCOUNT = 3876
SIGNAL = 'inventory_counts_changed'

class _Notify:
	'''what psycopg2 hands back on DB.notifies'''
	def __init__(self, channel, payload, pid):
		self.channel = channel
		self.payload = payload
		self.pid = pid

class CountTriggerTest(DBTestCase):
	'''the triggers themselves. Delivery cannot be tested here: the suite runs in
	one transaction that is rolled back, and Postgres holds notifications until
	commit, so what is checked is that the triggers exist and fire on the right
	columns'''
	def triggerdef(self, name):
		return self.one("SELECT pg_get_triggerdef(oid) FROM pg_trigger "
						"WHERE tgname = %s", (name,))

	def test_the_insert_trigger_fires_on_every_row(self):
		definition = self.triggerdef('count_summary_insert_trigger')
		self.assertIn('AFTER INSERT ON inventory.count_summaries', definition)
		self.assertIn('count_summary_changed', definition)
		self.assertNotIn('WHEN', definition)

	def test_the_update_trigger_fires_on_the_four_columns(self):
		definition = self.triggerdef('count_summary_update_trigger')
		self.assertIn('AFTER UPDATE ON inventory.count_summaries', definition)
		for column in ('name', 'fiscal_id', 'location_id', 'active'):
			self.assertIn('new.%s IS DISTINCT FROM old.%s' % (column, column),
							definition)

	def test_the_update_trigger_ignores_the_totals(self):
		'''the close writes them in the same statement as active, so they would
		only make the trigger fire twice as often for nothing'''
		definition = self.triggerdef('count_summary_update_trigger')
		for column in ('total_cost', 'total_retail', 'date_ended'):
			self.assertNotIn(column, definition)

class NotifyDispatchTest(unittest.TestCase):
	'''the one place a typo kills the feature silently: channel name to signal.
	No database, no GTK, just the mapping'''
	class _DB:
		def __init__(self, notifies):
			self.notifies = notifies
			self.closed = 0
		def poll(self):
			pass

	def dispatch(self, notifies):
		broadcast = db_connection.Broadcast.__new__(db_connection.Broadcast)
		db_connection.GObject.GObject.__init__(broadcast)
		seen = []
		broadcast.connect(SIGNAL, lambda b, i: seen.append(i))
		real_db = db_connection.DB
		db_connection.DB = self._DB(notifies)
		try:
			self.assertTrue(broadcast.process_notifies())
		finally:
			db_connection.DB = real_db
		return seen

	def test_the_channel_reaches_the_signal_as_an_int(self):
		self.assertEqual(self.dispatch([_Notify('inventory_counts', '42', 999)]),
							[42])

	def test_our_own_write_is_not_filtered_out(self):
		'''windows in one process share a connection, so a sibling window has to
		hear a close its own backend made'''
		self.assertEqual(
			self.dispatch([_Notify('inventory_counts', '7',
									db_connection.DB_PROCESS_ID)]), [7])

	def test_another_channel_does_not_reach_it(self):
		self.assertEqual(self.dispatch([_Notify('resources', '7', 999)]), [])

class CountWindowBroadcastTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.location_id = self.new_location('Broadcast location')
		self.summary_id = self.new_summary('watched count')
		self.other_id = self.new_summary('some other count')
		self.product_id = self.one("SELECT id FROM products "
									"WHERE NOT deleted AND stock ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE products SET inventory_account = %s, "
							"default_expense_account = %s, inventory_enabled = True, "
							"cost = 2.50 WHERE id = %s",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.product_id))
		self.count_row(self.summary_id, 3)
		self.DB.commit()
		from inventory import inventory_count
		self.module = inventory_count
		# the window under test, standing in for the stale one
		self.gui = self.window(self.summary_id)

	def new_summary(self, name):
		return self.one("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, location_id) VALUES (%s, %s, %s) "
						"RETURNING id", (name, self.fiscal_id, self.location_id))

	def count_row(self, summary_id, qty):
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, %s, 2.50, 4.00) "
							"ON CONFLICT DO NOTHING",
							(summary_id, self.product_id, qty))

	def window(self, summary_id):
		gui = self.module.InventoryCountGUI()
		gui.summary_id = str(summary_id) # what the combo really hands out
		gui.get_object('widget_box').set_sensitive(True)
		gui.populate_inventory_count()
		return gui

	def close_in_the_database(self, summary_id = None):
		'''what another machine's close looks like from here'''
		self.cursor.execute("UPDATE inventory.count_summaries "
							"SET active = False WHERE id = %s",
							(summary_id if summary_id else self.summary_id,))
		self.DB.commit()

	def emit(self, summary_id = None):
		db_connection.broadcaster.emit(SIGNAL,
						int(summary_id if summary_id else self.summary_id))

	# subscription

	def test_the_window_subscribes_and_unsubscribes(self):
		broadcaster = db_connection.broadcaster
		self.assertIn(self.gui.count_summaries_changed,
						broadcaster.connected(SIGNAL))
		self.gui.destroy(None)
		self.assertNotIn(self.gui.count_summaries_changed,
							broadcaster.connected(SIGNAL))

	# reacting

	def test_a_close_elsewhere_resets_the_window(self):
		self.close_in_the_database()
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.emit()
		self.assertIsNone(self.gui.summary_id)
		self.assertFalse(self.gui.get_object('widget_box').get_sensitive())
		self.assertEqual(len(self.gui.get_object('inventory_rows_store')), 0)
		self.assertIn('watched count', m.call_args[0][0])

	def test_a_close_of_another_count_leaves_this_one_alone(self):
		self.close_in_the_database(self.other_id)
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.emit(self.other_id)
		self.assertEqual(self.gui.summary_id, str(self.summary_id))
		self.assertTrue(self.gui.get_object('widget_box').get_sensitive())
		self.assertEqual(len(self.gui.get_object('inventory_rows_store')), 1)
		m.assert_not_called()

	def test_a_rename_repopulates_without_resetting(self):
		self.cursor.execute("UPDATE inventory.count_summaries SET name = 'renamed' "
							"WHERE id = %s", (self.summary_id,))
		self.DB.commit()
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.emit()
		self.assertEqual(self.gui.summary_id, str(self.summary_id))
		m.assert_not_called()
		for row in self.gui.get_object('inventory_summaries_store'):
			if row[0] == str(self.summary_id):
				self.assertIn('renamed', row[1])
				return
		self.fail('renamed count not listed')

	def test_a_window_with_no_count_picked_only_repopulates(self):
		self.gui.destroy(None) # it holds the count, and would warn rightly
		fresh = self.module.InventoryCountGUI()
		self.assertIsNone(fresh.summary_id)
		self.close_in_the_database()
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.emit()
		m.assert_not_called()

	def test_two_windows_on_one_count_both_hear_a_close(self):
		'''the case an is_remote filter would have broken: these share a
		connection, so the pid cannot tell them apart'''
		second = self.window(self.summary_id)
		self.close_in_the_database()
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message'):
			self.emit()
		self.assertIsNone(self.gui.summary_id)
		self.assertIsNone(second.summary_id)

	def test_the_closing_window_does_not_warn_itself(self):
		'''close_count_clicked drops its summary id before it commits, and that
		commit delivers the notify synchronously'''
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.YES):
			with mock.patch.object(self.module.InventoryCountGUI,
									'show_message') as m:
				self.gui.close_count_clicked(None)
				self.emit() # the real commit would have done this
		self.assertEqual(len(m.call_args_list), 1)
		self.assertIn('Closed', m.call_args_list[0][0][0])
		self.assertFalse(self.one("SELECT active FROM inventory.count_summaries "
									"WHERE id = %s", (self.summary_id,)))

	# the write guards

	def rows(self, summary_id = None):
		return self.one("SELECT count(*) FROM inventory.count_rows "
						"WHERE count_summary_id = %s",
						(summary_id if summary_id else self.summary_id,))

	def test_a_scan_into_a_closed_count_writes_nothing(self):
		self.close_in_the_database()
		before = self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id))
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.gui.process_product(self.product_id)
		self.assertEqual(self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id)), before)
		self.assertIsNone(self.gui.summary_id)
		m.assert_called_once()

	def test_a_scan_of_a_new_product_into_a_closed_count_adds_no_row(self):
		other_product = self.one("SELECT id FROM products WHERE NOT deleted "
									"AND stock AND id <> %s ORDER BY id LIMIT 1",
									(self.product_id,))
		self.close_in_the_database()
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message'):
			self.gui.process_product(other_product)
		self.assertEqual(self.rows(), 1)

	def test_a_qty_edit_on_a_closed_count_is_refused(self):
		self.close_in_the_database()
		store = self.gui.get_object('inventory_rows_store')
		with mock.patch.object(self.module.InventoryCountGUI, 'show_message') as m:
			self.gui.qty_edited(None, '0', '9')
		self.assertEqual(self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id)), 3)
		m.assert_called_once()

	def test_a_scan_into_an_open_count_still_works(self):
		self.gui.process_product(self.product_id)
		self.assertEqual(self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id)), 4)

	def test_a_qty_edit_on_an_open_count_still_works(self):
		self.gui.qty_edited(None, '0', '9')
		self.assertEqual(self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id)), 9)

class _Combo:
	def __init__(self, active_id):
		self.active_id = active_id
	def get_active_id(self):
		return self.active_id

class CompareWindowBroadcastTest(DBTestCase):
	'''the window the stale writes were actually possible from'''
	def setUp(self):
		super().setUp()
		self.fiscal_id = self.one("SELECT id FROM fiscal_years LIMIT 1")
		self.location_id = self.new_location('Compare broadcast location')
		# 1999 so no real summary in the restore copy can fall between them and
		# be picked as the previous count instead
		self.previous_id = self.summary('last year', '1999-01-01')
		self.summary_id = self.summary('this year', '1999-06-01')
		self.product_id = self.one("SELECT id FROM products "
									"WHERE NOT deleted AND stock ORDER BY id LIMIT 1")
		self.other_product = self.one("SELECT id FROM products WHERE NOT deleted "
										"AND stock AND id <> %s ORDER BY id LIMIT 1",
										(self.product_id,))
		self.count_row(self.previous_id, self.product_id, 5)
		self.count_row(self.summary_id, self.product_id, 2)
		self.DB.commit()
		from inventory import inventory_compare
		self.module = inventory_compare
		self.gui = inventory_compare.InventoryCompareGUI()
		self.gui.inventory_summary_changed(_Combo(str(self.summary_id)))

	def summary(self, name, date):
		return self.one("INSERT INTO inventory.count_summaries "
						"(name, fiscal_id, location_id, date_created) "
						"VALUES (%s, %s, %s, %s) RETURNING id",
						(name, self.fiscal_id, self.location_id, date))

	def count_row(self, summary_id, product_id, qty):
		self.cursor.execute("INSERT INTO inventory.count_rows "
							"(count_summary_id, product_id, qty, cost, retail) "
							"VALUES (%s, %s, %s, 2.50, 4.00)",
							(summary_id, product_id, qty))

	def close_in_the_database(self):
		self.cursor.execute("UPDATE inventory.count_summaries "
							"SET active = False WHERE id = %s", (self.summary_id,))
		self.DB.commit()

	def emit(self):
		db_connection.broadcaster.emit(SIGNAL, int(self.summary_id))

	def rows(self):
		return self.one("SELECT count(*) FROM inventory.count_rows "
						"WHERE count_summary_id = %s", (self.summary_id,))

	def select_previous(self):
		selection = self.gui.get_object('previous_inventory_selection')
		store = self.gui.get_object('previous_inventory_store')
		self.assertNotEqual(len(store), 0, 'no previous count rows to select')
		for row in store:
			selection.select_path(row.path)

	def test_the_window_subscribes_and_unsubscribes(self):
		broadcaster = db_connection.broadcaster
		self.assertIn(self.gui.count_summaries_changed,
						broadcaster.connected(SIGNAL))
		self.gui.destroy(None)
		self.assertNotIn(self.gui.count_summaries_changed,
							broadcaster.connected(SIGNAL))

	def test_a_close_elsewhere_desensitises_the_buttons(self):
		self.assertTrue(self.gui.get_object('copy_button').get_sensitive())
		self.close_in_the_database()
		with mock.patch.object(self.module.InventoryCompareGUI, 'show_message') as m:
			self.emit()
		self.assertIsNone(self.gui.summary_id)
		for button in ('copy_button', 'update_button', 'create_button'):
			self.assertFalse(self.gui.get_object(button).get_sensitive(), button)
		self.assertEqual(len(self.gui.get_object('current_inventory_store')), 0)
		self.assertIn('this year', m.call_args[0][0])

	def test_the_previous_count_being_closed_is_not_a_problem(self):
		'''comparing against last year's closed count is the normal case'''
		self.cursor.execute("UPDATE inventory.count_summaries SET active = False "
							"WHERE id = %s", (self.previous_id,))
		self.DB.commit()
		with mock.patch.object(self.module.InventoryCompareGUI, 'show_message') as m:
			db_connection.broadcaster.emit(SIGNAL, int(self.previous_id))
		self.assertEqual(self.gui.summary_id, str(self.summary_id))
		m.assert_not_called()

	def test_copy_into_a_closed_count_writes_nothing(self):
		self.count_row(self.previous_id, self.other_product, 4)
		self.close_in_the_database()
		before = self.rows()
		self.select_previous()
		self.gui.copy_inventory_clicked(None)
		self.assertEqual(self.rows(), before)

	def test_update_of_a_closed_count_writes_nothing(self):
		self.close_in_the_database()
		self.select_previous()
		self.gui.update_inventory_clicked(None)
		self.assertEqual(self.one("SELECT qty FROM inventory.count_rows "
							"WHERE (count_summary_id, product_id) = (%s, %s)",
							(self.summary_id, self.product_id)), 2)

	def test_create_into_a_closed_count_writes_nothing(self):
		self.count_row(self.previous_id, self.other_product, 4)
		self.close_in_the_database()
		before = self.rows()
		self.select_previous()
		self.gui.create_inventory_clicked(None)
		self.assertEqual(self.rows(), before)

	def test_delete_from_a_closed_count_writes_nothing(self):
		self.close_in_the_database()
		selection = self.gui.get_object('current_inventory_selection')
		store = self.gui.get_object('current_inventory_store')
		self.assertEqual(len(store), 1)
		selection.select_path(store[0].path)
		self.gui.delete_activated(None)
		self.assertEqual(self.rows(), 1)

	def test_delete_from_an_open_count_still_works(self):
		'''so the closed count test above is testing the guard, not a selection
		that never reached the delete'''
		selection = self.gui.get_object('current_inventory_selection')
		store = self.gui.get_object('current_inventory_store')
		selection.select_path(store[0].path)
		self.gui.delete_activated(None)
		self.assertEqual(self.rows(), 0)

	def test_the_writes_still_work_on_an_open_count(self):
		self.count_row(self.previous_id, self.other_product, 4)
		self.DB.commit()
		self.gui.inventory_summary_changed(_Combo(str(self.summary_id)))
		self.select_previous()
		self.gui.copy_inventory_clicked(None)
		self.assertEqual(self.rows(), 2)

if __name__ == '__main__':
	unittest.main()
