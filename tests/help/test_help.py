# test_help.py
#
# The user manual in help/C/pygtk-posting, read as files: no database, no
# display. Every page must be well formed Mallard that yelp can reach from the
# index, every link must land, every page a window opens must exist, and every
# window must open one with F1 (user_manual.bind_f1), so a window added later
# without help fails here.

import os, re, glob, unittest
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'src')
HELP = os.path.join(ROOT, 'help', 'C', 'pygtk-posting')
MAL = '{http://projectmallard.org/1.0/}'
# vendored libraries, not windows of the program
NOT_OURS = ('py3o', 'linuxzpl', 'pyjon', '__pycache__')

# windows that open no help, and why
EXEMPT = {
	'traceback_handler.py': 'the error window, which shows a traceback',
	'db/database_backup.py': 'a progress window that closes itself',
	'db/database_restore.py': 'a progress window that closes itself',
	'modules/simple_example.py': 'a sample for writing a module',
	'kit_products.py': 'nothing in the program opens it',
	'write_check.py': 'nothing in the program opens it: no menu item '
						'is connected to main_window.write_check',
}


def pages ():
	"page id: parsed root, for every .page"
	result = {}
	for path in glob.glob(os.path.join(HELP, '*.page')):
		name = os.path.basename(path)[:-len('.page')]
		result[name] = ET.parse(path).getroot()
	return result

def source_files ():
	for path in sorted(glob.glob(os.path.join(SRC, '**', '*.py'),
														recursive = True)):
		relative = os.path.relpath(path, SRC)
		if not any(part in relative for part in NOT_OURS):
			with open(path) as f:
				yield relative, f.read()

def toplevel_windows (ui_path):
	root = ET.parse(ui_path).getroot()
	return [o.get('id') for o in root.findall('object')
			if o.get('class') in ('GtkWindow', 'GtkApplicationWindow')]


class Pages (unittest.TestCase):

	def setUp (self):
		self.pages = pages()

	def test_mallard_page_named_by_its_file (self):
		for name, root in self.pages.items():
			self.assertEqual(root.tag, MAL + 'page', name)
			self.assertEqual(root.get('id'), name, name)
			self.assertIsNotNone(root.find(MAL + 'title'), name)

	def test_links_land (self):
		for name, root in self.pages.items():
			for element in root.iter():
				xref = element.get('xref')
				if xref is None or element.tag == MAL + 'links':
					continue
				page, _, section = xref.partition('#')
				page = page or name
				self.assertTrue(page in self.pages,
								"%s links to %s" % (name, xref))
				if section:
					ids = {e.get('id') for e in self.pages[page].iter(MAL + 'section')}
					self.assertTrue(section in ids,
								"%s links to %s" % (name, xref))

	def test_every_page_reachable_from_index (self):
		guides = {}
		for name, root in self.pages.items():
			info = root.find(MAL + 'info')
			links = [] if info is None else info.findall(MAL + 'link')
			guides[name] = {l.get('xref').partition('#')[0] for l in links
							if l.get('type') == 'guide'}
		reachable = {'index'}
		grew = True
		while grew:
			grew = False
			for name, up in guides.items():
				if name not in reachable and up & reachable:
					reachable.add(name)
					grew = True
		self.assertEqual(set(self.pages) - reachable, set())


class Windows (unittest.TestCase):

	maxDiff = None

	def setUp (self):
		self.pages = pages()

	def test_pages_opened_exist (self):
		# the page is the call's double quoted string; windows are fetched
		# with single quotes, get_object('window')
		call = re.compile(r'user_manual\.(?:show|bind_f1)\s*\([^"]*?"([^"]*)"')
		for relative, text in source_files():
			for name in call.findall(text):
				self.assertTrue(name in self.pages,
							"%s opens %s.page" % (relative, name))

	def test_every_window_binds_f1 (self):
		ui_name = re.compile(r'["\']([\w/]+\.ui)["\']')
		missing = []
		for relative, text in source_files():
			if relative in EXEMPT:
				continue
			for ui in ui_name.findall(text):
				ui = ui.lstrip('/') # "//miscellaneous_revenue.ui"
				if ui.startswith('src/'): # pdf_attachment.py
					ui = ui[len('src/'):]
				ui_path = os.path.join(SRC, ui)
				if not os.path.exists(ui_path):
					continue
				if toplevel_windows(ui_path) and 'user_manual.bind_f1' not in text:
					missing.append(relative)
					break
		self.assertEqual(missing, [], "no user_manual.bind_f1")


if __name__ == '__main__':
	unittest.main()
