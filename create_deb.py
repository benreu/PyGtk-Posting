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

import shutil, os, subprocess
JOIN = os.path.join
CWD = os.getcwd()


def copy_files (folder, dest_folder):
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

package_name = "pygtk_posting_5.1-1"
package_folder = JOIN(CWD, package_name)
if os.path.exists(package_folder):
	shutil.rmtree (package_folder)
ui_dest_folder = JOIN(package_folder, "usr/share/pygtk_posting/ui")
os.makedirs (ui_dest_folder)
py_dest_folder = JOIN(package_folder, "usr/lib/python3/dist-packages/pygtk_posting")
os.makedirs (py_dest_folder)
copy_files ("src", '')
odt_dest_folder = JOIN(package_folder, "usr/share/pygtk_posting/templates")
os.makedirs (odt_dest_folder)
with os.scandir(JOIN(CWD, "templates")) as odts:
	for odt in odts:
		end = odt.name.endswith
		if end(".odt") or end(".txt") or end(".pil") or end(".pbm"): 
			shutil.copy2(odt, odt_dest_folder)
exec_dest_folder = JOIN(package_folder, "usr/bin")
os.makedirs (exec_dest_folder)
shutil.copy2(JOIN(CWD, "pygtk_posting"), exec_dest_folder)
#shutil.chown(JOIN(exec_dest_folder, "posting"), 'root', 'root')
desktop_dest_folder = JOIN(package_folder, "usr/share/applications")
os.makedirs (desktop_dest_folder)
shutil.copy2(JOIN(CWD, "pygtk-posting.desktop"), desktop_dest_folder)
shutil.copytree(JOIN(CWD, "icons"), JOIN(package_folder, "usr/share/icons"))
debian_folder = JOIN(package_folder, "DEBIAN")
os.mkdir (debian_folder)
shutil.copy2(JOIN(CWD, "control"), debian_folder)
shutil.copy2(JOIN(CWD, "postinst"), debian_folder)
subprocess.call(["dpkg-deb", "--build", package_name])
subprocess.call(["lintian", package_name+".deb"])

