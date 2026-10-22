# test_sql_files.py
#
# database_tools.execute_file runs create_db.sql, insert_basic.sql and both
# update files by splitting them on "--", so each "--" starts a new statement
# chunk. A "--" comment inside a statement cuts it in two, and neither half
# runs: a comment inside CREATE TABLE public.settings made Create database stop
# at that table, while every existing database upgraded without trouble,
# because only a fresh install runs create_db.sql. Comments inside a statement
# have to be /* */. Nothing here needs a database.

import os, re, unittest

SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
						'..', '..', 'src', 'db')
# every file execute_file is given
SPLIT_FILES = ('create_db.sql', 'insert_basic.sql', 'update_db_major.sql',
				'update_db_minor.sql')
DOLLAR_QUOTE = re.compile(r'\$[A-Za-z_]*\$')
BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)


def chunks (name):
	'''(line, sql) for each chunk execute_file runs: the text after one "--",
	less its first line, which is the chunk's description'''
	with open(os.path.join(SQL_DIR, name)) as f:
		contents = f.read()
	line = 1
	for index, chunk in enumerate(contents.split("--")):
		start = line
		line += chunk.count('\n')
		if index == 0:
			continue # what comes before the first "--"
		yield start, chunk.split('\n', 1)[1] if '\n' in chunk else ''


def cut (sql):
	'''whether this chunk stops in the middle of a statement: a dollar quote
	left open, or text that does not end the way a statement does'''
	if len(DOLLAR_QUOTE.findall(sql)) % 2:
		return True
	rest = BLOCK_COMMENT.sub('', sql).strip()
	return rest != '' and not (rest.endswith(';')
								or DOLLAR_QUOTE.search(rest[-30:]) and
									rest.endswith('$'))


class SplitTest (unittest.TestCase):

	def test_no_statement_is_cut_in_two (self):
		broken = ["%s:%d %r" % (name, line, sql.rstrip()[-60:])
					for name in SPLIT_FILES
					for line, sql in chunks(name) if cut(sql)]
		self.assertEqual(broken, [], "a -- comment inside a statement; "
										"use /* */ there")

	def test_a_comment_inside_a_statement_is_caught (self):
		# the shape of the one that broke Create database
		self.assertTrue(cut("CREATE TABLE t (\n    a integer,\n    "))
		self.assertFalse(cut("CREATE TABLE t (\n    a integer\n);\n"))
		self.assertFalse(cut("CREATE FUNCTION f() RETURNS integer\n"
								"AS $BODY$ SELECT 1 $BODY$"))
		self.assertTrue(cut("CREATE FUNCTION f() RETURNS integer\n"
								"AS $BODY$\n    BEGIN\n    "))


if __name__ == '__main__':
	unittest.main()
