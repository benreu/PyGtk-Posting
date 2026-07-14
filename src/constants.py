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

from gi.repository import GLib, GObject
import os, shutil, psycopg2
from db_connection import ReconnectStatusDialog

dev_mode = False
DB = None
DB_PROCESS_ID = 0
cursor = None
broadcaster = None
reconnect_status = None
ACCOUNTS = None
is_admin = False
log_file = None
mobile = False
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


def start_broadcaster():
    global broadcaster, ACCOUNTS, reconnect_status
    import accounts as ACCOUNTS
    broadcaster = Broadcast()
    reconnect_status = ReconnectStatusDialog()
    DB.register_reconnect_listener(reconnect_status.on_reconnect_event)


class Broadcast(GObject.GObject):
    __gsignals__ = {
        'products_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'contacts_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'clock_entries_changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'invoices_changed': (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
        'purchase_orders_changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'admin_changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        'shutdown': (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        global DB_PROCESS_ID
        GObject.GObject.__init__(self)
        self.io_watch_id = GLib.io_add_watch(
            DB.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_db_readable
        )
        self.connect("shutdown", self.on_shutdown)
        self._listen()
        DB_PROCESS_ID = DB.get_backend_pid()
        DB.register_reconnect_listener(self._on_reconnect)

    def _listen(self):
        c = DB.cursor()
        c.execute("LISTEN products;"
                  "LISTEN contacts;"
                  "LISTEN accounts;"
                  "LISTEN time_clock_entries;"
                  "LISTEN invoices;"
                  "LISTEN purchase_orders;")
        c.close()
        DB.commit()

    def _on_reconnect(self, event, attempt=None, max_attempts=None):
        global DB_PROCESS_ID
        if event != 'reconnected':
            return
        try:
            GLib.source_remove(self.io_watch_id)
        except Exception:
            pass
        self.io_watch_id = GLib.io_add_watch(
            DB.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_db_readable
        )
        self._listen()
        DB_PROCESS_ID = DB.get_backend_pid()

    def on_shutdown(self, broadcaster):
        GLib.source_remove(self.io_watch_id)

    def on_db_readable(self, source, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR) or DB.closed == 1:
            GLib.idle_add(DB.reconnect)
            return False
        try:
            DB.poll()
            while DB.notifies:
                notify = DB.notifies.pop(0)
                if notify.channel == "products":
                    self.emit('products_changed')
                elif notify.channel == "contacts":
                    self.emit('contacts_changed')
                elif notify.channel == "accounts":
                    ACCOUNTS.populate_accounts()
                elif notify.channel == "time_clock_entries":
                    self.emit('clock_entries_changed')
                elif notify.channel == "invoices":
                    invoice_id = notify.payload
                    self.emit("invoices_changed", int(invoice_id),
                              notify.pid != DB_PROCESS_ID)
                elif notify.channel == "purchase_orders":
                    po_id = notify.payload
                    if notify.pid != DB_PROCESS_ID:
                        self.emit("purchase_orders_changed", int(po_id))
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # the connection died while handling a background notification - DB has
            # already reconnected (or is reconnecting) via the cursor that hit this;
            # there's no user action to retry here, so just skip this refresh
            print("constants: on_db_readable: %s" % e)
        return True


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
