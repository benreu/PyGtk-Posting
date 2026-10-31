import unittest
from datetime import date
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

PRICE = Decimal('7.25') # the customer's price for the product, set in setUp

class DocumentsTest(DBTestCase):
	'''General > Create document posted when the print dialog called it off,
	deleted without asking (and not at all once it had lines), raised on every
	scan and drop, and showed a product's price without saving it; Documents
	to invoice ignored Refresh prices'''
	def setUp(self):
		super().setUp()
		import documents_window
		self.documents_window = documents_window
		# a customer with a markup row: contacts LIMIT 1 is not a customer
		self.customer_id = self.one("SELECT c.id FROM contacts AS c "
							"JOIN customer_markup_percent AS m "
								"ON m.id = c.markup_percent_id "
							"WHERE (c.deleted, c.customer) = (False, True) "
							"ORDER BY c.id LIMIT 1")
		self.product_id = 19
		self.barcode = 'TESTDOCBARCODE19'
		self.cursor.execute("UPDATE products SET (barcode, cost, deleted, "
								"sellable, stock) = (%s, 3, False, True, True) "
							"WHERE id = %s", (self.barcode, self.product_id))
		markup_id = self.one("SELECT markup_percent_id FROM contacts "
							"WHERE id = %s", (self.customer_id,))
		self.cursor.execute("DELETE FROM products_markup_prices "
							"WHERE (product_id, markup_id) = (%s, %s)",
							(self.product_id, markup_id))
		self.cursor.execute("INSERT INTO products_markup_prices "
							"(product_id, markup_id, price) VALUES (%s, %s, %s)",
							(self.product_id, markup_id, PRICE))
		self.other_product_id = self.one("SELECT id FROM products "
										"WHERE id <> %s ORDER BY id LIMIT 1",
										(self.product_id,))
		self.cursor.execute("SELECT id, name FROM document_types "
							"ORDER BY id LIMIT 1")
		row = self.cursor.fetchone()
		if row == None:
			row = (self.one("INSERT INTO document_types (name) "
							"VALUES ('Quote') RETURNING id"), 'Quote')
		self.document_type_id, self.document_type = row
		self.document_id = self.one("INSERT INTO documents (contact_id, "
								"closed, invoiced, canceled, date_created, "
								"dated_for, document_type_id, pending_invoice, "
								"name) VALUES (%s, False, False, False, %s, %s, "
								"%s, False, 'Quo_test') RETURNING id",
								(self.customer_id, date.today(), date.today(),
								self.document_type_id))
		self.DB.commit()

	def window(self):
		'''the window with the test document open, as existing_document leaves it'''
		gui = self.documents_window.DocumentGUI()
		gui.contact_id = str(self.customer_id) # a string, as the combo hands it over
		gui.document_type_id = str(self.document_type_id)
		gui.document_type = self.document_type
		gui.document_id = self.document_id
		gui.populate_document_store()
		self.messaged = mock.patch.object(gui, 'show_message').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def scan(self, gui, barcode = None):
		entry = gui.builder.get_object('entry2')
		entry.set_text(barcode or self.barcode)
		gui.barcode_entry_activated(entry)

	def lines(self, document_id = None):
		self.cursor.execute("SELECT product_id, qty, price, ext_price "
							"FROM document_items WHERE document_id = %s "
							"ORDER BY id", (document_id or self.document_id,))
		return self.cursor.fetchall()

	def add_line(self, product_id, qty, price):
		self.cursor.execute("INSERT INTO document_items (document_id, "
							"product_id, qty, price, ext_price) "
							"VALUES (%s, %s, %s, %s, %s * %s)",
							(self.document_id, product_id, qty, price, qty, price))
		self.DB.commit()

	def test_an_unknown_barcode_is_reported(self):
		gui = self.window()
		self.scan(gui, 'NO SUCH BARCODE <&>')
		self.messaged.assert_called_once()
		self.assertIn('&lt;&amp;&gt;', self.messaged.call_args[0][0])
		self.assertEqual(self.lines(), [])

	def test_a_scan_with_no_document_open_is_reported(self):
		gui = self.window()
		gui.document_id = 0
		self.scan(gui)
		self.messaged.assert_called_once()
		self.assertEqual(self.lines(), [])

	def test_a_first_scan_saves_a_line_at_the_customer_price(self):
		gui = self.window()
		self.scan(gui)
		self.assertEqual(self.lines(), [(self.product_id, Decimal('1.00'),
										PRICE, PRICE)])
		self.assertEqual([(row[1], row[12], row[14]) for row in gui.documents_store],
						[('1.00', '7.2500', '7.25')])
		self.assertEqual(gui.builder.get_object('entry8').get_text(), '7.25')
		self.messaged.assert_not_called()

	def test_a_second_scan_adds_to_the_same_line(self):
		gui = self.window()
		self.scan(gui)
		self.scan(gui)
		self.assertEqual(self.lines(), [(self.product_id, Decimal('2.00'),
										PRICE, PRICE * 2)])
		self.assertEqual(len(gui.documents_store), 1)

	def test_a_dropped_product_is_added_with_its_qty(self):
		gui = self.window()
		data = mock.Mock() # products_overview sends "qty product_id"
		data.get_text.return_value = '3 %s' % self.product_id
		gui.on_drag_data_received(gui.treeview, None, 0, 0, data, 129, 0)
		self.assertEqual(self.lines(), [(self.product_id, Decimal('3.00'),
										PRICE, PRICE * 3)])

	def test_choosing_a_product_saves_its_price(self):
		self.add_line(self.other_product_id, 2, 0)
		gui = self.window()
		gui.product_selected(str(self.product_id), Gtk.TreePath(0))
		self.assertEqual(self.lines(), [(self.product_id, Decimal('2.00'),
										PRICE, PRICE * 2)])
		row = gui.documents_store[0]
		self.assertEqual((row[2], row[12], row[14]),
						(self.product_id, '7.2500', '14.50'))
		self.assertEqual(gui.builder.get_object('entry8').get_text(), '14.50')

	def post(self, gui, result):
		'''post with the document stubbed out, so no odt is rendered and no
		print dialog opens'''
		gui.builder.get_object('menuitem1').set_active(False) # the print dialog
		gui.builder.get_object('menuitem4').set_active(False) # no email
		with mock.patch('documenting.Setup') as Setup, \
				mock.patch.object(gui.window, 'destroy') as destroy:
			Setup.return_value.print_dialog.return_value = result
			gui.post_document_clicked(None)
		return Setup.return_value.post, destroy

	def test_a_canceled_print_posts_nothing(self):
		self.add_line(self.product_id, 1, PRICE)
		gui = self.window()
		post, destroy = self.post(gui, 'user canceled')
		post.assert_not_called()
		destroy.assert_not_called()

	def test_the_dialogs_own_cancel_still_posts(self):
		self.add_line(self.product_id, 1, PRICE)
		gui = self.window()
		post, destroy = self.post(gui, Gtk.PrintOperationResult.CANCEL)
		post.assert_called_once_with(self.document_id)
		destroy.assert_called_once()

	def delete(self, gui, response):
		with mock.patch('gi.repository.Gtk.MessageDialog.run',
						return_value = response) as run:
			gui.delete_document_clicked(None)
		return run

	def test_delete_asks_and_no_keeps_the_document(self):
		self.add_line(self.product_id, 1, PRICE)
		gui = self.window()
		run = self.delete(gui, Gtk.ResponseType.NO)
		run.assert_called_once()
		self.assertEqual(self.one("SELECT COUNT(*) FROM documents "
								"WHERE id = %s", (self.document_id,)), 1)
		self.assertEqual(len(self.lines()), 1)
		self.assertEqual(gui.document_id, self.document_id)

	def test_delete_removes_a_document_with_lines(self):
		self.add_line(self.product_id, 1, PRICE)
		gui = self.window()
		self.delete(gui, Gtk.ResponseType.YES)
		self.assertEqual(self.one("SELECT COUNT(*) FROM documents "
								"WHERE id = %s", (self.document_id,)), 0)
		self.assertEqual(self.lines(), [])
		self.assertEqual(gui.document_id, 0)
		self.assertEqual(len(gui.documents_store), 0)
		self.assertFalse(gui.builder.get_object('button15').get_sensitive())

	def test_delete_with_no_document_asks_nothing(self):
		gui = self.window()
		gui.document_id = 0
		run = self.delete(gui, Gtk.ResponseType.YES)
		run.assert_not_called()

	def import_to_invoice(self, refresh_prices):
		'''the document's line is priced at 5.00; the customer's price is 7.25'''
		self.add_line(self.product_id, 2, Decimal('5.00'))
		self.cursor.execute("UPDATE documents SET pending_invoice = True "
							"WHERE id = %s", (self.document_id,))
		import documents_to_invoice, invoice_window
		invoice_id = invoice_window.create_new_invoice(self.customer_id)
		self.DB.commit()
		gui = documents_to_invoice.DocumentsToInvoiceGUI()
		gui.builder.get_object('togglebutton1').set_active(refresh_prices)
		gui.import_document_items_to_invoice(self.document_id, invoice_id)
		self.assertEqual(self.one("SELECT invoiced FROM documents "
								"WHERE id = %s", (self.document_id,)), True)
		self.cursor.execute("SELECT product_id, qty, price, ext_price "
							"FROM invoice_items WHERE invoice_id = %s "
							"ORDER BY id", (invoice_id,))
		return self.cursor.fetchall()

	def test_import_uses_the_document_price(self):
		self.assertEqual(self.import_to_invoice(False),
						[(self.product_id, Decimal('2.0'), Decimal('5.00'),
						Decimal('10.00'))])

	def test_import_refreshes_to_the_customer_price(self):
		self.assertEqual(self.import_to_invoice(True),
						[(self.product_id, Decimal('2.0'), PRICE,
						PRICE * 2)])

	def test_a_qty_sum_is_saved_as_its_result(self):
		self.add_line(self.product_id, 1, PRICE)
		gui = self.window()
		gui.qty_edited(None, '0', '(2+1)*4')
		self.messaged.assert_not_called()
		self.assertEqual(self.lines(),
						[(self.product_id, Decimal(12), PRICE, 12 * PRICE)])

if __name__ == '__main__':
	unittest.main()
