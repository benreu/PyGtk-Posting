# correspondence_window.py
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

'''What has been written to a contact, readable from any workstation.

Posting has recorded every message it sent since 0.7.37, but the only way to
read those rows was the SQL window, so in practice the record of what had been
sent to a customer was still whatever was in the Sent folder of whichever
workstation sent it. This is the window that was the point of recording them.

A message is found by the links recorded when it was sent, never by matching
an email address. contacts.email is not unique, is not trimmed and is not
case-folded on write, and there is a second address column on
contact_individuals, so an address match would sooner or later show one
customer another customer's mail. The compose window knew exactly who was
chosen, so that is what is stored and what is read back.

The attachment is not stored twice. A sent invoice's pdf is already in
invoices.pdf_data on the record the message is linked to, so Open goes and
gets it from there: what opens is provably the bytes that were attached.'''

from gi.repository import Gtk, GLib
from datetime import date, datetime, timedelta
import os, subprocess, tempfile
from db_connection import DB, broadcaster
from constants import ui_directory
from sqlite_utils import get_apsw_connection
from dateutils import DateTimeCalendar
import user_manual

UI_FILE = ui_directory + "/correspondence_window.ui"

# How long after a notification the store is repopulated. One send does not
# need a wait at all; the IMAP sync will notify once per committed slice, and
# without this the store would be rebuilt two dozen times in a minute during
# the first one
REFRESH_DELAY = 250

# What each kind of link is called in the list, and whether there is anything
# to open for it. A contact is a real link - it is how this window finds the
# message at all - but a contact is not a document
LINK_KINDS = (('invoice_id', 'Invoice', 'invoices'),
				('purchase_order_id', 'Purchase order', 'purchase_orders'),
				('contact_id', 'Contact', None))


class CorrespondenceGUI (Gtk.Builder):

	def __init__ (self, contact_id = None):
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.contact_store = self.get_object('contact_store')
		self.message_store = self.get_object('message_store')
		self.link_store = self.get_object('link_store')
		self.contact_id = None
		self.message_id = None
		self.refresh_timeout = None
		self.search_text = ''
		# set while the opening dates are put in, because set_date fires
		# day-selected and each one would otherwise populate the store before
		# the other date exists
		self.loading = True
		completion = self.get_object('contact_completion')
		completion.set_match_func(self.contact_match_func)
		self.populate_contact_store()
		self.filter = self.get_object('message_filter')
		self.filter.set_visible_func(self.filter_func)

		# override = True because these are a reporting cut, not a posting
		# date. Without it DateTimeCalendar refuses any date outside an active
		# fiscal year and re-pops itself every two seconds, which for a
		# company whose fiscal years stop short of today is every date
		self.start_calendar = DateTimeCalendar(override = True)
		self.start_calendar.set_relative_to(self.get_object('start_entry'))
		self.end_calendar = DateTimeCalendar(override = True)
		self.end_calendar.set_relative_to(self.get_object('end_entry'))
		self.start_calendar.connect('day-selected', self.start_date_selected)
		self.end_calendar.connect('day-selected', self.end_date_selected)

		# before the set_date calls: they reach the date handlers, and
		# anything those put on screen is transient for this window
		self.window = self.get_object('window')
		user_manual.bind_f1(self.window, "correspondence")
		self.start_calendar.set_date(datetime.today() - timedelta(days = 365))
		self.end_calendar.set_today()
		self.loading = False

		self.handler_ids = list()
		for signal, handler in (('mail_messages_changed', self.mail_changed),
								('contacts_changed', self.contacts_changed)):
			self.handler_ids.append(broadcaster.connect(signal, handler))

		self.set_window_layout_from_settings()
		# before show_all, the way every other contact combo in this program
		# does it. set_active_id writes into the combo's own entry, and doing
		# that to a window already on screen resets that entry's input method
		# context after the input method has started on it
		if contact_id != None:
			self.get_object('contact_combo').set_active_id(str(contact_id))
		else:
			self.populate_messages()
		self.window.show_all()

	def destroy (self, window):
		'''Nothing of this window may outlive it. A broadcaster handler left
		connected is called with a destroyed window the next time anything
		sends, and a timeout left armed repopulates a store that is gone.'''
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.handler_ids = list()
		if self.refresh_timeout != None:
			GLib.source_remove(self.refresh_timeout)
			self.refresh_timeout = None

	############################## window layout

	def set_window_layout_from_settings (self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT value FROM correspondence "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT value FROM correspondence "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT value FROM correspondence "
					"WHERE widget_id = 'paned_position'")
		self.get_object('paned').set_position(c.fetchone()[0])
		c.execute("SELECT widget_id, value FROM correspondence WHERE "
					"widget_id IN ('date_column', 'direction_column', "
										"'contact_column', 'subject_column')")
		for widget_id, column_width in c.fetchall():
			self.get_object(widget_id).set_fixed_width(column_width)
		sqlite.close()

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO correspondence (widget_id, value) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO correspondence (widget_id, value) "
					"VALUES ('window_height', ?)", (height,))
		c.execute("REPLACE INTO correspondence (widget_id, value) "
					"VALUES ('paned_position', ?)",
					(self.get_object('paned').get_position(),))
		for widget_id in ('date_column', 'direction_column',
							'contact_column', 'subject_column'):
			c.execute("REPLACE INTO correspondence (widget_id, value) "
						"VALUES (?, ?)",
						(widget_id, self.get_object(widget_id).get_width()))
		sqlite.close()

	############################## the contact

	def populate_contact_store (self):
		'''Every contact, not only the ones with an email address. A message
		is found by its recorded link, so a contact whose address was since
		blanked still has the correspondence that was sent to it.'''
		self.contact_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id::text, name FROM contacts "
						"WHERE deleted = False ORDER BY name")
		for row in cursor.fetchall():
			self.contact_store.append(row)
		cursor.close()
		DB.rollback()

	def contacts_changed (self, broadcaster):
		chosen = self.get_object('contact_combo').get_active_id()
		self.populate_contact_store()
		if chosen != None:
			self.get_object('contact_combo').set_active_id(chosen)

	def contact_match_func (self, completion, key, iter_):
		for text in key.split():
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def contact_match_selected (self, completion, model, iter_):
		self.get_object('contact_combo').set_active_id(model[iter_][0])

	def contact_combo_changed (self, combo):
		contact_id = combo.get_active_id()
		if contact_id == None:
			return # typed into the entry, not chosen from the list
		self.contact_id = int(contact_id)
		self.populate_messages()

	def direction_combo_changed (self, combo):
		if self.loading == False:
			self.populate_messages()

	def clear_clicked (self, button):
		'''No contact means every contact. The window is a customer's
		correspondence and the company's outbox depending on this.'''
		self.contact_id = None
		combo = self.get_object('contact_combo')
		combo.set_active(-1)
		combo.get_child().set_text('')
		self.populate_messages()

	############################## the dates

	def start_icon_released (self, entry, icon, event):
		self.start_calendar.show()

	def end_icon_released (self, entry, icon, event):
		self.end_calendar.show()

	def start_date_selected (self, calendar):
		self.get_object('start_entry').set_text(calendar.get_text())
		if self.loading == False:
			self.populate_messages()

	def end_date_selected (self, calendar):
		self.get_object('end_entry').set_text(calendar.get_text())
		if self.loading == False:
			self.populate_messages()

	############################## the list

	def mail_changed (self, broadcaster):
		if self.refresh_timeout != None:
			return # one is already due; this is the same answer
		self.refresh_timeout = GLib.timeout_add(REFRESH_DELAY, self.refresh_due)

	def refresh_due (self):
		self.refresh_timeout = None
		self.populate_messages()
		return False # once, never re-armed

	def search_entry_changed (self, searchentry):
		self.search_text = searchentry.get_text().lower()
		self.filter.refilter()

	def filter_func (self, model, iter_, data = None):
		if self.search_text == '':
			return True
		for column in (4, 5): # the contact and the subject
			if self.search_text in (model[iter_][column] or '').lower():
				return True
		return False

	def populate_messages (self):
		'''Re-read the list. The contact and the dates re-query because they
		are predicates the database can answer with an index; the search box
		refilters what is already here.'''
		treeview = self.get_object('message_treeview')
		selected = self.message_id
		treeview.set_model(None)
		self.message_store.clear()
		cursor = DB.cursor()
		# COALESCE because date_sent is nullable: a row whose message carried
		# no usable Date still belongs somewhere, and when it was recorded is
		# the honest answer. string_agg rather than a join to contacts, so a
		# message linked to two contacts is one row and not two
		where = ["COALESCE(m.date_sent, m.date_inserted)::date >= %s"]
		args = [self.start_calendar.get_date()]
		end = self.end_calendar.get_date()
		if end != None and end < date.today():
			where.append("COALESCE(m.date_sent, m.date_inserted)::date <= %s")
			args.append(end)
		# an end date of today means up to now, and is left off the query
		# rather than fixed at the date the window opened. One left open
		# overnight would otherwise stop showing mail at midnight, and go on
		# refreshing itself for messages it had decided not to show
		if self.contact_id != None:
			where.append("EXISTS (SELECT 1 FROM mail_links "
							"WHERE mail_messages_id = m.id "
							"AND contact_id = %s)")
			args.append(self.contact_id)
		direction = self.get_object('direction_combo').get_active_id()
		if direction in ('sent', 'received'):
			where.append("m.outgoing = %s")
			args.append(direction == 'sent')
		cursor.execute("SELECT m.id, "
							"COALESCE(m.date_sent, m.date_inserted)::text, "
							"format_timestamp(COALESCE(m.date_sent, "
													"m.date_inserted)), "
							"CASE WHEN m.outgoing THEN 'Sent' "
													"ELSE 'Received' END, "
							"COALESCE(linked.names, CASE WHEN m.outgoing "
								"THEN m.to_addresses ELSE m.from_address END), "
							"m.subject, "
							"CASE WHEN m.has_attachments THEN 'Yes' "
													"ELSE '' END, "
							"m.folder "
						"FROM mail_messages AS m "
						"LEFT JOIN (SELECT ml.mail_messages_id, "
										"string_agg(c.name, ', ' "
											"ORDER BY c.name) AS names "
									"FROM mail_links AS ml "
									"JOIN contacts AS c "
										"ON c.id = ml.contact_id "
									"GROUP BY ml.mail_messages_id) AS linked "
							"ON linked.mail_messages_id = m.id "
						"WHERE " + " AND ".join(where) + " "
						"ORDER BY COALESCE(m.date_sent, m.date_inserted) DESC",
						args)
		rows = cursor.fetchall()
		for row in rows:
			self.message_store.append(row)
		cursor.close()
		DB.rollback()
		treeview.set_model(self.get_object('message_sort'))
		self.get_object('status_label').set_label(self.said(len(rows)))
		self.reselect(selected)

	def said (self, count):
		if count > 0:
			return "%s message%s" % (count, '' if count == 1 else 's')
		# an empty list has two quite different meanings, and the window
		# opened on the last year. An imported archive is mostly older than
		# that, so without this the whole of it looks like nothing at all
		oldest = self.oldest()
		if oldest != None and oldest < self.start_calendar.get_date():
			return ("Nothing in this period. The oldest message here is from "
					"%s - widen the dates to see it." % oldest)
		if self.contact_id != None:
			return "Nothing has been emailed to or from this contact."
		return "Nothing has been emailed in this period."

	def oldest (self):
		"the date of the oldest message there is, whatever the dates say"
		where, args = '', []
		if self.contact_id != None:
			where = ("WHERE EXISTS (SELECT 1 FROM mail_links "
						"WHERE mail_messages_id = m.id AND contact_id = %s)")
			args.append(self.contact_id)
		cursor = DB.cursor()
		cursor.execute("SELECT min(COALESCE(m.date_sent, "
										"m.date_inserted))::date "
						"FROM mail_messages AS m " + where, args)
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		return row[0] if row else None

	def reselect (self, message_id):
		'''Put the cursor back on the message that was selected. A refresh
		arriving while somebody is reading one must not move them off it.'''
		if message_id == None:
			return
		model = self.get_object('message_sort')
		for row in model:
			if row[0] == message_id:
				self.get_object('message_treeview').set_cursor(row.path)
				return
		# it is no longer in the list: the dates or the contact changed under
		# it, so there is nothing to show about it either
		self.clear_message()

	############################## the message

	def message_selection_changed (self, selection):
		model, tree_iter = selection.get_selected()
		if tree_iter == None:
			self.clear_message()
			return
		self.message_id = model[tree_iter][0]
		cursor = DB.cursor()
		cursor.execute("SELECT body_text FROM mail_messages WHERE id = %s",
						(self.message_id,))
		row = cursor.fetchone()
		self.get_object('body_buffer').set_text(row[0] if row else '')
		cursor.close()
		DB.rollback()
		self.populate_links()

	def clear_message (self):
		self.message_id = None
		self.get_object('body_buffer').set_text('')
		self.link_store.clear()
		self.get_object('open_button').set_sensitive(False)

	def populate_links (self):
		'''What the message was about, as it was recorded when it was sent.
		An invoice emailed to a customer is two rows, because it is about
		both.'''
		self.link_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT 'Invoice', i.name, 'invoice_id', ml.invoice_id "
						"FROM mail_links AS ml "
						"JOIN invoices AS i ON i.id = ml.invoice_id "
						"WHERE ml.mail_messages_id = %s "
					"UNION ALL "
						"SELECT 'Purchase order', p.name, 'purchase_order_id', "
							"ml.purchase_order_id "
						"FROM mail_links AS ml "
						"JOIN purchase_orders AS p "
							"ON p.id = ml.purchase_order_id "
						"WHERE ml.mail_messages_id = %s "
					"UNION ALL "
						"SELECT 'Contact', c.name, 'contact_id', ml.contact_id "
						"FROM mail_links AS ml "
						"JOIN contacts AS c ON c.id = ml.contact_id "
						"WHERE ml.mail_messages_id = %s "
					"ORDER BY 1, 2",
					(self.message_id, self.message_id, self.message_id))
		for row in cursor.fetchall():
			self.link_store.append(row)
		cursor.close()
		DB.rollback()
		self.get_object('open_button').set_sensitive(False)

	def link_selection_changed (self, selection):
		model, tree_iter = selection.get_selected()
		openable = tree_iter != None and self.table_for(model[tree_iter][2])
		self.get_object('open_button').set_sensitive(bool(openable))

	def table_for (self, column):
		for link_column, label, table in LINK_KINDS:
			if link_column == column:
				return table
		return None

	def link_row_activated (self, treeview, path, column):
		self.open_clicked(None)

	def open_clicked (self, button):
		'''Open the document that was attached, out of the table it is already
		in. Nothing of the attachment is kept on the message's own row, so
		this cannot show something other than what was sent.'''
		model, tree_iter = self.get_object('link_selection').get_selected()
		if tree_iter == None:
			return
		table = self.table_for(model[tree_iter][2])
		if table == None:
			return
		name, record_id = model[tree_iter][1], model[tree_iter][3]
		cursor = DB.cursor()
		cursor.execute("SELECT pdf_data FROM %s WHERE id = %%s" % table,
						(record_id,))
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		if row == None or row[0] == None:
			self.show_message("There is no saved pdf for %s, so there is "
								"nothing to open.\n\nThe message was sent "
								"with one; this record has not kept it."
								% name)
			return
		# left in /tmp like every other preview in this program, so the viewer
		# can keep the file open after this returns
		directory = tempfile.mkdtemp(prefix = "posting_mail_")
		path = os.path.join(directory, "%s.pdf" % name.replace('/', '_'))
		with open(path, 'wb') as pdf_file:
			pdf_file.write(bytes(row[0]))
		subprocess.Popen(["xdg-open", path])

	def show_message (self, text):
		dialog = Gtk.MessageDialog(message_type = Gtk.MessageType.WARNING,
									buttons = Gtk.ButtonsType.CLOSE,
									transient_for = self.window)
		dialog.set_markup(GLib.markup_escape_text(text))
		dialog.run()
		dialog.destroy()
