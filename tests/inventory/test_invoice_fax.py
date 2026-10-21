# test_invoice_fax.py
#
# Faxing an invoice. In the invoice window the number is confirmed before the
# invoice is posted, while it can still be checked against it, and posting
# faxes to it without asking again; from Unpaid invoices the saved pdf is faxed
# as it was printed. faxing itself, the dialog and the Send fax window are in
# test_faxing.py. Nothing here can reach the real lp: the dialog, the queue
# check and the send are mocked in every test that could fax.

import os, sys, shutil, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
import faxing # first: it asks for the Poppler version
from gi.repository import Gtk
from test_faxing import write_pdf

class InvoiceFaxTest(harness.DBTestCase):
	'''the number is confirmed in the invoice window before posting, while it
	can still be checked against the invoice, and posting faxes to it without
	asking again'''

	REAL_CUSTOMERS = ("SELECT c.id FROM contacts AS c "
						"JOIN customer_markup_percent AS m "
							"ON m.id = c.markup_percent_id "
						"WHERE (c.deleted, c.customer) = (False, True) "
						"ORDER BY c.id LIMIT 2")

	def setUp(self):
		super().setUp()
		# customers the combo holds: the first contact in the table is not one
		self.cursor.execute(self.REAL_CUSTOMERS)
		(self.customer_id,), (self.other_customer_id,) = self.cursor.fetchall()
		self.cursor.execute("UPDATE contacts SET fax = '585 554 6779' "
							"WHERE id = %s", (self.customer_id,))
		self.customer_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.customer_id,))
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id",
									(self.customer_id,))
		self.DB.commit()
		self.message = mock.patch.object(faxing, 'show_message').start()
		self.queue = mock.patch.object(faxing, 'queue_available',
										return_value = True).start()
		self.dialog = mock.patch.object(faxing, 'FaxDialog').start()
		self.addCleanup(mock.patch.stopall)
		import invoice_window
		self.gui = invoice_window.InvoiceGUI(self.invoice_id)

	def menuitem(self):
		return self.gui.builder.get_object('fax_invoice_menuitem')

	def choose(self, number):
		self.dialog.return_value.get_number.return_value = number
		self.gui.fax_invoice_activated(None)

	def test_nothing_is_faxed_until_asked_for(self):
		self.assertIsNone(self.gui.fax_number)
		self.assertTrue(self.menuitem().get_sensitive())
		self.assertEqual(self.menuitem().get_label(), 'Fax invoice...')

	def test_choosing_fax_confirms_the_number_before_posting(self):
		self.choose('15855546779')
		self.dialog.assert_called_once_with(self.gui.window, self.customer_name,
											'585 554 6779', number = None,
											send_label = 'Fax when posted',
											can_stop = False)
		self.assertEqual(self.gui.fax_number, '15855546779')
		self.assertEqual(self.menuitem().get_label(),
							'Fax invoice to 1 (585) 554-6779...')

	def test_choosing_again_offers_the_number_and_can_take_it_back(self):
		self.choose('15855546779')
		self.choose(None) # canceled: the number stands
		self.assertEqual(self.gui.fax_number, '15855546779')
		self.assertEqual(self.dialog.call_args[1]['number'], '15855546779')
		self.assertTrue(self.dialog.call_args[1]['can_stop'])
		self.choose('') # Don't fax
		self.assertIsNone(self.gui.fax_number)
		self.assertEqual(self.menuitem().get_label(), 'Fax invoice...')

	def test_without_a_fax_queue_nothing_is_asked(self):
		self.queue.return_value = False
		self.gui.fax_invoice_activated(None)
		self.dialog.assert_not_called()
		self.assertIsNone(self.gui.fax_number)
		self.assertIn('no fax queue', self.message.call_args[0][2])

	def test_another_customer_takes_the_fax_back(self):
		self.choose('15855546779')
		self.gui.loading = True # stay on this invoice, as a transfer does
		self.gui.customer_selected(str(self.customer_id))
		self.assertEqual(self.gui.fax_number, '15855546779')
		self.gui.customer_selected(str(self.other_customer_id))
		self.gui.loading = False
		self.assertIsNone(self.gui.fax_number)
		self.assertEqual(self.menuitem().get_label(), 'Fax invoice...')

	def test_leaving_the_invoice_takes_the_fax_back(self):
		self.choose('15855546779')
		self.gui.clear_invoice()
		self.assertIsNone(self.gui.fax_number)

	def post(self):
		'''post_invoice with the printing and the stock moves stood in for:
		what is under test is only what happens after the invoice is saved'''
		invoice = mock.Mock()
		invoice.print_dialog.return_value = Gtk.PrintOperationResult.APPLY
		with mock.patch.object(self.gui, 'invoice_has_items',
								return_value = True), \
				mock.patch.object(self.gui, 'calculate_totals'), \
				mock.patch.object(self.gui, 'create_invoice_document',
									return_value = invoice), \
				mock.patch('inventory.inventorying.fractional_quantity_message',
							return_value = None), \
				mock.patch('inventory.inventorying.negative_stock_message',
							return_value = None), \
				mock.patch('inventory.inventorying.sell'):
			self.gui.post_invoice(None)
		invoice.post.assert_called_once_with()
		return invoice

	def test_posting_faxes_the_confirmed_number_without_asking(self):
		self.choose('15855546779')
		self.dialog.reset_mock()
		invoice = self.post()
		invoice.fax.assert_called_once_with(self.gui.window, '15855546779')
		self.dialog.assert_not_called()

	def test_posting_without_a_fax_sends_none(self):
		invoice = self.post()
		invoice.fax.assert_not_called()

	def test_setup_faxes_its_own_pdf(self):
		from invoice import invoice_create
		setup = invoice_create.Setup.__new__(invoice_create.Setup)
		setup.invoice_id = self.invoice_id
		setup.invoice_pdf = '/tmp/Inv_test.pdf'
		with mock.patch.object(faxing, 'send_and_report',
								return_value = 'BRFAX-3') as send:
			self.assertEqual(setup.fax('window', '15855546779'), 'BRFAX-3')
		send.assert_called_once_with('window', '/tmp/Inv_test.pdf',
										'15855546779',
										'Invoice_%s' % self.invoice_id)


class UnpaidInvoiceFaxTest(harness.DBTestCase):
	'''the posted invoice is faxed from invoices.pdf_data as it was printed,
	not rebuilt, and the copy written for lp does not outlive the fax'''

	def setUp(self):
		super().setUp()
		directory = tempfile.mkdtemp(prefix = 'test_faxing_')
		self.addCleanup(shutil.rmtree, directory, True)
		with open(write_pdf(os.path.join(directory, 'inv.pdf'), 1,
								'posted invoice'), 'rb') as f:
			self.pdf_bytes = f.read()
		self.customer_id = self.one("SELECT id FROM contacts "
									"WHERE deleted = False ORDER BY id LIMIT 1")
		self.cursor.execute("UPDATE contacts SET fax = '607 231 4032' "
							"WHERE id = %s", (self.customer_id,))
		self.customer_name = self.one("SELECT name FROM contacts WHERE id = %s",
										(self.customer_id,))
		import psycopg2
		self.invoice_id = self.one("INSERT INTO invoices (customer_id, pdf_data) "
									"VALUES (%s, %s) RETURNING id",
									(self.customer_id,
									psycopg2.Binary(self.pdf_bytes)))
		self.DB.commit()
		self.addCleanup(mock.patch.stopall)
		# the builder alone: the full window also reads its saved layout and
		# fills itself with every unpaid invoice, neither of which this needs
		import unpaid_invoices
		self.gui = unpaid_invoices.GUI.__new__(unpaid_invoices.GUI)
		Gtk.Builder.__init__(self.gui)
		self.gui.add_from_file(unpaid_invoices.UI_FILE)
		self.gui.window = self.gui.get_object('window')
		self.addCleanup(self.gui.window.destroy)
		store = self.gui.get_object('unpaid_invoice_store')
		tree_iter = store.append([self.invoice_id, 'Inv', self.customer_id,
									self.customer_name, '', '', '0', 0, 0])
		self.gui.get_object('treeview-selection').select_iter(tree_iter)

	def test_the_saved_pdf_goes_to_the_customers_fax(self):
		faxed = []
		def fax_pdf(parent, path, title, name, stored):
			with open(path, 'rb') as f:
				faxed.append((f.read(), path, title, name, stored))
		with mock.patch.object(faxing, 'fax_pdf', side_effect = fax_pdf):
			self.gui.fax_invoice_activated(None)
		self.assertEqual(len(faxed), 1)
		data, path, title, name, stored = faxed[0]
		self.assertEqual(data, self.pdf_bytes)
		self.assertEqual((title, name, stored),
						('Invoice_%s' % self.invoice_id, self.customer_name,
						'607 231 4032'))
		self.assertFalse(os.path.exists(path))

	def test_an_invoice_without_a_saved_pdf_is_said(self):
		self.cursor.execute("UPDATE invoices SET pdf_data = NULL WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		with mock.patch.object(faxing, 'fax_pdf') as fax, \
				mock.patch.object(self.gui, 'show_message') as message:
			self.gui.fax_invoice_activated(None)
		fax.assert_not_called()
		message.assert_called_once_with("No saved PDF found for this invoice.")


if __name__ == '__main__':
	unittest.main()
