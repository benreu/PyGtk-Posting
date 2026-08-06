# constants.py
#
# Copyright (C) 2019 - Reuben
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

import os, shutil

dev_mode = False
is_admin = False
log_file = None
installed = False
PRODUCT_LOCK_CLASSID = 1
CONTACT_LOCK_CLASSID = 2
ORDER_NUMBER_LOCK_CLASSID = 3
PRODUCT_LOCATION_LOCK_CLASSID = 4
MANUFACTURING_SERIAL_LOCK_CLASSID = 5
MANUFACTURING_PROJECT_LOCK_CLASSID = 6
CONTACT_FILES_LOCK_CLASSID = 7
CONTACT_TAX_EXEMPTIONS_LOCK_CLASSID = 8
CONTACT_INDIVIDUALS_LOCK_CLASSID = 9


help_dir = ''
ui_directory = ''
template_dir = ''
modules_dir = ''
sql_dir = ''
cur_dir = os.getcwd()
home = os.path.expanduser('~')
preferences_path = os.path.join(home, '.config/posting')


def set_directories():
    global help_dir, ui_directory, template_dir, modules_dir, sql_dir, installed
    if cur_dir.split('/')[1] == "usr":  #posting is launching from an installed .deb
        help_dir = os.path.relpath("/usr/share/help/C/pygtk-posting")
        ui_directory = os.path.relpath("/usr/share/pygtk_posting/ui/")
        template_orig = os.path.relpath("/usr/share/pygtk_posting/templates/")
        template_dir = os.path.join(home, ".config/posting/templates")
        if not os.path.exists(template_dir):  #copy templates
            shutil.copytree(template_orig, template_dir)
            print("copied *.odt templates to %s" % template_dir)
        modules_orig = os.path.relpath("/usr/lib/python3/dist-packages/pygtk_posting/modules/")
        modules_dir = os.path.join(home, ".config/posting/modules/")
        if not os.path.exists(modules_dir):  #copy modules
            shutil.copytree(modules_orig, modules_dir)
            print("copied *.py modules to %s" % modules_dir)
        sql_dir = os.path.realpath("/usr/lib/python3/dist-packages/pygtk_posting/db/")
        installed = True
    else:  # use local files
        help_dir = os.path.join(cur_dir, "help/C/pygtk-posting")
        ui_directory = os.path.join(cur_dir, "src")
        template_dir = os.path.join(cur_dir, "templates")
        modules_dir = os.path.join(cur_dir, "src/modules/")
        sql_dir = os.path.join(cur_dir, "src/db/")
