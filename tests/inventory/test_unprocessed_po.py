import unittest
from decimal import Decimal
from unittest import mock
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk

class SaveAndPayTest(DBTestCase):
	'''Save and pay called a save_invoice that did not exist, and the payment
	window it meant to open ignored the purchase order it was handed. The
	window also read each line's account as gl_accounts.expense_account, the
	flag, so an inventory account read as missing and Save corrections wrote
	the flag back as the line's account'''
	def setUp(self):
		super().setUp()
		import unprocessed_po, vendor_payment
		self.unprocessed_po = unprocessed_po
		self.vendor_payment = vendor_payment
		self.vendor_id = self.one("INSERT INTO contacts (name, vendor, "
										"markup_percent_id, terms_and_discounts_id) "
									"SELECT 'test vendor', True, "
									"(SELECT id FROM customer_markup_percent "
										"ORDER BY id LIMIT 1), "
									"(SELECT id FROM terms_and_discounts "
										"ORDER BY id LIMIT 1) "
									"RETURNING id")
		self.po_id = self.one("INSERT INTO purchase_orders (vendor_id, closed) "
								"VALUES (%s, True) RETURNING id",
								(self.vendor_id,))
		# an inventory account is not flagged as an expense account, which is
		# what made the window take a tracked product's line for one without
		self.account = self.one("SELECT number FROM gl_accounts "
								"WHERE (inventory_account, expense_account) = "
									"(True, False) ORDER BY number LIMIT 1")
		# a product with no stock history, so a correction is never refused for
		# taking some location negative
		product_id = self.one("SELECT id FROM products AS p "
								"WHERE (expense, deleted) = (False, False) "
								"AND NOT EXISTS (SELECT 1 "
									"FROM inventory_transactions AS it "
									"WHERE it.product_id = p.id) "
								"ORDER BY id LIMIT 1")
		self.line_id = self.one("INSERT INTO purchase_order_items "
									"(purchase_order_id, qty, product_id, remark, "
									"price, ext_price, canceled, expense_account, "
									"order_number) "
								"VALUES (%s, 5, %s, '', 3, 15, False, %s, '') "
								"RETURNING id",
								(self.po_id, product_id, self.account))
		self.cursor.execute("UPDATE settings SET (request_po_attachment, "
							"accrual_based) = (False, False)")
		self.DB.commit() # survive the window's own rollback after it reads

	def tearDown(self):
		try:
			super().tearDown()
		finally:
			# advisory locks belong to the session and outlive the rollback
			self.DB.execute("SELECT pg_advisory_unlock_all()")

	def window(self, correction = False):
		gui = self.unprocessed_po.GUI(self.po_id, correction)
		gui.get_object('entry6').set_text('INV-1234')
		self.destroy = mock.patch.object(gui.window, 'destroy').start()
		self.messaged = mock.patch.object(gui, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def save_and_pay(self, gui):
		with mock.patch('vendor_payment.GUI') as payment:
			gui.save_and_pay_invoice(None)
		return payment

	def test_save_and_pay_saves_and_opens_the_payment(self):
		gui = self.window()
		self.assertTrue(gui.get_object('button2').get_sensitive())
		payment = self.save_and_pay(gui)
		self.cursor.execute("SELECT invoiced, amount_due, total, "
								"invoice_description, gl_entries_id IS NOT NULL "
							"FROM purchase_orders WHERE id = %s", (self.po_id,))
		self.assertEqual(self.cursor.fetchone(),
						(True, Decimal('15.00'), Decimal('15.00'), 'INV-1234', True))
		payment.assert_called_once_with(self.po_id)
		self.destroy.assert_called_once_with()

	def test_a_cancelled_attachment_question_saves_nothing(self):
		gui = self.window()
		gui.request_po_attachment = True
		gui.attachment = False
		dialog = gui.get_object('missing_attachment_dialog')
		with mock.patch.object(dialog, 'run',
								return_value = Gtk.ResponseType.CANCEL):
			payment = self.save_and_pay(gui)
		self.assertFalse(self.one("SELECT invoiced FROM purchase_orders "
									"WHERE id = %s", (self.po_id,)))
		payment.assert_not_called()
		self.destroy.assert_not_called()

	def test_a_blank_description_turns_save_and_pay_off(self):
		gui = self.window()
		gui.get_object('entry6').set_text('')
		self.assertFalse(gui.get_object('button5').get_sensitive())
		self.assertFalse(gui.get_object('button2').get_sensitive())

	def test_the_payment_window_opens_on_the_bill(self):
		gui = self.window()
		self.save_and_pay(gui)
		payment = self.vendor_payment.GUI(self.po_id)
		self.assertEqual(payment.builder.get_object('combobox1').get_active_id(),
						str(self.vendor_id))
		selection = payment.builder.get_object('treeview-selection1')
		model, paths = selection.get_selected_rows()
		self.assertEqual([model[path][0] for path in paths], [self.po_id])
		self.assertEqual(payment.total, Decimal('15.00'))
		payment.window.destroy()

	def test_a_po_id_from_the_combo_is_a_string(self):
		gui = self.window()
		self.save_and_pay(gui)
		payment = self.vendor_payment.GUI(str(self.po_id))
		selection = payment.builder.get_object('treeview-selection1')
		model, paths = selection.get_selected_rows()
		self.assertEqual([model[path][0] for path in paths], [self.po_id])
		payment.window.destroy()

	def test_an_inventory_account_counts_as_chosen(self):
		gui = self.window()
		self.assertEqual(gui.purchase_order_items_store[0][7], self.account)
		self.assertTrue(gui.get_object('button5').get_sensitive())
		self.assertTrue(gui.get_object('button2').get_sensitive())

	def test_a_line_without_an_account_still_reads_missing(self):
		self.cursor.execute("UPDATE purchase_order_items "
							"SET expense_account = NULL WHERE id = %s",
							(self.line_id,))
		self.DB.commit()
		gui = self.window()
		self.assertEqual(gui.get_object('button5').get_label(),
						"Missing expense account")
		self.assertFalse(gui.get_object('button5').get_sensitive())
		self.assertFalse(gui.get_object('button2').get_sensitive())

	def test_save_corrections_keeps_the_line_account(self):
		self.save_and_pay(self.window())
		gui = self.window(correction = True)
		self.assertTrue(gui.get_object('button5').get_sensitive())
		gui.qty_edited(None, '0', '4')
		gui.save_corrections_clicked(None)
		self.messaged.assert_not_called()
		self.destroy.assert_called_once_with()
		self.cursor.execute("SELECT qty, ext_price, expense_account "
							"FROM purchase_order_items WHERE id = %s",
							(self.line_id,))
		self.assertEqual(self.cursor.fetchone(),
						(Decimal(4), Decimal('12.00'), self.account))
		self.assertEqual(self.one("SELECT total FROM purchase_orders "
									"WHERE id = %s", (self.po_id,)),
						Decimal('12.00'))

	def test_a_qty_sum_is_used_as_its_result(self):
		gui = self.window()
		gui.qty_edited(None, '0', '2x2')
		self.messaged.assert_not_called()
		self.assertEqual(gui.purchase_order_items_store[0][1], 4)
		self.assertEqual(gui.purchase_order_items_store[0][6], Decimal('12.00'))

	def test_a_qty_that_is_not_a_sum_is_refused(self):
		gui = self.window()
		gui.qty_edited(None, '0', '4/')
		self.messaged.assert_called_once()
		self.assertEqual(gui.purchase_order_items_store[0][1], 5)

if __name__ == '__main__':
	unittest.main()
