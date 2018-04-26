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

from gi.repository import Gtk, GLib, Gdk
from datetime import datetime, date
from dateutils import DateTimeCalendar, seconds_to_compact_string, datetime_to_text,\
						text_to_datetime, seconds_to_user_format

UI_FILE = "src/resource_management.ui"

class ResourceManagementGUI:
	def __init__(self, db, id_ = None):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.editing = False
		self.timer_timeout = None
		
		self.resource_store = self.builder.get_object('resource_store')
		self.contact_store = self.builder.get_object('contact_store')
		self.contact_completion = self.builder.get_object('contact_completion')
		self.contact_completion.set_match_func(self.contact_match_func)
		self.tag_store = self.builder.get_object('tag_store')

		self.dated_for_calendar = DateTimeCalendar()
		no_date_button = self.builder.get_object('button5')
		self.dated_for_calendar.pack_start(no_date_button)
		date_label = self.builder.get_object('treeviewcolumn5').get_widget()
		self.dated_for_calendar.set_relative_to(date_label)
		self.dated_for_calendar.connect('day-selected', self.dated_for_calendar_day_selected )
		
		self.older_than_calendar = DateTimeCalendar()
		self.older_than_calendar.set_today()
		self.older_than_calendar.connect('day-selected', self.older_than_date_selected )
		self.older_than_calendar.set_today()
		self.populate_stores()
		self.populate_resource_store ()

		if id_ != None:
			selection = self.builder.get_object('treeview-selection1')
			for row in self.resource_store:
				if row[0] == id_:
					selection.select_path(row.path)
			self.editing_buffer = True
			self.cursor.execute("SELECT notes FROM resources "
								"WHERE id = %s", (id_,))
			for row in self.cursor.fetchall():
				text = row[0]
				self.builder.get_object('textbuffer1').set_text(text)
				break
			else:
				self.builder.get_object('textbuffer1').set_text('')
		self.editing_buffer = False
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def focus_in_event (self, window, event):
		self.populate_stores ()

	def unfinished_only_toggled (self, togglebutton):
		self.populate_resource_store ()
	
	def row_limit_value_changed (self, spinbutton):
		self.populate_resource_store ()

	def resource_threaded_checkbutton_toggled (self, checkbutton):
		self.populate_resource_store ()

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def delete_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			row_id = model[path][0]
			try:
				self.cursor.execute("DELETE FROM resources "
									"WHERE id = %s", (row_id,))
				self.db.commit()
			except Exception as e:
				print (e)
				self.db.rollback()
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
				self.db.commit()
			except Exception as e:
				print (e)
				self.db.rollback()

	def row_activated (self, treeview, path, treeview_column):
		self.editing_buffer = True
		row_id = self.resource_store[path][0]
		self.cursor.execute("SELECT notes FROM resources "
							"WHERE id = %s", (row_id,))
		for row in self.cursor.fetchall():
			text = row[0]
			self.builder.get_object('textbuffer1').set_text(text)
			break
		else:
			self.builder.get_object('textbuffer1').set_text('')
		self.editing_buffer = False

	def contact_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False # no match
		return True # it's a hit!

	def contact_match_selected(self, completion, model, iter):
		self.editing = False
		contact_id = model[iter][0]
		contact_name = model[iter][1]
		contact_phone = model[iter][3]
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			model[path][2] = int(contact_id)
			model[path][3] = contact_name
			model[path][11] = contact_phone
		self.save_row (str(path[0]))

	def contact_editing_started (self, renderer_combo, combobox, path):
		self.editing = True
		entry = combobox.get_child()
		entry.set_completion(self.contact_completion)

	def contact_changed (self, renderer_combo, path, tree_iter):
		contact_id = self.contact_store[tree_iter][0]
		contact_name = self.contact_store[tree_iter][1]
		contact_phone = self.contact_store[tree_iter][3]
		self.resource_store[path][2] = int(contact_id)
		self.resource_store[path][3] = contact_name
		self.resource_store[path][11] = contact_phone
		self.editing = False
		self.save_row (path)

	def contact_edited (self, renderer_combo, path, text):
		self.editing = False

	def contact_editing_canceled (self, renderer):
		self.editing = False

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name, phone FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			ext_name = row[2]
			contact_phone = row[3]
			self.contact_store.append([contact_id, contact_name, ext_name, contact_phone])
		self.tag_store.clear()
		self.cursor.execute("SELECT id, tag, red, green, blue, alpha "
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
			self.tag_store.append([str(tag_id), tag_name, rgba])
			for row in self.resource_store:
				if row[8] == tag_id:
					row[10] = rgba

	def new_top_level_clicked (self, button):
		self.resource_store.append(None,[0, 'New subject', 0, '', False, 0,  '',
										'', 0, '', Gdk.RGBA(0,0,0,1), 
										'0', 0, '', False])

	def child_of_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		child_id = model[path][0] 
		dialog = self.builder.get_object('parent_dialog')
		result = dialog.run()
		dialog.hide()
		if result == Gtk.ResponseType.ACCEPT:
			selection = self.builder.get_object('treeview-selection2')
			model, path = selection.get_selected_rows()
			parent_id = model[path][0]
			if child_id == parent_id:
				return
			self.cursor.execute("UPDATE resources "
								"SET parent_id = %s WHERE id = %s", 
								(parent_id, child_id))
			self.db.commit()
			
	def new_child_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			tree_iter = model.get_iter(path)
			self.resource_store.append(tree_iter,[0, 'New child', 0, '',
							False, 0, '', '', 0, '', Gdk.RGBA(0,0,0,1), 
							0, 0, '', False])
															
	def subject_editing_started (self, renderer_entry, entry, path):
		self.editing = True
		
	def subject_edited (self, renderer_text, path, text):
		self.editing = False
		self.resource_store[path][1] = text
		self.save_row (path)

	def subject_editing_canceled (self, renderer):
		self.editing = False

	def dated_for_calendar_day_selected (self, calendar):
		text = calendar.get_text()
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		model[path][7] = text
		p = path[0]
		self.save_row (str(p))

	def dated_for_editing_started (self, widget, entry, text):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		text = model[path][7]
		if text == '':
			self.dated_for_calendar.set_today()
		else:
			date_time = text_to_datetime (text)
			self.dated_for_calendar.set_datetime(date_time)
		self.dated_for_calendar.show()

	def tag_editing_started (self, renderer_combo, combobox, path):
		self.editing = True

	def tag_changed (self, renderer_combo, path, tree_iter):
		self.editing = False
		tag_id = self.tag_store[tree_iter][0]
		self.cursor.execute("SELECT tag, red, green, blue, alpha "
							"FROM resource_tags "
							"WHERE id = %s", (tag_id,))
		for row in self.cursor.fetchall():
			tag_name = row[0]
			red = row[1]
			green = row[2]
			blue = row[3]
			alpha = row[4]
			rgba = Gdk.RGBA(red, green, blue, alpha)
			self.resource_store[path][8] = int(tag_id)
			self.resource_store[path][9] = tag_name
			self.resource_store[path][10] = rgba
		self.save_row (path)
		self.populate_resource_store ()

	def tag_editing_canceled (self, renderer):
		self.editing = False

	def turn_off_timer (self, store, treeiter, selected_path):
		while treeiter != None:
			path = store.get_path(treeiter)
			if path != selected_path:
				if store[path][4] == True:
					GLib.source_remove(self.timer_timeout)
					store[path][4] = False
			if store.iter_has_child(treeiter):
				childiter = store.iter_children(treeiter)
				self.turn_off_timer(store, childiter, selected_path)
			treeiter = store.iter_next(treeiter)

	def timed_toggled (self, renderer, path):
		selected_path = Gtk.TreePath(path)
		tree_iter = self.resource_store.get_iter_first()
		self.turn_off_timer (self.resource_store, tree_iter, selected_path)
		active = not self.resource_store[path][4]
		self.resource_store[path][4] = active
		if active == True:
			self.time = self.resource_store[path][5]
			self.timer_timeout = GLib.timeout_add_seconds(1, self.track_time, path)
		else:
			GLib.source_remove(self.timer_timeout)

	def track_time (self, path):
		self.time += 1
		if self.time % 60 == 0:
			row_id = self.resource_store[path][0]
			self.cursor.execute("UPDATE resources "
								"SET timed_seconds = %s WHERE id = %s", 
								(self.time, row_id))
			self.db.commit()
		if self.editing == False:
			self.resource_store[path][5] = self.time
			self.resource_store[path][6] = seconds_to_compact_string (self.time)
		return True

	def text_buffer_changed (self, textbuffer):
		self.save_notes ()

	def save_notes (self):
		if self.editing_buffer == True:
			return
		text_buffer = self.builder.get_object('textbuffer1')
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		if row_id != 0:
			start = text_buffer.get_start_iter()
			end = text_buffer.get_end_iter()
			notes = text_buffer.get_text(start,end,True)
			self.cursor.execute("UPDATE resources SET notes = %s "
								"WHERE id = %s", (notes, row_id))
			self.db.commit()

	def save_row (self, path):
		split_path = path.split(':')
		if len(split_path) > 1:
			split_path.pop()
		parent_path = split_path[-1]
		parent_id = self.resource_store[parent_path][0]
		if parent_id == 0:
			parent_id = None
		line = self.resource_store[path]
		row_id = line[0]
		subject = line[1]
		contact_id = line[2]
		time_seconds = line[5]
		dated_for = line[7]
		tag_id = line[8]
		phone_number = line[11]
		if tag_id == 0:
			tag_id = None
		if contact_id == 0:
			contact_id = None
		if dated_for == '' :
			dated_for = None
		else:
			dated_for = text_to_datetime (dated_for)
		if row_id == 0:
			self.cursor.execute("INSERT INTO resources "
								"(subject, contact_id, timed_seconds, "
								"date_created, dated_for, tag_id, parent_id, "
								"phone_number) "
								"VALUES (%s, %s, %s, CURRENT_DATE, "
								"%s, %s, %s, %s) "
								"RETURNING id", 
								(subject, contact_id, time_seconds, 
								dated_for, tag_id, parent_id, phone_number))
			line[0] = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE resources "
								"SET (subject, contact_id, timed_seconds, "
								"dated_for, tag_id, phone_number) = "
								"(%s, %s, %s, %s, %s, %s) "
								"WHERE id = %s", 
								(subject, contact_id, time_seconds, 
								dated_for, tag_id, phone_number, row_id))
		self.save_notes ()
		self.db.commit()

	def populate_resource_store (self):
		self.resource_store.clear()
		row_limit = self.builder.get_object('spinbutton1').get_value()
		finished = self.builder.get_object('checkbutton3').get_active()
		if self.builder.get_object('checkbutton2').get_active() == True:
			self.populate_resource_store_threaded (row_limit, finished)
		else:
			self.populate_resource_store_flat (row_limit, finished)

	def populate_resource_store_flat (self, row_limit, finished):
		self.cursor.execute("SELECT rm.id, subject, "
							"COALESCE(contact_id, 0), "
							"COALESCE(name, ''), "
							"timed_seconds, dated_for, format_date(dated_for), "
							"rmt.id, tag, red, "
							"green, blue, alpha, phone_number, "
							"call_received_time, to_do "
							"FROM resources AS rm "
							"LEFT JOIN resource_tags AS rmt "
							"ON rmt.id = rm.tag_id "
							"LEFT JOIN contacts "
							"ON rm.contact_id = contacts.id "
							"WHERE date_created <= %s "
							"AND finished != %s OR finished IS NULL "
							"AND diary = False "
							"LIMIT %s", (self.older_than_date, finished, 
							row_limit))
		for row in self.cursor.fetchall():
			rgba = Gdk.RGBA(1, 1, 1, 1)
			row_id = row[0]
			subject = row[1]
			contact_id = row[2]
			contact_name = row[3]
			timed_seconds = row[4]
			dated_for = row[5]
			date_formatted = row[6]
			tag_id = row[7]
			tag_name = row[8]
			if tag_id == None:
				tag_id = 0
				tag_name = ''
			else:
				rgba.red = row[9]
				rgba.green = row[10]
				rgba.blue = row[11]
				rgba.alpha = row[12]
			phone_number = row[13]
			call_received_time = row[14]
			to_do = row[15]
			c_r_time_formatted = seconds_to_user_format(call_received_time)
			time_formatted = seconds_to_compact_string (timed_seconds)
			self.resource_store.append(None,[row_id, subject, contact_id,
										contact_name, False, timed_seconds, 
										time_formatted, date_formatted, tag_id, 
										tag_name, rgba, phone_number,
										call_received_time, 
										c_r_time_formatted, to_do])

	def populate_resource_store_threaded (self, row_limit, finished):
		self.cursor.execute("SELECT rm.id, subject, contact_id, name, "
							"timed_seconds, dated_for, rmt.id, tag, red, "
							"green, blue, alpha, phone_number, "
							"call_received_time, to_do "
							"FROM resources AS rm "
							"LEFT JOIN resource_tags AS rmt "
							"ON rmt.id = rm.tag_id "
							"LEFT JOIN contacts "
							"ON rm.contact_id = contacts.id "
							"WHERE (finished != %s OR finished IS NULL) "
							"AND date_created <= %s AND parent_id IS NULL "
							"AND diary = False "
							"LIMIT %s", (finished, self.older_than_date,  
							row_limit))
		for row in self.cursor.fetchall():
			rgba = Gdk.RGBA(1, 1, 1, 1)
			row_id = row[0]
			subject = row[1]
			contact_id = row[2]
			contact_name = row[3]
			timed_seconds = row[4]
			dated_for = row[5]
			tag_id = row[6]
			tag_name = row[7]
			if tag_id == None:
				tag_id = 0
				tag_name = ''
			else:
				rgba.red = row[8]
				rgba.green = row[9]
				rgba.blue = row[10]
				rgba.alpha = row[11]
			phone_number = row[12]
			call_received_time = row[13]
			to_do = row[14]
			c_r_time_formatted = seconds_to_user_format(call_received_time)
			if contact_id == None:
				contact_id = 0
				contact_name = ''
			time_formatted = seconds_to_compact_string (timed_seconds)
			date_formatted = datetime_to_text(dated_for)
			parent_iter = self.resource_store.append(None,[row_id, subject, 
													contact_id,contact_name, 
													False, timed_seconds, 
													time_formatted, 
													date_formatted, tag_id, 
													tag_name, rgba, 
													phone_number,
													call_received_time,
													c_r_time_formatted, to_do])
			self.add_resource_children (row_id, parent_iter, finished)

	def add_resource_children (self, parent_id, parent_iter, finished):
		self.cursor.execute("SELECT rm.id, subject, contact_id, name, "
							"timed_seconds, dated_for, rmt.id, tag, red, "
							"green, blue, alpha, phone_number, "
							"call_received_time, to_do "
							"FROM resources AS rm "
							"LEFT JOIN resource_tags AS rmt "
							"ON rmt.id = rm.tag_id "
							"LEFT JOIN contacts "
							"ON rm.contact_id = contacts.id "
							"WHERE rm.parent_id = %s "
							"AND (finished != %s OR finished IS NULL) "
							"AND diary = False", 
							(parent_id, finished ))
		for row in self.cursor.fetchall():
			rgba = Gdk.RGBA(1, 1, 1, 1)
			row_id = row[0]
			subject = row[1]
			contact_id = row[2]
			contact_name = row[3]
			timed_seconds = row[4]
			dated_for = row[5]
			tag_id = row[6]
			tag_name = row[7]
			if tag_id == None:
				tag_id = 0
				tag_name = ''
			else:
				rgba.red = row[8]
				rgba.green = row[9]
				rgba.blue = row[10]
				rgba.alpha = row[11]
			phone_number = row[12]
			call_received_time = row[13]
			to_do = row[14]
			c_r_time_formatted = seconds_to_user_format(call_received_time)
			if contact_id == None:
				contact_id = 0
				contact_name = ''
			time_formatted = seconds_to_compact_string (timed_seconds)
			date_formatted = datetime_to_text(dated_for)
			parent = self.resource_store.append(parent_iter,
															[row_id, 
															subject, 
															contact_id, 
															contact_name, 
															False, 
															timed_seconds, 
															time_formatted, 
															date_formatted, 
															tag_id, 
															tag_name, rgba, 
															phone_number,
															call_received_time,
															c_r_time_formatted,
															to_do])
			self.add_resource_children (row_id, parent, finished)
		
	def older_than_entry_icon_released (self, entry, icon, event):
		self.older_than_calendar.set_relative_to(entry)
		self.older_than_calendar.show()

	def older_than_date_selected (self, calendar):
		date_text = calendar.get_text ()
		self.builder.get_object('entry1').set_text(date_text)
		self.older_than_date = calendar.get_date()
		self.populate_resource_store ()

	def tags_clicked (self, button):
		import resource_management_tags
		resource_management_tags.ResourceManagementTagsGUI (self.db)

	def no_date_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		model[path][7] = ''
		p = path[0]
		self.save_row (str(p))
		self.dated_for_calendar.hide()

	def to_do_toggled (self, renderer, path):
		active = not self.resource_store[path][14]
		self.resource_store[path][14] = active
		id_ = self.resource_store[path][0]
		self.cursor.execute("UPDATE resources SET to_do = %s "
							"WHERE id = %s", (active, id_))
		self.db.commit()


		


		
