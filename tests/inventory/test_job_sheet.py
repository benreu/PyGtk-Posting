import unittest
from decimal import Decimal, ROUND_HALF_UP
from unittest import mock
import os, sys
# the harness is a directory up, beside the other test folders; its
# own directory is here as well, for the fixtures a folder shares
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)),
				os.path.join(os.path.dirname(os.path.abspath(__file__)),
								'..')]

from harness import DBTestCase
from gi.repository import Gtk, Gdk

PRICE = Decimal('7.25') # the customer's price for the product, set in setUp
APPEND_ITEMS = 2 # show_invoice_exists_message's "Append items" response

class JobSheetTest(DBTestCase):
	'''Customer > Job sheet: F3 called a missing delete_line, deleting the last
	line raised on reselecting it, and Post job to invoice priced every line
	at 0.00'''
	def setUp(self):
		super().setUp()
		import job_sheet
		self.job_sheet = job_sheet
		# a customer with a markup row and no draft invoice to be asked about
		self.customer_id = self.one("SELECT c.id FROM contacts AS c "
							"JOIN customer_markup_percent AS m "
								"ON m.id = c.markup_percent_id "
							"WHERE (c.deleted, c.customer) = (False, True) "
							"AND NOT EXISTS (SELECT 1 FROM invoices AS i "
								"WHERE i.customer_id = c.id AND "
								"(i.posted, i.canceled, i.active) = "
								"(False, False, True)) "
							"ORDER BY c.id LIMIT 1")
		self.product_id = 19
		self.cursor.execute("SELECT id, rate FROM tax_rates WHERE rate > 0 "
							"ORDER BY id LIMIT 1")
		tax_rate_id, self.rate = self.cursor.fetchone()
		self.cursor.execute("UPDATE products SET (cost, deleted, sellable, "
								"stock, tax_rate_id) = (3, False, True, True, %s) "
							"WHERE id = %s", (tax_rate_id, self.product_id))
		markup_id = self.one("SELECT markup_percent_id FROM contacts "
							"WHERE id = %s", (self.customer_id,))
		self.cursor.execute("DELETE FROM products_markup_prices "
							"WHERE (product_id, markup_id) = (%s, %s)",
							(self.product_id, markup_id))
		self.cursor.execute("INSERT INTO products_markup_prices "
							"(product_id, markup_id, price) VALUES (%s, %s, %s)",
							(self.product_id, markup_id, PRICE))
		job_type_id = self.one("INSERT INTO job_types (name) "
								"VALUES ('Test job type') RETURNING id")
		self.job_id = self.one("INSERT INTO job_sheets (contact_id, "
								"job_type_id, description) "
								"VALUES (%s, %s, 'Test job') RETURNING id",
								(self.customer_id, job_type_id))
		self.DB.commit()

	def add_line(self, qty, remark = ''):
		line_id = self.one("INSERT INTO job_sheet_items (job_sheet_id, qty, "
							"product_id, remark) VALUES (%s, %s, %s, %s) "
							"RETURNING id",
							(self.job_id, qty, self.product_id, remark))
		self.DB.commit()
		return line_id

	def window(self):
		'''the window with the test job open, as existing_job_combo_changed
		leaves it'''
		gui = self.job_sheet.JobSheetGUI()
		gui.customer_id = str(self.customer_id) # a string, as the combo hands it over
		gui.job_id = self.job_id
		gui.populate_job_treeview()
		self.asked = mock.patch.object(gui, 'show_invoice_exists_message',
										return_value = APPEND_ITEMS).start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def select(self, gui, row):
		gui.get_object('treeview-selection1').select_path(Gtk.TreePath(row))

	def job_lines(self):
		self.cursor.execute("SELECT id FROM job_sheet_items "
							"WHERE job_sheet_id = %s ORDER BY id",
							(self.job_id,))
		return [row[0] for row in self.cursor.fetchall()]

	def invoice_lines(self, invoice_id):
		self.cursor.execute("SELECT product_id, qty, remark, price, ext_price, "
							"tax FROM invoice_items WHERE invoice_id = %s "
							"ORDER BY id", (invoice_id,))
		return self.cursor.fetchall()

	def draft_invoice(self):
		return self.one("SELECT id FROM invoices WHERE customer_id = %s AND "
						"(posted, canceled, active) = (False, False, True) "
						"ORDER BY id DESC LIMIT 1", (self.customer_id,))

	def tax(self, ext_price):
		return (self.rate * ext_price / 100).quantize(Decimal('0.01'),
													ROUND_HALF_UP)

	def test_f3_deletes_the_selected_line(self):
		self.add_line(1)
		second = self.add_line(2)
		gui = self.window()
		self.select(gui, 0)
		gui.window_key_release_event_(gui.window,
										mock.Mock(keyval = Gdk.KEY_F3))
		self.assertEqual(self.job_lines(), [second])
		self.assertEqual([row[0] for row in gui.job_store], [second])

	def test_deleting_the_last_line_raises_nothing(self):
		first = self.add_line(1)
		second = self.add_line(2)
		gui = self.window()
		self.select(gui, 1)
		gui.delete_item()
		self.assertEqual(self.job_lines(), [first])
		self.assertEqual([row[0] for row in gui.job_store], [first])

	def test_posting_prices_the_lines_for_the_customer(self):
		self.add_line(2, 'left side')
		gui = self.window()
		gui.post_job_to_invoice_clicked(None)
		self.asked.assert_not_called() # the customer had no draft invoice
		self.assertEqual(self.invoice_lines(self.draft_invoice()),
						[(self.product_id, Decimal('2.00'), 'left side',
						PRICE, PRICE * 2, self.tax(PRICE * 2))])
		self.cursor.execute("SELECT invoiced, completed FROM job_sheets "
							"WHERE id = %s", (self.job_id,))
		self.assertEqual(self.cursor.fetchone(), (True, True))

	def test_appending_leaves_the_invoice_lines_alone(self):
		import invoice_window
		invoice_id = invoice_window.create_new_invoice(self.customer_id)
		self.cursor.execute("INSERT INTO invoice_items (invoice_id, qty, "
							"product_id, price) VALUES (%s, 1, %s, 5.00)",
							(invoice_id, self.product_id))
		self.DB.commit()
		self.add_line(3)
		gui = self.window()
		gui.post_job_to_invoice_clicked(None)
		self.asked.assert_called_once()
		self.assertEqual(self.invoice_lines(invoice_id),
						[(self.product_id, Decimal('1.00'), '',
						Decimal('5.00'), Decimal('5.00'),
						self.tax(Decimal('5.00'))),
						(self.product_id, Decimal('3.00'), '',
						PRICE, PRICE * 3, self.tax(PRICE * 3))])

if __name__ == '__main__':
	unittest.main()
