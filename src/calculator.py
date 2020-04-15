# Copyright 2018 Matt Gilson
#
# official link https://stackoverflow.com/questions/33029168
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# modified by Reuben Rissler for Python3 by using operator.truediv

import ast
import operator

_OP_MAP = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
	ast.Invert: operator.neg,
}


class Calc(ast.NodeVisitor):

	def visit_BinOp(self, node):
		left = self.visit(node.left)
		right = self.visit(node.right)
		return _OP_MAP[type(node.op)](left, right)

	def visit_Num(self, node):
		return node.n

	def visit_Expr(self, node):
		return self.visit(node.value)

	@classmethod
	def evaluate(cls, expression):
		tree = ast.parse(expression)
		calc = cls()
		return calc.visit(tree.body[0])


