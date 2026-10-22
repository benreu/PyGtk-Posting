# run_all.py
#
# Every test folder beside this file, in one run.
#
# It exists because unittest's own discovery cannot do it. 'discover -s tests'
# recurses only into directories it can import as packages, and these folders
# deliberately are not packages: an __init__.py in email/ would make it the
# package named 'email', which is the standard library's. Nothing would say so
# either - a directory with no __init__.py is only a namespace portion, and a
# real package beats one, so the standard library keeps winning right up until
# somebody adds the file, at which point every 'from email.message import ...'
# in the application finds this folder instead.
#
# So each folder is discovered as its own top level, the way it is when run
# from inside it, and the suites are added together. harness.py is one module
# across all of them: it sits a directory up, and both folders reach it
# through the same path.
#
# Usage: POSTING_TEST_DB_PASSWORD=... python3 tests/run_all.py [-v]

import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDERS = ('inventory', 'email')


def suite ():
	loader = unittest.defaultTestLoader
	everything = unittest.TestSuite()
	for folder in FOLDERS:
		path = os.path.join(HERE, folder)
		everything.addTests(loader.discover(path, top_level_dir = path))
	if loader.errors:
		# a module that would not import is reported as a test that fails, so
		# it is easy to miss in a run of a thousand; say it here as well
		for error in loader.errors:
			print(error, file = sys.stderr)
	return everything


if __name__ == '__main__':
	verbosity = 2 if '-v' in sys.argv else 1
	result = unittest.TextTestRunner(verbosity = verbosity).run(suite())
	sys.exit(0 if result.wasSuccessful() else 1)
