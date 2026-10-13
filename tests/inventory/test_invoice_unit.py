import os
import unittest
from html.parser import HTMLParser
from harness import DBTestCase  # pins Gtk to 3.0, so it is imported first
from unittest import mock

UNIT = 13 # invoice_store column

class InvoiceLineUnitTest(DBTestCase):
	'''invoice_items stores no unit: a line shows whatever its product says now,
	the way the line's product name already does'''

	def setUp(self):
		super().setUp()
		self.product_id = 19
		self.customer_id = self.one("SELECT c.id FROM contacts AS c "
									"JOIN customer_markup_percent AS m "
									"ON m.id = c.markup_percent_id "
									"WHERE (c.deleted, c.customer) = "
										"(False, True) "
									"ORDER BY c.id LIMIT 1")
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.foot = self.one("SELECT id FROM units WHERE name = 'Foot'")
		self.cursor.execute("UPDATE products SET unit = %s WHERE id = %s",
							(self.foot, self.product_id))
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id",
									(self.customer_id,))
		self.cursor.execute("INSERT INTO invoice_items "
							"(invoice_id, qty, product_id, tax_rate_id, price) "
							"VALUES (%s, 4, %s, %s, 5)",
							(self.invoice_id, self.product_id,
							self.tax_rate_id))
		self.DB.commit()

	def window(self):
		import invoice_window
		gui = invoice_window.InvoiceGUI(self.invoice_id)
		mock.patch.object(gui, 'show_negative_stock_warning').start()
		mock.patch.object(gui, 'show_error_dialog').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def unit_of(self, product_id):
		return self.one("SELECT COALESCE(NULLIF(u.abbreviation, ''), u.name) "
						"FROM products AS p JOIN units AS u ON u.id = p.unit "
						"WHERE p.id = %s", (product_id,))

	def test_the_store_still_matches_its_append_literals(self):
		'''three append () call sites pass a literal list; PyGObject raises if
		one falls out of step with the store'''
		self.assertEqual(self.window().invoice_store.get_n_columns(), 14)

	def test_loading_an_invoice_brings_the_unit_along(self):
		gui = self.window()
		self.assertEqual([row[UNIT] for row in gui.invoice_store], ['ft'])

	def test_a_unit_with_no_abbreviation_falls_back_to_its_name(self):
		self.cursor.execute("UPDATE units SET abbreviation = '' WHERE id = %s",
							(self.foot,))
		self.DB.commit()
		gui = self.window()
		self.assertEqual([row[UNIT] for row in gui.invoice_store], ['Foot'])

	def test_changing_the_product_changes_the_unit(self):
		other = self.one("SELECT p.id FROM products AS p "
							"JOIN units AS u ON u.id = p.unit "
							"WHERE (p.deleted, p.sellable) = (False, True) "
								"AND u.id <> %s AND p.id <> %s "
							"ORDER BY p.id LIMIT 1",
							(self.foot, self.product_id))
		gui = self.window()
		gui.product_selected(other, '0')
		self.assertEqual(gui.invoice_store[0][UNIT], self.unit_of(other))

	def test_a_brand_new_line_gets_its_unit(self):
		'''new_item_clicked appends without going through product_selected'''
		gui = self.window()
		gui.new_item_clicked(None)
		row = gui.invoice_store[-1]
		self.assertEqual(row[UNIT], self.unit_of(row[2]))
		self.assertNotEqual(row[UNIT], '')

	def test_the_pdf_builder_reads_the_unit_off_the_store(self):
		'''invoice_create is handed the live store, so this is what prints'''
		import invoice_window
		from invoice import invoice_create
		gui = self.window()
		items = []
		for i in gui.invoice_store:
			item = invoice_create.Item()
			item.unit = i[UNIT]
			items.append(item)
		self.assertEqual([i.unit for i in items], ['ft'])

class ItemsTableWidth(HTMLParser):
	'''cells per row of the items table, honouring colspan and rowspan'''
	def __init__(self):
		super().__init__()
		self.inside = False
		self.rows = []
		self.carry = {}
		self.row = None

	def handle_starttag(self, tag, attrs):
		a = dict(attrs)
		if tag == 'table':
			self.inside = 'items' in (a.get('class') or '')
		if not self.inside:
			return
		if tag == 'tr':
			self.row = sum(v for k, v in self.carry.items() if k > 0)
			self.carry = dict((k - 1, v) for k, v in self.carry.items()
								if k - 1 > 0)
		if tag in ('td', 'th') and self.row is not None:
			span = int(a.get('colspan', 1))
			rows = int(a.get('rowspan', 1))
			self.row += span
			if rows > 1:
				self.carry[rows - 1] = self.carry.get(rows - 1, 0) + span

	def handle_endtag(self, tag):
		if tag == 'tr' and self.inside and self.row is not None:
			self.rows.append(self.row)
			self.row = None
		if tag == 'table':
			self.inside = False

class InvoiceTemplateTest(unittest.TestCase):
	'''the real invoice_template.html, which Jinja and WeasyPrint render'''

	def render(self):
		from jinja2 import Environment, FileSystemLoader
		here = os.path.dirname(os.path.abspath(__file__))
		templates = os.path.join(here, '..', '..', 'templates')

		class Stub(object):
			def __getattr__(self, name):
				return ''
		def line(qty, unit):
			item = Stub()
			item.qty, item.unit, item.product = qty, unit, 'A PRODUCT'
			item.price, item.ext_price, item.tax_letter = '1.00', '2.00', 'T'
			return item
		env = Environment(loader = FileSystemLoader(templates))
		return env.get_template('invoice_template.html').render(
					items = [line('10', 'ft'), line('3', 'hr')],
					document = Stub(), contact = Stub(), shipping = Stub(),
					terms = Stub(), company = Stub(), serial_numbers = [])

	def test_the_unit_is_printed(self):
		out = self.render()
		self.assertIn('>ft<', out)
		self.assertIn('>hr<', out)
		self.assertIn('Unit', out)

	def test_the_table_is_square(self):
		'''adding a column means the footer's colspans have to keep up'''
		parser = ItemsTableWidth()
		parser.feed(self.render())
		self.assertTrue(parser.rows, 'the items table was not found')
		self.assertEqual(set(parser.rows), {6},
							'rows are %s cells wide' % parser.rows)

if __name__ == '__main__':
	unittest.main()
