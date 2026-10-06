import unittest
from decimal import Decimal
from harness import DBTestCase

INVENTORY_ACCOUNT = 1761 # a real inventory asset account; 1710 is receivables
EXPENSE_ACCOUNT = 3876

class CapitalizePurchaseTest(DBTestCase):
	'''buying a tracked product is not an expense, it is a swap of one asset for
	another, so the cost sits on the inventory account until the sale relieves it'''
	def setUp(self):
		super().setUp()
		import purchase_order_window
		from db import transactor
		self.po_window = purchase_order_window
		self.transactor = transactor
		self.tracked_id = 19
		self.untracked_id = 962
		self.cursor.execute("UPDATE products SET cost = 3, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.tracked_id))
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"default_expense_account = %s WHERE id = %s",
							(EXPENSE_ACCOUNT, self.untracked_id))
		self.vendor_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.po_id = self.one("INSERT INTO purchase_orders (vendor_id) "
								"VALUES (%s) RETURNING id", (self.vendor_id,))
		self.DB.commit()

	def line_account(self, line_id):
		return self.one("SELECT expense_account FROM purchase_order_items "
						"WHERE id = %s", (line_id,))

	def add_line(self, product_id, qty = 5):
		return self.po_window.add_manufacturing_item_to_po(self.po_id,
															product_id, qty)

	def test_a_tracked_line_posts_to_inventory(self):
		line_id = self.add_line(self.tracked_id)
		self.assertEqual(self.line_account(line_id), INVENTORY_ACCOUNT)

	def test_an_untracked_line_still_posts_to_expense(self):
		line_id = self.add_line(self.untracked_id)
		self.assertEqual(self.line_account(line_id), EXPENSE_ACCOUNT)

	def test_tracking_off_with_an_account_left_over_still_expenses(self):
		# turning tracking off does not clear inventory_account, so the flag and
		# not the presence of an account is what decides where the line posts
		self.cursor.execute("UPDATE products SET inventory_enabled = False, "
							"inventory_account = %s WHERE id = %s",
							(INVENTORY_ACCOUNT, self.untracked_id))
		line_id = self.add_line(self.untracked_id)
		self.assertEqual(self.line_account(line_id), EXPENSE_ACCOUNT)

	def test_the_ledger_debits_inventory_not_expense(self):
		line_id = self.add_line(self.tracked_id)
		self.cursor.execute("UPDATE purchase_order_items SET (price, ext_price) "
							"= (3, 15) WHERE id = %s", (line_id,))
		self.transactor.post_purchase_order(Decimal('15.00'), self.po_id)
		self.transactor.post_purchase_order_accounts(self.po_id, '2026-01-01')
		self.assertEqual(self.one("SELECT ge.debit_account FROM gl_entries AS ge "
									"JOIN purchase_order_items AS poli "
										"ON poli.gl_entries_id = ge.id "
									"WHERE poli.id = %s", (line_id,)),
						INVENTORY_ACCOUNT)

	def test_a_reposted_line_keeps_the_inventory_account(self):
		line_id = self.add_line(self.tracked_id)
		self.cursor.execute("UPDATE purchase_order_items SET (price, ext_price) "
							"= (3, 15) WHERE id = %s", (line_id,))
		self.transactor.post_purchase_order(Decimal('15.00'), self.po_id)
		self.transactor.post_purchase_order_accounts(self.po_id, '2026-01-01')
		self.transactor.repost_purchase_order_accounts(self.po_id)
		self.assertEqual(self.one("SELECT ge.debit_account FROM gl_entries AS ge "
									"JOIN purchase_order_items AS poli "
										"ON poli.gl_entries_id = ge.id "
									"WHERE poli.id = %s", (line_id,)),
						INVENTORY_ACCOUNT)

if __name__ == '__main__':
	unittest.main()
