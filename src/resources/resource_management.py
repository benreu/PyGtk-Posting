# resource_management.py
#
# Copyright (C) 2017 - reuben
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

from gi.repository import Gtk, GLib, Gdk, GObject
from datetime import datetime, date
from dateutils import DateTimeCalendar
import spell_check
from constants import ui_directory, DB, broadcaster

UI_FILE = ui_directory + "/resources/resource_management.ui"

class CellRendererRgbaArray(Gtk.CellRendererText):
	__gtype_name__ = 'CellRendererRgbaArray'
	__gproperties__ = {'RGBA-array': 
							( GObject.TYPE_PYOBJECT, 
							'RGBA array', 
							'column in TreeStore with RGBA array', 
							GObject.ParamFlags.READWRITE), }
	def __init__(self):
		Gtk.CellRendererText.__init__(self)

	def do_set_property (self, param, value):
		name = param.name
		if name == 'RGBA-array':
			self.rgba_array = value
			self.rgba_leng = len(value)

	def do_render (self, cr, treeview, src, dest, flags):
		for index, rgba in enumerate(self.rgba_array):
			cr.save()
			cr.set_source_rgba(rgba.red, rgba.green, rgba.blue)
			x = dest.x + ((dest.width/self.rgba_leng) * index)
			cr.translate(x, dest.y)
			cr.rectangle(0, 0, dest.width/self.rgba_leng, dest.height)
			cr.fill ()
			cr.restore()

class ResourceManagementGUI:
	timeout_id = None
	time_clock = None
	def __init__(self, id_ = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.handler_ids = list()
		for connection in (("shutdown", self.main_shutdown), ):
			handler = broadcaster.connect(connection[0], connection[1])
			self.handler_ids.append(handler)

		renderer = CellRendererRgbaArray ()
		treecolumn = self.builder.get_object('treeviewcolumn6')
		treecolumn.pack_start(renderer, True)
		treecolumn.set_attributes(renderer, RGBA_array = 8)
		renderer.set_property('editable', True)
		renderer.connect('editing-started', self.tag_editing_started)
		
		self.timer_timeout = None
		self.row_id = None
		self.join_filter = ''
		
		self.resource_store = self.builder.get_object('resource_store')
		self.contact_store = self.builder.get_object('contact_store')
		self.contact_completion = self.builder.get_object('contact_completion')
		self.contact_completion.set_match_func(self.contact_match_func)
		
		textview = self.builder.get_object('textview1')
		spell_check.add_checker_to_widget (textview)

		self.dated_for_calendar = DateTimeCalendar()
		no_date_button = self.builder.get_object('button5')
		self.dated_for_calendar.pack_start(no_date_button)
		treeview = self.builder.get_object('treeview1')
		self.dated_for_calendar.set_relative_to(treeview)
		self.dated_for_calendar.connect('day-selected', self.dated_for_calendar_day_selected )
		
		self.older_than_calendar = DateTimeCalendar()
		self.older_than_calendar.connect('day-selected', self.older_than_date_selected )
		entry = self.builder.get_object('entry1')
		self.older_than_calendar.set_relative_to(entry)

		if id_ != None:
			selection = self.builder.get_object('treeview-selection1')
			for row in self.resource_store:
				if row[0] == id_:
					selection.select_path(row.path)
			self.cursor.execute("SELECT notes FROM resources "
								"WHERE id = %s", (id_,))
			for row in self.cursor.fetchall():
				text = row[0]
				self.builder.get_object('notes_buffer').set_text(text)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		self.older_than_calendar.set_today()
		self.populate_stores()

	def destroy (self, widget):
		for handler in self.handler_ids:
			broadcaster.disconnect(handler)
		self.cursor.close()

	def main_shutdown (self, main):
		if self.timeout_id:
			self.save_notes()

	def focus_in_event (self, window, event):
		self.populate_stores ()
	
	def row_limit_value_changed (self, spinbutton):
		self.populate_resource_store ()

	def resource_threaded_checkbutton_toggled (self, checkbutton):
		self.populate_resource_store ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup_at_pointer()

	def delete_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			row_id = model[path][0]
			try:
				self.cursor.execute("DELETE FROM resources "
									"WHERE id = %s", (row_id,))
				DB.commit()
			except Exception as e:
				self.show_message (e)
				DB.rollback()
			self.populate_resource_store()

	def block_number_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			phone_number = model[path][11]
			try:
				self.cursor.execute("INSERT INTO phone_blacklist "
							"(number, blocked_calls) VALUES (%s, 0)", 
							(phone_number,))
				DB.commit()
			except Exception as e:
				self.show_message (e)
				DB.rollback()

	def contact_hub_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			contact_id = model[path][2]
			if contact_id == 0:
				self.show_message ("No contact selected for this row!")
				return
			import contact_hub
			contact_hub.ContactHubGUI(contact_id)

	def report_hub_activated (self, button):
		treeview = self.builder.get_object('treeview1')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def remove_tags (self):
		flowbox = self.builder.get_object('tag_flowbox')
		for child in flowbox.get_children():
			flowbox.remove(child)

	def populate_tag_flowbox (self):
		self.remove_tags()
		flowbox = self.builder.get_object('tag_flowbox')
		c = DB.cursor()
		c.execute("SELECT "
					"tag, "
					"red, "
					"green, "
					"blue, "
					"alpha "
					"FROM resource_ids_tag_ids AS riti "
					"JOIN resource_tags AS rt ON rt.id = riti.resource_tag_id "
					"WHERE riti.resource_id = %s", (self.row_id,))
		for row in c.fetchall():
			tag_name = row[0]
			red = int(row[1]*255)
			green = int(row[2]*255)
			blue = int(row[3]*255)
			alpha = int(row[4]*255)
			hex_color = '#%02x%02x%02x%02x' %  (red, green, blue, alpha)
			string = "<span foreground='%s'>%s</span>\n" % (hex_color, tag_name)
			label = Gtk.Label()
			label.set_markup(string)
			label.show()
			flowbox.add(label)

	def populate_tags_applied_store (self):
		store = self.builder.get_object('tags_applied_store')
		store.clear()
		c = DB.cursor()
		c.execute("SELECT id::text, tag, red, green, blue, alpha, "
					"(SELECT True FROM resource_ids_tag_ids AS riti "
					"WHERE (riti.resource_id, resource_tag_id) = (%s, rt.id)) "
					"FROM resource_tags AS rt "
					"ORDER BY tag", (self.row_id,))
		for row in c.fetchall():
			tag_id = row[0]
			tag_name = row[1]
			rgba = Gdk.RGBA(1, 1, 1, 1)
			rgba.red = row[2]
			rgba.green = row[3]
			rgba.blue = row[4]
			rgba.alpha = row[5]
			applied = row[6]
			store.append([tag_id, tag_name, rgba, applied])

	def tag_toggled (self, cellrenderertoggle, path):
		store = self.builder.get_object('tags_applied_store')
		active = cellrenderertoggle.get_active()
		tag_id = store[path][0]
		store[path][3] = not active
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		resource_id = model[path][0]
		c = DB.cursor()
		if not active:
			c.execute("INSERT INTO resource_ids_tag_ids "
						"(resource_id, resource_tag_id) VALUES "
						"(%s, %s) "
						"ON CONFLICT (resource_id, resource_tag_id) "
						"DO NOTHING ", (resource_id, tag_id))
		else:
			c.execute("DELETE FROM resource_ids_tag_ids WHERE "
						"(resource_id, resource_tag_id) = "
						"(%s, %s)", (resource_id, tag_id))
		DB.commit()

	def tag_popover_closed (self, popover):
		self.populate_tag_flowbox()
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = self.resource_store.get_iter(path)
		self.populate_row_tag_list(iter_)

	def row_activated (self, treeview, path, treeview_column):
		if self.timeout_id:
			self.save_notes()
		self.row_id = self.resource_store[path][0]
		self.populate_notes()
		self.populate_tag_flowbox()
		self.populate_tags_applied_store()

	def populate_notes (self):
		if self.row_id == None:
			return
		self.cursor.execute("SELECT notes FROM resources "
							"WHERE id = %s", (self.row_id,))
		for row in self.cursor.fetchall():
			text = row[0]
			self.builder.get_object('notes_buffer').set_text(text)
			break
		else:
			self.builder.get_object('notes_buffer').set_text('')
		DB.rollback()

	def contact_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False # no match
		return True # it's a hit!

	def contact_match_selected(self, completion, model, iter_):
		contact_id = model[iter_][0]
		selection = self.builder.get_object('treeview-selection1')
		tree_model, path = selection.get_selected_rows()
		id_ = tree_model[path][0]
		self.cursor.execute("UPDATE resources "
							"SET (contact_id, phone_number) = "
							"(%s, (SELECT phone FROM contacts WHERE id = %s)) "
							"WHERE id = %s ",
							(contact_id, contact_id, id_))
		DB.commit()
		self.populate_resource_store()

	def contact_editing_started (self, renderer_combo, combobox, path):
		entry = combobox.get_child()
		entry.set_completion(self.contact_completion)

	def contact_changed (self, renderer_combo, path, tree_iter):
		contact_id = self.contact_store[tree_iter][0]
		id_ = self.resource_store[path][0]
		self.cursor.execute("UPDATE resources "
							"SET (contact_id, phone_number) = "
							"(%s, (SELECT phone FROM contacts WHERE id = %s)) "
							"WHERE id = %s",
							(contact_id, contact_id, id_))
		DB.commit()
		self.populate_resource_store()

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT "
								"id::text, "
								"name, "
								"ext_name, "
								"phone "
							"FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		active = self.builder.get_object('tag_combo').get_active()
		store = self.builder.get_object('tag_store')
		store.clear()
		store.append(['', 'All tags', Gdk.RGBA(0, 0, 0, 0)])
		self.cursor.execute("SELECT id::text, tag, red, green, blue, alpha "
							"FROM resource_tags "
							"ORDER BY tag")
		for row in self.cursor.fetchall():
			tag_id = row[0]
			tag_name = row[1]
			rgba = Gdk.RGBA(1, 1, 1, 1)
			rgba.red = row[2]
			rgba.green = row[3]
			rgba.blue = row[4]
			rgba.alpha = row[5]
			store.append([tag_id, tag_name, rgba])
		self.builder.get_object('tag_combo').set_active(active)
		DB.rollback()

	def new_entry_clicked (self, button):
		self.cursor.execute("INSERT INTO resources "
								"(tag_id) "
								"SELECT id FROM resource_tags "
									"WHERE finished = False LIMIT 1 "
								"RETURNING id")
		new_id = self.cursor.fetchone()[0]
		DB.commit()
		self.populate_resource_store(new = True)

	def post_entry_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		c = DB.cursor()
		c.execute("UPDATE resources SET posted = True WHERE id = %s; "
					"UPDATE time_clock_projects "
					"SET active = False "
					"WHERE resource_id = %s ", (row_id, row_id))
		DB.commit()
		self.populate_resource_store()
		self.builder.get_object('notes_buffer').set_text('')
		
	def subject_edited (self, renderer_text, path, text):
		self.editing = False
		id_ = self.resource_store[path][0]
		self.cursor.execute("UPDATE resources "
							"SET subject = %s "
							"WHERE id = %s", (text, id_))
		DB.commit()
		self.resource_store[path][1] = text

	def dated_for_calendar_day_selected (self, calendar):
		date = calendar.get_date()
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		id_ = model[path][0]
		self.cursor.execute("UPDATE resources "
							"SET dated_for = %s "
							"WHERE id = %s", (date, id_))
		DB.commit()
		self.populate_resource_store()

	def dated_for_editing_started (self, widget, entry, text):
		event = Gtk.get_current_event()
		rect = Gdk.Rectangle()
		rect.x = event.x
		rect.y = event.y + 30
		rect.width = rect.height = 1
		self.dated_for_calendar.set_pointing_to(rect)
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		row_id = model[path][0]
		self.cursor.execute("SELECT COALESCE(dated_for, CURRENT_DATE) "
							"FROM resources WHERE id = %s", (row_id,))
		for row in self.cursor.fetchall():
			self.dated_for_calendar.set_datetime(row[0])
		GLib.idle_add(self.dated_for_calendar.show) # this hides the entry
		DB.rollback()

	def tag_editing_started (self, renderer_combo, combobox, path):
		event = Gtk.get_current_event()
		rect = Gdk.Rectangle()
		rect.x = event.x
		rect.y = event.y + 30
		rect.width = rect.height = 1
		combobox.hide()
		popover = self.builder.get_object('tag_popover')
		popover.set_pointing_to(rect)
		GLib.idle_add(popover.show)

	def sort_by_combo_changed (self, combobox):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			id_ = model[path][0]
			self.populate_resource_store()
		else:
			self.populate_resource_store()

	def tag_combo_changed (self, combobox):
		tag_id = combobox.get_active_id()
		if tag_id == None:
			return
		if tag_id == '':
			self.join_filter = ''
		else:
			self.join_filter = 'JOIN resource_ids_tag_ids AS riti '\
								'ON riti.resource_id = rm.id '\
								'AND riti.resource_tag_id = %s' % tag_id
		self.populate_resource_store()

	def notes_buffer_changed (self, text_buffer):
		#only save changes created by user
		if not self.builder.get_object('textview1').is_focus():
			return
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		self.row_id = model[path][0]
		start = text_buffer.get_start_iter()
		end = text_buffer.get_end_iter()
		self.notes = text_buffer.get_text(start,end,True)
		if self.timeout_id:
			GLib.source_remove(self.timeout_id)
		self.timeout_id = GLib.timeout_add_seconds(10, self.save_notes)

	def save_notes (self ):
		if self.timeout_id:
			GLib.source_remove(self.timeout_id)
		self.cursor.execute("UPDATE resources SET notes = %s "
							"WHERE id = %s", (self.notes, self.row_id))
		DB.commit()
		self.timeout_id = None

	def populate_resource_store (self, new = False):
		id_ = None
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			id_ = model[path][0]
		self.resource_store.clear()
		self.builder.get_object('notes_buffer').set_text('')
		row_limit = self.builder.get_object('spinbutton1').get_value()
		sort = self.builder.get_object('sort_by_combo').get_active_id()
		c = DB.cursor()
		c.execute("SELECT "
					"rm.id, "
					"subject, "
					"COALESCE(contact_id, 0), "
					"COALESCE(name, ''), "
					"COALESCE(ext_name, ''), "
					"to_char(timed_seconds, 'HH24:MI:SS')::text AS time, "
					"dated_for::text, "
					"format_date(dated_for), "
					"'', "
					"phone_number, "
					"call_received_time::text, "
					"format_timestamp(call_received_time), "
					"to_do "
				"FROM resources AS rm "
				"%s "
				"LEFT JOIN contacts "
				"ON rm.contact_id = contacts.id "
				"WHERE (dated_for <= '%s' OR dated_for IS NULL) "
				"AND posted = False "
				"ORDER BY %s, rm.id "
				"LIMIT %s" % 
				(self.join_filter, self.older_than_date, sort, row_limit))
		for row in c.fetchall():
			row_id = row[0]
			iter_ = self.resource_store.append(row)
			self.populate_row_tag_list(iter_)
			if row_id == id_:
				selection.select_iter(iter_)
		c.close()
		self.populate_notes()
		if new == True:
			treeview = self.builder.get_object('treeview1')
			c = treeview.get_column(0)
			path = self.resource_store.get_path(iter_)
			treeview.set_cursor(path, c, True)
		DB.rollback()

	def populate_row_tag_list (self, iter_):
		row_id = self.resource_store[iter_][0]
		c = DB.cursor()
		tag_list = list()
		c.execute("SELECT "
					"red, "
					"green, "
					"blue, "
					"alpha "
					"FROM resources AS r "
					"JOIN resource_ids_tag_ids AS riti "
						"ON riti.resource_id = r.id "
					"JOIN resource_tags AS rt "
						"ON rt.id = riti.resource_tag_id "
					"WHERE r.id = %s ORDER BY rt.id", (row_id,))
		for row in c.fetchall():
			rgba = Gdk.RGBA(row[0], row[1], row[2], row[3])
			tag_list.append(rgba)
		self.resource_store[iter_][8] = tag_list
		
	def time_clock_project_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			self.show_message("Please select a row")
			return
		resource_id = model[path][0]
		subject = model[path][1]
		self.builder.get_object('project_name_entry').set_text(subject)
		dialog = self.builder.get_object('time_clock_create_dialog')
		result = dialog.run()
		dialog.hide()
		if result != Gtk.ResponseType.ACCEPT:
			return
		subject  = self.builder.get_object('project_name_entry').get_text()
		try:
			self.cursor.execute("INSERT INTO time_clock_projects "
								"(name, start_date, active, permanent, "
								"resource_id) "
								"VALUES (%s, now(), True, False, %s)"
								"ON CONFLICT (resource_id) "
								"DO UPDATE SET name = %s "
				  				"WHERE time_clock_projects.resource_id = %s", 
								(subject, resource_id, subject, resource_id))
		except Exception as e:
			self.show_message (e)
			DB.rollback ()
			return
		DB.commit()
		if self.builder.get_object('time_clock_checkbutton').get_active() == True:
			if not self.time_clock:
				import time_clock
				self.time_clock = time_clock.TimeClockGUI()
			else:
				self.time_clock.present()

	def older_than_entry_icon_released (self, entry, icon, event):
		self.older_than_calendar.set_relative_to(entry)
		self.older_than_calendar.show()

	def older_than_date_selected (self, calendar):
		date_text = calendar.get_text ()
		self.builder.get_object('entry1').set_text(date_text)
		self.older_than_date = calendar.get_date()
		if self.older_than_date == None:
			self.older_than_date = datetime.today()
		self.populate_resource_store ()

	def tags_activated (self, button):
		import resource_management_tags
		resource_management_tags.ResourceManagementTagsGUI ()

	def down_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = model.get_iter(path)
		iter_next = model.iter_next(iter_)
		model.move_after(iter_, iter_next)
		self.save_row_ordering()
		self.builder.get_object('sort_by_combo').set_active_id('sort')

	def up_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		iter_ = model.get_iter(path)
		iter_prev = model.iter_previous(iter_)
		model.move_before(iter_, iter_prev)
		self.save_row_ordering()
		self.builder.get_object('sort_by_combo').set_active_id('sort')

	def save_row_ordering (self):
		for row_count, row in enumerate (self.resource_store):
			row_id = row[0]
			self.cursor.execute("UPDATE resources "
								"SET sort = %s WHERE id = %s", 
								(row_count, row_id))
		DB.commit()

	def no_date_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		id_ = model[path][0]
		self.cursor.execute("UPDATE resources "
							"SET dated_for = NULL "
							"WHERE id = %s", ( id_, ))
		DB.commit()
		self.populate_resource_store()
		self.dated_for_calendar.hide()

	def to_do_toggled (self, renderer, path):
		active = not self.resource_store[path][12]
		self.resource_store[path][12] = active
		id_ = self.resource_store[path][0]
		self.cursor.execute("UPDATE resources SET to_do = %s "
							"WHERE id = %s", (active, id_))
		DB.commit()
		
	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

	def treeview_key_release_event (self, treeview, event):
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab" or keyname=="Esc":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			if keyname == 'Tab':
				GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)
			elif keyname == 'Escape':
				pass




