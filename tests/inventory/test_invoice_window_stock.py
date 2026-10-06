import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase

class InvoiceWindowStockTest(DBTestCase):
	'''the window has no save button, every edit is written as it is typed, so a
	posted invoice has to follow each one into the ledger by itself'''
	def setUp(self):
		super().setUp()
		self.product_id = 19
		self.untracked_id = 962 # neither product is serial numbered
		self.cursor.execute("UPDATE products SET inventory_account = 1710, "
							"inventory_enabled = True, cost = 3 WHERE id = %s",
							(self.product_id,))
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.untracked_id,))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id IN (%s, %s)",
							(self.product_id, self.untracked_id))
		self.customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.location_id = self.new_location('A test location')
		self.other_location_id = self.new_location('B test location')
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id",
									(self.customer_id,))
		self.line_id = self.invoice_line(4)
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, 20, 1, %s, CURRENT_DATE, 'test')",
							(self.product_id, self.location_id))
		from inventory import inventorying
		inventorying.sell([[self.line_id, '4.00', self.product_id,
							'', '', '', '5.00']],
							self.location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()

	def invoice_line(self, qty, product_id = None):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id, price) "
						"VALUES (%s, %s, %s, %s, 5) RETURNING id",
						(self.invoice_id, qty,
						product_id or self.product_id, self.tax_rate_id))

	def window(self):
		import invoice_window
		gui = invoice_window.InvoiceGUI(self.invoice_id)
		# the dialogs are modal, nothing may block the test on them
		self.warned = mock.patch.object(gui, 'show_negative_stock_warning').start()
		self.errored = mock.patch.object(gui, 'show_error_dialog').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def ledger(self):
		self.cursor.execute("SELECT invoice_line_id, qty_out, location_id "
							"FROM inventory_transactions "
							"WHERE invoice_line_id IN (SELECT id "
								"FROM invoice_items WHERE invoice_id = %s) "
							"ORDER BY id", (self.invoice_id,))
		return self.cursor.fetchall()

	def path_of(self, gui, product_id):
		for row in gui.invoice_store:
			if row[2] == product_id:
				return str(row.path)
		self.fail('product %s is not on the invoice' % product_id)

	def qty_of(self, line_id):
		return self.one("SELECT qty FROM invoice_items WHERE id = %s",
						(line_id,))

	# ---------------- opening and focus must not write ----------------

	def test_opening_a_posted_invoice_leaves_the_ledger_alone(self):
		before = self.ledger()
		gui = self.window()
		self.assertEqual(gui.posted, True)
		self.assertEqual(self.ledger(), before)
		combo = gui.builder.get_object('location_combo')
		self.assertEqual(combo.get_active_id(), str(self.location_id))

	def test_a_focus_in_does_not_move_the_stock(self):
		gui = self.window()
		before = self.ledger()
		gui.focus(None, None) # refills the location combo on every focus in
		self.assertEqual(self.ledger(), before)
		self.warned.assert_not_called()

	# ---------------- an edit follows into the ledger ----------------

	def test_a_quantity_edit_follows_into_the_ledger(self):
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.product_id), '7')
		self.errored.assert_not_called()
		self.assertEqual(self.ledger(), [(self.line_id, 7, self.location_id)])
		self.assertEqual(self.on_hand(self.product_id), 13)

	def test_a_price_edit_leaves_the_cost_basis_alone(self):
		# the ledger price is the cost the sale is relieved at, not what the
		# customer was charged, so repricing a line must not touch it
		gui = self.window()
		gui.price_edited(None, self.path_of(gui, self.product_id), '9')
		self.assertEqual(self.one("SELECT price FROM inventory_transactions "
									"WHERE invoice_line_id = %s",
									(self.line_id,)), Decimal('3.000000'))

	def test_deleting_a_line_releases_its_stock(self):
		gui = self.window()
		path = self.path_of(gui, self.product_id)
		gui.builder.get_object('invoice_selection').select_path(path)
		gui.delete_line_item_activated (None)
		# the line is only flagged canceled, so ON DELETE CASCADE never fires
		self.assertEqual(self.ledger(), [])
		self.assertEqual(self.on_hand(self.product_id), 20)

	def test_changing_the_location_moves_the_stock(self):
		gui = self.window()
		combo = gui.builder.get_object('location_combo')
		combo.set_active_id(str(self.other_location_id))
		self.assertEqual(self.ledger(),
						[(self.line_id, 4, self.other_location_id)])

	def test_the_same_shortage_is_only_reported_once(self):
		gui = self.window()
		combo = gui.builder.get_object('location_combo')
		combo.set_active_id(str(self.other_location_id)) # holds nothing
		self.assertEqual(self.warned.call_count, 1)
		gui.qty_edited(None, self.path_of(gui, self.product_id), '4')
		self.assertEqual(self.warned.call_count, 1)

	def test_a_draft_invoice_is_left_alone(self):
		self.cursor.execute("UPDATE invoices SET posted = False WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.product_id), '7')
		# sell () takes the stock when it is posted, not before
		self.assertEqual(self.ledger(), [(self.line_id, 4, self.location_id)])

	# ---------------- whole units ----------------

	def test_a_tracked_product_refuses_a_fraction(self):
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.product_id), '1.5')
		self.errored.assert_called_once()
		self.assertIn('whole units', self.errored.call_args[0][0])
		self.assertEqual(self.qty_of(self.line_id), 4)

	def test_a_quantity_that_is_not_a_number_is_refused(self):
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.product_id), 'abc')
		self.errored.assert_called_once()
		self.assertEqual(self.qty_of(self.line_id), 4)

	def test_an_untracked_product_still_takes_a_fraction(self):
		untracked_line = self.invoice_line(2, self.untracked_id)
		self.DB.commit()
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.untracked_id), '1.5')
		self.errored.assert_not_called()
		self.assertEqual(self.qty_of(untracked_line), Decimal('1.50'))


if __name__ == '__main__':
	unittest.main()
