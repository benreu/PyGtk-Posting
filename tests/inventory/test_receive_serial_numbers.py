import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase

from gi.repository import Gtk

class _Selection:
	def __init__(self, model, rows):
		self.model = model
		self.rows = rows
	def get_selected_rows(self):
		return self.model, self.rows

class _Entry:
	def __init__(self, text = ''):
		self.text = text
	def get_text(self):
		return self.text
	def set_text(self, text):
		self.text = text
	def grab_focus(self):
		pass
	def select_region(self, start, end):
		pass

class ReceiveSerialNumbersTest(DBTestCase):
	'''nothing used to write serial_numbers.purchase_order_item_id, so the
	serial check in purchase_order_inventory_blocked could never fire and the
	purchase order columns of the serial numbers window were always blank'''
	def setUp(self):
		super().setUp()
		self.location_id = self.new_location('serial receive location')
		self.vendor_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.po_id = self.one("INSERT INTO purchase_orders "
								"(vendor_id, invoiced, closed) "
								"VALUES (%s, True, True) RETURNING id",
								(self.vendor_id,))
		self.tracked_id = self.new_product('tracked by serial', True)
		self.plain_id = self.new_product('not tracked by serial', False)

	def new_product(self, name, invoice_serial_numbers):
		tax_rate_id = self.one("SELECT id FROM tax_rates WHERE standard = True")
		return self.one("INSERT INTO products (name, ext_name, description, "
						"unit, cost, tax_rate_id, invoice_serial_numbers, "
						"inventory_enabled, inventory_account, "
						"default_expense_account, revenue_account) "
						"VALUES (%s, '', '', 1, 1.00, %s, %s, True, "
							"(SELECT number FROM gl_accounts "
							"WHERE inventory_account = True LIMIT 1), "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 3 LIMIT 1), "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 4 LIMIT 1)) RETURNING id",
						(name, tax_rate_id, invoice_serial_numbers))

	def add_line(self, product_id, qty = 3, received = None):
		return self.one("INSERT INTO purchase_order_items "
						"(purchase_order_id, product_id, qty, price, received) "
						"VALUES (%s, %s, %s, 1.00, %s) RETURNING id",
						(self.po_id, product_id, qty, received))

	def window(self):
		self.DB.commit()
		import receive_orders
		gui = receive_orders.ReceiveOrdersGUI()
		# set_active_id fires the window's own changed handler
		gui.builder.get_object('combobox1').set_active_id(str(self.po_id))
		return gui

	def select(self, gui, line_id):
		'''through the real handler, so the test holds the selection the same
		way the window does'''
		store = gui.receive_order_store
		rows = [row for row in store if row[0] == line_id]
		gui.receive_selection_changed(_Selection(store, [rows[0].path]))

	def serials_on(self, line_id):
		self.cursor.execute("SELECT serial_number FROM serial_numbers "
							"WHERE purchase_order_item_id = %s ORDER BY id",
							(line_id,))
		return [row[0] for row in self.cursor.fetchall()]

	def enter(self, gui, serial_number):
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.CLOSE):
			gui.serial_number_entry_activated(_Entry(serial_number))

	def test_a_serial_entered_on_receipt_is_tied_to_the_line(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-FIRST')
		self.assertEqual(self.serials_on(line_id), ['SN-FIRST'])

	def test_the_serial_carries_the_product_it_arrived_as(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-PRODUCT')
		self.assertEqual(self.one("SELECT product_id FROM serial_numbers "
									"WHERE serial_number = 'SN-PRODUCT'"),
							self.tracked_id)

	def test_the_list_shows_what_has_been_entered(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-ONE')
		self.enter(gui, 'SN-TWO')
		listed = [row[0] for row in gui.serial_number_store]
		self.assertEqual(listed, ['SN-ONE', 'SN-TWO'])
		self.assertEqual(gui.builder.get_object('serial_count_label').get_label(), '2 of 2')

	def test_no_more_serials_than_arrived(self):
		'''what was counted in is also how many of these there can be'''
		line_id = self.add_line(self.tracked_id, received = 1)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-ROOM')
		self.enter(gui, 'SN-NO-ROOM')
		self.assertEqual(self.serials_on(line_id), ['SN-ROOM'])

	def test_a_line_nobody_counted_takes_no_serials_yet(self):
		line_id = self.add_line(self.tracked_id, received = None)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-UNCOUNTED')
		self.assertEqual(self.serials_on(line_id), [])

	def test_the_same_serial_twice_is_refused(self):
		line_id = self.add_line(self.tracked_id, received = 3)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-TWICE')
		self.enter(gui, 'SN-TWICE')
		self.assertEqual(self.serials_on(line_id), ['SN-TWICE'])

	def test_the_box_is_only_there_for_a_tracked_product(self):
		plain_line = self.add_line(self.plain_id, received = 1)
		gui = self.window()
		self.select(gui, plain_line)
		self.assertFalse(gui.builder.get_object('serial_number_box').get_sensitive())

	def test_the_box_is_there_for_a_tracked_product(self):
		line_id = self.add_line(self.tracked_id, received = 1)
		gui = self.window()
		self.select(gui, line_id)
		self.assertTrue(gui.builder.get_object('serial_number_box').get_sensitive())

	def test_a_serial_can_be_taken_back_off_the_line(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-MISTAKE')
		store = gui.serial_number_store
		gui.builder.get_object = _patched(gui, 'serial_number_selection',
									_Selection(store, [store[0].path]))
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.CLOSE):
			gui.remove_serial_number_clicked(None)
		self.assertEqual(self.serials_on(line_id), [])

	def test_a_serial_with_a_history_is_not_deleted(self):
		'''somebody else's record: the invoice window and the serial numbers
		window both hang things off it'''
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-HISTORY')
		serial_id = self.one("SELECT id FROM serial_numbers "
								"WHERE serial_number = 'SN-HISTORY'")
		self.one("INSERT INTO serial_number_history "
					"(contact_id, date_inserted, description, serial_number_id) "
					"VALUES (%s, CURRENT_DATE, 'sold on', %s) RETURNING id",
					(self.vendor_id, serial_id))
		self.DB.commit()
		store = gui.serial_number_store
		gui.builder.get_object = _patched(gui, 'serial_number_selection',
									_Selection(store, [store[0].path]))
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.CLOSE):
			gui.remove_serial_number_clicked(None)
		self.assertEqual(self.serials_on(line_id), ['SN-HISTORY'])

	def test_the_dead_guard_can_now_fire(self):
		'''the serial half of purchase_order_inventory_blocked was unreachable
		because nothing wrote the column it reads'''
		from db.transactor import purchase_order_inventory_blocked
		line_id = self.add_line(self.tracked_id, qty = 3, received = 3)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-A')
		self.enter(gui, 'SN-B')
		self.assertIsNone(purchase_order_inventory_blocked(self.po_id))
		# the order is corrected back below what has been identified
		self.cursor.execute("UPDATE purchase_order_items SET qty = 1 "
							"WHERE id = %s", (line_id,))
		message = purchase_order_inventory_blocked(self.po_id)
		self.assertIsNotNone(message)
		self.assertIn('serial numbers', message)

class MissingSerialNumbersTest(ReceiveSerialNumbersTest):
	'''the close warns rather than refuses: ten arriving with nine labels in
	hand is a real shipment'''
	def test_a_short_count_of_serials_is_reported(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-ONLY-ONE')
		message = gui.missing_serial_numbers()
		self.assertIsNotNone(message)
		self.assertIn('2 arrived, 1 identified', message)

	def test_nothing_is_reported_when_they_match(self):
		line_id = self.add_line(self.tracked_id, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-MATCH-1')
		self.enter(gui, 'SN-MATCH-2')
		self.assertIsNone(gui.missing_serial_numbers())

	def test_an_untracked_product_is_never_reported(self):
		self.add_line(self.plain_id, received = 2)
		gui = self.window()
		self.assertIsNone(gui.missing_serial_numbers())

	def test_a_refused_warning_posts_nothing(self):
		line_id = self.add_line(self.tracked_id, qty = 2, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-REFUSE')
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.NO):
			gui.close_purchase_order_clicked(None)
		self.assertEqual(self.one("SELECT COUNT(*) FROM inventory_transactions "
									"WHERE purchase_order_item_id = %s",
									(line_id,)), 0)

	def test_an_accepted_warning_posts_the_receipt(self):
		line_id = self.add_line(self.tracked_id, qty = 2, received = 2)
		gui = self.window()
		self.select(gui, line_id)
		self.enter(gui, 'SN-ACCEPT')
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.YES):
			gui.close_purchase_order_clicked(None)
		self.assertEqual(self.one("SELECT COALESCE(SUM(qty_in), 0) "
									"FROM inventory_transactions "
									"WHERE purchase_order_item_id = %s",
									(line_id,)), 2)

	def test_a_line_nobody_counted_raises_no_warning(self):
		'''the close zeroes an uncounted line first, so it is owed no serials
		rather than all of them'''
		self.add_line(self.tracked_id, qty = 2, received = None)
		gui = self.window()
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = Gtk.ResponseType.NO) as run:
			gui.close_purchase_order_clicked(None)
		self.assertEqual(run.call_count, 0) # no dialog was raised at all

def _patched(gui, name, replacement):
	original = gui.builder.get_object
	def get_object(wanted):
		if wanted == name:
			return replacement
		return original(wanted)
	return get_object

if __name__ == '__main__':
	unittest.main()
