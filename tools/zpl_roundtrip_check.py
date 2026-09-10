#!/usr/bin/env python3
'''Check that label templates survive a trip through the ZPL designer.

Posting stores its Zebra templates in the database and lets the LinuxZPL
designer edit them. That is only safe while opening a template and saving it
again preserves every command that changes the label. Upstream tests this too,
but its suite needs the Qt frontend, which Posting does not ship, so this
stands in as the guard for the one property Posting depends on.

Run it after moving the submodule pin, and against any template that gives
trouble:

    python3 tools/zpl_roundtrip_check.py [file.zpl ...]

With no arguments it checks the reference copies in tools/fixtures. Those are
Posting's, deliberately not the submodule's own tests/fixtures: the point is to
assert that our templates survive the engine, and reading them out of the thing
under test would invert the check.
'''

import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, 'src', 'linuxzpl')
if not os.path.isdir(os.path.join(ENGINE, 'zplcore')):
	raise SystemExit("The LinuxZPL engine is missing. From the Posting source "
					"directory run:\n\n    git submodule update --init src/linuxzpl")
sys.path.append(ENGINE)

from zplcore import parser as zpl_parser
from zplcore import workflow

# ^PW and ^LL are written from the document's label size whether or not the
# original carried them, and ^FX is the designer's own comment. Neither is a
# lost instruction, so neither counts as a difference here.
INJECTED = ('^XA', '^XZ', '^FS', '^PW', '^LL', '^FX')


def commands (zpl, extra = ()):
	return [(c, p.strip()) for c, p in zpl_parser.tokenise(zpl)
			if c not in INJECTED + tuple(extra)]


def check_file (path):
	"True when this template round-trips with nothing lost."
	source = open(path).read()
	written = zpl_parser.parse_zpl(source)[0].to_zpl()
	before, after = commands(source), commands(written)
	unsupported = workflow.unsupported_commands(source)
	name = os.path.basename(path)
	if before == after and not unsupported:
		print("PASS %s round-trips (%d commands)" % (name, len(before)))
		return True
	print("FAIL %s" % name)
	if unsupported:
		print("     the designer does not understand: %s" % ', '.join(unsupported))
	for a, b in zip(before, after):
		if a != b:
			print("     %s -> %s" % (a, b))
	if len(before) != len(after):
		print("     %d commands in, %d out" % (len(before), len(after)))
	return False


def main (argv):
	paths = argv[1:]
	if not paths:
		here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
		paths = [os.path.join(here, f) for f in sorted(os.listdir(here))
					if f.endswith('.zpl')]
	ok = [check_file(p) for p in paths]
	print("\n%s" % ("ALL CHECKS PASSED" if all(ok) else "FAILURES ABOVE"))
	return 0 if all(ok) else 1


if __name__ == '__main__':
	sys.exit(main(sys.argv))
