# calculator.py
#
# Copyright (C) 2026 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

'''Arithmetic typed into a quantity cell, such as 2x12+3.

The text is read by its own small grammar, never by Python, so nothing typed
can run as code:

	expr   := term   (('+' | '-') term)*
	term   := factor (('*' | '/') factor)*
	factor := ('+' | '-') factor  |  NUMBER  |  '(' expr ')'

Numbers become Decimals straight from their digits, so 1.1*3 is exactly 3.3.
x, X and the times sign multiply, the division sign divides, and anything else
is refused.'''

import re
from decimal import Decimal, DecimalException, localcontext

MAX_LENGTH = 100 # bounds the recursion of nested brackets and the work done
LIMIT = Decimal(10) ** 9 # beyond any quantity, and within a Gtk int column

# a number, or one character; whitespace before either is skipped
TOKEN = re.compile(r'\s*(?:([0-9]+(?:\.[0-9]*)?|\.[0-9]+)|(\S))')
OPERATORS = {'+': '+', '-': '-', '*': '*', '/': '/', '(': '(', ')': ')',
				'x': '*', 'X': '*', '×': '*', '÷': '/'}

class CalculatorError (ValueError):
	pass

def tokens (text):
	'''Decimals and operator characters, in order'''
	found = list()
	position = 0
	text = text.rstrip()
	while position < len(text):
		match = TOKEN.match(text, position)
		number, character = match.groups()
		if number != None:
			found.append(Decimal(number))
		elif character in OPERATORS:
			found.append(OPERATORS[character])
		else:
			raise SyntaxError(character)
		position = match.end()
	return found

class Parser:
	'''one method per rule of the grammar; expr and term loop, only factor
	recurses'''
	def __init__ (self, tokens):
		self.tokens = tokens
		self.position = 0

	def peek (self):
		if self.position < len(self.tokens):
			return self.tokens[self.position]
		return None

	def take (self):
		token = self.peek()
		if token == None:
			raise SyntaxError('the sum ends too soon')
		self.position += 1
		return token

	def expr (self):
		value = self.term()
		while self.peek() in ('+', '-'):
			if self.take() == '+':
				value += self.term()
			else:
				value -= self.term()
		return value

	def term (self):
		value = self.factor()
		while self.peek() in ('*', '/'):
			if self.take() == '*':
				value *= self.factor()
			else:
				divisor = self.factor()
				if divisor == 0: # 0/0 is decimal's InvalidOperation otherwise
					raise ZeroDivisionError
				value /= divisor
		return value

	def factor (self):
		token = self.take()
		if token == '+':
			return self.factor()
		if token == '-':
			return -self.factor()
		if token == '(':
			value = self.expr()
			if self.take() != ')':
				raise SyntaxError('a bracket is not closed')
			return value
		if isinstance(token, Decimal):
			return token
		raise SyntaxError(token)

def evaluate (text):
	'''the value of text as a Decimal; raises CalculatorError when text is not a
	sum of numbers'''
	typed = text
	text = text.strip()
	if text.startswith('='):
		text = text[1:] # a spreadsheet habit
	if len(text) > MAX_LENGTH:
		raise CalculatorError("'%s' is too long to be a quantity" % typed)
	try:
		with localcontext():
			parser = Parser(tokens(text))
			value = parser.expr()
			if parser.peek() != None:
				raise SyntaxError('something follows the sum')
	except SyntaxError:
		raise CalculatorError("'%s' is not a quantity: use numbers, "
								"+ - * / x and brackets" % typed) from None
	except ZeroDivisionError:
		raise CalculatorError("'%s' divides by zero" % typed) from None
	except DecimalException:
		raise CalculatorError("'%s' is not a quantity" % typed) from None
	if abs(value) >= LIMIT:
		raise CalculatorError("'%s' is too large to be a quantity" % typed)
	return value

def whole (text):
	'''the value of text as an int; raises CalculatorError when it is not a
	whole number'''
	value = evaluate(text)
	if value != value.to_integral_value():
		raise CalculatorError("'%s' is not a whole number" % text)
	return int(value)
