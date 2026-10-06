import os, unittest
from decimal import Decimal
from harness import DBTestCase
from constants import sql_dir

def minor_update_block (version):
	'''the statement update_db_minor.sql ships for one version marker, so the
	test cannot drift from what is actually applied to a database. execute_file
	splits that file on a double dash, which is why a body may not contain one'''
	path = os.path.join(sql_dir, 'update_db_minor.sql')
	with open(path) as sql_file:
		commands = sql_file.read().split("--")
	for command in commands:
		if command.startswith(version):
			assert "--" not in command, 'the block would be split in two'
			return "--" + command # execute_file puts back what the split ate
	raise AssertionError('no %s block in update_db_minor.sql' % version)

class BarcodeScanTest(DBTestCase):
	'''a deleted invoice line is only flagged canceled and the window does not
	show it, so a scan must not quietly add a quantity to it'''
	def setUp(self):
		super().setUp()
		self.cursor.execute(minor_update_block('0.7.17'))
		self.product_id = 19
		self.barcode = 'TESTBARCODE19'
		self.cursor.execute("UPDATE products SET (barcode, deleted) = (%s, False) "
							"WHERE id = %s", (self.barcode, self.product_id))
		customer_id = self.one("SELECT id FROM contacts LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (customer_id,))

	def scan(self):
		return self.one("SELECT process_invoice_barcode(%s, %s)",
						(self.barcode, self.invoice_id))

	def lines(self):
		self.cursor.execute("SELECT id, qty, canceled FROM invoice_items "
							"WHERE invoice_id = %s ORDER BY id",
							(self.invoice_id,))
		return self.cursor.fetchall()

	def second_line(self):
		'''the window can put the same product on a second line'''
		return self.one("INSERT INTO invoice_items (invoice_id, qty, product_id, "
						"tax_rate_id) VALUES (%s, 1, %s, "
						"(SELECT id FROM tax_rates LIMIT 1)) RETURNING id",
						(self.invoice_id, self.product_id))

	def cancel(self, line_id):
		self.cursor.execute("UPDATE invoice_items SET (qty, price, ext_price, "
							"tax, canceled) = (0, 0, 0, 0, True) WHERE id = %s",
							(line_id,))

	def test_a_first_scan_starts_a_line(self):
		line_id = self.scan()
		self.assertEqual(self.lines(),
						[(line_id, Decimal('1.00'), False)])

	def test_a_second_scan_adds_to_the_same_line(self):
		line_id = self.scan()
		self.assertEqual(self.scan(), line_id)
		self.assertEqual(self.lines(), [(line_id, Decimal('2.00'), False)])

	def test_a_scan_brings_a_deleted_line_back(self):
		line_id = self.scan()
		self.cancel(line_id)
		# the line returns where it was, no second one appears below it
		self.assertEqual(self.scan(), line_id)
		self.assertEqual(self.lines(), [(line_id, Decimal('1.00'), False)])

	def test_a_line_brought_back_then_counts_up_again(self):
		line_id = self.scan()
		self.cancel(line_id)
		self.scan()
		self.assertEqual(self.scan(), line_id)
		self.assertEqual(self.lines(), [(line_id, Decimal('1.00') + 1, False)])

	def test_a_deleted_line_comes_back_with_one_not_its_old_quantity(self):
		line_id = self.scan()
		self.scan()
		self.scan() # three on the line
		self.cancel(line_id)
		self.scan()
		# a delete means gone, so the scan is one item and not the old three
		self.assertEqual(self.lines(), [(line_id, Decimal('1.00'), False)])

	def test_a_live_line_is_preferred_over_a_canceled_one(self):
		canceled_id = self.scan()
		live_id = self.second_line()
		self.cancel(canceled_id)
		self.assertEqual(self.scan(), live_id)
		self.assertEqual(self.lines(), [(canceled_id, Decimal('0.00'), True),
										(live_id, Decimal('2.00'), False)])

	def test_the_first_of_several_canceled_lines_comes_back(self):
		first_id = self.scan()
		second_id = self.second_line()
		self.cancel(first_id)
		self.cancel(second_id)
		self.assertEqual(self.scan(), first_id)
		self.assertEqual(self.lines(), [(first_id, Decimal('1.00'), False),
										(second_id, Decimal('0.00'), True)])

	def test_an_unknown_barcode_returns_zero(self):
		self.assertEqual(self.one("SELECT process_invoice_barcode(%s, %s)",
									('NOSUCHBARCODE', self.invoice_id)), 0)
		self.assertEqual(self.lines(), [])


class BarcodeScanWindowTest(DBTestCase):
	'''the window hides a canceled line, so the scan has to come back visible'''
	def setUp(self):
		super().setUp()
		self.cursor.execute(minor_update_block('0.7.17'))
		self.barcode = 'TESTBARCODE19'
		self.cursor.execute("UPDATE products SET (barcode, deleted) = (%s, False) "
							"WHERE id = 19", (self.barcode,))
		# only contacts flagged as customers reach the window's customer combo
		customer_id = self.one("SELECT id FROM contacts WHERE "
								"(deleted, customer) = (False, True) "
								"ORDER BY id LIMIT 1")
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id", (customer_id,))
		self.DB.commit()
		import invoice_window
		self.gui = invoice_window.InvoiceGUI(self.invoice_id)
		self.assertIsNotNone(self.gui.customer_id)
		self.entry = self.gui.builder.get_object('barcode_entry')

	def scan(self):
		self.entry.set_text(self.barcode)
		self.gui.barcode_entry_activate (self.entry)

	def shown(self):
		'''id, qty and price of each line the user can see'''
		return [(row[0], row[1], row[6]) for row in self.gui.invoice_store]

	def delete_first_line(self):
		self.gui.builder.get_object('invoice_selection').select_path('0')
		self.gui.delete_line_item_activated (None)

	def test_a_deleted_line_is_scanned_back_into_view(self):
		self.scan()
		self.scan()
		line_id, price = self.shown()[0][0], self.shown()[0][2]
		self.assertEqual(self.shown(), [(line_id, '2.00', price)])
		self.delete_first_line()
		self.assertEqual(self.shown(), [])
		self.scan()
		# the same line, visible again, with the price the scan sets
		self.assertEqual(self.shown(), [(line_id, '1.00', price)])


if __name__ == '__main__':
	unittest.main()
