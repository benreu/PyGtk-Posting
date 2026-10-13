# test_invoice_shipping_address.py
#
# The invoice window's Ship To combo and the read-only box beside it. The box
# shows the address the printed Ship To block will carry, and blank when the
# invoice ships to the billing address, which is already in the box above it.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
from gi.repository import Gtk

class InvoiceShippingAddressTest(harness.DBTestCase):

	def setUp(self):
		super().setUp()
		self.customer_id = self.real_customer()
		self.other_customer_id = self.real_customer(self.customer_id)
		# standard first, so populate_ puts the combo on it by default
		self.dock_id = self.shipping_address(self.customer_id, 'Dock',
								'1 Dock St', 'Reading', 'PA', '19601', True)
		self.yard_id = self.shipping_address(self.customer_id, 'Yard',
								'2 Yard Ln', 'Lancaster', 'PA', '17601')
		self.other_id = self.shipping_address(self.other_customer_id, 'Theirs',
								'3 Their Way', 'York', 'PA', '17401')
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id",
									(self.customer_id,))
		self.DB.commit() # the window rolls back after every read

	def real_customer(self, besides = None):
		'''a contact the customer combo will actually hold: SELECT id FROM
		contacts LIMIT 1 returns one with customer = False, which never reaches
		the combo and leaves gui.customer_id None'''
		return self.one("SELECT c.id FROM contacts AS c "
						"JOIN customer_markup_percent AS m "
							"ON m.id = c.markup_percent_id "
						"WHERE (c.deleted, c.customer) = (False, True) "
							"AND (%s::bigint IS NULL OR c.id != %s) "
						"ORDER BY c.id LIMIT 1", (besides, besides))

	def shipping_address(self, contact_id, description, address, city, state,
							zip_code, standard = False):
		return self.one("INSERT INTO contact_shipping_addresses "
						"(contact_id, description, address, city, state, zip, "
						"standard) VALUES (%s, %s, %s, %s, %s, %s, %s) "
						"RETURNING id",
						(contact_id, description, address, city, state,
						zip_code, standard))

	def ships_to(self, address_id):
		self.cursor.execute("UPDATE invoices SET shipping_address_id = %s "
							"WHERE id = %s", (address_id, self.invoice_id))
		self.DB.commit()

	def saved_address_id(self):
		return self.one("SELECT shipping_address_id FROM invoices "
						"WHERE id = %s", (self.invoice_id,))

	def window(self):
		import invoice_window
		gui = invoice_window.InvoiceGUI(self.invoice_id)
		mock.patch.object(gui, 'show_error_dialog').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def combo(self, gui):
		return gui.builder.get_object('comboboxtext_shipping')

	def box(self, gui, name = 'shipping_address_box'):
		buf = gui.builder.get_object(name).get_buffer()
		return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

	def combo_ids(self, gui):
		combo = self.combo(gui)
		return [row[1] for row in combo.get_model()]

	# ---------------- the box follows the combo ----------------

	def test_opening_an_invoice_shows_its_saved_address(self):
		'''the combo was only ever filled by customer_selected, which bails out
		while an invoice is being loaded, so the saved address never showed'''
		self.ships_to(self.yard_id)
		gui = self.window()
		self.assertEqual(self.combo(gui).get_active_id(), str(self.yard_id))
		self.assertEqual(self.box(gui), '2 Yard Ln\nLancaster, PA 17601')

	def test_billing_address_leaves_the_box_blank(self):
		self.ships_to(self.yard_id)
		gui = self.window()
		self.combo(gui).set_active_id('0')
		self.assertEqual(self.box(gui), '')
		self.assertNotEqual(self.box(gui, 'address_box'), '',
							'the billing address is still shown above it')

	def test_choosing_an_address_fills_the_box_and_is_saved(self):
		'''the box must never be refreshed between the UPDATE and the commit: a
		read helper ending in the house-style DB.rollback () would drop it'''
		gui = self.window()
		self.combo(gui).set_active_id(str(self.yard_id))
		self.assertEqual(self.box(gui), '2 Yard Ln\nLancaster, PA 17601')
		self.assertEqual(self.saved_address_id(), self.yard_id)

	def test_switching_back_to_billing_clears_the_box_and_the_column(self):
		self.ships_to(self.yard_id)
		gui = self.window()
		self.combo(gui).set_active_id('0')
		self.assertEqual(self.box(gui), '')
		self.assertIsNone(self.saved_address_id())

	# ---------------- every path that loads an invoice ----------------

	def test_reload_brings_the_address_along(self):
		gui = self.window()
		self.ships_to(self.yard_id) # as another posting station would
		gui.reload_invoice ()
		self.assertEqual(self.combo(gui).get_active_id(), str(self.yard_id))
		self.assertEqual(self.box(gui), '2 Yard Ln\nLancaster, PA 17601')

	def test_a_new_invoice_starts_on_the_standard_address(self):
		self.ships_to(self.yard_id)
		gui = self.window()
		gui.clear_invoice ()
		self.assertEqual(self.combo(gui).get_active_id(), str(self.dock_id))
		self.assertEqual(self.box(gui), '1 Dock St\nReading, PA 19601')

	# ---------------- addresses that no longer belong ----------------

	def test_a_retired_address_is_still_shown(self):
		'''invoice_create does not filter sa.deleted, so the screen may not
		either or it disagrees with what prints'''
		self.ships_to(self.yard_id)
		self.cursor.execute("UPDATE contact_shipping_addresses "
							"SET deleted = True WHERE id = %s", (self.yard_id,))
		self.DB.commit()
		gui = self.window()
		self.assertEqual(self.combo(gui).get_active_id(), str(self.yard_id))
		self.assertEqual(self.box(gui), '2 Yard Ln\nLancaster, PA 17601')

	def test_another_contacts_address_leaves_the_combo_on_something(self):
		'''set_active_id finds no such row and silently leaves the combo on
		nothing at all, so get_active_id () would come back None'''
		self.ships_to(self.other_id)
		gui = self.window()
		self.assertEqual(self.combo(gui).get_active_id(), str(self.dock_id))
		self.assertNotIn(str(self.other_id), self.combo_ids(gui))

	def test_a_transfer_drops_the_other_contacts_address(self):
		self.ships_to(self.yard_id)
		gui = self.window()
		dialog = gui.builder.get_object('transfer_invoice_dialog')
		mock.patch.object(dialog, 'run',
							return_value = Gtk.ResponseType.ACCEPT).start()
		mock.patch.object(dialog, 'hide').start()
		gui.builder.get_object('transfer_customer_combo').set_active_id(
													str(self.other_customer_id))
		gui.transfer_invoice_activated (None)
		self.assertIsNone(self.saved_address_id())
		self.assertEqual(self.combo_ids(gui), ['0', str(self.other_id)])
		self.assertEqual(self.box(gui), '3 Their Way\nYork, PA 17401')

if __name__ == '__main__':
	unittest.main()
