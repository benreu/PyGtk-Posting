# product_name_rules.py
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

'''Product naming convention rules.

The rules themselves live in public.product_name_rules so every database can
state its own convention. A row says only *what* to unify, never *how* to
match it: Ruleset builds the pattern from rule_type and escapes every variant.
That is deliberate. A rule written by hand as

	regexp_replace(name, '([0-9])v($|[ ,])', '\\1V')

drops the delimiter it captured and turns "Capacitor electrolytic 6.3v 100uf"
into "...6.3V100uf", eating the space. No row in the table can express that.

Ruleset is pure, so it can be unit tested from literal rows with no server and
no display. load_rules() is the only function here that touches the database.
'''

import re
from collections import namedtuple

AUTO_SAFE = 'auto'   #mechanical, reversible, no change of meaning
REVIEW = 'review'    #a real inconsistency, but a human confirms each one
REPORT = 'report'    #surfaced for information only, never rewritten
GUARD = 'guard'      #contributes no finding, only suppresses another rule

Rule = namedtuple('Rule',
			'name rule_type kind label variants canonical sort_order')
Finding = namedtuple('Finding', 'kind rule label before after')

'''A pin count token is a plain number with the suffix on the end and nothing
else: "2P", "12pin", "6P". Anything mixing letters in among the digits is a
part number rather than a count, so "ATMEGA328P" and "DCP020507P" are out of
reach because their digits do not start the token.

That still leaves "3386P", "3006P" and "3286P", the Bourns trimpots, which
really are digits followed by P. Those are told apart by width: the catalog's
largest genuine position counts are "112pos" and "154pos", three digits, while
the part numbers are four. So the digit count is bounded here in code rather
than in a rule row, because it is a fact about the shape of a part number and
not a convention anybody would want to retune.

The whole space separated word has to be the count, which is why the boundary
below is whitespace and commas rather than "not a letter or digit". A hyphen
does not separate: "DT04-4P", "DTP04-4P-LE07" and the NEMA plug "1-15P" are
single part numbers that happen to contain a number followed by P, and turning
them into "DT04-4pos" is exactly the corruption this guards against.

The *words* that mean a bare P is a pole rather than a position are a
pin_count_exclude row, so that list does stay tunable.'''
PIN_COUNT_DIGITS = r'[0-9]{1,3}'
#preceded and followed by whitespace, a comma, or the end of the name
PIN_COUNT_LEFT = r'(?<![^\s,])'
PIN_COUNT_RIGHT = r'(?![^\s,])'
'''The count is written both ways, "12pin" and "12 pin", so the gap is
optional and the canonical form closes it: "Socket DIP 14 pin" becomes
"Socket DIP 14pos", matching the "17pos" already dominant in the catalog.

Requiring the digits to be a whole word is what makes the gap safe. "Power
supply 12V 1A 5.5/2.1 pos center" is a centre positive barrel jack, not a
2.1 position anything, and the number in front of that "pos" is "5.5/2.1",
which is not a plain number, so it is never matched.'''
PIN_COUNT_GAP = r'\s*'

def split_variants (variants):
	'''Rule rows hold variants as a comma separated string; PostgreSQL array
	columns are unused everywhere else in this schema. No canonical variant
	contains a comma.'''
	return [v.strip() for v in variants.split(',') if v.strip()]

class Ruleset (object):
	'''Compiled rules. Built from a list of Rule, in no particular order; the
	ruleset sorts by sort_order itself, which is load bearing, a combined token
	such as vac/dc has to be canonicalized ahead of the single vac rule or
	"24vac/dc" comes out half fixed as "24VAC/dc".'''

	def __init__ (self, rules):
		self.rules = sorted(rules, key = lambda r: (r.sort_order, r.name))
		self._pattern = dict()
		self._exclude_words = list()
		for rule in self.rules:
			variants = split_variants(rule.variants)
			if rule.rule_type == 'pin_count_exclude':
				self._exclude_words += variants
			elif rule.rule_type == 'unit':
				#a digit must precede the unit and no letter may follow it,
				#so "12vdc" is never caught by the bare volts rule and the
				#trailing letters of a part number are out of reach entirely
				self._pattern[rule.name] = re.compile(
						r'(?<=[0-9])(?:%s)(?![A-Za-z])'
						% '|'.join(re.escape(v) for v in variants))
			elif rule.rule_type == 'pin_count':
				#the count must be a plain number, optionally a gap, then the
				#suffix, with nothing alphanumeric either side, so a word with
				#letters mixed in among the digits is never touched. The
				#digits are captured because the replacement has to put them
				#back, and the gap is dropped on the way through. Longest
				#variant first, so "pin" is preferred over "p" and the match
				#reaches the end of the word rather than stopping inside it.
				#matched without regard to case, because capitals never carry
				#meaning in a count: pin, Pin and PIN are one spelling, so a
				#rule row lists "pin" once instead of every casing of it
				self._pattern[rule.name] = re.compile(
						r'%s(%s)%s(%s)%s'
						% (PIN_COUNT_LEFT, PIN_COUNT_DIGITS, PIN_COUNT_GAP,
							'|'.join(re.escape(v) for v in
								sorted(variants, key = len, reverse = True)),
							PIN_COUNT_RIGHT), re.I)
			elif rule.rule_type == 'vocabulary':
				self._pattern[rule.name] = re.compile(
						r'\b(?:%s)\b'
						% '|'.join(re.escape(v) for v in variants), re.I)
			elif rule.rule_type == 'brand':
				self._pattern[rule.name] = [
						(v, re.compile(r'\b%s\b' % re.escape(v), re.I))
						for v in variants]
		self._exclude_re = None
		if self._exclude_words:
			self._exclude_re = re.compile(r'\b(?:%s)\b'
					% '|'.join(re.escape(w) for w in self._exclude_words),
					re.I)

	def _apply_one (self, rule, name):
		'''The result of accepting a single rule, or name unchanged.'''
		if rule.rule_type == 'whitespace':
			if rule.name == 'trim':
				return name.strip()
			if rule.name == 'double_space':
				return re.sub(r'\s+', ' ', name)
			return name          #an unknown whitespace rule does nothing
		#canonical comes out of a table a user edits, so every replacement goes
		#through a function. Handing it to re.sub as a template would let a
		#stray backslash in that column be read as an escape or a group
		#reference rather than the literal text somebody typed.
		if rule.rule_type in ('unit', 'vocabulary'):
			return self._pattern[rule.name].sub(
						lambda match: rule.canonical, name)
		if rule.rule_type == 'pin_count':
			return self._pattern[rule.name].sub(
						lambda match: self._pin_count(rule, name, match), name)
		return name              #brand and guard rows never rewrite

	def _pin_count (self, rule, name, match):
		'''What one matched count becomes, or the text untouched.

		Only a one letter suffix is ambiguous: the P in "Breaker 15A 2P" is
		poles, not positions, which is what the exclude words are there to
		catch. A spelled out suffix says what it means, so "Relay socket 8
		pin" and "Switch DIP 2 pos" are counts even though "relay" and
		"switch" are exclude words. Suppressing those by name, as an earlier
		version did, lost 15 real counts in this catalog.'''
		if len(match.group(2)) == 1 and self._pole_context(name):
			return match.group(0)
		return match.group(1) + rule.canonical

	def _pole_context (self, name):
		'''Whether a bare P in this name reads as poles rather than positions.
		It depends on what the product is, so it is the one guard that has to
		look at the whole name.'''
		if self._exclude_re is not None and self._exclude_re.search(name):
			return True
		return False

	def apply (self, name, rule_names = None):
		'''Apply exactly the named rules, in sort order. The cleanup window
		passes the rules the user ticked, so accepting one suggestion never
		drags another one in.'''
		for rule in self.rules:
			if rule_names is not None and rule.name not in rule_names:
				continue
			name = self._apply_one(rule, name)
		return name

	def auto_rule_names (self):
		return [r.name for r in self.rules if r.kind == AUTO_SAFE]

	def normalize (self, name):
		'''The auto safe subset: whitespace and unit casing. Idempotent, and
		never changes the wording of a name.'''
		return self.apply(name, self.auto_rule_names())

	def findings (self, name):
		'''Every finding for one name, auto safe first. before and after are
		the step that one rule makes, and rule names the rule, so a caller can
		re-apply precisely the subset a user accepted.'''
		found = list()
		running = name
		for rule in self.rules:
			if rule.kind == AUTO_SAFE:
				fixed = self._apply_one(rule, running)
				if fixed != running:
					found.append(Finding(AUTO_SAFE, rule.name, rule.label,
											running, fixed))
					running = fixed
		#review and report rules are measured against the auto safe result,
		#so a suggestion never re-proposes a fix already covered above
		for rule in self.rules:
			if rule.kind == REVIEW:
				fixed = self._apply_one(rule, running)
				if fixed != running:
					found.append(Finding(REVIEW, rule.name, rule.label,
											running, fixed))
			elif rule.kind == REPORT and rule.rule_type == 'brand':
				found += self._brand_findings(rule, running)
		return found

	def _brand_findings (self, rule, name):
		'''A brand sitting mid name, where the catalog's other convention would
		have led with it. Reported, never reordered.'''
		for variant, pattern in self._pattern.get(rule.name, []):
			if pattern.search(name) \
					and not name.lower().startswith(variant.lower()):
				return [Finding(REPORT, rule.name, rule.label, name, '')]
		return []

	def suggest (self, name):
		'''(auto safe corrected name, all findings) for the product window.'''
		return self.normalize(name), self.findings(name)

EMPTY = Ruleset([])

_ruleset = None

def installed ():
	'''Whether this database has opted in. The rules table is created by the
	cleanup window on request, not by the version upgrade mechanism, so that
	this feature can be adopted one database at a time and does not have to
	queue behind whatever schema work is in flight.'''
	from db_connection import DB
	cursor = DB.cursor()
	cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables "
						"WHERE table_schema = 'public' "
						"AND table_name = 'product_name_rules')")
	exists = cursor.fetchone()[0]
	cursor.close()
	DB.rollback()
	return exists

def install ():
	'''Create and seed the rules table from db/product_name_rules.sql. Every
	statement in that file is idempotent, so this is safe to call again; it
	will not revive a rule that was deactivated or soft deleted.'''
	import os
	from constants import sql_dir
	from db_connection import DB
	sql_file = os.path.join(sql_dir, 'product_name_rules.sql')
	with open(sql_file, 'r') as f:
		sql = f.read()
	cursor = DB.cursor()
	cursor.execute(sql)
	cursor.close()
	DB.commit()
	return load_rules()

def load_rules ():
	'''Re-read the rules table into the module cache. Called when a window that
	needs the rules opens, and again after the Rules tab edits one.'''
	global _ruleset
	from db_connection import DB
	if not installed():
		#not opted in: no rules means no normalization and no findings, so
		#every caller stays inert rather than guessing at a convention
		_ruleset = EMPTY
		return _ruleset
	cursor = DB.cursor()
	cursor.execute("SELECT name, rule_type, kind, label, variants, "
						"canonical, sort_order "
						"FROM product_name_rules "
						"WHERE (active, deleted) = (True, False) "
						"ORDER BY sort_order")
	_ruleset = Ruleset([Rule(*row) for row in cursor.fetchall()])
	cursor.close()
	DB.rollback()
	return _ruleset

def ruleset ():
	if _ruleset is None:
		return load_rules()
	return _ruleset

def normalize (name):
	return ruleset().normalize(name)

def findings (name):
	return ruleset().findings(name)

def suggest (name):
	return ruleset().suggest(name)

def duplicate_key (name):
	'''The key two names collide on once case and spacing are ignored, for the
	cleanup window's duplicate report.'''
	return re.sub(r'\s+', ' ', name).strip().lower()
