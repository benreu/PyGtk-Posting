# test_product_name_rules.py
#
# The rule engine is pure, so these run with no database and no display. They
# pin the engine's semantics; test_product_name_cleanup.py pins the seed that
# db/product_name_rules.sql actually installs.

import os, re, sys, unittest

SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
sys.path.insert(0, os.path.abspath(SRC))

from product_name_rules import (Ruleset, Rule, split_variants, token_role,
								token_roles, TOKEN_ROLE_NAMES, QUALIFIER,
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
	rule(161, 'picofarads', 'unit', AUTO_SAFE, 'Unit case', 'pf,PF', 'pF'),
	rule(162, 'microhenries', 'unit', AUTO_SAFE, 'Unit case', 'uh,UH', 'uH'),
	rule(163, 'millihenries', 'unit', AUTO_SAFE, 'Unit case', 'mh,MH', 'mH'),
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
	rule(600, 'order_cfg_part', 'token_order', REVIEW, 'Token order', 'CFG,PART'),
	rule(610, 'order_amps_count', 'token_order', REVIEW, 'Token order', 'A,COUNT'),
	rule(620, 'order_gauge_size', 'token_order', REVIEW, 'Token order',
			'GAUGE,SIZE'),
	rule(630, 'order_cfg_amps', 'token_order', REVIEW, 'Token order', 'CFG,A'),
	rule(640, 'order_cfg_volts', 'token_order', REVIEW, 'Token order', 'CFG,V'),
	rule(650, 'order_volts_amps', 'token_order', REVIEW, 'Token order', 'V,A'),
	rule(660, 'qualifiers', 'qualifier', REVIEW, 'Token order',
			'THT,TH,SMD,SMT'),
	]

#not seeded: at 66% the catalog does not agree with itself about a voltage
#against a part number, so this is the row a database adds by hand
VOLTS_PART = rule(660, 'order_volts_part', 'token_order', REVIEW,
					'Token order', 'V,PART')

ORDER_RULES = [r.name for r in SEED
				if r.rule_type in ('token_order', 'qualifier')]

#real names, spanning the naming systems the catalog actually contains: relays
#and switches, passives, connectors, drives, and mechanical hardware
CATALOG_SAMPLE = [
	'Relay SPDT RH1B 120VAC',
	'Relay SPDT RH1B 24VDC',
	'Relay SPDT socket RH1B',
	'Relay DPDT 120VAC RH2B',
	'Relay 110VAC PCB DPDT',
	'Relay 12V 30A automotive SPST',
	'Relay DPST 30A 12V T92S7D12-12',
	'Relay latching mechanical DPST 5A 5V 1NC-1NO',
	'Relay SSR ZC 1.2A 600VAC',
	'Surge ARC 24VDC 10A 3PDT relay',
	'Switch rocker SPST 16A 125V',
	'Switch toggle DPDT 10A 125V on-mom angle tabs',
	'Fuse PCB mount 3.15A 125VAC',
	'PTC fuse .75A THT 72V',
	'Rectifier Bridge 35A 200V',
	'Diode 1N5404 400V 3A',
	'Capacitor electrolytic 6.3V 100uF',
	'Capacitor FTX2 275V 0.047uF',
	'Resistor 1/4W 0.1% 1K',
	'Socket Superseal 1.0mm 20AWG',
	'Socket TE/AMP 1.5mm 17-20AWG',
	'Socket DIP 14pos',
	'Drive Yaskawa J1000 240V 6.0A 3PH',
	'Power supply 12V .42A Mean Well NFM-05-12',
	'Bolt 18-8SS 1/4 - 20 x 12"',
	'Tubing heat shrink 3/8" black',
	'Magnet neodymium 1/2" x 1/8"',
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
				('Capacitor ceramic 18pf 100V', 'Capacitor ceramic 18pF 100V'),
				('Inductor 22uh 5A', 'Inductor 22uH 5A'),
				('Inductor Bourns 470uh', 'Inductor Bourns 470uH'),
				('Choke 25MH 100mA', 'Choke 25mH 100mA'),
				('Choke 36mh 4.5OHM 300mA', 'Choke 36mH 4.5OHM 300mA'),
				]:
			self.assertEqual(seeded().normalize(before), after)

	def test_a_henry_rule_does_not_reach_into_a_longer_unit(self):
		'''The lookahead earns its keep here: MH opens MHZ, and a crystal is
		not a 4 millihenry anything.'''
		for name in ('Crystal 4MHZ HC49', 'Crystal oscillator 16MHz',
						'Inductor 22uHy'):
			self.assertEqual(seeded().normalize(name), name, name)

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

class UnitGuardTest(unittest.TestCase):
	'''A unit is only a unit when the number it belongs to starts the section,
	the same guard the pin count uses and for the same reason. Without it the
	rule needs nothing but a digit somewhere to the left, so a part number
	ending in digits and a unit spelling gets rewritten.'''

	def test_a_unit_rule_does_not_reach_the_tail_of_a_part_number(self):
		for name in ('Relay T92UH 12V', 'Socket DT04-4ga', 'Choke 2chMH 100mA',
						'Driver LM2577ma 3A', 'Capacitor A23Cuf 50V'):
			self.assertEqual(seeded().normalize(name), name, name)

	def test_the_catalogs_own_part_numbers_stay_whole(self):
		for name in ('Potentiometer Bourns 3386P 10K',
						'Recep Deutsch DT04-2P',
						'Relay DPST 30A 12V T92S7D12-12',
						'Mitsubishi MG200J6ES61 IGBT Transistor 200A 600V',
						'Battery 12V A23C'):
			self.assertEqual(seeded().normalize(name), name, name)

	def test_a_number_may_open_with_a_dot(self):
		self.assertEqual(seeded().normalize('PTC fuse .75a 72v'),
							'PTC fuse .75A 72V')

	def test_a_number_may_hold_a_range_or_a_fraction(self):
		for before, after in [
				('Resistor 1/4w 0.1% 1K', 'Resistor 1/4W 0.1% 1K'),
				('Driver LED 100-200vdc out', 'Driver LED 100-200VDC out'),
				('Fuse kit ATOF 3-30a', 'Fuse kit ATOF 3-30A'),
				('Relay SPDT PCB 12vdc 30~20a',
					'Relay SPDT PCB 12VDC 30~20A'),
				('Socket TE/AMP 1.5mm 17-20awg',
					'Socket TE/AMP 1.5mm 17-20AWG')]:
			self.assertEqual(seeded().normalize(before), after, before)

	def test_the_number_is_put_back_untouched(self):
		'''It is captured rather than looked behind because it is variable
		width, so the rule has to write it back, and a lost digit would be a
		silent corruption rather than a visible one. A unit rule only ever
		changes letters, so everything that is not one has to survive.'''
		for name in ('Capacitor electrolytic 22000uf 75V',
						'Capacitor start 400-480uf 125V',
						'Relay SPDT PCB 12vdc 30~20a',
						'Resistor 0.02ohm 1% 2W'):
			self.assertEqual(re.sub(r'[A-Za-z]', '', seeded().normalize(name)),
								re.sub(r'[A-Za-z]', '', name),
								'%r moved something that is not a letter' % name)

	def test_a_comma_still_closes_a_section(self):
		self.assertEqual(seeded().normalize('Relay 12v, 5a'), 'Relay 12V, 5A')

	def test_vocabulary_is_unaffected_by_the_unit_guard(self):
		'''The two rule types compile separately; a vocabulary fix is a word,
		not a number and a unit.'''
		ruleset = seeded()
		self.assertEqual(ruleset.apply('Recept 12pin plug',
							ruleset.auto_rule_names() + ['receptacle']),
						'Recep 12pin plug')

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

class TokenRoleTest(unittest.TestCase):
	'''Roles are shapes, which is what lets an ordering rule be stated for the
	whole catalog without a list of part numbers anywhere.'''

	def test_every_role_shape(self):
		for token, expected in [
					('SPDT', 'CFG'), ('DPDT', 'CFG'),
					('120VAC', 'V'), ('24VDC', 'V'), ('5V', 'V'),
					('10A', 'A'), ('500mA', 'A'),
					('35W', 'W'), ('20VA', 'W'),
					('100uF', 'VAL'), ('4.7K', 'VAL'), ('240OHM', 'VAL'),
					('18AWG', 'GAUGE'), ('14-16AWG', 'GAUGE'),
					('12pos', 'COUNT'), ('8pin', 'COUNT'),
					('3/8"', 'SIZE'), ('5x20mm', 'SIZE'), ('1.0mm', 'SIZE'),
					('RH1B', 'PART'), ('G2RL', 'PART'),
					('T92S7D12-12', 'PART'), ('18-8SS', 'PART')]:
			self.assertEqual(token_role(token), expected, token)

	def test_the_config_shape_takes_a_digit(self):
		'''The regression that found this: a shape of '\\d?[SPD]P[DS]T' needs
		four characters after the digit and only three remain, so 4PDT fell
		through to PART and got moved as though it were an identifier.'''
		for token in ('4PDT', '3PDT', '4PST-NO', '4PST-NC'):
			self.assertEqual(token_role(token), 'CFG', token)

	def test_a_part_number_does_not_swallow_a_spec(self):
		'''PART is last on purpose: it is only "digits and letters, and none of
		the above", so anything it reached would be reordered as an
		identifier.'''
		for token in ('22uh', '35W', '0.1uF', '12mm', '5x20mm', '4.7K',
						'18AWG', '12pos', '120VAC', 'SPDT'):
			self.assertNotEqual(token_role(token), 'PART', token)

	def test_a_bare_m_is_not_a_value(self):
		'''It was, and it made the 3M brand a component value. In this catalog
		a bare M is the brand, the way count of a Weatherpack plug and metres
		of cable far more often than it is megohms, so the shape gives it up:
		a crystal's 10.00M is read as a part number, which moves nothing,
		while 3M stays where it belongs.'''
		for token in ('3M', '4M', '1.83m', '2m', '1000m', '10.00M'):
			self.assertNotEqual(token_role(token), 'VAL', token)

	def test_a_bare_k_is_still_a_value(self):
		'''73 uses and almost all of them resistance. The worst case is a
		colour temperature, 4000K, read as one, and it orders the same way.'''
		for token in ('1K', '4.7K', '100k', '4000K'):
			self.assertEqual(token_role(token), 'VAL', token)

	def test_a_section_with_no_digits_or_no_letters_has_no_role(self):
		for token in ('socket', 'relay', 'PCB', 'automotive', 'mount',
						'1/4', '20', 'x', '-'):
			self.assertEqual(token_role(token), '', token)

	def test_case_is_ignored(self):
		'''K was left out of the unit rules deliberately and uH has no rule at
		all, so a role that insisted on canonical casing would read those as
		part numbers and shuffle them about.'''
		for token, expected in [('spdt', 'CFG'), ('120vac', 'V'),
								('4.7k', 'VAL'), ('22uh', 'VAL'),
								('18awg', 'GAUGE'), ('12POS', 'COUNT')]:
			self.assertEqual(token_role(token), expected, token)

	def test_the_declared_role_names_are_the_ones_classified(self):
		self.assertEqual(sorted(TOKEN_ROLE_NAMES),
			sorted(['CFG', 'V', 'A', 'W', 'VAL', 'GAUGE', 'COUNT', 'SIZE',
					'PART']))

class QualifierTest(unittest.TestCase):
	'''A trailing note goes after every recognised section, which is what
	declaring it says, so a qualifier row is a word list and not a pair.'''

	def _ordered (self, name):
		ruleset = seeded()
		return ruleset.apply(name, ruleset.auto_rule_names() + ORDER_RULES)

	def test_a_declared_note_goes_last(self):
		for before, after in [
				('PTC fuse .75A THT 72V', 'PTC fuse 72V .75A THT'),
				('Capacitor ceramic 50V THT 10uF',
					'Capacitor ceramic 50V 10uF THT'),
				('Capacitor film 250V 0.015uF THT F339',
					'Capacitor film 250V 0.015uF F339 THT'),
				('ESP32 SMT 4MB', 'ESP32 4MB SMT')]:
			self.assertEqual(self._ordered(before), after)

	def test_the_result_matches_the_rest_of_the_family(self):
		'''The whole point of the screenshot: three PTC fuses read voltage
		then current, and the fourth had a note wedged into the middle. The
		sections differ, so what has to match is the order of their roles.'''
		def roles (name):
			ordered = self._ordered(name).split()
			return [role for role in token_roles(ordered, set(['tht']))
					if role]
		self.assertEqual(roles('PTC fuse 1.1A 72V'), ['V', 'A'])
		self.assertEqual(roles('PTC fuse .75A THT 72V'),
							['V', 'A', QUALIFIER])

	def test_a_note_in_front_of_the_first_spec_is_the_product_name(self):
		'''Declaring a word never drags apart the name of the thing. There is
		nothing recognised in front of these for the note to trail.'''
		for name in ('THT fuse 72V', 'Resistor SMD 1206', 'SMD LED red'):
			self.assertEqual(self._ordered(name), name)

	def test_an_undeclared_word_is_never_moved(self):
		'''Measured on the catalog: taking every unrecognised section after
		the first spec as a note reads this one as carrying two, and mistakes
		the class of every name that leads with a part number.'''
		for name in ('Inverter 24VDC in 12VDC out 1.67A',
						'Mitsubishi MG200J6ES61 IGBT Transistor 200A 600V',
						'LM2585 switcher 3A',
						'Relay 12V 30A automotive SPST'):
			self.assertNotIn('THT', self._ordered(name))
			self.assertEqual(
				seeded().apply(name, ['qualifiers']), name, name)

	def test_a_declared_word_is_matched_whatever_its_case(self):
		self.assertEqual(self._ordered('PTC fuse .75A tht 72V'),
							'PTC fuse 72V .75A tht')

	def test_the_roles_of_a_name(self):
		tokens = 'PTC fuse .75A THT 72V'.split()
		self.assertEqual(token_roles(tokens, set(['tht'])),
							['', '', 'A', QUALIFIER, 'V'])
		self.assertEqual(token_roles(tokens),
							['', '', 'A', '', 'V'],
							'nothing is a qualifier until it is declared')

	def test_a_phrase_moves_as_one_section(self):
		'''"mount" is never a note on its own in this catalog, it is the tail
		of one, so a qualifier row names the phrase and it travels whole.'''
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'PCB mount,panel mount')])
		rules = ruleset.auto_rule_names() + ORDER_RULES
		for before, after in [
				('Fuse PCB mount 2A 250VAC', 'Fuse 250VAC 2A PCB mount'),
				('Fuse PCB mount 8A', 'Fuse 8A PCB mount'),
				('Potentiometer panel mount 1/4W 1K',
					'Potentiometer 1/4W 1K panel mount'),
				('Relay PCB mount 12V 30A SPST',
					'Relay SPST 12V 30A PCB mount')]:
			self.assertEqual(ruleset.apply(before, rules), after)

	def test_declaring_the_word_alone_would_split_the_phrase(self):
		'''Why a phrase is needed at all: "mount" on its own is carried off
		and "panel" is left where it stood.'''
		name = 'Switch 12V panel mount 20A'
		words = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'mount')])
		self.assertEqual(words.apply(name, ['qualifiers']),
							'Switch 12V panel 20A mount')
		phrase = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'panel mount')])
		self.assertEqual(phrase.apply(name, ['qualifiers']),
							'Switch 12V 20A panel mount')

	def test_a_phrase_is_a_note_even_with_no_spec_before_it(self):
		'''Naming two words together says which "mount" is meant, which a
		lone word cannot, so a phrase does not have to wait for a recognised
		section the way a declared word does. That is what reaches the fuses,
		where the note sits straight after the class.'''
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'PCB mount')])
		self.assertEqual(ruleset.apply('Fuse PCB mount 8A', ['qualifiers']),
							'Fuse 8A PCB mount')

	def test_a_phrase_opening_the_name_is_the_product_name(self):
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'PCB mount')])
		self.assertEqual(ruleset.apply('PCB mount fuse 8A', ['qualifiers']),
							'PCB mount fuse 8A')

	def test_the_longest_phrase_wins(self):
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'mount,panel mount')])
		self.assertEqual(
			ruleset.apply('Switch 12V panel mount', ['qualifiers']),
			'Switch 12V panel mount')
		self.assertEqual(
			ruleset.apply('Switch panel mount 12V', ['qualifiers']),
			'Switch 12V panel mount')

	def test_a_phrase_overrides_the_shape_of_its_parts(self):
		'''Declaring it says this is one note, so the size inside it stops
		being a section any rule can reach on its own.'''
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', '1/2" mount')])
		self.assertEqual(
			ruleset.apply('Indicator neon 1/2" mount 220V amber',
							['qualifiers']),
			'Indicator neon 220V 1/2" mount amber')

	def test_a_pair_rule_cannot_split_a_phrase(self):
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', '1/2" mount')])
		self.assertEqual(
			ruleset.apply('Indicator 1/2" mount 18AWG', ['order_gauge_size']),
			'Indicator 1/2" mount 18AWG')

	def test_the_spacing_inside_a_phrase_travels_with_it(self):
		ruleset = Ruleset(SEED[:-1] + [rule(660, 'qualifiers', 'qualifier',
					REVIEW, 'Token order', 'PCB mount')])
		self.assertEqual(
			ruleset.apply('Fuse  PCB  mount   2A', ['qualifiers']),
			'Fuse  2A   PCB  mount')

	def test_a_qualifier_is_not_a_pair_role(self):
		'''QUAL cannot be named in a token_order row: it is last against
		everything or it is not a qualifier, so there is no pair to state.'''
		self.assertNotIn(QUALIFIER, TOKEN_ROLE_NAMES)

	def test_a_name_of_nothing_but_notes_is_left_alone(self):
		ruleset = Ruleset(SEED)
		self.assertEqual(ruleset.apply('THT SMD', ['qualifiers']), 'THT SMD')

class TokenOrderTest(unittest.TestCase):
	'''One row is one precedence pair, so a rule has an opinion only about a
	name carrying both of its roles. That is what keeps it applicable to the
	whole catalog: there is no total order over the roles anywhere, because
	measuring found the catalog genuinely inconsistent about a part number
	against a spec, and any single declared order mangles one naming system to
	tidy another.'''

	def _ordered (self, name, extra = None):
		rules = SEED if extra is None else SEED + [extra]
		ruleset = Ruleset(rules)
		order_rules = [r.name for r in rules if r.rule_type == 'token_order']
		return ruleset.apply(name, ruleset.auto_rule_names() + order_rules)

	def test_the_measured_pairs(self):
		for before, after in [
				('Fuse PCB mount 3.15A 125VAC', 'Fuse PCB mount 125VAC 3.15A'),
				('Relay 240VAC 3PDT', 'Relay 3PDT 240VAC'),
				('Breaker 20A pushbutton 250V', 'Breaker 250V pushbutton 20A'),
				('Contactor 24VDC 3PDT 1NOaux',
					'Contactor 3PDT 24VDC 1NOaux'),
				('Relay 110VAC PCB DPDT', 'Relay DPDT PCB 110VAC'),
				('Socket Superseal 1.0mm 20AWG',
					'Socket Superseal 20AWG 1.0mm')]:
			self.assertEqual(self._ordered(before), after)

	def test_a_rule_fires_only_where_both_roles_appear(self):
		'''The mechanical hardware is left alone not by excluding it but
		because those names carry no such pair. Enforcing a total order turns
		this one into 'Bolt 12" 1/4 - 20 x 18-8SS'.'''
		for name in ('Bolt 18-8SS 1/4 - 20 x 12"',
						'Tubing heat shrink 3/8" black',
						'Nut nylock 1/4 - 20 18-8SS',
						'Magnet neodymium 1/2" x 1/8"'):
			self.assertEqual(self._ordered(name), name)

	def test_an_already_ordered_name_is_untouched(self):
		for name in ('Relay DPDT socket RH2B', 'Relay SPDT RH1B 120VAC',
						'Relay DPDT 120VAC RH2B', 'Switch rocker SPST 125V 16A'):
			self.assertEqual(self._ordered(name), name)

	def test_a_section_with_no_role_stays_where_it_is(self):
		'''Nothing is compacted, so 'socket' and 'PCB mount' keep their
		positions. Compacting the governed sections instead would tidy one
		name and move 'socket' in a dozen that are already right.'''
		self.assertEqual(self._ordered('Relay 110VAC PCB DPDT').split()[2],
							'PCB')
		self.assertEqual(
			self._ordered('Fuse PCB mount 2A 250VAC'),
			'Fuse PCB mount 250VAC 2A')

	def test_the_straddled_swap_reads_oddly_and_is_accepted(self):
		'''The known cost of not compacting, 1 of the 33 names the seeded
		pairs reach. Review only is what makes leaving it in safe: it is
		offered unticked and can simply be declined.'''
		self.assertEqual(self._ordered('Relay 12V 30A automotive SPST'),
							'Relay SPST 12V automotive 30A')

	def test_two_sections_of_one_role_keep_their_relative_order(self):
		self.assertEqual(self._ordered('Fuse 2A 250VAC 125VAC'),
							'Fuse 250VAC 125VAC 2A')

	def test_the_result_is_always_a_permutation(self):
		'''No section added and none lost, which is what makes every
		suggestion reversible.'''
		for name in CATALOG_SAMPLE:
			after = self._ordered(name, VOLTS_PART)
			self.assertEqual(sorted(seeded().normalize(name).split()),
								sorted(after.split()), name)

	def test_applying_twice_changes_nothing(self):
		for name in CATALOG_SAMPLE:
			once = self._ordered(name, VOLTS_PART)
			self.assertEqual(self._ordered(once, VOLTS_PART), once, name)

	def test_whitespace_is_carried_through_untouched(self):
		'''Order is all this rule is about; a doubled space is the whitespace
		rules' business and reports as its own finding.'''
		ruleset = seeded()
		self.assertEqual(
			ruleset.apply('Relay  240VAC   3PDT', ['order_cfg_volts']),
			'Relay  3PDT   240VAC')

	def test_token_order_is_review_not_auto(self):
		self.assertEqual([n for n in seeded().auto_rule_names()
							if n in ORDER_RULES], [])
		self.assertEqual(seeded().normalize('Relay 240VAC 3PDT'),
							'Relay 240VAC 3PDT')

	def test_a_finding_names_the_one_rule_that_made_it(self):
		found = [f for f in seeded().findings('Relay 240VAC 3PDT')
					if f.rule in ORDER_RULES]
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].kind, REVIEW)
		self.assertEqual(found[0].rule, 'order_cfg_volts')
		self.assertEqual(found[0].label, 'Token order')
		self.assertEqual(found[0].after, 'Relay 3PDT 240VAC')

	def test_the_pairs_that_fire_are_offered_as_one_suggestion(self):
		'''Separately the two pairs on this name read as contradictions, so
		offering the halves would ask for a decision between two wrong
		answers. One row, carrying the finished order.'''
		found = [f for f in seeded().findings('Relay PCB mount 12V 30A SPST')
					if f.label == 'Token order']
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].rule, 'order_cfg_amps,order_cfg_volts')
		self.assertEqual(found[0].after, 'Relay PCB mount SPST 12V 30A')

	def test_a_grouped_suggestion_is_what_accepting_it_produces(self):
		'''What the fix list shows is apply(name, auto + [finding.rule]), so
		a comma separated rule has to expand to exactly the composition the
		finding measured, or the window offers one name and writes another.'''
		ruleset = seeded()
		auto = ruleset.auto_rule_names()
		for name in CATALOG_SAMPLE + ['Relay PCB mount 12V 30A SPST',
										'Surge ARC 24VDC 10A 3PDT relay']:
			for finding in ruleset.findings(name):
				if finding.label != 'Token order':
					continue
				self.assertEqual(ruleset.apply(name, auto + [finding.rule]),
									finding.after, name)

	def test_a_grouped_suggestion_names_only_the_rules_that_fired(self):
		'''A pair that would change nothing is left out rather than listed,
		which is the same thing as applying it and makes the row say what it
		did.'''
		found = [f for f in seeded().findings('Relay 240VAC 3PDT')
					if f.label == 'Token order']
		self.assertEqual(found[0].rule, 'order_cfg_volts')

	def test_the_ungrouped_review_rules_still_stand_alone(self):
		'''Grouping is for suggestions that compose. A vocabulary fix and a
		pin count are independent, so they stay one row each and can be taken
		separately.'''
		rules = [f.rule for f in seeded().findings('Recept 12pin plug')]
		self.assertEqual(sorted(rules), ['pin_count', 'receptacle'])

	def test_the_unseeded_pair_reaches_the_prompting_example(self):
		'''A voltage against a part number is the pair that orders the
		screenshot the way the catalog's majority does, and the pair the
		catalog agrees with itself about least. It is added by hand.'''
		self.assertEqual(self._ordered('Relay SPDT RH1B 120VAC', VOLTS_PART),
							'Relay SPDT 120VAC RH1B')
		self.assertEqual(self._ordered('Relay SPDT socket RH1B', VOLTS_PART),
							'Relay SPDT socket RH1B')

	def test_a_variants_that_is_not_two_known_roles_is_inert(self):
		'''Refused, not raised: a typo in the rules tab costs that one rule
		and not the window. The table has a check constraint that turns the
		same mistake into a message, but a row can also arrive from SQL.'''
		for variants in ('CFG', 'CFG,NOPE', 'CFG,V,A', '', 'cfg,part'):
			bad = rule(700, 'bad_order', 'token_order', REVIEW,
						'Token order', variants)
			ruleset = Ruleset(SEED + [bad])
			self.assertEqual(
				ruleset.apply('Relay 240VAC 3PDT', ['bad_order']),
				'Relay 240VAC 3PDT', variants)
			self.assertEqual([f for f in ruleset.findings('Relay 240VAC 3PDT')
								if f.rule == 'bad_order'], [], variants)

	def test_a_pair_naming_one_role_twice_is_inert(self):
		same = rule(700, 'same_order', 'token_order', REVIEW,
					'Token order', 'V,V')
		self.assertEqual(
			Ruleset(SEED + [same]).apply('Relay 240VAC 120VAC', ['same_order']),
			'Relay 240VAC 120VAC')
