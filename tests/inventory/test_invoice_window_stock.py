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


class PostedInvoiceLedgerTest(InvoiceWindowStockTest):
	'''the same window edits, followed into the general ledger. The base class
	leaves the invoice without a gl transaction, so its own tests go on exercising
	the stock half by itself'''
	def setUp(self):
		super().setUp()
		from db import transactor
		self.transactor = transactor
		# the base class points inventory at 1710, which is receivables; netting a
		# whole transaction needs them kept apart
		self.cursor.execute("UPDATE products SET inventory_account = 1761, "
							"default_expense_account = 3876 WHERE id = %s",
							(self.product_id,))
		# the window only recognizes a contact flagged as a customer, and the base
		# class takes the first contact there is, which need not be one. Without this
		# the customer combo selects nothing, gui.customer_id stays None and every
		# price lookup off it fails
		self.customer_id = self.one("SELECT c.id FROM contacts AS c "
									"JOIN customer_markup_percent AS m "
										"ON m.id = c.markup_percent_id "
									"WHERE (c.deleted, c.customer) = (False, True) "
									"ORDER BY c.id LIMIT 1")
		self.cursor.execute("UPDATE invoices SET customer_id = %s WHERE id = %s",
							(self.customer_id, self.invoice_id))
		self.receivable = self.one("SELECT account FROM gl_account_flow "
									"WHERE function = 'post_invoice'")
		self.revenue_account = self.one("SELECT revenue_account FROM products "
										"WHERE id = %s", (self.product_id,))
		# what calculate_totals and invoice_create.post write before the ledger
		self.cursor.execute("UPDATE invoices AS i SET (subtotal, tax, total) = "
								"(t.subtotal, t.tax, t.total) "
							"FROM (SELECT COALESCE(SUM(ext_price), 0.00) AS subtotal, "
									"COALESCE(SUM(tax), 0.00) AS tax, "
									"COALESCE(SUM(ext_price) + SUM(tax), 0.00) AS total "
									"FROM invoice_items WHERE invoice_id = %s) AS t "
							"WHERE i.id = %s",
							(self.invoice_id, self.invoice_id))
		self.cursor.execute("UPDATE invoices "
							"SET (amount_due, dated_for) = (total, '2026-01-01') "
							"WHERE id = %s RETURNING total", (self.invoice_id,))
		transactor.post_invoice_accounts('2026-01-01', self.invoice_id,
											self.cursor.fetchone()[0])
		self.DB.commit()

	def invoice_total(self):
		return self.one("SELECT total FROM invoices WHERE id = %s",
						(self.invoice_id,))

	def transaction_id(self):
		return self.one("SELECT ge.gl_transaction_id FROM gl_entries AS ge "
						"JOIN invoices AS i ON i.gl_entries_id = ge.id "
						"WHERE i.id = %s", (self.invoice_id,))

	def receivable_amount(self):
		return self.one("SELECT ge.amount FROM gl_entries AS ge "
						"JOIN invoices AS i ON i.gl_entries_id = ge.id "
						"WHERE i.id = %s", (self.invoice_id,))

	def revenue_of(self, line_id):
		return self.one("SELECT ge.amount FROM gl_entries AS ge "
						"JOIN invoice_items AS ii ON ii.gl_entries_id = ge.id "
						"WHERE ii.id = %s", (line_id,))

	def tax_on(self, account):
		return self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
						"WHERE (gl_transaction_id, credit_account) = (%s, %s) "
						"AND debit_account IS NULL",
						(self.transaction_id(), account))

	def assertBalances(self):
		debits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND debit_account IS NOT NULL",
							(self.transaction_id(),))
		credits = self.one("SELECT COALESCE(SUM(amount), 0) FROM gl_entries "
							"WHERE gl_transaction_id = %s "
							"AND credit_account IS NOT NULL",
							(self.transaction_id(),))
		self.assertEqual(debits, credits)

	def assertReceivableCarriesTheInvoice(self):
		self.assertEqual(self.receivable_amount(), self.invoice_total())
		self.assertBalances()

	def test_a_quantity_edit_follows_into_the_revenue(self):
		gui = self.window()
		gui.qty_edited(None, self.path_of(gui, self.product_id), '7')
		self.errored.assert_not_called()
		self.assertEqual(self.revenue_of(self.line_id), Decimal('35.00'))
		self.assertReceivableCarriesTheInvoice()

	def test_a_price_edit_follows_into_the_revenue(self):
		gui = self.window()
		gui.price_edited(None, self.path_of(gui, self.product_id), '9')
		self.errored.assert_not_called()
		self.assertEqual(self.revenue_of(self.line_id), Decimal('36.00'))
		self.assertReceivableCarriesTheInvoice()

	def test_deleting_a_line_zeroes_its_revenue_and_the_receivable(self):
		gui = self.window()
		path = self.path_of(gui, self.product_id)
		gui.builder.get_object('invoice_selection').select_path(path)
		gui.delete_line_item_activated (None)
		self.assertEqual(self.revenue_of(self.line_id), Decimal('0.00'))
		self.assertEqual(self.invoice_total(), Decimal('0.00'))
		self.assertReceivableCarriesTheInvoice()

	def test_a_tax_exemption_change_follows_into_the_ledger(self):
		# the one edit that can take the tax to another tax_received_account, which
		# only the blanket zeroing of the old entry can retire
		other_rate = self.one("INSERT INTO tax_rates (name, rate, standard, "
								"tax_letter, tax_received_account) "
								"VALUES ('test rate', 8.00, False, 'T', 5200) "
								"RETURNING id")
		self.DB.commit()
		gui = self.window()
		old_account = self.one("SELECT tax_received_account FROM tax_rates "
								"WHERE id = %s", (self.tax_rate_id,))
		combo = gui.builder.get_object('tax_exemption_combo')
		combo.append(str(other_rate), 'test rate')
		combo.set_active_id(str(other_rate))
		self.assertEqual(self.tax_on(5200), Decimal('1.60')) # 8% of 20.00
		if old_account != 5200:
			self.assertEqual(self.tax_on(old_account), Decimal('0.00'))
		self.assertReceivableCarriesTheInvoice()

	def test_refreshing_all_prices_follows_into_the_ledger(self):
		# set_product_price writes the line price and never calls calculate_totals,
		# so the ledger can only be right if the re-sync recomputes the totals
		gui = self.window()
		gui.refresh_all_prices_clicked (None)
		self.errored.assert_not_called()
		ext_price = self.one("SELECT ext_price FROM invoice_items WHERE id = %s",
							(self.line_id,))
		self.assertEqual(self.revenue_of(self.line_id), ext_price)
		self.assertReceivableCarriesTheInvoice()

	def test_a_new_line_gets_a_revenue_entry(self):
		gui = self.window()
		gui.new_item_clicked (None)
		added = self.one("SELECT id FROM invoice_items "
						"WHERE invoice_id = %s ORDER BY id DESC LIMIT 1",
						(self.invoice_id,))
		self.assertNotEqual(added, self.line_id)
		self.assertEqual(self.revenue_of(added), Decimal('1.00')) # 1 at 1.00
		self.assertReceivableCarriesTheInvoice()

	def test_a_barcode_scan_follows_into_the_ledger(self):
		gui = self.window()
		barcode = self.one("SELECT barcode FROM products WHERE id = %s",
							(self.product_id,))
		if barcode in (None, ''):
			self.skipTest('product %s carries no barcode' % self.product_id)
		gui.builder.get_object('barcode_entry').set_text(barcode)
		gui.barcode_entry_activate (gui.builder.get_object('barcode_entry'))
		self.assertReceivableCarriesTheInvoice()

	def test_a_failure_rolls_the_stock_back_with_the_ledger(self):
		# the two halves share one commit, so neither may land without the other
		gui = self.window()
		before = self.ledger()
		with mock.patch.object(self.transactor, 'resync_invoice_accounts',
								side_effect = Exception('no')):
			gui.qty_edited(None, self.path_of(gui, self.product_id), '7')
		self.errored.assert_called_once()
		self.assertIn('not updated', self.errored.call_args[0][0])
		self.assertEqual(self.ledger(), before)
		self.assertEqual(self.revenue_of(self.line_id), Decimal('20.00'))

if __name__ == '__main__':
	unittest.main()
