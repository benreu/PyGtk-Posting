# create_deb.py
#
# Copyright (C) 2018 - reuben
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

# run this file with the command    fakeroot python3 ./create_deb.py

import shutil, os, subprocess, re
JOIN = os.path.join
CWD = os.getcwd()


def copy_files (folder, dest_folder):
	"copy all the .py, .sql, and .ui files to their respective folders"
	orig_folder = JOIN(CWD, folder)
	with os.scandir(orig_folder) as objects:
		for obj in (o for o in objects if o.name != "__pycache__"):
			if not obj.is_dir():
				source_obj = JOIN(folder, obj)
			if obj.is_dir():
				if dest_folder == '':
					copy_files (os.path.relpath(obj), obj.name)
				else:
					copy_files (os.path.relpath(obj), (dest_folder+"/"+obj.name))
			elif obj.name.endswith (".ui") :
				ui_dest = JOIN(ui_dest_folder, dest_folder)
				if not os.path.exists(ui_dest):
					os.mkdir(ui_dest)
				ui_file = JOIN(orig_folder, obj)
				ui_dest = JOIN(ui_dest, obj.name)
				shutil.copy2(ui_file, ui_dest)
				os.chmod(ui_dest, 0o644)
			elif obj.name.endswith (".py") or obj.name.endswith (".sql") :
				py_dest = JOIN(py_dest_folder, dest_folder)
				if not os.path.exists(py_dest):
					os.makedirs (py_dest)
				py_file = JOIN(orig_folder, obj)
				py_dest = JOIN(py_dest, obj.name)
				shutil.copy2(py_file, py_dest)
				os.chmod (py_dest, 0o644)

with open ("./Makefile", 'r') as mf:
	"read Anjuta makefile for version number"
	for line in mf.read().split('\n'):
		if line[0:14] == 'PACKAGE_STRING': # get current version of Posting
			tupl = line.split()
			version = tupl[-1]
output = ''
with open ("control", 'r') as old_c:
	"read current debian control file"
	for row, text in enumerate(old_c.read().split('\n')):
		if row == 1:
			output += ("Version: %s\n" % version)
		elif text != '':
			output += (text + "\n")
with open ("control", 'w') as new_c:
	"write posting version to debian control file"
	new_c.write(output)
package_name = "pygtk_posting_%s-1" % version
package_folder = JOIN(CWD, package_name)
if os.path.exists(package_folder):
	print ("folder %s already exists, this may result in improper debian packaging" % package_folder)
#create .ui file directory
ui_dest_folder = JOIN(package_folder, "usr/share/pygtk_posting/ui")
os.makedirs (ui_dest_folder)
#create .py file directory
py_dest_folder = JOIN(package_folder, "usr/lib/python3/dist-packages/pygtk_posting")
os.makedirs (py_dest_folder)
copy_files ("src", '')
#create .odt template folders
odt_dest_folder = JOIN(package_folder, "usr/share/pygtk_posting/templates")
os.makedirs (odt_dest_folder)
with os.scandir(JOIN(CWD, "templates")) as odts:
	for odt in odts:
		end = odt.name.endswith
		if end(".odt") or end(".txt"): 
			shutil.copy2(odt, odt_dest_folder)
#create .page help file directory
help_dest_folder = JOIN(package_folder, "usr/share/help/C/pygtk-posting")
os.makedirs (help_dest_folder)
with os.scandir(JOIN(CWD, "help/C/pygtk-posting")) as pages:
	for page in pages:
		if page.name.endswith(".page") : 
			shutil.copy2(page, help_dest_folder)
#create usr/bin folder + main executable
exec_dest_folder = JOIN(package_folder, "usr/bin")
os.makedirs (exec_dest_folder)
shutil.copy2(JOIN(CWD, "pygtk-posting"), exec_dest_folder)
#create desktop entry
desktop_dest_folder = JOIN(package_folder, "usr/share/applications")
os.makedirs (desktop_dest_folder)
shutil.copy2(JOIN(CWD, "pygtk-posting.desktop"), desktop_dest_folder)
#create icon directory
shutil.copytree(JOIN(CWD, "icons"), JOIN(package_folder, "usr/share/icons"))
#create directory required for all debian packages
doc_dest_folder = JOIN(package_folder, "usr/share/doc/pygtk-posting")
os.makedirs (doc_dest_folder)
shutil.copy2(JOIN(CWD, "copyright"), doc_dest_folder)
#include code128 truetype font for templates with barcodes
font_dest_folder = JOIN(package_folder, "usr/share/fonts/truetype/code128")
os.makedirs (font_dest_folder)
shutil.copy2(JOIN(CWD, "code128.ttf"), font_dest_folder)
#copy files for debian packaging
debian_folder = JOIN(package_folder, "DEBIAN")
os.mkdir (debian_folder)
shutil.copy2(JOIN(CWD, "control"), debian_folder)
shutil.copy2(JOIN(CWD, "postinst"), debian_folder)
shutil.copy2(JOIN(CWD, "prerm"), debian_folder)
#create debian package
subprocess.call(["dpkg-deb", "--build", package_name])
#call lintian to report problems
subprocess.call(["lintian", package_name+".deb"])
shutil.rmtree (package_folder)

	

