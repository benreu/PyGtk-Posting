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
	window it meant to open ignored the purchase order it was handed'''
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
		# the window reads the line's account through gl_accounts.expense_account,
		# so it has to be one flagged as an expense account to count as chosen
		account = self.one("SELECT number FROM gl_accounts "
							"WHERE expense_account = True ORDER BY number LIMIT 1")
		self.cursor.execute("INSERT INTO purchase_order_items "
								"(purchase_order_id, qty, product_id, remark, "
								"price, ext_price, canceled, expense_account, "
								"order_number) "
							"VALUES (%s, 5, 19, '', 3, 15, False, %s, '')",
							(self.po_id, account))
		self.cursor.execute("UPDATE settings SET (request_po_attachment, "
							"accrual_based) = (False, False)")
		self.DB.commit() # survive the window's own rollback after it reads

	def window(self):
		gui = self.unprocessed_po.GUI(self.po_id)
		gui.get_object('entry6').set_text('INV-1234')
		self.destroy = mock.patch.object(gui.window, 'destroy').start()
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

if __name__ == '__main__':
	unittest.main()
