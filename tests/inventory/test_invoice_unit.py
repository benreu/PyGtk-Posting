import os
import unittest
from html.parser import HTMLParser
from harness import DBTestCase  # pins Gtk to 3.0, so it is imported first
from unittest import mock

UNIT = 13 # invoice_store column
PX = 96.0 # WeasyPrint lays the page out in CSS pixels
COMPANY_Y = 2.187 # the billing address, as it sits in the envelope window
FOLD_MARK_Y = 3.851

class Stub(object):
	'''a template value that answers '' for whatever was not set'''

	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

	def __getattr__(self, name):
		return ''

DEFAULT_SHIPPING = object() # render()'s own blank Stub, not an omitted address

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

	def render(self, shipping = DEFAULT_SHIPPING, items = None):
		from jinja2 import Environment, FileSystemLoader
		here = os.path.dirname(os.path.abspath(__file__))
		templates = os.path.join(here, '..', '..', 'templates')
		if shipping is DEFAULT_SHIPPING:
			shipping = Stub()
		if items == None:
			items = [self.line('10', 'ft'), self.line('3', 'hr')]
		contact = Stub(name = 'CUSTOMER NAME', street = '100 Billing Rd',
						city = 'Billtown', state = 'PA', zip = '17500')
		company = Stub(name = 'OUR COMPANY', street = '1 Main St',
						city = 'Ourtown', state = 'PA', zip = '17000')
		document = Stub(type = 'Invoice', number = '12345',
						date = '10/13/2026', subtotal = '$20.00', tax = '$1.20',
						total = '$21.20', payment_due = 'Due 11/12/2026')
		env = Environment(loader = FileSystemLoader(templates))
		return env.get_template('invoice_template.html').render(
					items = items,
					document = document, contact = contact, shipping = shipping,
					terms = Stub(), company = company, serial_numbers = [])

	def line(self, qty, unit, remark = ''):
		item = Stub()
		item.qty, item.unit, item.product = qty, unit, 'A PRODUCT'
		item.price, item.ext_price, item.tax_letter = '1.00', '2.00', 'T'
		item.remark = remark
		return item

	def ship_to(self, **kwargs):
		fields = dict(name = 'CUSTOMER NAME', street = '250 Shipping Ln',
						city = 'Shipville', state = 'PA', zip = '17600',
						carrier = 'UPS Ground')
		fields.update(kwargs)
		return Stub(**fields)

	def anchor_positions(self, html):
		'''y of each class's first box, in inches down the sheet'''
		import weasyprint
		page = weasyprint.HTML(string = html).render().pages[0]

		def walk(box):
			for child in getattr(box, 'all_children', lambda: [])():
				yield child
				for further in walk(child):
					yield further
		found = {}
		for box in walk(page._page_box):
			element = getattr(box, 'element', None)
			classes = (element.get('class') or '') if element != None else ''
			for name in classes.split():
				if name not in found:
					found[name] = box.position_y / PX
		return found

	def test_the_unit_is_printed(self):
		out = self.render()
		self.assertIn('>ft<', out)
		self.assertIn('>hr<', out)
		self.assertIn('Unit', out)

	def test_the_table_is_square(self):
		'''adding a column means the footer's colspans have to keep up, and the
		comment row's too'''
		parser = ItemsTableWidth()
		parser.feed(self.render(items = [self.line('10', 'ft', 'cut to length'),
										self.line('3', 'hr')]))
		self.assertTrue(parser.rows, 'the items table was not found')
		self.assertEqual(set(parser.rows), {6},
							'rows are %s cells wide' % parser.rows)

	def test_only_a_line_with_a_comment_gets_a_comment_row(self):
		out = self.render(items = [self.line('10', 'ft', 'cut to length'),
									self.line('3', 'hr')])
		self.assertEqual(out.count('<tr class="remark">'), 1)
		self.assertIn('class="remark">cut to length<', out)
		self.assertNotIn(' : ', out) # no longer tacked onto the product
		self.assertNotIn('<tr class="remark">', self.render())

	def test_the_envelope_window_anchors_hold(self):
		'''the sheet is folded for a window envelope, so no shipping address,
		however long, may shift the billing address or the fold mark'''
		long = self.ship_to(name = 'A VERY LONG RECEIVING DEPARTMENT NAME LLC',
							street = '12345 Extremely Long Industrial Parkway',
							city = 'Averylongcitynamehere',
							carrier = 'Some Freight Carrier Co')
		for label, shipping in (('a shipping address', self.ship_to()),
								('no shipping address', None),
								('a long shipping address', long)):
			with self.subTest(label):
				found = self.anchor_positions(self.render(shipping))
				self.assertAlmostEqual(found['company'], COMPANY_Y, delta = 0.01,
						msg = 'the billing address left the envelope window')
				self.assertAlmostEqual(found['fold-mark'], FOLD_MARK_Y,
						delta = 0.01, msg = 'the fold mark moved')
				if shipping != None:
					self.assertLess(found['ship-to'], found['fold-mark'],
							msg = 'ship to belongs above the fold, beside the '
									'billing address')
					self.assertAlmostEqual(found['ship-to'], found['company'],
							delta = 0.01, msg = 'the two names start on one line')
					self.assertLess(found['label'], found['company'],
							msg = 'the Ship To label sits above both addresses')

	def test_ship_to_is_printed_only_when_the_invoice_has_one(self):
		'''the address used to be COALESCEd onto the customer's own, so every
		invoice printed a Ship To that just repeated the billing address'''
		self.assertNotIn('Ship To', self.render(None))
		out = self.render(self.ship_to())
		self.assertIn('Ship To', out)
		self.assertIn('250 Shipping Ln', out)
		self.assertIn('via UPS Ground', out)
		self.assertNotIn('via', self.render(self.ship_to(carrier = '')))

if __name__ == '__main__':
	unittest.main()
