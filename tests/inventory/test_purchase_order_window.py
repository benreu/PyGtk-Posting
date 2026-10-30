import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase
from gi.repository import Gdk, Gtk

def key (keyval, state = 0):
	'''what a key-release-event handler reads off its event'''
	event = mock.Mock(keyval = keyval)
	event.get_state.return_value = Gdk.ModifierType(state)
	return event

class PurchaseOrderWindowTest(DBTestCase):
	'''scanning, F3 and posting were each calling a method that does not exist,
	and posting went ahead when the print dialog called it off'''
	def setUp(self):
		super().setUp()
		import purchase_order_window
		self.po_window = purchase_order_window
		self.product_id = 19
		self.barcode = 'TESTPOBARCODE19'
		self.cursor.execute("UPDATE products SET (barcode, cost, deleted, "
								"purchasable, stock) = (%s, 3, False, True, True) "
							"WHERE id = %s", (self.barcode, self.product_id))
		# a vendor of its own, so select_vendor finds no open order to pick up
		self.vendor_id = self.new_vendor()
		self.DB.commit()

	def tearDown(self):
		try:
			super().tearDown()
		finally:
			# advisory locks belong to the session and outlive the rollback
			self.DB.execute("SELECT pg_advisory_unlock_all()")

	def new_vendor(self):
		return self.one("INSERT INTO contacts (name, vendor, markup_percent_id, "
							"terms_and_discounts_id) "
						"SELECT 'test vendor', True, "
							"(SELECT id FROM customer_markup_percent ORDER BY id LIMIT 1), "
							"(SELECT id FROM terms_and_discounts ORDER BY id LIMIT 1) "
						"RETURNING id")

	def window(self):
		gui = self.po_window.PurchaseOrderGUI()
		# a string, as the vendor combo hands it over
		gui.select_vendor(str(self.vendor_id))
		self.assertEqual(gui.purchase_order_id, None)
		self.messaged = mock.patch.object(gui, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def scan(self, gui, state = 0):
		entry = gui.get_object('entry9')
		entry.set_text(self.barcode)
		gui.barcode_entry_key_released(entry, key(Gdk.KEY_Return, state))

	def lines(self, gui):
		self.cursor.execute("SELECT qty, ext_price FROM purchase_order_items "
							"WHERE purchase_order_id = %s ORDER BY id",
							(gui.purchase_order_id,))
		return self.cursor.fetchall()

	def post(self, gui, result):
		'''post with the document stubbed out, so no pdf is rendered and no
		print dialog opens'''
		gui.get_object('direct_print_checkmenuitem').set_active(False)
		with mock.patch('purchase_ordering.Setup') as Setup, \
				mock.patch('unprocessed_po.GUI') as unprocessed, \
				mock.patch.object(gui.window, 'destroy') as destroy:
			Setup.return_value.print_dialog.return_value = result
			gui.post_and_process(None)
		return Setup.return_value.post, unprocessed, destroy

	def exclusive_lock_held(self, po_id):
		return self.one("SELECT COUNT(*) FROM pg_locks "
						"WHERE (locktype, mode, classid, objid, objsubid) = "
							"('advisory', 'ExclusiveLock', 0, %s, 1) "
						"AND pid = pg_backend_pid()", (po_id,)) > 0

	def test_a_first_scan_starts_a_line(self):
		gui = self.window()
		self.scan(gui)
		self.assertEqual(self.lines(gui), [(Decimal(1), Decimal('3.00'))])

	def test_a_numeric_vendor_id_still_saves_the_product(self):
		# the vendor id ran into the next word of the query, '2177WHERE', which
		# PostgreSQL 15 refuses; a string from the combo was quoted and got by
		gui = self.window()
		gui.select_vendor(self.vendor_id)
		self.scan(gui)
		self.assertEqual(self.lines(gui), [(Decimal(1), Decimal('3.00'))])

	def test_a_second_scan_adds_to_the_same_line(self):
		gui = self.window()
		self.scan(gui)
		self.scan(gui)
		self.assertEqual(self.lines(gui), [(Decimal(2), Decimal('6.00'))])
		self.assertEqual([row[1] for row in gui.p_o_store], ['2'])
		self.messaged.assert_not_called()

	def test_shift_takes_one_off(self):
		gui = self.window()
		self.scan(gui)
		self.scan(gui)
		self.scan(gui, Gdk.ModifierType.SHIFT_MASK)
		self.assertEqual(self.lines(gui), [(Decimal(1), Decimal('3.00'))])

	def test_view_all_leaves_another_vendors_line_alone(self):
		other_po = self.one("INSERT INTO purchase_orders (vendor_id) "
							"VALUES (%s) RETURNING id", (self.new_vendor(),))
		other_line = self.po_window.add_manufacturing_item_to_po(other_po,
														self.product_id, 5)
		gui = self.window()
		self.scan(gui)
		gui.get_object('view_all_checkbutton').set_active(True)
		self.assertIn(other_line, [row[0] for row in gui.p_o_store])
		self.scan(gui)
		self.assertEqual(self.lines(gui), [(Decimal(2), Decimal('6.00'))])
		self.assertEqual(self.one("SELECT qty FROM purchase_order_items "
								"WHERE id = %s", (other_line,)), 5)

	def test_f3_deletes_the_selected_line(self):
		gui = self.window()
		self.scan(gui)
		gui.get_object('treeview-selection').select_path(Gtk.TreePath(0))
		gui.window_key_event(gui.window, key(Gdk.KEY_F3))
		self.assertEqual(self.lines(gui), [])
		self.assertEqual(len(gui.p_o_store), 0)

	def test_a_canceled_print_posts_nothing(self):
		gui = self.window()
		self.scan(gui)
		post, unprocessed, destroy = self.post(gui, 'user canceled')
		post.assert_not_called()
		unprocessed.assert_not_called()
		destroy.assert_not_called()
		self.assertEqual(self.one("SELECT closed FROM purchase_orders "
								"WHERE id = %s", (gui.purchase_order_id,)), False)
		self.assertFalse(self.exclusive_lock_held(gui.purchase_order_id))

	def test_the_fixture_posts_when_the_print_goes_through(self):
		gui = self.window()
		self.scan(gui)
		post, unprocessed, destroy = self.post(gui,
										Gtk.PrintOperationResult.APPLY)
		post.assert_called_once()
		unprocessed.assert_called_once()
		destroy.assert_called_once()

if __name__ == '__main__':
	unittest.main()
