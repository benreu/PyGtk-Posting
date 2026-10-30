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

PRICE = Decimal('7.25') # the customer's price for the product, set in setUp
APPEND_ITEMS = 2 # show_invoice_exists_message's "Append items" response

class TaxExemptionLinesTest(DBTestCase):
	'''Lines posted to an invoice from the job sheet window took the product's
	own tax rate, so a tax exempt customer was charged tax until the invoice's
	exemption was chosen again. They now take the customer's newest exemption,
	which is also what the invoice window starts on'''
	def setUp(self):
		super().setUp()
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
							"AND NOT exemption ORDER BY id LIMIT 1")
		self.product_rate_id, self.product_rate = self.cursor.fetchone()
		self.cursor.execute("UPDATE products SET (cost, deleted, sellable, "
								"stock, tax_rate_id, tax_exemptible) = "
								"(3, False, True, True, %s, True) "
							"WHERE id = %s", (self.product_rate_id,
							self.product_id))
		markup_id = self.one("SELECT markup_percent_id FROM contacts "
							"WHERE id = %s", (self.customer_id,))
		self.cursor.execute("DELETE FROM products_markup_prices "
							"WHERE (product_id, markup_id) = (%s, %s)",
							(self.product_id, markup_id))
		self.cursor.execute("INSERT INTO products_markup_prices "
							"(product_id, markup_id, price) VALUES (%s, %s, %s)",
							(self.product_id, markup_id, PRICE))
		# an older exemption and the newest, which is the one lines take
		self.cursor.execute("DELETE FROM customer_tax_exemptions "
							"WHERE customer_id = %s", (self.customer_id,))
		self.older_exemption_id = self.exemption('Test older exemption', 1)
		self.exemption_id = self.exemption('Test exemption', 0)
		self.DB.commit()

	def exemption(self, name, rate):
		tax_rate_id = self.one("INSERT INTO tax_rates (name, rate, standard, "
								"exemption, tax_letter, tax_received_account) "
							"SELECT %s, %s, False, True, 'E', "
								"tax_received_account "
							"FROM tax_rates WHERE id = %s RETURNING id",
							(name, rate, self.product_rate_id))
		self.cursor.execute("INSERT INTO customer_tax_exemptions "
							"(customer_id, tax_rate_id) VALUES (%s, %s)",
							(self.customer_id, tax_rate_id))
		return tax_rate_id

	def invoice_lines(self, invoice_id):
		self.cursor.execute("SELECT tax_rate_id, ext_price, tax "
							"FROM invoice_items WHERE invoice_id = %s "
							"ORDER BY id", (invoice_id,))
		return self.cursor.fetchall()

	def draft_invoice(self):
		return self.one("SELECT id FROM invoices WHERE customer_id = %s AND "
						"(posted, canceled, active) = (False, False, True) "
						"ORDER BY id DESC LIMIT 1", (self.customer_id,))

	def new_job(self, qty = 2):
		job_type_id = self.one("INSERT INTO job_types (name) "
								"VALUES ('Test job type') RETURNING id")
		job_id = self.one("INSERT INTO job_sheets (contact_id, job_type_id, "
							"description) VALUES (%s, %s, 'Test job') "
							"RETURNING id", (self.customer_id, job_type_id))
		self.cursor.execute("INSERT INTO job_sheet_items (job_sheet_id, qty, "
							"product_id) VALUES (%s, %s, %s)",
							(job_id, qty, self.product_id))
		self.DB.commit()
		return job_id

	def post_job_sheet(self):
		import job_sheet
		job_id = self.new_job()
		gui = job_sheet.JobSheetGUI()
		gui.customer_id = str(self.customer_id) # a string, as the combo hands it over
		gui.job_id = job_id
		with mock.patch.object(gui, 'show_invoice_exists_message',
								return_value = APPEND_ITEMS):
			gui.post_job_to_invoice_clicked(None)
		return self.invoice_lines(self.draft_invoice())

	def test_the_job_sheet_window_uses_the_newest_exemption(self):
		self.assertEqual(self.post_job_sheet(),
						[(self.exemption_id, PRICE * 2, Decimal('0.00'))])

	def test_a_product_that_is_not_exemptible_keeps_its_rate(self):
		self.cursor.execute("UPDATE products SET tax_exemptible = False "
							"WHERE id = %s", (self.product_id,))
		self.DB.commit()
		self.assertEqual([row[0] for row in self.post_job_sheet()],
						[self.product_rate_id])

	def test_a_customer_with_no_exemption_gets_the_products_rate(self):
		self.cursor.execute("DELETE FROM customer_tax_exemptions "
							"WHERE customer_id = %s", (self.customer_id,))
		self.DB.commit()
		self.assertEqual([row[0] for row in self.post_job_sheet()],
						[self.product_rate_id])

	def open_invoice(self):
		import invoice_window
		invoice_id = invoice_window.create_new_invoice(self.customer_id)
		self.DB.commit()
		return invoice_window.InvoiceGUI(invoice_id), invoice_id

	def test_the_invoice_window_starts_on_the_newest_exemption(self):
		gui, invoice_id = self.open_invoice()
		combo = gui.builder.get_object('tax_exemption_combo')
		self.assertEqual(combo.get_active_id(), str(self.exemption_id))

if __name__ == '__main__':
	unittest.main()
