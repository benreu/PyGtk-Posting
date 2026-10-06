import unittest
from decimal import Decimal
from unittest import mock
from harness import DBTestCase

INVENTORY_ACCOUNT = 1710
EXPENSE_ACCOUNT = 3876

class AdjustmentTest(DBTestCase):
	def setUp(self):
		super().setUp()
		self.product_id = 19
		self.location_id = self.new_location()
		self.cursor.execute("UPDATE products SET cost = 2.50, "
							"inventory_account = %s, default_expense_account = %s, "
							"inventory_enabled = True WHERE id = %s",
							(INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, self.product_id))
		self.cursor.execute("DELETE FROM inventory_transactions WHERE product_id = %s",
							(self.product_id,))
		self.DB.commit()

	def adjust(self, amount):
		from inventory import inventory_adjustment
		gui = inventory_adjustment.InventoryAdjustmentGUI(self.product_id)
		gui.builder.get_object('combobox3').set_active_id(str(self.location_id))
		gui.builder.get_object('comboboxtext3').set_active(0)
		gui.builder.get_object('spinbutton12').set_value(amount)
		gui.apply_inventory_adjustment_clicked(mock.Mock())

	def last_transaction(self):
		self.cursor.execute("SELECT it.qty_in, it.qty_out, ge.debit_account, "
							"ge.credit_account, ge.amount "
							"FROM inventory_transactions AS it "
							"JOIN gl_entries AS ge ON ge.id = it.gl_entries_id "
							"WHERE it.product_id = %s ORDER BY it.id DESC LIMIT 1",
							(self.product_id,))
		return self.cursor.fetchone()

	def test_increase_debits_inventory(self):
		self.adjust(4)
		self.assertEqual(self.last_transaction(),
						(4, 0, INVENTORY_ACCOUNT, EXPENSE_ACCOUNT, Decimal('10.00')))
		self.assertEqual(self.on_hand(self.product_id), 4)

	def test_decrease_is_qty_out_and_credits_inventory(self):
		self.adjust(10)
		self.adjust(-3)
		self.assertEqual(self.last_transaction(),
						(0, 3, EXPENSE_ACCOUNT, INVENTORY_ACCOUNT, Decimal('7.50')))
		self.assertEqual(self.on_hand(self.product_id), 7)

	def test_adjustment_of_zero_does_not_enable_inventory(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.DB.commit()
		self.adjust(0)
		self.assertFalse(self.one("SELECT inventory_enabled FROM products "
								"WHERE id = %s", (self.product_id,)))

	def test_first_adjustment_enables_inventory(self):
		self.cursor.execute("UPDATE products SET inventory_enabled = False "
							"WHERE id = %s", (self.product_id,))
		self.DB.commit()
		self.adjust(2)
		self.assertTrue(self.one("SELECT inventory_enabled FROM products "
								"WHERE id = %s", (self.product_id,)))

if __name__ == '__main__':
	unittest.main()
