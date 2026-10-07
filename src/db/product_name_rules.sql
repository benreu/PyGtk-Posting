/* Product name convention rules.

   Deliberately NOT part of update_db_minor.sql and NOT tied to VERSION_MINOR.
   The product name cleanup window runs this file itself, once, when the user
   opts in, so the feature can land while other schema work is in flight
   without taking a version number or forcing the upgrade on anybody.

   Every statement is idempotent, so running it again is a no operation and
   a rule somebody deactivated or soft deleted is never resurrected.

   variants is a comma separated list of spellings to replace. A row says only
   what to unify, never how to match it: product_name_rules.Ruleset builds the
   pattern from rule_type and escapes each variant. That is the whole point of
   the column layout. A pattern written by hand as

       regexp_replace(name, '([0-9])v($|[ ,])', '\1V')

   drops the delimiter it captured and turns "Capacitor electrolytic 6.3v
   100uf" into "...6.3V100uf", eating the space. No row here can express that.

   sort_order is load bearing: a combined token such as vac/dc has to be
   canonicalized ahead of the single vac rule, or "24vac/dc" comes out half
   fixed as "24VAC/dc". */

CREATE TABLE IF NOT EXISTS public.product_name_rules (
	id serial PRIMARY KEY,
	name varchar NOT NULL UNIQUE,
	rule_type varchar NOT NULL DEFAULT 'unit',
	kind varchar NOT NULL DEFAULT 'auto',
	label varchar NOT NULL DEFAULT '',
	variants varchar NOT NULL DEFAULT '',
	canonical varchar NOT NULL DEFAULT '',
	sort_order integer NOT NULL DEFAULT 0,
	active boolean NOT NULL DEFAULT True,
	deleted boolean NOT NULL DEFAULT False,
	CONSTRAINT product_name_rules_rule_type_ck
		CHECK (rule_type IN ('whitespace', 'unit', 'vocabulary',
								'pin_count', 'pin_count_exclude', 'brand')),
	CONSTRAINT product_name_rules_kind_ck
		CHECK (kind IN ('auto', 'review', 'report', 'guard'))
);

/* The seeded convention is the one the catalog already mostly follows, taken
   from the dominant spelling of each unit, except uF, where the SI casing was
   chosen over the catalog's own majority spelling uf.

   K is left out on purpose: 100K against 1k is split roughly evenly and no
   canonical form was picked, so a database that wants one adds the row. */
INSERT INTO public.product_name_rules
		(sort_order, name, rule_type, kind, label, variants, canonical) VALUES
	(10, 'trim', 'whitespace', 'auto', 'Whitespace', '', ''),
	(20, 'double_space', 'whitespace', 'auto', 'Whitespace', '', ''),
	(100, 'volts', 'unit', 'auto', 'Unit case', 'v', 'V'),
	(110, 'volts_ac_dc', 'unit', 'auto', 'Unit case',
		'vac/dc,VAC/dc,vac/DC', 'VAC/DC'),
	(120, 'volts_ac', 'unit', 'auto', 'Unit case', 'vac,Vac,vAC', 'VAC'),
	(130, 'volts_dc', 'unit', 'auto', 'Unit case', 'vdc,Vdc,vDC', 'VDC'),
	(140, 'amps', 'unit', 'auto', 'Unit case', 'a', 'A'),
	(150, 'milliamps', 'unit', 'auto', 'Unit case', 'ma,MA,Ma', 'mA'),
	(160, 'microfarads', 'unit', 'auto', 'Unit case', 'uf,UF', 'uF'),
	(170, 'watts', 'unit', 'auto', 'Unit case', 'w', 'W'),
	(180, 'ohms', 'unit', 'auto', 'Unit case', 'ohm,Ohm', 'OHM'),
	(190, 'wire_gauge', 'unit', 'auto', 'Unit case', 'awg', 'AWG'),
	(200, 'gauge', 'unit', 'auto', 'Unit case', 'ga', 'GA'),
	(300, 'receptacle', 'vocabulary', 'review', 'Vocabulary',
		'recep,recept,receptacle,rcpt', 'Recep'),
	(400, 'pin_count', 'pin_count', 'review', 'Pin count',
		'P,pin,pins,pos,position,positions', 'pos'),
	(410, 'pin_count_exclude', 'pin_count_exclude', 'guard', 'Pin count',
		'relay,contactor,breaker,switch,disconnect', ''),
	(500, 'brands', 'brand', 'report', 'Word order',
		'Visotron,Dellatron,Deutsch,Stimopuls,Westfalia,Wedgelock,Boumatic', '')
ON CONFLICT (name) DO NOTHING;
