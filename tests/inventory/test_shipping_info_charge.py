# test_shipping_info_charge.py
#
# The shipping window bills the freight it has just paid a carrier to the
# customer's invoice: one line item of the product the user picked, priced at the
# carrier payment, carrying the tracking number as its remark. The charge is
# written in the transaction the shipping_info row is written in, so a shipment is
# never recorded with half of its paperwork.
#
# incoming_invoice_applied is driven directly with a stand-in for the payment page,
# because what it needs from IncomingInvoiceGUI is one attribute: the id of the
# incoming_invoices row the payment page has already saved and committed.

import unittest
from datetime import date
from decimal import Decimal
from unittest import mock

from harness import DBTestCase

TRACKING = '1Z999AA10123456784'


class PaymentStub:
	'''what incoming_invoice hands over with its invoice_applied signal'''
	def __init__(self, invoice_id):
		self.invoice_id = invoice_id


class ShippingInfoChargeTest(DBTestCase):

	def setUp(self):
		super().setUp()
		from db import transactor
		self.transactor = transactor
		self.customer_id = self.real_customer()
		self.tax_rate_id = self.one("SELECT id FROM tax_rates "
									"WHERE (standard, deleted) = (True, False) "
									"ORDER BY id LIMIT 1")
		self.product_id = self.new_product('Test freight out')
		self.invoice_id = self.new_invoice()
		# the copy remembers whichever product real use last billed freight as,
		# and a window pre-selects it. Cleared so that every test states the
		# precondition it means to test rather than inheriting one
		self.cursor.execute("UPDATE settings SET freight_product_id = NULL")
		self.DB.commit() # the window rolls back after every read

	# ---------------- fixtures ----------------

	def real_customer(self):
		'''SELECT id FROM contacts LIMIT 1 returns a contact with customer =
		False. The shipping window itself does not filter on it, but
		populate_invoices only finds invoices whose customer_id matches, so the
		invoice combo would come up empty'''
		return self.one("SELECT c.id FROM contacts AS c "
						"JOIN customer_markup_percent AS m "
							"ON m.id = c.markup_percent_id "
						"WHERE (c.deleted, c.customer) = (False, True) "
						"ORDER BY c.id LIMIT 1")

	def new_product(self, name):
		'''sellable, so it reaches the combo, and inventory_enabled False by
		default, which is what a freight product is'''
		return self.one("INSERT INTO products (name, ext_name, description, "
						"unit, cost, tax_rate_id, default_expense_account, "
						"revenue_account) "
						"VALUES (%s, '', '', 1, 1.00, %s, "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 3 LIMIT 1), "
							"(SELECT number FROM gl_accounts "
							"WHERE type = 4 LIMIT 1)) RETURNING id",
						(name, self.tax_rate_id))

	def new_invoice(self):
		return self.one("INSERT INTO invoices (customer_id) "
						"VALUES (%s) RETURNING id", (self.customer_id,))

	def invoice_line(self, qty, price, product_id = None):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id, price) "
						"VALUES (%s, %s, %s, %s, %s) RETURNING id",
						(self.invoice_id, qty,
						product_id or self.new_product('Test widget'),
						self.tax_rate_id, price))

	def save_totals(self):
		'''what calculate_totals writes on every keystroke'''
		self.cursor.execute("UPDATE invoices AS i SET (subtotal, tax, total) = "
								"(t.subtotal, t.tax, t.total) "
							"FROM (SELECT COALESCE(SUM(ext_price), 0.00) "
										"AS subtotal, "
									"COALESCE(SUM(tax), 0.00) AS tax, "
									"COALESCE(SUM(ext_price) + SUM(tax), 0.00) "
										"AS total "
									"FROM invoice_items "
									"WHERE invoice_id = %s) AS t "
							"WHERE i.id = %s", (self.invoice_id,
												self.invoice_id))

	def post_the_invoice(self):
		'''what invoice_window and invoice_create do between them. No stock to
		move: neither product here is inventory_enabled'''
		self.save_totals()
		self.cursor.execute("UPDATE invoices "
							"SET (posted, amount_due, dated_for) = "
								"(True, total, '2026-01-01') "
							"WHERE id = %s RETURNING total", (self.invoice_id,))
		total = self.cursor.fetchone()[0]
		self.transactor.post_invoice_accounts('2026-01-01', self.invoice_id,
												total)
		self.DB.commit()
		return total

	def carrier_payment(self, amount = '14.50'):
		'''the incoming_invoices row the payment page saved and committed before
		it emitted invoice_applied'''
		incoming_invoice_id = self.one("INSERT INTO incoming_invoices "
						"(contact_id, date_created, amount, description) "
						"VALUES (%s, %s, %s, 'test freight') RETURNING id",
						(self.customer_id, date.today(), Decimal(amount)))
		self.DB.commit()
		return PaymentStub(incoming_invoice_id)

	def existing_shipment(self, tracking = 'TEST-EARLIER-SHIPMENT'):
		'''shipping_info.invoice_id is unique, so an invoice that already carries
		a shipment can take no second one'''
		self.one("INSERT INTO shipping_info (date_shipped, tracking_number, "
					"contact_id, invoice_id) VALUES (%s, %s, %s, %s) "
					"RETURNING id",
				(date.today(), tracking, self.customer_id, self.invoice_id))
		self.DB.commit()

	def close_onto_a_statement(self):
		'''what statementing.close_invoices_and_payments does once a statement is
		finalised: the statement keeps an amount and a pdf of its own, and every
		invoice it covers is stamped and never looked at again'''
		statement_id = self.one("INSERT INTO statements "
								"(customer_id, amount, printed) "
								"VALUES (%s, 100.00, True) RETURNING id",
								(self.customer_id,))
		self.cursor.execute("UPDATE invoices SET statement_id = %s "
							"WHERE id = %s", (statement_id, self.invoice_id))
		self.DB.commit()
		return statement_id

	def window(self, invoice = True, product = True, confirm = True):
		'''driven through the real cascade: the date enables the contact combo,
		the contact fills the invoice combo, the invoice arms the product combo.
		The posted invoice question is patched out before that last step, which
		is where it is raised - a real dialog here would hang the suite'''
		import shipping_info
		gui = shipping_info.ShippingInfoGUI()
		self.message = mock.patch.object(gui, 'show_message').start()
		self.confirm = mock.patch.object(gui, 'confirm_posted_invoice',
										return_value = confirm).start()
		self.addCleanup(mock.patch.stopall)
		gui.calendar.set_date(date.today())
		gui.get_object('contact_combo').set_active_id(str(self.customer_id))
		if invoice:
			gui.get_object('invoice_id_combo').set_active_id(str(self.invoice_id))
		if product:
			gui.get_object('freight_product_combo').set_active_id(str(self.product_id))
		gui.get_object('tracking_number_entry').set_text(TRACKING)
		return gui

	# ---------------- readers ----------------

	def lines(self):
		self.cursor.execute("SELECT qty, product_id, remark, price, ext_price, "
								"tax, gl_entries_id "
							"FROM invoice_items WHERE invoice_id = %s "
							"ORDER BY id", (self.invoice_id,))
		return self.cursor.fetchall()

	def listed_invoices(self, gui):
		return [row[0] for row in gui.invoice_store]

	def freight_lines(self):
		'''only the lines billed as the shipping product, so a fixture line the
		invoice already carried is not mistaken for one'''
		return [line for line in self.lines() if line[1] == self.product_id]

	def shipments(self):
		return self.one("SELECT COUNT(*) FROM shipping_info "
						"WHERE contact_id = %s", (self.customer_id,))

	def invoice_totals(self):
		self.cursor.execute("SELECT subtotal, tax, total, amount_due "
							"FROM invoices WHERE id = %s", (self.invoice_id,))
		return self.cursor.fetchone()

	# ---------------- the charge ----------------

	def test_a_draft_invoice_gets_the_freight_as_a_line(self):
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment('14.50'))
		self.message.assert_not_called()
		lines = self.lines()
		self.assertEqual(len(lines), 1)
		qty, product_id, remark, price, ext_price, tax, _ = lines[0]
		self.assertEqual(qty, Decimal('1.00'))
		self.assertEqual(product_id, self.product_id)
		self.assertEqual(remark, TRACKING)
		self.assertEqual(price, Decimal('14.50'))
		self.assertEqual(ext_price, Decimal('14.50'))

	def test_the_draft_totals_follow_the_charge(self):
		'''resync_invoice_accounts leaves a draft alone, so the window saves the
		totals calculate_totals would have'''
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment('14.50'))
		_, _, _, ext_price, tax, _ = self.lines()[0][1:]
		subtotal, invoice_tax, total, amount_due = self.invoice_totals()
		self.assertEqual(subtotal, Decimal('14.50'))
		self.assertEqual(invoice_tax, tax)
		self.assertEqual(total, Decimal('14.50') + tax)
		self.assertEqual(amount_due, Decimal('0.00')) # a draft owes nothing yet

	def test_the_charge_is_added_beneath_the_lines_already_there(self):
		self.invoice_line(2, '10.00')
		self.save_totals()
		self.DB.commit()
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment('14.50'))
		lines = self.lines()
		self.assertEqual(len(lines), 2)
		self.assertEqual(lines[1][1], self.product_id) # sorts last by id
		self.assertEqual(self.invoice_totals()[0], Decimal('34.50'))

	def test_the_shipment_is_recorded_with_the_charge(self):
		gui = self.window()
		payment = self.carrier_payment()
		gui.incoming_invoice_applied(payment)
		self.cursor.execute("SELECT tracking_number, invoice_id, "
								"incoming_invoice_id "
							"FROM shipping_info WHERE contact_id = %s",
							(self.customer_id,))
		self.assertEqual(self.cursor.fetchone(),
						(TRACKING, self.invoice_id, payment.invoice_id))

	# ---------------- the remembered product ----------------

	def test_the_product_billed_is_remembered(self):
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment())
		self.assertEqual(self.one("SELECT freight_product_id FROM settings"),
						self.product_id)

	def test_a_later_window_opens_on_the_remembered_product(self):
		self.cursor.execute("UPDATE settings SET freight_product_id = %s",
							(self.product_id,))
		self.DB.commit()
		import shipping_info
		gui = shipping_info.ShippingInfoGUI()
		self.assertEqual(gui.get_object('freight_product_combo').get_active_id(),
						str(self.product_id))
		self.assertEqual(gui.freight_product_id, str(self.product_id))

	def test_a_retired_product_leaves_the_combo_empty(self):
		'''set_active_id cannot find an id that is not in the store, and the
		product is chosen again rather than silently billed'''
		self.cursor.execute("UPDATE settings SET freight_product_id = %s",
							(self.product_id,))
		self.cursor.execute("UPDATE products SET sellable = False WHERE id = %s",
							(self.product_id,))
		self.DB.commit()
		import shipping_info
		gui = shipping_info.ShippingInfoGUI()
		self.assertEqual(gui.get_object('freight_product_combo').get_active_id(), None)
		self.assertEqual(gui.freight_product_id, None)

	# ---------------- when nothing may be billed ----------------

	def test_a_description_only_shipment_bills_nothing(self):
		'''no invoice was chosen, so there is nothing to put the charge on, and
		the whole freight row greys out to say so rather than leaving a remembered
		product sitting there looking like it will be billed. The shipment itself
		is still recorded'''
		gui = self.window(invoice = False)
		gui.get_object('shipping_description_entry').set_text('two boxes')
		self.assertFalse(gui.get_object('bill_freight_check').get_sensitive())
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())
		self.assertFalse(gui.freight_is_billable ())
		gui.incoming_invoice_applied(self.carrier_payment())
		self.message.assert_not_called()
		self.assertEqual(self.lines(), [])
		self.assertEqual(self.shipments(), 1)

	def test_no_product_chosen_bills_nothing(self):
		gui = self.window(product = False)
		gui.incoming_invoice_applied(self.carrier_payment())
		self.message.assert_not_called()
		self.assertEqual(self.lines(), [])
		self.assertEqual(self.shipments(), 1)

	def test_a_draft_and_a_posted_invoice_are_both_listed(self):
		'''the positive control for the filter below: a freight charge can go on
		either, the posted one after the question has been answered'''
		draft_id = self.invoice_id
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		posted_id = self.invoice_id
		self.invoice_id = self.new_invoice() # a second draft to open the window on
		self.DB.commit()
		gui = self.window(invoice = False)
		listed = self.listed_invoices(gui)
		self.assertIn(str(draft_id), listed)
		self.assertIn(str(posted_id), listed)

	def test_clearing_the_box_bills_nothing(self):
		'''the shipment and the carrier payment are still recorded, the customer
		is simply not charged for the freight'''
		gui = self.window()
		gui.get_object('bill_freight_check').set_active(False)
		self.assertFalse(gui.freight_is_billable ())
		gui.incoming_invoice_applied(self.carrier_payment())
		self.message.assert_not_called()
		self.assertEqual(self.freight_lines(), [])
		self.assertEqual(self.shipments(), 1)

	def test_clearing_the_box_disables_the_product_combo(self):
		gui = self.window()
		self.assertTrue(gui.get_object('freight_product_combo').get_sensitive())
		gui.get_object('bill_freight_check').set_active(False)
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())
		gui.get_object('bill_freight_check').set_active(True)
		self.assertTrue(gui.get_object('freight_product_combo').get_sensitive())

	def test_the_box_is_checked_again_on_the_next_shipment(self):
		'''a decision per shipment, not a preference: nothing saves it'''
		gui = self.window()
		gui.get_object('bill_freight_check').set_active(False)
		gui.incoming_invoice_applied(self.carrier_payment())
		import shipping_info
		later = shipping_info.ShippingInfoGUI()
		self.assertTrue(later.get_object('bill_freight_check').get_active())

	def test_the_box_cannot_arm_an_invoice_that_refuses_the_charge(self):
		'''checking it back on does not override the invoice's own state'''
		self.cursor.execute("UPDATE invoices SET paid = True WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui = self.window(invoice = False)
		gui.invoice_id = str(self.invoice_id) # as a stale list would leave it
		gui.set_freight_charge_state ()
		gui.get_object('bill_freight_check').set_active(False)
		gui.get_object('bill_freight_check').set_active(True)
		self.assertFalse(gui.freight_is_billable ())
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())

	def test_a_paid_invoice_is_not_listed(self):
		'''its receivable is already offset, so resync_invoice_accounts skips it
		and a line there would raise the total with no revenue under it'''
		self.cursor.execute("UPDATE invoices SET paid = True WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui = self.window(invoice = False)
		self.assertNotIn(str(self.invoice_id), self.listed_invoices(gui))

	def test_an_invoice_that_already_shipped_is_not_listed(self):
		'''shipping_info.invoice_id is unique, and the insert that would fail
		runs after the carrier payment has already been committed'''
		self.existing_shipment()
		gui = self.window(invoice = False)
		self.assertNotIn(str(self.invoice_id), self.listed_invoices(gui))

	def test_the_gate_still_refuses_an_invoice_the_list_has_gone_stale_on(self):
		'''the list is only rebuilt when the contact changes, so an invoice paid
		while the window was open is still selectable'''
		gui = self.window()
		self.assertTrue(gui.bill_freight)
		self.cursor.execute("UPDATE invoices SET paid = True WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		gui.set_freight_charge_state ()
		self.assertFalse(gui.bill_freight)
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())
		gui.incoming_invoice_applied(self.carrier_payment())
		self.assertEqual(self.freight_lines(), [])
		self.assertEqual(self.shipments(), 1)

	def test_an_invoice_on_a_statement_is_not_listed(self):
		'''the statement has frozen its own amount and its pdf, and
		close_invoices_and_payments only ever picks up invoices with no
		statement_id, so the charge would reach no statement ever'''
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		self.close_onto_a_statement()
		gui = self.window(invoice = False)
		self.assertNotIn(str(self.invoice_id), self.listed_invoices(gui))
		self.confirm.assert_not_called() # it was never offered to be asked about

	def test_a_posted_invoice_asks_before_it_is_billed(self):
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		gui = self.window(confirm = True)
		self.confirm.assert_called_once()
		self.assertTrue(gui.bill_freight)
		gui.incoming_invoice_applied(self.carrier_payment('14.50'))
		self.assertEqual(len(self.freight_lines()), 1)

	def test_a_declined_posted_invoice_bills_nothing(self):
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		gui = self.window(confirm = False)
		self.confirm.assert_called_once()
		self.assertFalse(gui.bill_freight)
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())
		gui.incoming_invoice_applied(self.carrier_payment())
		self.assertEqual(self.freight_lines(), [])
		self.assertEqual(self.shipments(), 1) # the shipment is recorded either way

	def test_a_draft_invoice_is_never_asked_about(self):
		gui = self.window()
		self.confirm.assert_not_called()
		self.assertTrue(gui.bill_freight)

	def test_the_posted_question_is_asked_once_per_invoice(self):
		'''invoice_changed and invoice_match_selected both land in
		set_freight_charge_state and either may fire for a single pick'''
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		gui = self.window()
		gui.set_freight_charge_state ()
		gui.set_freight_charge_state ()
		self.confirm.assert_called_once()

	def test_an_invoice_statemented_after_it_was_picked_bills_nothing(self):
		'''the payment page can sit open for a while, so the state is read back
		where the charge is written and not only where the invoice was chosen'''
		self.invoice_line(2, '10.00')
		self.post_the_invoice()
		gui = self.window()
		self.assertTrue(gui.bill_freight)
		self.close_onto_a_statement() # while the payment page was open
		gui.incoming_invoice_applied(self.carrier_payment())
		self.assertTrue(gui.bill_freight) # the window still believes it may
		self.assertEqual(self.freight_lines(), [])
		self.assertEqual(self.shipments(), 1)

	def test_changing_contact_disarms_the_freight_product_combo(self):
		'''populate_invoices clears the invoice, so the charge has nowhere to go
		until another one is picked'''
		gui = self.window()
		self.assertTrue(gui.get_object('freight_product_combo').get_sensitive())
		other_id = self.one("SELECT c.id FROM contacts AS c "
							"JOIN customer_markup_percent AS m "
								"ON m.id = c.markup_percent_id "
							"WHERE (c.deleted, c.customer) = (False, True) "
								"AND c.id != %s ORDER BY c.id LIMIT 1",
							(self.customer_id,))
		gui.get_object('contact_combo').set_active_id(str(other_id))
		self.assertFalse(gui.get_object('freight_product_combo').get_sensitive())
		self.assertFalse(gui.bill_freight)

	def test_a_rejected_shipment_takes_the_charge_down_with_it(self):
		'''the tracking number is unique: a second apply of the same shipment
		must not leave a second freight line behind'''
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment())
		self.assertEqual(len(self.lines()), 1)
		gui.incoming_invoice_applied(self.carrier_payment())
		self.message.assert_called_once()
		self.assertEqual(len(self.lines()), 1)
		self.assertEqual(self.shipments(), 1)

	# ---------------- a posted invoice follows into the ledger ----------------

	# (see test_invoice_accounts_resync for the ledger rewrite itself)
	def test_a_posted_invoice_is_restated_around_the_charge(self):
		self.invoice_line(2, '10.00')
		posted_total = self.post_the_invoice()
		gui = self.window()
		gui.incoming_invoice_applied(self.carrier_payment('14.50'))
		self.message.assert_not_called()
		subtotal, invoice_tax, total, amount_due = self.invoice_totals()
		self.assertEqual(subtotal, Decimal('34.50'))
		self.assertEqual(total, Decimal('34.50') + invoice_tax)
		self.assertGreater(total, posted_total)
		self.assertEqual(amount_due, total) # the receivable owes the freight too
		# post_invoice_accounts gave the new line its own revenue entry
		freight = self.lines()[1]
		self.assertIsNotNone(freight[6])
		self.assertEqual(self.one("SELECT amount FROM gl_entries WHERE id = %s",
								(freight[6],)), Decimal('14.50'))


if __name__ == '__main__':
	unittest.main()
