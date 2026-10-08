import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # 1710 is receivables, it must not double as inventory
COGS_ACCOUNT = 3876

class CreditMemoWindowTest(DBTestCase):
	'''posting a memo prints it first, and the print dialog is where the user can
	still call the whole thing off'''
	def setUp(self):
		super().setUp()
		from inventory import inventorying
		from db import transactor
		self.inventorying = inventorying
		self.transactor = transactor
		self.product_id = 19
		self.location_id = self.new_location()
		self.cursor.execute("UPDATE products SET cost = 3, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, COGS_ACCOUNT, self.product_id))
		self.cursor.execute("DELETE FROM inventory_transactions "
							"WHERE product_id = %s", (self.product_id,))
		# a contact the window recognizes, with no other unposted memo of its own
		# for select_customer to pick up instead of this one
		self.customer_id = self.one("SELECT c.id FROM contacts AS c "
									"WHERE (c.deleted, c.customer) = (False, True) "
									"AND NOT EXISTS (SELECT 1 FROM credit_memos "
										"WHERE (customer_id, posted) = "
											"(c.id, False)) "
									"ORDER BY c.id LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (self.customer_id,))
		self.line_id = self.one("INSERT INTO invoice_items "
								"(invoice_id, qty, product_id, tax_rate_id, price) "
								"VALUES (%s, 4, %s, %s, 5) RETURNING id",
								(self.invoice_id, self.product_id, self.tax_rate_id))
		self.cursor.execute("INSERT INTO inventory_transactions "
							"(product_id, qty_in, price, location_id, "
							"date_inserted, reason) "
							"VALUES (%s, 10, 3, %s, CURRENT_DATE, 'test')",
							(self.product_id, self.location_id))
		self.inventorying.sell(
			[[self.line_id, '4.00', self.product_id, '', '', '', '5.00']],
			self.location_id, self.customer_id, '2026-01-01')
		self.cursor.execute("UPDATE invoices SET posted = True WHERE id = %s",
							(self.invoice_id,))
		self.credit_memo_id = self.one("INSERT INTO credit_memos "
										"(customer_id, date_created, dated_for, "
										"amount_owed, tax) "
										"VALUES (%s, CURRENT_DATE, '2026-02-15', "
										"10, 0) RETURNING id",
										(self.customer_id,))
		self.cursor.execute("INSERT INTO credit_memo_items "
							"(credit_memo_id, qty, invoice_item_id, price, "
							"date_returned, tax, ext_price) "
							"VALUES (%s, 2, %s, 5, CURRENT_DATE, 0, 10)",
							(self.credit_memo_id, self.line_id))
		self.DB.commit()

	def window(self):
		import credit_memo
		gui = credit_memo.CreditMemoGUI()
		gui.select_customer(self.customer_id)
		self.assertEqual(gui.credit_memo_id, self.credit_memo_id)
		self.messaged = mock.patch.object(gui, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def post(self, gui, result = None, post_raises = False):
		'''click the button with the template stubbed out, so no odt is rendered
		and no print dialog opens'''
		with mock.patch('credit_memo_template.Setup') as Setup:
			Setup.return_value.print_pdf.return_value = result
			if post_raises:
				Setup.return_value.post.side_effect = Exception('no')
			else:
				Setup.return_value.post.side_effect = \
					lambda: self.transactor.post_credit_memo(self.credit_memo_id)
			gui.post_credit_memo_clicked(gui.builder.get_object('button1'))

	def restock_rows(self):
		return self.one("SELECT COUNT(*) FROM inventory_transactions "
						"WHERE credit_memo_item_id IN "
							"(SELECT id FROM credit_memo_items "
							"WHERE credit_memo_id = %s)",
						(self.credit_memo_id,))

	def memo_entry(self):
		return self.one("SELECT gl_entries_id FROM credit_memos WHERE id = %s",
						(self.credit_memo_id,))

	def test_the_fixture_posts_when_the_print_goes_through(self):
		gui = self.window()
		self.post(gui)
		self.messaged.assert_not_called()
		self.assertNotEqual(self.memo_entry(), None)
		self.assertEqual(self.restock_rows(), 1)
		self.assertEqual(self.on_hand(self.product_id), 8) # 10, sold 4, back 2

	def test_a_canceled_print_posts_nothing(self):
		gui = self.window()
		high_water = self.one("SELECT COALESCE(MAX(id), 0) FROM gl_entries")
		self.post(gui, result = 'user canceled')
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_entries "
									"WHERE id > %s", (high_water,)), 0)
		self.assertEqual(self.memo_entry(), None)
		self.assertEqual(self.restock_rows(), 0)
		self.assertEqual(self.on_hand(self.product_id), 6) # the stock stayed out

	def test_a_canceled_print_leaves_the_window_open_and_the_button_live(self):
		gui = self.window()
		self.post(gui, result = 'user canceled')
		self.assertEqual(gui.builder.get_object('button1').get_sensitive(), True)
		self.messaged.assert_not_called()

	def test_the_button_is_insensitive_while_the_dialog_is_up(self):
		# it runs a main loop of its own, so a live button lets a second click
		# re-enter the handler and print the memo twice
		gui = self.window()
		button = gui.builder.get_object('button1')
		seen = []
		with mock.patch('credit_memo_template.Setup') as Setup:
			Setup.return_value.print_pdf.side_effect = \
				lambda window: seen.append(button.get_sensitive())
			Setup.return_value.post.side_effect = \
				lambda: self.transactor.post_credit_memo(self.credit_memo_id)
			gui.post_credit_memo_clicked(button)
		self.assertEqual(seen, [False])

	def test_a_failed_post_takes_the_stock_back_out_with_it(self):
		# restock runs before the ledger does, so a failure in the second half
		# may not leave the returned stock on hand
		gui = self.window()
		high_water = self.one("SELECT COALESCE(MAX(id), 0) FROM gl_entries")
		self.post(gui, post_raises = True)
		self.messaged.assert_called_once()
		self.assertIn('not posted', self.messaged.call_args[0][0])
		self.assertEqual(self.restock_rows(), 0)
		self.assertEqual(self.on_hand(self.product_id), 6)
		self.assertEqual(self.one("SELECT COUNT(*) FROM gl_entries "
									"WHERE id > %s", (high_water,)), 0)
		self.assertEqual(gui.builder.get_object('button1').get_sensitive(), True)

if __name__ == '__main__':
	unittest.main()
