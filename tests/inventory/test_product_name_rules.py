# test_product_name_rules.py
#
# The rule engine is pure, so these run with no database and no display. They
# pin the engine's semantics; test_product_name_cleanup.py pins the seed that
# db/product_name_rules.sql actually installs.

import os, sys, unittest

SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
sys.path.insert(0, os.path.abspath(SRC))

from product_name_rules import (Ruleset, Rule, split_variants,
								AUTO_SAFE, REVIEW, REPORT)

def rule (sort_order, name, rule_type, kind, label, variants, canonical = ''):
	return Rule(name, rule_type, kind, label, variants, canonical, sort_order)

#the same convention db/product_name_rules.sql seeds, as literal rows
SEED = [
	rule(10, 'trim', 'whitespace', AUTO_SAFE, 'Whitespace', ''),
	rule(20, 'double_space', 'whitespace', AUTO_SAFE, 'Whitespace', ''),
	rule(100, 'volts', 'unit', AUTO_SAFE, 'Unit case', 'v', 'V'),
	rule(110, 'volts_ac_dc', 'unit', AUTO_SAFE, 'Unit case',
			'vac/dc,VAC/dc,vac/DC', 'VAC/DC'),
	rule(120, 'volts_ac', 'unit', AUTO_SAFE, 'Unit case', 'vac,Vac,vAC', 'VAC'),
	rule(130, 'volts_dc', 'unit', AUTO_SAFE, 'Unit case', 'vdc,Vdc,vDC', 'VDC'),
	rule(140, 'amps', 'unit', AUTO_SAFE, 'Unit case', 'a', 'A'),
	rule(150, 'milliamps', 'unit', AUTO_SAFE, 'Unit case', 'ma,MA,Ma', 'mA'),
	rule(160, 'microfarads', 'unit', AUTO_SAFE, 'Unit case', 'uf,UF', 'uF'),
	rule(170, 'watts', 'unit', AUTO_SAFE, 'Unit case', 'w', 'W'),
	rule(180, 'ohms', 'unit', AUTO_SAFE, 'Unit case', 'ohm,Ohm', 'OHM'),
	rule(190, 'wire_gauge', 'unit', AUTO_SAFE, 'Unit case', 'awg', 'AWG'),
	rule(200, 'gauge', 'unit', AUTO_SAFE, 'Unit case', 'ga', 'GA'),
	rule(300, 'receptacle', 'vocabulary', REVIEW, 'Vocabulary',
			'recep,recept,receptacle,rcpt', 'Recep'),
	rule(400, 'pin_count', 'pin_count', REVIEW, 'Pin count',
			'P,pin,pins,pos,position,positions', 'pos'),
	rule(410, 'pin_count_exclude', 'pin_count_exclude', 'guard', 'Pin count',
			'relay,contactor,breaker,switch,disconnect'),
	rule(500, 'brands', 'brand', REPORT, 'Word order',
			'Visotron,Dellatron,Deutsch,Stimopuls,Westfalia,Wedgelock,Boumatic'),
	]

def seeded ():
	return Ruleset(SEED)

class VariantSplitTest(unittest.TestCase):
	def test_splits_and_strips(self):
		self.assertEqual(split_variants('uf, UF ,uF'), ['uf', 'UF', 'uF'])

	def test_empty_variants_give_no_entries(self):
		self.assertEqual(split_variants(''), [])
		self.assertEqual(split_variants(' , '), [])

class DelimiterTest(unittest.TestCase):
	'''The bug that motivated the whole variants-plus-canonical design: a hand
	written '([0-9])v($|[ ,])' -> '\\1V' eats the space after the unit.'''

	def test_space_after_the_unit_survives(self):
		self.assertEqual(
			seeded().normalize('Capacitor electrolytic 6.3v 100uf'),
			'Capacitor electrolytic 6.3V 100uF')

	def test_does_not_run_the_tokens_together(self):
		self.assertNotIn(
			'6.3V100',
			seeded().normalize('Capacitor electrolytic 6.3v 100uf'))

	def test_comma_delimiter_survives(self):
		self.assertEqual(seeded().normalize('Relay 12v, 5a'), 'Relay 12V, 5A')

	def test_unit_at_end_of_string(self):
		self.assertEqual(seeded().normalize('Soldering station 80w'),
						'Soldering station 80W')

class SortOrderTest(unittest.TestCase):
	def test_combined_token_wins_over_the_single_rule(self):
		'''volts_ac_dc sorts ahead of volts_ac, or this comes out 24VAC/dc.'''
		self.assertEqual(seeded().normalize('Indicator green 10mm 24vac/dc'),
						'Indicator green 10mm 24VAC/DC')

	def test_order_is_taken_from_sort_order_not_list_order(self):
		shuffled = Ruleset(list(reversed(SEED)))
		self.assertEqual(shuffled.normalize('Indicator green 10mm 24vac/dc'),
						'Indicator green 10mm 24VAC/DC')

class UnitCaseTest(unittest.TestCase):
	def test_each_seeded_unit(self):
		for before, after in [
				('Battery 12v A23C', 'Battery 12V A23C'),
				('Recom 9v 2a THT', 'Recom 9V 2A THT'),
				('Driver LED 45V 1050MA', 'Driver LED 45V 1050mA'),
				('Driver LED 190v 1050ma', 'Driver LED 190V 1050mA'),
				('Capacitor electrolytic 75V 22000uF',
					'Capacitor electrolytic 75V 22000uF'),
				('Capacitor 660VAC 4UF Weaverline',
					'Capacitor 660VAC 4uF Weaverline'),
				('Indicator red 8m 12vdc', 'Indicator red 8m 12VDC'),
				('Resistor 150W 100Ohm', 'Resistor 150W 100OHM'),
				('Wire stranded 8awg THHN', 'Wire stranded 8AWG THHN'),
				('Cable ferrule 14ga', 'Cable ferrule 14GA'),
				]:
			self.assertEqual(seeded().normalize(before), after)

	def test_a_unit_glued_to_letters_is_left_alone(self):
		'''"12vdc" must not be caught by the bare volts rule, and a part
		number's trailing letters are unreachable.'''
		for name in ['Plug Deutsch DT06-12SB-CE13 black', 'Diode zener 1N4733',
						'Relay DPDT 120VAC RU2S', 'Socket Molex MX150L 14-16AWG',
						'LED driver 107V 1400mA XLG-150-M-A',
						'Switch E-Stop Idec XN1E-BV402MR']:
			self.assertEqual(seeded().normalize(name), name)

	def test_units_with_no_rule_keep_their_case(self):
		'''kiloamps, volt-amps, picofarads and millihenries were never given a
		canonical form, so only the volts in these names changes'''
		self.assertEqual(seeded().normalize('Varistor MOV 275v 4.5ka'),
						'Varistor MOV 275V 4.5ka')
		self.assertEqual(seeded().normalize('Transformer Sola 120v 150va'),
						'Transformer Sola 120V 150va')
		self.assertEqual(seeded().normalize('Capacitor ceramic 18pf THT 100v'),
						'Capacitor ceramic 18pf THT 100V')
		self.assertEqual(seeded().normalize('Choke 36mh 4.5ohm 300mA'),
						'Choke 36mh 4.5OHM 300mA')

class WhitespaceTest(unittest.TestCase):
	def test_trim(self):
		self.assertEqual(seeded().normalize('Potentiometer '), 'Potentiometer')

	def test_collapse_double_space(self):
		self.assertEqual(seeded().normalize('Relay  SPDT'), 'Relay SPDT')

class IdempotenceTest(unittest.TestCase):
	def test_normalizing_twice_changes_nothing(self):
		rs = seeded()
		for name in ['Capacitor electrolytic 6.3v 100uf', 'Potentiometer ',
						'Indicator green 10mm 24vac/dc', 'Relay  SPDT 12v',
						'Wire stranded 8awg THHN', 'Resistor 150W 100Ohm']:
			once = rs.normalize(name)
			self.assertEqual(rs.normalize(once), once)

class PinCountGuardTest(unittest.TestCase):
	'''P means poles on a breaker and belongs to the part number on a trimpot.
	Rewriting either to "pos" is corruption, so both are suppressed.'''

	def _pin_findings (self, name):
		return [f for f in seeded().findings(name) if f.rule == 'pin_count']

	def test_pole_context_is_suppressed(self):
		for name in ['Breaker 15A 2P', 'Contactor 24V 50A 3P',
						'Breaker .5A 2p lever DIN rail',
						'Relay SPDT 2P', 'Switch rotary 4P']:
			self.assertEqual(self._pin_findings(name), [], name)

	def test_part_numbers_are_suppressed(self):
		for name in ['ATMEGA328P', 'ATMEGA644P', 'Dc/dc isolator DCP020507P',
						'Potentiometer Bourns 3006P 10K',
						'Potentiometer PCB mount 100K 3386P',
						'Potentiometer 3286P 20K']:
			self.assertEqual(self._pin_findings(name), [], name)

	def test_a_word_mixing_letters_among_the_digits_is_ignored(self):
		'''a count is a plain number with the suffix on the end; anything with
		letters in among the digits is a part number'''
		for name in ['SPP15P10', 'VNN7NV04P', 'Autonics counter CT4S-1P4',
						'GPS Sparkfun ZED-F9P RTK',
						'IGBT Fuji 7MBR50U4P120-50',
						'Socket Deutsch PCB DRC20-50P03']:
			self.assertEqual(self._pin_findings(name), [], name)

	def test_a_hyphen_does_not_separate_the_count_from_a_part_number(self):
		'''"DT04-4P" is one part number, not a 4 position something, and the
		NEMA plug "1-15P" is not a 15 position one either'''
		for name in ['Recep Deutsch DT04-2P', 'Recep Deutsch DTP04-4P-LE07',
						'Deutsch DT04-4P-L012 gasket',
						'Recep Deutsch DT13-6P panel PCB gray',
						"Cord 18AWG 1-15P - 320-C7 6'"]:
			self.assertEqual(self._pin_findings(name), [], name)

	def test_width_tells_a_count_from_a_trimpot_part_number(self):
		'''the catalog's largest real counts are three digits, 112pos and
		154pos; the Bourns part numbers are four'''
		self.assertEqual(self._pin_findings('Potentiometer 3386P'), [])
		found = self._pin_findings('Header 112P')
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].after, 'Header 112pos')

	def test_the_count_may_sit_anywhere_in_the_name(self):
		for name, after in [
				('2P header', '2pos header'),
				('Molex 2P vertical header', 'Molex 2pos vertical header'),
				('TPA MetriPack 150 2P', 'TPA MetriPack 150 2pos'),
				('Plug Amp Econoseal III 2P 344075-1',
					'Plug Amp Econoseal III 2pos 344075-1'),
				]:
			found = self._pin_findings(name)
			self.assertEqual(len(found), 1, name)
			self.assertEqual(found[0].after, after)

	def test_a_comma_separates_a_count(self):
		found = self._pin_findings('Header 4P, gold')
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].after, 'Header 4pos, gold')

	def test_the_digits_are_kept(self):
		'''the replacement has to put the captured number back, the same trap
		the unit rules have with their delimiter'''
		self.assertEqual(self._pin_findings('Terminal 10P 5MM side entry')[0]
						.after, 'Terminal 10pos 5MM side entry')

	def test_genuine_pin_counts_are_still_suggested(self):
		for name, after in [
				('Terminal block 3.5mm 12pin plug',
					'Terminal block 3.5mm 12pos plug'),
				('Molex 2P vertical header', 'Molex 2pos vertical header'),
				('0.156" 6P recept latch', '0.156" 6pos recept latch'),
				]:
			found = self._pin_findings(name)
			self.assertEqual(len(found), 1, name)
			self.assertEqual(found[0].after, after)

	def test_a_gap_between_the_number_and_the_suffix_is_picked_up(self):
		'''the count is written both ways in the catalog, "12pin" and
		"12 pin", and the canonical form closes the gap'''
		for name, after in [
				('Socket DIP 14 pin .3" wide', 'Socket DIP 14pos .3" wide'),
				('Wedgelock Deutsch DT plug 12 pin',
					'Wedgelock Deutsch DT plug 12pos'),
				('Terminal block right angle plug 2 pos',
					'Terminal block right angle plug 2pos'),
				('Connector FFC Vertical 6 Position',
					'Connector FFC Vertical 6pos'),
				('Plug AMP 16 pin (12+4)', 'Plug AMP 16pos (12+4)'),
				('ZIF socket 24 pin', 'ZIF socket 24pos'),
				]:
			found = self._pin_findings(name)
			self.assertEqual(len(found), 1, name)
			self.assertEqual(found[0].after, after)

	def test_both_spacings_reach_the_same_canonical_form(self):
		rs = seeded()
		self.assertEqual(rs.apply('Header 4 pin', ['pin_count']),
						rs.apply('Header 4pin', ['pin_count']))

	def test_the_suffix_is_matched_whatever_its_case(self):
		'''capitals never carry meaning in a count, so one variant covers
		every casing of it'''
		for name in ['Header 4pin', 'Header 4Pin', 'Header 4PIN',
						'Header 4 POS', 'Header 4 Pos']:
			found = self._pin_findings(name)
			self.assertEqual(len(found), 1, name)
			self.assertEqual(found[0].after, 'Header 4pos', name)

	def test_a_number_that_is_not_a_whole_word_is_not_a_count(self):
		'''"5.5/2.1 pos center" is a centre positive barrel jack, so the thing
		in front of that "pos" is not a plain number and must not be read as
		one'''
		for name in ['Power supply 12V 1A 5.5/2.1 pos center',
						'Power supply 12V 5.5/2.5 pos center',
						'Power supply 12V 1.5A 5.5/2.1 positive center']:
			self.assertEqual(self._pin_findings(name), [], name)

	def test_only_a_one_letter_suffix_defers_to_the_pole_words(self):
		'''the P in "Breaker 15A 2P" is poles, but a spelled out suffix says
		what it means, so "Relay socket 8 pin" is a count even though "relay"
		is an exclude word'''
		for name, after in [
				('Relay socket 8 pin octal', 'Relay socket 8pos octal'),
				('Switch DIP 2 pos', 'Switch DIP 2pos'),
				('Switch DIP 10 pos sealed', 'Switch DIP 10pos sealed'),
				('Breaker panel 12 position', 'Breaker panel 12pos'),
				]:
			found = self._pin_findings(name)
			self.assertEqual(len(found), 1, name)
			self.assertEqual(found[0].after, after)

	def test_a_pole_name_with_both_forms_only_fixes_the_spelled_one(self):
		found = self._pin_findings('Relay 2P socket 8 pin')
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].after, 'Relay 2P socket 8pos')

	def test_pin_count_is_review_not_auto(self):
		found = self._pin_findings('Molex 2P vertical header')
		self.assertEqual(found[0].kind, REVIEW)
		#and so it is never applied by normalize
		self.assertEqual(seeded().normalize('Molex 2P vertical header'),
						'Molex 2P vertical header')

	def test_removing_the_guard_row_lets_poles_through(self):
		'''proves the exclude list really is what suppresses them, and that a
		database can retune it'''
		without = Ruleset([r for r in SEED
							if r.rule_type != 'pin_count_exclude'])
		found = [f for f in without.findings('Breaker 15A 2P')
					if f.rule == 'pin_count']
		self.assertEqual(len(found), 1)

class VocabularyTest(unittest.TestCase):
	def test_every_spelling_collapses_to_one(self):
		rs = seeded()
		for spelling in ['Recep', 'recep', 'Recept', 'recept',
							'Receptacle', 'receptacle', 'Rcpt']:
			found = [f for f in rs.findings('%s Deutsch DT13 gray' % spelling)
						if f.rule == 'receptacle']
			if spelling == 'Recep':
				self.assertEqual(found, [])          #already canonical
			else:
				self.assertEqual(len(found), 1, spelling)
				self.assertTrue(found[0].after.startswith('Recep '), spelling)

	def test_vocabulary_is_review_not_auto(self):
		found = [f for f in seeded().findings('Recept Deutsch')
					if f.rule == 'receptacle']
		self.assertEqual(found[0].kind, REVIEW)
		self.assertEqual(seeded().normalize('Recept Deutsch'), 'Recept Deutsch')

	def test_not_matched_inside_a_longer_word(self):
		self.assertEqual([f for f in seeded().findings('Interception box')
							if f.rule == 'receptacle'], [])

class BrandReportTest(unittest.TestCase):
	def test_brand_mid_name_is_reported(self):
		found = [f for f in seeded().findings('O-ring 26x1.5mm Visotron solenoid')
					if f.rule == 'brands']
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].kind, REPORT)

	def test_brand_leading_is_not_reported(self):
		self.assertEqual([f for f in seeded().findings('Visotron cable 22/8 hi-flex')
							if f.rule == 'brands'], [])

	def test_report_never_rewrites(self):
		name = 'O-ring 26x1.5mm Visotron solenoid'
		self.assertEqual(seeded().normalize(name), name)
		found = [f for f in seeded().findings(name) if f.rule == 'brands'][0]
		self.assertEqual(found.after, '')

class NoFalsePositiveTest(unittest.TestCase):
	def test_a_name_starting_with_a_digit_is_clean(self):
		'''110 names legitimately lead with the pitch, so there is deliberately
		no "must start with a capital" rule.'''
		for name in ['0.1" 1x36 header female', '0.156" 2P header latch',
						'0.1" 1x40 header male right angle']:
			auto = [f for f in seeded().findings(name) if f.kind == AUTO_SAFE]
			self.assertEqual(auto, [], name)

	def test_an_already_clean_name_has_no_findings(self):
		for name in ['Capacitor electrolytic 16V 100uF', 'Relay DPDT 120VAC RU2S',
						'Cable gland 1/2" silver']:
			self.assertEqual(seeded().findings(name), [], name)

class SelectiveApplyTest(unittest.TestCase):
	'''Accepting one suggestion must not drag another one in, which is what the
	cleanup window's per-row toggles depend on.'''

	def test_each_subset_applies_alone(self):
		rs = seeded()
		auto = rs.auto_rule_names()
		name = 'Recept 12pin plug'
		self.assertEqual(rs.apply(name, auto + ['receptacle']),
						'Recep 12pin plug')
		self.assertEqual(rs.apply(name, auto + ['pin_count']),
						'Recept 12pos plug')
		self.assertEqual(rs.apply(name, auto + ['receptacle', 'pin_count']),
						'Recep 12pos plug')

	def test_auto_only_leaves_review_alone(self):
		self.assertEqual(seeded().normalize('Recept 12pin plug  '),
						'Recept 12pin plug')

class RulesetConfigurationTest(unittest.TestCase):
	def test_empty_ruleset_is_the_identity(self):
		self.assertEqual(Ruleset([]).normalize('  Relay 12v  '), '  Relay 12v  ')
		self.assertEqual(Ruleset([]).findings('  Relay 12v  '), [])

	def test_dropping_a_rule_drops_its_findings(self):
		without = Ruleset([r for r in SEED if r.name != 'microfarads'])
		self.assertEqual(without.normalize('Capacitor 50V 100uf'),
						'Capacitor 50V 100uf')
		self.assertEqual(seeded().normalize('Capacitor 50V 100uf'),
						'Capacitor 50V 100uF')

	def test_a_database_can_add_its_own_rule(self):
		'''the point of keeping the rules in a table: K was left unseeded'''
		extra = SEED + [rule(210, 'kilo', 'unit', AUTO_SAFE, 'Unit case',
								'k', 'K')]
		self.assertEqual(Ruleset(extra).normalize('Resistor 10k 1%'),
						'Resistor 10K 1%')

	def test_unknown_whitespace_rule_name_does_nothing(self):
		odd = [rule(10, 'squash', 'whitespace', AUTO_SAFE, 'Whitespace', '')]
		self.assertEqual(Ruleset(odd).normalize(' a  b '), ' a  b ')

	def test_variants_are_escaped_not_treated_as_regex(self):
		'''a variant is a literal spelling, never a pattern'''
		odd = [rule(10, 'dotty', 'vocabulary', REVIEW, 'Vocabulary', 'a.c', 'AC')]
		rs = Ruleset(odd)
		self.assertEqual(rs.apply('one a.c two', ['dotty']), 'one AC two')
		self.assertEqual(rs.apply('one abc two', ['dotty']), 'one abc two')

	def test_canonical_is_literal_text_not_a_replacement_template(self):
		'''both columns are typed by a user, so a backslash in the canonical
		column has to come out as a backslash rather than be read as an escape
		or a group reference'''
		odd = [rule(10, 'odd', 'vocabulary', REVIEW, 'Vocabulary', 'foo',
					r'a\1b\nc')]
		self.assertEqual(Ruleset(odd).apply('x foo y', ['odd']),
						'x a\\1b\\nc y')

	def test_canonical_is_literal_for_a_pin_count_too(self):
		odd = [rule(10, 'pins', 'pin_count', REVIEW, 'Pin count', 'P', r'p\0s')]
		self.assertEqual(Ruleset(odd).apply('Header 4P', ['pins']),
						'Header 4p\\0s')

if __name__ == '__main__':
	unittest.main()
