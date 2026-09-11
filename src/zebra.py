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

import os, glob, socket
import psycopg2
from db_connection import DB
from constants import template_dir

PRODUCT = 'product'
SERIAL = 'serial'

# How many %s a template of each type is printed with. The product label is
# sent (barcode, name); a serial label just the number. Listing both kinds in
# one combo is what used to raise TypeError out of a signal handler the moment
# a serial template was picked in the product window.
PLACEHOLDER_COUNT = {PRODUCT: 2, SERIAL: 1}


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

	Trial formatting catches all three mistakes at once: the wrong number of
	placeholders, a literal % typed into a text element, and %d where %s was
	meant. Without this the error surfaces at print time, in somebody else's
	window, days later.
	'''
	count = PLACEHOLDER_COUNT.get(label_type)
	if count == None:
		raise ZebraError("'%s' is not a label type." % label_type)
	format_template(text, tuple(['X'] * count))


def format_template (text, args):
	"Substitute the label data into a template."
	try:
		return text % args
	except TypeError:
		raise ZebraError("This template does not take %s value(s). Check that "
							"its placeholder count matches its label type."
							% len(args))
	except ValueError as e:
		raise ZebraError("This template has a bad placeholder (%s). A literal "
							"percent sign has to be written as two." % e)


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


def print_label (host, port, template_id, args, copies = 1):
	'''Print a stored template, substituting args, copies times.

	The whole payload is built before the socket is opened, so a template that
	cannot be formatted fails with nothing left half open, and the copies go
	out down one connection.
	'''
	template = fetch_template(template_id)
	label = format_template(template, args)
	send_to_printer(host, port, label * copies)
