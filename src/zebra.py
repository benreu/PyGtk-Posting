# zebra.py
#
# Copyright (C) 2026 - reuben
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

'''Zebra label templates, shared by every client through the database.

The templates used to be loose .zpl files under templates/Zebra, globbed
relative to the current directory. That made them per workstation, and
invisible altogether from an installed .deb, which runs from /usr. They now
live in settings.zebra_templates, so one edit reaches the whole shop and
pg_dump backs them up with everything else.
'''

import os, sys, glob, socket
import psycopg2
from db_connection import DB
from constants import template_dir

# Label is the LinuxZPL engine's public entry point; the submodule is an
# application, so its directory goes on the path the way zebra_designer does.
_ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'linuxzpl')
if _ENGINE not in sys.path:
	sys.path.append(_ENGINE)
from zplcore import Label

PRODUCT = 'product'
SERIAL = 'serial'

# The ^FX IDs a template of each type must carry. LinuxZPL's Label fills the
# element holding an ID, so a template is a plain label the designer can draw
# and render, with no %s to substitute. A product label is given a barcode and
# a name; a serial label a number. Listing both kinds in one combo is what
# used to raise TypeError out of a signal handler the moment a serial template
# was picked in the product window.
LABEL_IDS = {PRODUCT: ('barcode', 'name'), SERIAL: ('serial_number',)}


class ZebraError (Exception):
	'A failure with a message worth showing the user in a dialog.'


class TemplateGone (ZebraError):
	'''The template was deleted from under us, by another client.

	Its own class so the designer can tell this apart from a template that
	failed validation: the right response to "gone" is to offer Save as,
	not to keep failing on the same dead id forever.
	'''


def list_templates (label_type = None):
	"The stored templates, as (id, name, label_type), optionally of one type."
	cursor = DB.cursor()
	if label_type == None:
		cursor.execute("SELECT id, name, label_type FROM settings.zebra_templates "
						"ORDER BY name")
	else:
		cursor.execute("SELECT id, name, label_type FROM settings.zebra_templates "
						"WHERE label_type = %s ORDER BY name", (label_type,))
	rows = cursor.fetchall()
	cursor.close()
	DB.rollback()
	return rows


def fetch_template (template_id):
	"The ZPL text of one template."
	cursor = DB.cursor()
	cursor.execute("SELECT template FROM settings.zebra_templates WHERE id = %s",
					(template_id,))
	row = cursor.fetchone()
	cursor.close()
	DB.rollback()
	if row == None:
		# Another client can delete a template while this window sits open
		raise TemplateGone("The label template no longer exists; "
							"reselect the printer to refresh the list.")
	return row[0]


def save_template (name, label_type, text, template_id = None):
	"Insert or update a template, returning its id."
	validate_template(text, label_type)
	cursor = DB.cursor()
	try:
		if template_id == None:
			cursor.execute("INSERT INTO settings.zebra_templates "
							"(name, label_type, template) VALUES (%s, %s, %s) "
							"RETURNING id", (name, label_type, text))
		else:
			cursor.execute("UPDATE settings.zebra_templates SET "
							"(name, label_type, template, date_changed) = "
							"(%s, %s, %s, now()) WHERE id = %s RETURNING id",
							(name, label_type, text, template_id))
	except psycopg2.IntegrityError:
		# The name is UNIQUE, and another client can take it between our
		# check and this write. Roll back, or the shared connection sits in
		# an aborted transaction and every later query in the app fails.
		cursor.close()
		DB.rollback()
		raise ZebraError("A label template named '%s' already exists." % name)
	row = cursor.fetchone()
	cursor.close()
	if row == None:
		DB.rollback()
		raise TemplateGone("The label template no longer exists; it may have "
							"been deleted by another user.")
	DB.commit()
	return row[0]


def rename_template (template_id, name):
	"Change a template's name, leaving its ZPL and type alone."
	cursor = DB.cursor()
	try:
		cursor.execute("UPDATE settings.zebra_templates SET "
						"(name, date_changed) = (%s, now()) WHERE id = %s "
						"RETURNING id", (name, template_id))
	except psycopg2.IntegrityError:
		# as in save_template: UNIQUE(name), and roll back or the shared
		# connection is left in an aborted transaction
		cursor.close()
		DB.rollback()
		raise ZebraError("A label template named '%s' already exists." % name)
	row = cursor.fetchone()
	cursor.close()
	if row == None:
		DB.rollback()
		raise TemplateGone("The label template no longer exists; it may have "
							"been deleted by another user.")
	DB.commit()


def delete_template (template_id):
	cursor = DB.cursor()
	cursor.execute("DELETE FROM settings.zebra_templates WHERE id = %s",
					(template_id,))
	cursor.close()
	DB.commit()


def validate_template (text, label_type):
	'''Check a template can actually be printed, before it is stored.

	Trial filling catches a missing ID before it surfaces at print time, in
	somebody else's window, days later.
	'''
	ids = LABEL_IDS.get(label_type)
	if ids == None:
		raise ZebraError("'%s' is not a label type." % label_type)
	fill_template(text, label_type, dict.fromkeys(ids, 'X'))


def describe_label_type (label_type):
	"What a label type's template has to contain, for the Save as dialog."
	ids = LABEL_IDS[label_type]
	return "element%s with ID %s" % ('' if len(ids) == 1 else 's',
									' and '.join("'%s'" % i for i in ids))


def fill_template (text, label_type, values):
	'''Fill a template's elements by ID, returning the ZPL to print.

	values maps each ID of the label type to its data.
	'''
	try:
		label = Label.from_zpl(text)
		missing = [i for i in LABEL_IDS[label_type] if i not in label.ids]
		if missing:
			raise ZebraError("This %s template has no element with the ID %s. "
								"Double-click the element in the designer and "
								"fill in its ID row."
								% (label_type,
									' or '.join("'%s'" % i for i in missing)))
		label.fill(values)
		return label.to_zpl()
	except (ValueError, KeyError) as e:
		raise ZebraError("This template could not be filled in: %s" % e)


def populate_template_store (store, label_type):
	"Fill a template combo's store with the templates of one type."
	store.clear()
	for template_id, name, _label_type in list_templates(label_type):
		store.append(["zpl", name, template_id])


def selected_template_id (combo):
	'''The stored template a label window's combo has selected, or None.

	None also for an .odt row: those are files, and have nothing to edit in
	the designer. The combos' id-column is the kind, not the id, which is why
	this reads the row rather than asking the combo.
	'''
	treeiter = combo.get_active_iter()
	if treeiter == None:
		return None
	row = combo.get_model()[treeiter]
	if row[0] != 'zpl':
		return None
	return row[2]


def select_template (combo, template_id):
	"Select a stored template's row, if the combo lists it. True when it did."
	for row in combo.get_model():
		if row[0] == 'zpl' and row[2] == template_id:
			combo.set_active_iter(row.iter)
			return True
	return False


def populate_odt_store (store, pattern):
	'''Fill a template combo's store with the .odt templates matching a glob.

	Joined onto constants.template_dir rather than './templates', so the list
	is not empty when Posting runs from an installed .deb.
	'''
	store.clear()
	for path in sorted(glob.glob(os.path.join(template_dir, pattern))):
		store.append(["odt", os.path.basename(path), 0])


def send_to_printer (host, port, data, timeout = 10):
	"Send raw bytes to a networked Zebra printer."
	try:
		mysocket = socket.create_connection((host, int(port)), timeout)
	except OSError as e:
		raise ZebraError("Could not reach the printer at %s:%s\n\n%s"
							% (host, port, e))
	try:
		# sendall, not send: send() may write only part of a label, and one
		# carrying an image runs to tens of kilobytes
		mysocket.sendall(data.encode('utf-8'))
	except OSError as e:
		raise ZebraError("Could not send the label to %s:%s\n\n%s"
							% (host, port, e))
	finally:
		mysocket.close()


def test_label (name, host, port):
	'''A one-off label naming the printer, for confirming an address.

	The name is typed by whoever set the printer up; a caret or tilde in it
	would end the field early, so both are dropped rather than escaped.
	'''
	name = name.replace('^', '').replace('~', '')
	return ("^XA"
			"^FO30,30^A0N,40,40^FDPosting test label^FS"
			"^FO30,90^A0N,30,30^FD%s^FS"
			"^FO30,140^A0N,30,30^FD%s:%s^FS"
			"^XZ" % (name, host, port))


def print_label (host, port, template, label_type, values, copies = 1):
	'''Print a template's ZPL text, filling it in by ID from values, copies times.

	The caller reads the text with fetch_template, at a moment of its own
	choosing: that read ends whatever transaction it finds open, so nothing in
	here touches the database, and a window with writes pending can print
	after it commits rather than around a helper that would roll them back.

	The whole payload is built before the socket is opened, so a template that
	cannot be formatted fails with nothing left half open, and the copies go
	out down one connection.
	'''
	label = fill_template(template, label_type, values)
	send_to_printer(host, port, label * copies)
