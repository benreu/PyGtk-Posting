# test_contact_shipping_address.py
#
# The "Copy billing address" button in the shipping address editor. harness has
# to be imported first: contact_edit_shipping_address does `from db_connection
# import DB`, which copies the connection by value.

import os, sys, unittest

sys.path.insert(0, os.path.dirname(__file__))

import harness
from gi.repository import Gtk

import contact_edit_shipping_address as cesa

class FakeOverview:
	'''the editor only needs a window to be transient for, a contact_id, and the
	repopulate callback that save_clicked fires'''
	def __init__(self, contact_id = 0):
		self.window = Gtk.Window()
		self.contact_id = contact_id
		self.repopulated = 0

	def populate_contact_shipping_addresses(self):
		self.repopulated += 1

class TestCopyBillingAddress(harness.DBTestCase):

	def billing_contact(self):
		'''a real contact whose billing address is filled in'''
		self.cursor.execute("SELECT id, address, city, state, zip FROM contacts "
							"WHERE (deleted, customer) = (False, True) "
								"AND address != '' AND city != '' AND zip != '' "
							"ORDER BY id LIMIT 1")
		row = self.cursor.fetchone()
		if row is None:
			self.skipTest('no contact with a billing address')
		return row

	def entries(self, gui):
		get = lambda name: gui.builder.get_object(name).get_text()
		# entry3 is the zip and entry4/entry5 are city/state, the opposite of
		# the mapping contact_edit_main.ui uses
		return (get('entry2'), get('entry4'), get('entry5'), get('entry3'))

	def new_editor(self, contact_id):
		overview = FakeOverview(contact_id)
		gui = cesa.ContactEditShippingAddressGUI(overview)
		gui.contact_id = contact_id # what new_shipping_address_clicked does
		return gui, overview

	def test_copies_the_four_address_fields(self):
		contact_id, address, city, state, zip_code = self.billing_contact()
		gui, overview = self.new_editor(contact_id)
		self.assertEqual(self.entries(gui), ('', '', '', ''))
		gui.copy_billing_address_clicked(None)
		self.assertEqual(self.entries(gui), (address, city, state, zip_code))

	def test_leaves_the_description_alone(self):
		contact_id = self.billing_contact()[0]
		gui, overview = self.new_editor(contact_id)
		gui.copy_billing_address_clicked(None)
		self.assertEqual(gui.builder.get_object('entry1').get_text(), '')
		gui.builder.get_object('entry1').set_text('Warehouse')
		gui.copy_billing_address_clicked(None)
		self.assertEqual(gui.builder.get_object('entry1').get_text(), 'Warehouse')

	def test_overwrites_whatever_was_typed(self):
		contact_id, address, city, state, zip_code = self.billing_contact()
		gui, overview = self.new_editor(contact_id)
		gui.builder.get_object('entry2').set_text('999 Old Road')
		gui.builder.get_object('entry3').set_text('00000')
		gui.copy_billing_address_clicked(None)
		self.assertEqual(self.entries(gui), (address, city, state, zip_code))

	def test_falls_back_to_the_overview_contact_id(self):
		'''contact_id is assigned only after __init__ for a new address'''
		contact_id, address, city, state, zip_code = self.billing_contact()
		overview = FakeOverview(contact_id)
		gui = cesa.ContactEditShippingAddressGUI(overview)
		self.assertEqual(gui.contact_id, None) # the caller has not assigned yet
		gui.copy_billing_address_clicked(None)
		self.assertEqual(self.entries(gui), (address, city, state, zip_code))

	def test_no_contact_selected_is_a_no_op(self):
		gui, overview = self.new_editor(0)
		gui.contact_id = None
		overview.contact_id = 0
		gui.copy_billing_address_clicked(None)
		self.assertEqual(self.entries(gui), ('', '', '', ''))

	def test_editing_an_existing_row_copies_onto_it(self):
		'''in edit mode contact_id comes from the row, not from the caller'''
		contact_id, address, city, state, zip_code = self.billing_contact()
		address_id = self.one("INSERT INTO contact_shipping_addresses "
								"(contact_id, description, address, city, state, zip) "
								"VALUES (%s, 'Warehouse', '1 Dock St', 'Reading', "
								"'PA', '19601') RETURNING id", (contact_id,))
		self.DB.commit() # or populate_carrier_combo's rollback discards the row
		overview = FakeOverview(0) # deliberately useless, the row must win
		gui = cesa.ContactEditShippingAddressGUI(overview, address_id)
		self.assertEqual(gui.contact_id, contact_id)
		self.assertEqual(self.entries(gui),
							('1 Dock St', 'Reading', 'PA', '19601'))
		gui.copy_billing_address_clicked(None)
		self.assertEqual(self.entries(gui), (address, city, state, zip_code))
		self.assertEqual(gui.builder.get_object('entry1').get_text(), 'Warehouse')

if __name__ == '__main__':
	unittest.main()
