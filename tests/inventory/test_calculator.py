# test_calculator.py
#
# The calculator behind every quantity cell is pure, so these run with no
# database and no display. The last class reads the .ui files, so a quantity
# cell that Glade turns back into a spin button (which would parse 2*3 as 2
# before the handler ever saw it) fails here.

import os, sys, unittest
import xml.etree.ElementTree as ET
from decimal import Decimal

SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
sys.path.insert(0, os.path.abspath(SRC))

import calculator
from calculator import evaluate, whole, CalculatorError

class NumbersTest (unittest.TestCase):

	def test_plain_numbers (self):
		for text, value in (('7', 7), ('1.5', Decimal('1.5')),
							('.5', Decimal('0.5')), ('3.', 3), (' 3 ', 3),
							('-2', -2), ('--2', 2), ('+4', 4), ('=2*3', 6)):
			with self.subTest(text = text):
				self.assertEqual(evaluate(text), value)

	def test_a_number_is_a_decimal (self):
		self.assertIsInstance(evaluate('7'), Decimal)

class ArithmeticTest (unittest.TestCase):

	def test_precedence (self):
		self.assertEqual(evaluate('2+3*4'), 14)
		self.assertEqual(evaluate('2*3+4'), 10)
		self.assertEqual(evaluate('2*12+3'), 27)

	def test_left_association (self):
		self.assertEqual(evaluate('8-3-2'), 3)
		self.assertEqual(evaluate('12/3/2'), 2)

	def test_brackets (self):
		self.assertEqual(evaluate('(3+4)*6'), 42)
		self.assertEqual(evaluate('(-2)*3'), -6)
		self.assertEqual(evaluate('-(2+3)'), -5)

	def test_decimals_are_exact (self):
		# in floats this is 3.3000000000000003
		self.assertEqual(evaluate('1.1*3'), Decimal('3.3'))
		self.assertEqual(evaluate('0.1+0.2'), Decimal('0.3'))

	def test_division_keeps_its_places (self):
		# rounding to the column's places is left to whoever saves it
		self.assertEqual(evaluate('10/4'), Decimal('2.5'))
		self.assertEqual(evaluate('10/3').quantize(Decimal('0.01')),
							Decimal('3.33'))

	def test_other_signs_for_times_and_divide (self):
		for text in ('3x12', '3X12', '3×12', '3 x 12', '3*12'):
			with self.subTest(text = text):
				self.assertEqual(evaluate(text), 36)
		self.assertEqual(evaluate('12÷4'), 3)
		self.assertEqual(evaluate('0x10'), 0) # times, never hexadecimal

	def test_nested_brackets_within_the_length (self):
		text = '(' * 40 + '1' + ')' * 40
		self.assertEqual(evaluate(text), 1)

class RefusedTest (unittest.TestCase):

	def refused (self, text):
		with self.assertRaises(CalculatorError, msg = repr(text)) as caught:
			evaluate(text)
		return str(caught.exception)

	def test_not_a_sum (self):
		for text in ('', '   ', '=', 'abc', '2*', '*2', '2 3', '(2', '2)',
						'()', '2+*3', '1..2', '1.2.3'):
			with self.subTest(text = text):
				self.refused(text)

	def test_code_is_text_like_any_other (self):
		for text in ("__import__('os').system('true')", 'exit()', 'x',
						'().__class__', 'lambda: 1'):
			with self.subTest(text = text):
				self.refused(text)

	def test_what_python_would_take_but_a_quantity_does_not (self):
		for text in ('2**3', '5%2', '7//2', '1,000', '1_000', '1e5',
						'nan', 'inf', 'True', '1j', '٣'): # an Arabic 3
			with self.subTest(text = text):
				self.refused(text)

	def test_dividing_by_zero (self):
		for text in ('1/0', '4/(2-2)', '(1-1)/(1-1)'):
			with self.subTest(text = text):
				self.assertIn('divides by zero', self.refused(text))

	def test_too_large (self):
		self.assertIn('too large', self.refused('999999*999999'))
		self.assertIn('too large', self.refused('-1000000000'))
		self.assertEqual(evaluate('999999999'), 999999999)

	def test_too_long (self):
		self.assertIn('too long', self.refused('1+' * 50 + '1'))
		self.assertIn('too long', self.refused('(' * 51 + '1' + ')' * 51))

	def test_the_message_names_what_was_typed (self):
		self.assertIn("'2*'", self.refused('2*'))

	def test_it_is_a_value_error (self):
		# the handlers that caught ValueError around int () rely on it
		self.assertTrue(issubclass(CalculatorError, ValueError))

class WholeTest (unittest.TestCase):

	def test_a_whole_result (self):
		self.assertEqual(whole('4/2'), 2)
		self.assertEqual(whole('2.0*3'), 6)
		self.assertIsInstance(whole('4/2'), int)

	def test_a_fraction_is_refused (self):
		with self.assertRaises(CalculatorError) as caught:
			whole('3/2')
		self.assertIn('whole number', str(caught.exception))

	def test_not_a_sum_is_refused (self):
		with self.assertRaises(ValueError):
			whole('abc')

# every quantity cell that takes a sum: its .ui file and its edited handler
QUANTITY_CELLS = (
	('invoice_window.ui', 'qty_edited'),
	('credit_memo.ui', 'qty_edited'),
	('documents_window.ui', 'qty_edited'),
	('unprocessed_po.ui', 'qty_edited'),
	('purchase_order_window.ui', 'qty_edited'),
	('job_sheet.ui', 'qty_edited'),
	('inventory/inventory_count.ui', 'qty_edited'),
	('manufacturing/assembled_products.ui', 'qty_edited'),
	('resources/resource_calendar.ui', 'qty_edited'),
	('inventory/inventory_transfer.ui', 'transfer_qty_edited'),
	('manufacturing/project_edit_main.ui', 'order_qty_edited'),
	('manufacturing/project_edit_main.ui', 'needed_qty_edited'),
	('product_edit_order_numbers.ui', 'buy_qty_edited'),
	('units.ui', 'parent_qty_edited'),
)

class QuantityCellsTest (unittest.TestCase):

	def test_every_quantity_cell_is_a_text_cell (self):
		for ui_file, handler in QUANTITY_CELLS:
			with self.subTest(ui_file = ui_file, handler = handler):
				root = ET.parse(os.path.join(SRC, ui_file)).getroot()
				renderers = [o.get('class') for o in root.iter('object')
								if any(s.get('name') == 'edited' and
										s.get('handler') == handler
										for s in o.findall('signal'))]
				self.assertEqual(renderers, ['GtkCellRendererText'])

	def test_every_handler_uses_the_calculator (self):
		modules = {'invoice_window.ui': 'invoice_window.py'}
		for ui_file, handler in QUANTITY_CELLS:
			py_file = modules.get(ui_file, ui_file[:-len('.ui')] + '.py')
			with self.subTest(py_file = py_file, handler = handler):
				with open(os.path.join(SRC, py_file)) as f:
					source = f.read()
				body = source.split('def %s' % handler, 1)[1]
				body = body.split('\n\tdef ', 1)[0]
				self.assertIn('calculator.', body)

if __name__ == '__main__':
	unittest.main()
