# test_invoice_packing_list.py
#
# The invoice window's Packing list item: a pick sheet of what is on screen,
# with no money on it. It is built read only - nothing it does may reach the
# invoice's totals or its date_printed, which is the point of the separate
# module rather than a flag on invoice_create.

import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import harness
from gi.repository import Gtk

class Stub(object):
	'''a template value that answers '' for whatever was not set.
	The twin of the one in test_invoice_unit.py'''

	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

	def __getattr__(self, name):
		return ''

DEFAULT_SHIPPING = object() # render()'s own blank Stub, not an omitted address

class PackingListTest(harness.DBTestCase):

	def setUp(self):
		super().setUp()
		self.customer_id = self.real_customer()
		self.tax_rate_id = self.one("SELECT id FROM tax_rates LIMIT 1")
		self.first_id, self.first_name = self.sellable_product()
		self.second_id, self.second_name = self.sellable_product(self.first_id)
		self.invoice_id = self.one("INSERT INTO invoices (customer_id) "
									"VALUES (%s) RETURNING id",
									(self.customer_id,))
		# invoices.name defaults to '' and only create_new_invoice fills it, so
		# give this one a name: the nameless case is its own test below
		self.invoice_name = 'Inv_%s_tst_2026-10-13' % self.invoice_id
		self.cursor.execute("UPDATE invoices SET name = %s WHERE id = %s",
							(self.invoice_name, self.invoice_id))
		self.add_line(self.first_id, 4, 'a remark')
		self.add_line(self.second_id, 3)
		self.DB.commit() # the window rolls back after every read

	def real_customer(self):
		'''a contact the customer combo will actually hold: SELECT id FROM
		contacts LIMIT 1 returns one with customer = False, which never reaches
		the combo and leaves gui.customer_id None'''
		return self.one("SELECT c.id FROM contacts AS c "
						"JOIN customer_markup_percent AS m "
							"ON m.id = c.markup_percent_id "
						"WHERE (c.deleted, c.customer) = (False, True) "
						"ORDER BY c.id LIMIT 1")

	def sellable_product(self, besides = None):
		self.cursor.execute("SELECT p.id, p.name FROM products AS p "
							"JOIN units AS u ON u.id = p.unit "
							"WHERE (p.deleted, p.sellable) = (False, True) "
								"AND (%s::int IS NULL OR p.id != %s) "
							"ORDER BY p.id LIMIT 1", (besides, besides))
		return self.cursor.fetchone()

	def add_line(self, product_id, qty, remark = ''):
		return self.one("INSERT INTO invoice_items "
						"(invoice_id, qty, product_id, tax_rate_id, remark, "
						"price, ext_price) "
						"VALUES (%s, %s, %s, %s, %s, 5, 20) RETURNING id",
						(self.invoice_id, qty, product_id, self.tax_rate_id,
						remark))

	def window(self, invoice_id = -1):
		import invoice_window
		if invoice_id == -1:
			invoice_id = self.invoice_id
		gui = invoice_window.InvoiceGUI(invoice_id)
		mock.patch.object(gui, 'show_negative_stock_warning').start()
		mock.patch.object(gui, 'show_error_dialog').start()
		self.addCleanup(mock.patch.stopall)
		return gui

	def sheet(self, gui = None, comment = ''):
		'''the real generator, with the pdf cleaned up after'''
		from invoice import packing_list
		gui = gui or self.window()
		setup = packing_list.Setup (gui.invoice_store, gui.invoice_id,
									gui.datetime, comment)
		self.addCleanup(self.remove_pdf, setup.packing_list_pdf)
		return setup

	def remove_pdf(self, path):
		if os.path.exists(path):
			os.remove(path)

	def menuitem(self, gui):
		return gui.builder.get_object('packing_list_menuitem')

	def cancel_pending_comment(self, gui):
		'''drop the timeout set_text () armed, so nothing writes the comment
		behind the test and no stray source survives the window'''
		from gi.repository import GLib
		if gui.comment_timeout != None:
			GLib.source_remove(gui.comment_timeout)
			gui.comment_timeout = None

	def test_the_menu_item_waits_for_a_saved_invoice(self):
		import invoice_window
		blank = invoice_window.InvoiceGUI()
		self.assertFalse(self.menuitem(blank).get_sensitive())
		self.assertTrue(self.menuitem(self.window()).get_sensitive())

	def test_the_menu_is_still_in_alphabetical_order(self):
		'''the convention the whole of invoice_menu is kept in, which is the
		only thing placing Packing list where it sits'''
		menu = self.window().builder.get_object('invoice_menu')
		labels = [child.get_label() for child in menu.get_children()]
		self.assertIn('Packing list', labels)
		self.assertEqual(labels, sorted(labels))

	def test_activating_the_menu_item_builds_the_sheet(self):
		'''the only test that proves the .ui signal reaches the handler: a
		missing handler is a GtkBuilder warning, not an error'''
		gui = self.window()
		with mock.patch('invoice.packing_list.Setup') as setup:
			self.menuitem(gui).activate()
		setup.assert_called_once_with(gui.invoice_store, self.invoice_id,
										gui.datetime, '')
		setup.return_value.view.assert_called_once_with()

	def test_an_empty_invoice_is_refused(self):
		gui = self.window()
		gui.invoice_store.clear()
		with mock.patch('invoice.packing_list.Setup') as setup:
			gui.packing_list_activated (None)
		setup.assert_not_called()
		gui.show_error_dialog.assert_called_once()

	def test_building_the_sheet_writes_nothing(self):
		'''the headline test. invoice_create's CTE would "correct" a subtotal
		that disagrees with the lines; this must not'''
		self.cursor.execute("UPDATE invoices SET subtotal = 999 WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		before = self.one("SELECT xmin::text FROM invoices WHERE id = %s",
							(self.invoice_id,))
		self.sheet()
		self.cursor.execute("SELECT subtotal, date_printed, pdf_data, "
							"xmin::text FROM invoices WHERE id = %s",
							(self.invoice_id,))
		subtotal, date_printed, pdf_data, after = self.cursor.fetchone()
		self.assertEqual(subtotal, 999)
		self.assertIsNone(date_printed)
		self.assertIsNone(pdf_data)
		self.assertEqual(after, before) # the row was not UPDATEd at all

	def test_the_file_never_collides_with_the_invoice_pdf(self):
		'''invoice_create writes /tmp/<invoices.name>.pdf and its post () reads
		that exact path back into invoices.pdf_data, see invoice_create.py:168'''
		setup = self.sheet()
		self.assertTrue(setup.packing_list_pdf.endswith('_packing_list.pdf'))
		self.assertNotEqual(setup.packing_list_pdf,
							'/tmp/%s.pdf' % self.invoice_name)

	def test_a_nameless_invoice_still_gets_a_file(self):
		self.cursor.execute("UPDATE invoices SET name = '' WHERE id = %s",
							(self.invoice_id,))
		self.DB.commit()
		setup = self.sheet()
		self.assertEqual(setup.packing_list_pdf,
							'/tmp/Inv_%s_packing_list.pdf' % self.invoice_id)
		self.assertTrue(os.path.exists(setup.packing_list_pdf))

	def test_the_pdf_is_written_and_opened(self):
		with mock.patch('invoice.packing_list.subprocess.Popen') as popen:
			setup = self.sheet()
			setup.view ()
		with open(setup.packing_list_pdf, 'rb') as f:
			self.assertEqual(f.read(4), b'%PDF')
		popen.assert_called_once_with(["xdg-open", setup.packing_list_pdf])

	def test_the_sheet_carries_no_money(self):
		html = self.sheet().html
		for leak in ('$', 'Subtotal', 'Total', 'Price', 'price', '5.00', '20.00'):
			self.assertNotIn(leak, html)

	def test_the_lines_are_in_the_order_on_screen(self):
		gui = self.window()
		html = self.sheet(gui).html
		self.assertLess(html.index(self.first_name), html.index(self.second_name))
		gui.builder.get_object('invoice_selection').select_path('0')
		gui.move_down_activated (None)
		html = self.sheet(gui).html
		self.assertLess(html.index(self.second_name), html.index(self.first_name))

	def test_the_product_cell_carries_the_remark(self):
		self.assertIn('%s : a remark' % self.first_name, self.sheet().html)

	def test_a_canceled_line_is_not_picked(self):
		gui = self.window()
		gui.builder.get_object('invoice_selection').select_path('0')
		gui.delete_line_item_activated (None)
		html = self.sheet(gui).html
		self.assertNotIn(self.first_name, html)
		self.assertIn(self.second_name, html)

	def test_the_comment_is_taken_off_the_live_buffer(self):
		'''invoices.comments is only written after a 500ms typing pause, so the
		sheet has to read the buffer, exactly as the printed invoice does'''
		self.cursor.execute("UPDATE invoices SET comments = %s WHERE id = %s",
							('stale in the database', self.invoice_id))
		self.DB.commit()
		gui = self.window()
		gui.builder.get_object('comment_buffer').set_text('will-call Friday')
		self.cancel_pending_comment(gui) # the save must not have run
		with mock.patch('invoice.packing_list.Setup') as setup:
			self.menuitem(gui).activate()
		self.assertEqual(setup.call_args[0][3], 'will-call Friday')
		self.assertEqual(self.one("SELECT comments FROM invoices WHERE id = %s",
									(self.invoice_id,)),
							'stale in the database')

	def test_the_comment_is_printed_under_the_lines(self):
		html = self.sheet(comment = 'will-call Friday').html
		self.assertIn('Comments', html)
		self.assertIn('will-call Friday', html)
		self.assertLess(html.index(self.second_name), html.index('will-call'))

	def test_an_empty_comment_prints_no_block(self):
		self.assertNotIn('Comments', self.sheet().html)

	def test_the_sheet_is_signed_for(self):
		html = self.sheet().html
		self.assertIn('Picked by', html)
		self.assertIn('Date', html)

	def test_the_ship_to_block_follows_the_invoice(self):
		self.assertNotIn('Ship To', self.sheet().html)
		carrier_id = self.one("INSERT INTO shipping_carriers (name) "
								"VALUES ('UPS Ground') RETURNING id")
		address_id = self.one("INSERT INTO contact_shipping_addresses "
								"(contact_id, description, address, city, "
								"state, zip, shipping_carrier_id) "
								"VALUES (%s, 'Dock', '1 Dock St', 'Reading', "
								"'PA', '19601', %s) RETURNING id",
								(self.customer_id, carrier_id))
		self.cursor.execute("UPDATE invoices SET shipping_address_id = %s "
							"WHERE id = %s", (address_id, self.invoice_id))
		self.DB.commit()
		html = self.sheet().html
		self.assertIn('Ship To', html)
		self.assertIn('1 Dock St', html)
		self.assertIn('via UPS Ground', html)

class PackingListTemplateTest(unittest.TestCase):
	'''the real packing_list_template.html, which Jinja and WeasyPrint render.
	Needs neither the database nor a display'''

	def render(self, shipping = DEFAULT_SHIPPING, items = None, comment = ''):
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
		# document.type is set to prove the heading never consults it
		document = Stub(type = 'Invoice', number = '12345',
						date = '10/13/2026', comment = comment)
		env = Environment(loader = FileSystemLoader(templates))
		return env.get_template('packing_list_template.html').render(
					items = items, document = document, contact = contact,
					shipping = shipping, company = company)

	def line(self, qty, unit, product = 'A PRODUCT'):
		'''carries the money fields too, so the template gets the chance to
		print them and is shown not to take it'''
		item = Stub()
		item.qty, item.unit, item.product = qty, unit, product
		item.price, item.ext_price, item.tax_letter = '1.00', '2.00', 'T'
		return item

	def ship_to(self, **kwargs):
		fields = dict(name = 'CUSTOMER NAME', street = '250 Shipping Ln',
						city = 'Shipville', state = 'PA', zip = '17600',
						carrier = 'UPS Ground')
		fields.update(kwargs)
		return Stub(**fields)

	def pages(self, html):
		import weasyprint
		return weasyprint.HTML(string = html).render().pages

	def walk(self, box):
		for child in getattr(box, 'all_children', lambda: [])():
			yield child
			for further in self.walk(child):
				yield further

	def test_the_quantity_and_unit_are_printed(self):
		out = self.render()
		self.assertIn('>Qty<', out)
		self.assertIn('>Unit<', out)
		self.assertIn('>10<', out)
		self.assertIn('>ft<', out)

	def test_the_picked_column_is_blank(self):
		out = self.render()
		self.assertIn('>Picked<', out)
		self.assertEqual(out.count('<span class="box"></span>'), 2)
		self.assertNotIn('<input', out)
		self.assertNotIn('checked', out)

	def test_the_template_cannot_print_a_price(self):
		'''proves the leak is impossible at the template, not merely unwired at
		the generator: every money field is set on the items it is handed'''
		out = self.render()
		for leak in ('1.00', '2.00', '$', 'Price', 'Subtotal', 'Total', '>T<'):
			self.assertNotIn(leak, out)

	def test_the_heading_says_packing_list(self):
		out = self.render()
		self.assertIn('>Packing List<', out)
		self.assertNotIn('>Invoice<', out) # document.type is never consulted

	def test_ship_to_is_printed_only_when_the_invoice_has_one(self):
		self.assertNotIn('Ship To', self.render(None))
		out = self.render(self.ship_to())
		self.assertIn('Ship To', out)
		self.assertIn('250 Shipping Ln', out)
		self.assertIn('via UPS Ground', out)
		self.assertNotIn('via', self.render(self.ship_to(carrier = '')))

	def test_the_header_row_repeats_on_a_second_page(self):
		items = [self.line(str(n), 'ea', 'PRODUCT %s' % n) for n in range(80)]
		pages = self.pages(self.render(items = items))
		self.assertGreater(len(pages), 1)
		tags = set()
		for box in self.walk(pages[1]._page_box):
			element = getattr(box, 'element', None)
			if element != None:
				tags.add(element.tag)
		self.assertIn('th', tags)

	def test_the_comment_block_appears_only_when_there_is_one(self):
		self.assertNotIn('Comments', self.render())
		out = self.render(comment = 'will-call Friday')
		self.assertIn('>Comments<', out)
		self.assertIn('will-call Friday', out)

	def test_the_sign_off_rules_are_always_there(self):
		'''the picker signs the sheet whether or not anything else is on it'''
		out = self.render()
		self.assertIn('>Picked by<', out)
		self.assertIn('>Date<', out)
		self.assertEqual(out.count('<div class="line"></div>'), 2)

	def test_the_sign_off_comes_last(self):
		out = self.render(comment = 'will-call Friday')
		self.assertLess(out.index('will-call Friday'), out.index('Picked by'))

	def test_the_sheet_is_not_a_mailed_document(self):
		out = self.render()
		self.assertNotIn('fold-mark', out) # no envelope window to line up with
		self.assertNotIn('Thank you', out)

if __name__ == '__main__':
	unittest.main()
