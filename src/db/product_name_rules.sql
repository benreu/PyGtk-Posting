/* Product name convention rules.

   Deliberately NOT part of update_db_minor.sql and NOT tied to VERSION_MINOR.
   The product name cleanup window runs this file itself, when the user opts
   in and again whenever the window opens, so the feature can land while other
   schema work is in flight without taking a version number or forcing the
   upgrade on anybody.

   Every statement is idempotent, so running it again is a no operation and
   a rule somebody deactivated or soft deleted is never resurrected. Opening
   the window is also how a database that opted in earlier picks up rules that
   did not exist at the time, which is the only delivery this feature has.

   What that costs: CREATE TABLE IF NOT EXISTS does nothing at all once the
   table is there, so a change to the shape below never reaches a database
   that already has it. A later release that needs one states it as its own
   statement after the table, in the form

       ALTER TABLE public.product_name_rules
           DROP CONSTRAINT IF EXISTS product_name_rules_rule_type_ck;
       ALTER TABLE public.product_name_rules
           ADD CONSTRAINT product_name_rules_rule_type_ck CHECK (...);

   which is idempotent in both directions and brings an old table and a new
   one to the same place. The constraints are named here rather than left to
   PostgreSQL so that such a statement has something to aim at. There is
   nothing in that section today: every database holding this table was
   brought up to the shape below before it was released anywhere else.

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
		CHECK (rule_type IN ('whitespace', 'unit', 'vocabulary', 'pin_count',
								'pin_count_exclude', 'brand', 'token_order',
								'qualifier')),
	CONSTRAINT product_name_rules_kind_ck
		CHECK (kind IN ('auto', 'review', 'report', 'guard')),
	/* A token_order row is one precedence pair: exactly two role names, the
	   one that comes first and the one that comes second. The roles are
	   shapes, so they are classified in product_name_rules.TOKEN_ROLES rather
	   than here, and this list mirrors the names it defines. It is spelled
	   out so that a role misspelled in the rules tab is refused on the spot,
	   with the message the tab already shows for a bad rule_type, instead of
	   quietly doing nothing. */
	CONSTRAINT product_name_rules_token_order_ck
		CHECK (rule_type <> 'token_order'
				OR variants ~ '^\s*(CFG|V|A|W|VAL|GAUGE|COUNT|SIZE|PART)'
								'\s*,\s*'
								'(CFG|V|A|W|VAL|GAUGE|COUNT|SIZE|PART)\s*$')
);

/* Later changes to the shape above go here, as ALTER statements; see the
   header. Nothing yet. */

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
	(161, 'picofarads', 'unit', 'auto', 'Unit case', 'pf,PF', 'pF'),
	(162, 'microhenries', 'unit', 'auto', 'Unit case', 'uh,UH', 'uH'),
	(163, 'millihenries', 'unit', 'auto', 'Unit case', 'mh,MH', 'mH'),
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
		'Visotron,Dellatron,Deutsch,Stimopuls,Westfalia,Wedgelock,Boumatic', ''),

/* The section order. Measuring every role against every other across the
   whole catalog found six pairs it agrees on, and these are them: a contact
   configuration leads its part number in 100% of the names carrying both, a
   current leads a position count in 100%, a wire gauge leads a length in 93%,
   and a configuration leads a current, a voltage or either in 88% to 90%.

   The pair that would reach "Relay SPDT RH1B 120VAC", a voltage against a
   part number, is not seeded: at 66% the catalog does not agree with itself
   about it, and enforcing it reaches 81 names rather than 33 and moves
   identifiers that read better where they are, as in "Diode 1N5404 400V 3A".
   Add it in the rules tab as V,PART, look at what it offers and untick what
   you disagree with; it is a review rule, so nothing moves unasked. */
	(600, 'order_cfg_part', 'token_order', 'review', 'Token order',
		'CFG,PART', ''),
	(610, 'order_amps_count', 'token_order', 'review', 'Token order',
		'A,COUNT', ''),
	(620, 'order_gauge_size', 'token_order', 'review', 'Token order',
		'GAUGE,SIZE', ''),
	(630, 'order_cfg_amps', 'token_order', 'review', 'Token order',
		'CFG,A', ''),
	(640, 'order_cfg_volts', 'token_order', 'review', 'Token order',
		'CFG,V', ''),
	(650, 'order_volts_amps', 'token_order', 'review', 'Token order',
		'V,A', ''),

/* A qualifier is a trailing note rather than part of what the product is, and
   it goes after every recognised section, which is what declaring it says. So
   there is no pair to state and the row is just the list of notes: a
   qualifier is last against everything or it is not a qualifier.

   A note may be a phrase. "mount" is never a note on its own, it is the tail
   of one, and declaring the word alone carries it off and leaves "panel"
   behind, so a variant such as "PCB mount" matches the two sections together
   and they move as one. Naming two words says which "mount" is meant, which
   is why a phrase is taken as a note wherever it sits but for the opening
   section, while a single declared word waits for a recognised section to
   come before it.

   The words are named rather than guessed at. Taking every unrecognised
   section after the first spec as a note was measured and does not work: it
   reads "Inverter 24VDC in 12VDC out 1.67A" as carrying two of them, and it
   mistakes the class of every name that leads with a part number, where "IGBT
   Transistor" and "hall effect shunt" sit after one. 31 names, much of it
   wrong, to put one THT in its place.

   Seeded with the mounting designations, which are notes in any catalog. A
   word in front of the first recognised section is the product's own name and
   stays there, so the SMD in "Resistor SMD 1206" does not move. */
	(660, 'qualifiers', 'qualifier', 'review', 'Token order',
		'THT,TH,SMD,SMT', '')
ON CONFLICT (name) DO NOTHING;
