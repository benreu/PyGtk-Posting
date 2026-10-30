import unittest
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
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

class DraftJobSheetsTest(DBTestCase):
	'''Draft job sheets: Post Job to Invoice priced the job's lines and then
	every other line on the invoice too, so appending a job overwrote prices
	already set there; and neither it nor Post Job as Completed took the job
	out of the time clock'''
	def setUp(self):
		super().setUp()
		import draft_job_sheets
		self.draft_job_sheets = draft_job_sheets
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
		# taxed at the product's rate: real customers here carry exemptions,
		# which test_tax_exemption_lines covers
		self.cursor.execute("DELETE FROM customer_tax_exemptions "
							"WHERE customer_id = %s", (self.customer_id,))
		job_type_id = self.one("INSERT INTO job_types (name) "
								"VALUES ('Test job type') RETURNING id")
		self.job_id = self.one("INSERT INTO job_sheets (contact_id, "
								"job_type_id, description) "
								"VALUES (%s, %s, 'Test job') RETURNING id",
								(self.customer_id, job_type_id))
		self.DB.commit()

	def add_line(self, qty, remark = ''):
		self.cursor.execute("INSERT INTO job_sheet_items (job_sheet_id, qty, "
							"product_id, remark) VALUES (%s, %s, %s, %s)",
							(self.job_id, qty, self.product_id, remark))
		self.DB.commit()

	def gui(self):
		'''the window with the test job selected'''
		gui = self.draft_job_sheets.DraftJobSheetsGUI()
		for row in gui.jobs_store:
			if row[0] == self.job_id:
				gui.get_object('treeview-selection1').select_path(row.path)
				return gui
		self.fail('the test job is not listed')

	def post(self):
		'''Post Job to Invoice with the test job selected; returns the mocked
		question about an existing draft invoice'''
		gui = self.gui()
		with mock.patch.object(gui, 'show_invoice_exists_message',
								return_value = APPEND_ITEMS) as asked:
			gui.post_job_to_invoice_clicked(None)
		return asked

	def invoice_lines(self, invoice_id):
		self.cursor.execute("SELECT product_id, qty, remark, price, ext_price, "
							"tax FROM invoice_items WHERE invoice_id = %s "
							"ORDER BY id", (invoice_id,))
		return self.cursor.fetchall()

	def tax(self, ext_price):
		return (self.rate * ext_price / 100).quantize(Decimal('0.01'),
													ROUND_HALF_UP)

	def test_posting_prices_the_lines_for_the_customer(self):
		self.add_line(2, 'left side')
		asked = self.post()
		asked.assert_not_called() # the customer had no draft invoice
		invoice_id = self.one("SELECT id FROM invoices WHERE customer_id = %s "
							"AND (posted, canceled, active) = "
							"(False, False, True)", (self.customer_id,))
		self.assertEqual(self.invoice_lines(invoice_id),
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
		asked = self.post()
		asked.assert_called_once()
		self.assertEqual(self.invoice_lines(invoice_id),
						[(self.product_id, Decimal('1.00'), '',
						Decimal('5.00'), Decimal('5.00'),
						self.tax(Decimal('5.00'))),
						(self.product_id, Decimal('3.00'), '',
						PRICE, PRICE * 3, self.tax(PRICE * 3))])

	def put_in_time_clock(self, job_id):
		'''what checking Job available in Time Clock on the job sheet does,
		a week ago'''
		project_id = self.one("INSERT INTO time_clock_projects (name, "
								"start_date, active, permanent, job_sheet_id) "
								"VALUES ('Test job', %s, True, False, %s) "
								"RETURNING id",
								(date.today() - timedelta(days = 7), job_id))
		self.DB.commit()
		return project_id

	def time_clock_project(self, project_id):
		self.cursor.execute("SELECT active, stop_date FROM time_clock_projects "
							"WHERE id = %s", (project_id,))
		return self.cursor.fetchone()

	def other_job(self):
		'''a second job for the customer, which stays in the time clock'''
		job_id = self.one("INSERT INTO job_sheets (contact_id, job_type_id, "
							"description) SELECT contact_id, job_type_id, "
							"'Other job' FROM job_sheets WHERE id = %s "
							"RETURNING id", (self.job_id,))
		return self.put_in_time_clock(job_id)

	def test_posting_takes_the_job_out_of_the_time_clock(self):
		project_id = self.put_in_time_clock(self.job_id)
		other_project_id = self.other_job()
		self.add_line(1)
		self.post()
		self.assertEqual(self.time_clock_project(project_id),
						(False, date.today()))
		self.assertEqual(self.time_clock_project(other_project_id),
						(True, None))

	def test_completing_takes_the_job_out_of_the_time_clock(self):
		project_id = self.put_in_time_clock(self.job_id)
		other_project_id = self.other_job()
		self.gui().post_job_as_completed_clicked(None)
		self.assertEqual(self.time_clock_project(project_id),
						(False, date.today()))
		self.assertEqual(self.time_clock_project(other_project_id),
						(True, None))
		self.cursor.execute("SELECT invoiced, completed FROM job_sheets "
							"WHERE id = %s", (self.job_id,))
		self.assertEqual(self.cursor.fetchone(), (False, True))

if __name__ == '__main__':
	unittest.main()
