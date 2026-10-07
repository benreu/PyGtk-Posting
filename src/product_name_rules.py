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

'''Rule types whose suggestions compose rather than stand alone, and so are
offered as one finding carrying the finished name instead of one finding per
rule. See Ruleset._grouped_findings.'''
GROUPED_TYPES = ('token_order', 'qualifier')

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

'''A unit is only a unit when the number it belongs to starts the section.

The guard is the same one the pin count uses and it is there for the same
reason: without it the rule needs nothing more than a digit somewhere to the
left, so a part number ending in digits and a unit spelling is rewritten.
"T92UH" becomes "T92uH", and the catalog holds plenty of part numbers in that
shape, "A23C" and "MG200J6ES61" and "DT04-4P", that are one edit away from it.
Requiring the whole whitespace or comma delimited section to read as a number
followed by the unit puts every one of them out of reach, because a part
number does not begin with its digits.

The number itself may start with a dot, ".75A" is three quarters of an amp,
and may hold the punctuation a range or a fraction needs: "100-200VDC",
"3-30A", "1/4W", "30~20A". It is captured rather than looked behind because
it is variable width, and it is put back untouched, so the rule still only
ever rewrites the unit.'''
UNIT_LEFT = r'(?<![^\s,])'
UNIT_NUMBER = r'[.0-9][0-9.,/~+-]*'
UNIT_RIGHT = r'(?![A-Za-z])'

'''Token roles, for the token_order rules.

A product name is a sequence of sections, and the sections worth putting in a
fixed order are recognisable by their shape alone: "120VAC" is a voltage and
"SPDT" is a contact configuration no matter what product they belong to. So no
list of part numbers is needed anywhere, which is the only reason ordering can
be stated as a convention at all. These are facts about the shape of a
section rather than conventions anybody would retune, so they live here beside
the pin count guards while the precedence pairs themselves live in the table.

Order is load bearing: the first match wins and PART is last, because PART is
only "digits and letters, and none of the above" and would otherwise swallow
every spec in the list. A section matching nothing is ungoverned and never
moves, which is what keeps "socket", "PCB mount" and "automotive" in place.

Matching ignores case, because not every unit in this catalog has a settled
casing to rely on. K was left out of the seeded rules on purpose, uH and pF
have no rule at all, and a database is free to deactivate any of them. A role
that insisted on the canonical casing would read "22uh" and "4.7k" as part
numbers and shuffle them about as if they were identifiers, which is the one
mistake worth going out of the way to avoid, so a section is recognised by its
shape whatever case it is written in.'''
TOKEN_ROLES = (
	#SPDT, DPDT, 4PDT, 4PST-NO. The digit position also takes S and D, so a
	#three pole and a single pole form are one shape
	('CFG', r'[0-9SD]P[DS]T(-N[OC])?'),
	('V', r'[0-9.]+V(AC|DC)?'),
	('A', r'[0-9.-]+(A|mA)'),
	('W', r'[0-9.]+(W|VA|kVA)'),
	#a bare M is left out: in this catalog it is the 3M brand, the way count
	#of a Weatherpack plug, and metres of cable, against five crystals where
	#it means megahertz. K stays, where the worst case is a colour temperature
	#being read as a resistance, which orders the same way regardless
	('VAL', r'[0-9.]+(uF|pF|nF|uH|mH|H|OHM|mOHM|kOHM|K)'),
	('GAUGE', r'[0-9-]+(AWG|GA)'),
	('COUNT', r'[0-9]+(pos|pin|P)'),
	('SIZE', r'[0-9./]+("|mm|cm|in)|[0-9]+x[0-9.]+(mm)?'),
	#a part number: digits and letters in any arrangement, and none of the
	#shapes above. "RH1B", "G2RL", "T92S7D12-12", "18-8SS"
	('PART', r'(?=[^0-9]*[0-9])(?=[^A-Za-z]*[A-Za-z]).+'),
)
'''The one role that is not a shape. A qualifier is a trailing note rather
than part of what the product is, "THT" on the single through hole member of a
family, and no shape tells it from the product's own name: "THT" and "PTC" are
the same three capitals. Nor does position, which was measured and does not
work. Taking every unrecognised section after the first spec as a note reads
"Inverter 24VDC in 12VDC out 1.67A" as carrying two of them and offers
"Inverter 24VDC 12VDC in out 1.67A", and it mistakes the class of every name
that leads with a part number, where "IGBT Transistor" and "hall effect shunt"
sit after one: 31 names, much of it wrong, to put one THT in its place.

So qualifiers are named, in a qualifier rule row, and a word moves only
because somebody said it was a note. A declared word in front of the first
recognised section is still the product's own name and stays there, so
declaring "fuse" could not drag "PTC fuse" apart.'''
QUALIFIER = 'QUAL'
TOKEN_ROLE_NAMES = [role for role, pattern in TOKEN_ROLES]
_ROLE_PATTERNS = [(role, re.compile(r'(?:%s)\Z' % pattern, re.I))
					for role, pattern in TOKEN_ROLES]

def token_role (token):
	'''Which role one section of a name plays, or the empty string for a
	section that plays none and must therefore stay where it is.'''
	for role, pattern in _ROLE_PATTERNS:
		if pattern.match(token):
			return role
	return ''

def token_roles (tokens, qualifiers = ()):
	'''The role of every section of a name, in order, which is what an
	ordering rule works from: token_role for each section, and QUAL for a
	declared qualifier that a recognised section already precedes.'''
	roles = [token_role(token) for token in tokens]
	classified = False
	for i, role in enumerate(roles):
		if role:
			classified = True
		elif classified and tokens[i].lower() in qualifiers:
			roles[i] = QUALIFIER
	return roles

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
		self._qualifiers = set()
		self._qualifier_phrases = list()
		for rule in self.rules:
			variants = split_variants(rule.variants)
			if rule.rule_type == 'pin_count_exclude':
				self._exclude_words += variants
			elif rule.rule_type == 'qualifier':
				#every qualifier row contributes to one list, so a database
				#can group its notes however it finds them
				for variant in variants:
					words = variant.lower().split()
					if len(words) == 1:
						self._qualifiers.add(words[0])
					elif words:
						self._qualifier_phrases.append(tuple(words))
			elif rule.rule_type == 'unit':
				#the section must read as a number and then the unit, with no
				#letter following, so "12vdc" is never caught by the bare
				#volts rule and a part number is out of reach entirely. The
				#number is captured because the replacement has to put it
				#back. Longest variant first, so a spelling that opens
				#another is not matched short
				self._pattern[rule.name] = re.compile(
						r'%s(%s)(?:%s)%s'
						% (UNIT_LEFT, UNIT_NUMBER,
							'|'.join(re.escape(v) for v in
								sorted(variants, key = len, reverse = True)),
							UNIT_RIGHT))
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
			elif rule.rule_type == 'token_order':
					#one row is one precedence pair and nothing more: exactly
					#two role names, FIRST then SECOND. A row naming anything
					#else is left inert rather than raised, so a typo typed
					#into the rules tab costs that one rule and not the window
					if len(variants) == 2 \
							and all(v in TOKEN_ROLE_NAMES for v in variants):
						self._pattern[rule.name] = (variants[0], variants[1])
			elif rule.rule_type == 'brand':
				self._pattern[rule.name] = [
						(v, re.compile(r'\b%s\b' % re.escape(v), re.I))
						for v in variants]
		#longest first, so "panel mount" is preferred over a bare "mount"
		self._qualifier_phrases.sort(key = len, reverse = True)
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
		if rule.rule_type == 'unit':
			return self._pattern[rule.name].sub(
						lambda match: match.group(1) + rule.canonical, name)
		if rule.rule_type == 'vocabulary':
			return self._pattern[rule.name].sub(
						lambda match: rule.canonical, name)
		if rule.rule_type == 'pin_count':
			return self._pattern[rule.name].sub(
						lambda match: self._pin_count(rule, name, match), name)
		if rule.rule_type == 'token_order':
			pair = self._pattern.get(rule.name)
			if pair is None:
				return name      #not a pair of known roles: inert
			return self._reorder(name, pair,
						lambda role: 0 if role == pair[0] else 1)
		if rule.rule_type == 'qualifier':
			#a declared note goes after every recognised section, which is
			#what declaring it says. There is no pair to state: a qualifier
			#is last against everything or it is not a qualifier
			return self._reorder(name, None,
						lambda role: 1 if role == QUALIFIER else 0)
		return name              #brand and guard rows never rewrite

	def _reorder (self, name, governed, rank):
		'''The slot mechanic both ordering rules are built on: take the
		positions holding the sections the rule governs, order those sections
		by rank, and write them back into the same positions. governed is the
		roles the rule speaks for, or None for every recognised section.

		Nothing is compacted, nothing is inserted, and a section the rule does
		not govern keeps its position, so a rule can be declared for the whole
		catalog without having to say which products it applies to: a name
		that does not carry what the rule speaks about is not a name the rule
		has an opinion about. That is also why there is no total order over
		the roles anywhere in this module. The catalog is several naming
		systems at once, and measuring it found the ordering of a part number
		against a spec genuinely inconsistent, so any single declared order
		mangles one system to tidy another: the bolt named 18-8SS 1/4 - 20 x
		12 inch comes out with its material last. A pair at a time cannot
		reach that name at all.

		The result is always a permutation of the sections of the input, which
		is what makes every suggestion reversible, and applying it twice
		changes nothing. Both are asserted in the tests.

		Whitespace is carried through untouched rather than rebuilt, because
		these rules are about order only; a doubled or a trailing space is the
		whitespace rules' business and shows up as its own finding.'''
		texts, roles, gaps = self._sections(name)
		slots = [i for i, role in enumerate(roles)
					if role and (governed is None or role in governed)]
		if len(set(roles[i] for i in slots)) < 2:
			#the rule speaks about one kind of section here, or none: there is
			#nothing for it to put in an order
			return name
		picked = [texts[i] for i in slots]
		#stable, so two sections of the same role keep their relative order
		order = sorted(range(len(slots)),
						key = lambda k: (rank(roles[slots[k]]), k))
		for slot, pick in zip(slots, order):
			texts[slot] = picked[pick]
		return ''.join(text + gap for text, gap in zip(texts, gaps))

	def _sections (self, name):
		'''A name cut into the sections a rule orders: their text, their role,
		and the gap that follows each one.

		A declared phrase is one section. "mount" is never a note on its own
		in this catalog, it is the tail of one, and declaring the word alone
		pulls "panel mount" and "chassis mount" apart, so a qualifier row may
		name "PCB mount" and have it match, move and stay whole. The gaps
		inside a phrase travel with it and the gaps between sections stay
		where they are, so ordering never rewrites spacing.

		A phrase is a note wherever it sits, except as the opening section,
		which is what the product is. It can afford that where a single word
		cannot: naming two words together says which "mount" is meant, while
		a lone declared word only becomes a note once something recognised has
		come before it, so declaring "SMD" cannot turn "SMD LED red" around.
		That is also what reaches "Fuse PCB mount 2A 250VAC", where nothing is
		recognised before the note.'''
		parts = re.split(r'(\s+)', name)      #odd indices are the gaps
		tokens, spaces = parts[0::2], parts[1::2]
		word_roles = token_roles(tokens, self._qualifiers)
		lowered = [token.lower() for token in tokens]
		texts, roles, gaps = list(), list(), list()
		i = 0
		while i < len(tokens):
			span = self._phrase_span(lowered, i)
			text = tokens[i]
			for k in range(i + 1, i + span):
				text += spaces[k - 1] + tokens[k]
			if span > 1:
				roles.append(QUALIFIER if texts else '')
			else:
				roles.append(word_roles[i])
			texts.append(text)
			i += span
			gaps.append(spaces[i - 1] if i <= len(spaces) else '')
		return texts, roles, gaps

	def _phrase_span (self, lowered, i):
		'''How many sections a declared phrase starting here covers, or one
		for anything that is not the start of a phrase.'''
		for phrase in self._qualifier_phrases:
			if tuple(lowered[i:i + len(phrase)]) == phrase:
				return len(phrase)
		return 1

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
		drags another one in.

		An entry may name several rules at once, comma separated, which is how
		a grouped finding is accepted: its suggestion is the composed result
		of rules that do not stand alone, so it is taken or left whole.'''
		wanted = None
		if rule_names is not None:
			wanted = list()
			for entry in rule_names:
				wanted += split_variants(entry)
		for rule in self.rules:
			if wanted is not None and rule.name not in wanted:
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
		grouped = list()
		for rule in self.rules:
			if rule.kind == REVIEW:
				if rule.rule_type in GROUPED_TYPES:
					grouped.append(rule)
					continue
				fixed = self._apply_one(rule, running)
				if fixed != running:
					found.append(Finding(REVIEW, rule.name, rule.label,
											running, fixed))
			elif rule.kind == REPORT and rule.rule_type == 'brand':
				found += self._brand_findings(rule, running)
		return found + self._grouped_findings(grouped, running)

	def _grouped_findings (self, rules, name):
		'''One finding for the rules whose suggestions compose, or none.

		A precedence pair has an opinion about two roles and nothing else, so
		a name carrying two pairs draws a suggestion from each, and separately
		those two read as contradictions. Of "Relay PCB mount 12V 30A SPST",
		a configuration against a current says "12V SPST 30A" on its own and a
		configuration against a voltage says "SPST 30A 12V" on its own, while
		together they say "SPST 12V 30A", which is the one anybody would want.
		Offering the halves would ask for a decision between two wrong
		answers, so the pairs that fire are offered as one suggestion carrying
		the finished order, the same way the mechanical fixes are offered as
		one row rather than a step per rule.

		The finding names every rule that went into it, so accepting it still
		applies precisely those and nothing else: a rule that would not have
		changed anything is left out rather than listed, which is the same
		thing as applying it and makes the row say what it did.'''
		fired = list()
		labels = list()
		running = name
		for rule in rules:
			fixed = self._apply_one(rule, running)
			if fixed == running:
				continue
			fired.append(rule.name)
			if rule.label not in labels:
				labels.append(rule.label)
			running = fixed
		if not fired:
			return []
		return [Finding(REVIEW, ','.join(fired), ', '.join(labels),
						name, running)]

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
