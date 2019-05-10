# resource_calendar.py
# Copyright (C) 2017 reuben 
# 
# pygtk-calendar is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# pygtk-calendar is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
from dateutils import calendar_to_datetime, set_calendar_from_datetime 
import constants

UI_FILE = constants.ui_directory + "/resource_calendar.ui"


class ResourceCalendarGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = constants.db
		self.cursor = self.db.cursor()

		self.date_time = datetime.today ()
		
		self.day_detail_store = self.builder.get_object('day_detail_store')
		self.tag_store = self.builder.get_object('tag_store')
		self.contact_store = self.builder.get_object('contact_store')
		self.contact_completion = self.builder.get_object('contact_completion')
		self.contact_completion.set_match_func(self.contact_match_func)

		
		box = self.builder.get_object('box2')
		self.popover = Gtk.Popover()
		self.popover.add(box)
		
		self.populate_stores ()
				
		calendar = self.builder.get_object('calendar1')
		calendar.set_detail_func(self.calendar_func)
		today = datetime.today()
		set_calendar_from_datetime(calendar, today)
		
		window = self.builder.get_object('window')
		window.show_all()
		window.maximize()

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			contact_id = row[0]
			contact_name = row[1]
			self.contact_store.append([str(contact_id), contact_name])
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
			self.tag_store.append([str(tag_id), tag_name])

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def convert_to_diary_activated (self, menuitem):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return # nothing selected
		date = self.date_time.date()
		new_diary_id = model[path][0]
		new_diary_text = model[path][1]
		self.cursor.execute("SELECT id, subject FROM resources "
							"WHERE (dated_for, diary) = (%s, True)", 
							(date,))
		for row in self.cursor.fetchall():
			self.builder.get_object('edit_window').set_keep_above(False)
			existing_diary_id = row[0]
			existing_text = row[1]
			if existing_text == None:
				existing_text = ''
			self.builder.get_object('textbuffer2').set_text(new_diary_text)
			self.builder.get_object('textbuffer3').set_text(existing_text)
			dialog = self.builder.get_object('diary_exists_dialog')
			result = dialog.run()
			if result == Gtk.ResponseType.ACCEPT:
				self.merge_existing_and_new_diary (new_diary_id, 
															existing_diary_id)
			dialog.hide()
			break 
		else:
			self.cursor.execute("UPDATE resources "
								"SET (diary, contact_id) = (True, NULL) "
								"WHERE id = %s", 
								(new_diary_id,))
		self.populate_day_detail_store ()
		self.db.commit()

	def merge_existing_and_new_diary (self, new_id, existing_id):
		existing_buffer = self.builder.get_object('textbuffer2')
		start = existing_buffer.get_start_iter()
		end = existing_buffer.get_end_iter()
		existing_text = existing_buffer.get_text(start, end, True)
		
		new_buffer = self.builder.get_object('textbuffer3')
		start = new_buffer.get_start_iter()
		end = new_buffer.get_end_iter()
		new_text = new_buffer.get_text(start, end, True)

		text = existing_text + new_text
		self.cursor.execute("UPDATE resources SET subject = %s "
							"WHERE id = %s; "
							"DELETE FROM resources WHERE id = %s;",
							(text, existing_id, new_id))

	def calendar_button_release_event (self, calendar, event):
		rect = Gdk.Rectangle()
		allocation = calendar.get_allocation()
		rect.x = event.x - allocation.x
		rect.y = event.y - allocation.y
		rect.width = 1
		rect.heigth = 1
		if event.button == 3:
			self.populate_stores ()
			self.popover.set_pointing_to (rect)
			self.popover.set_relative_to (calendar)
			self.popover.show_all ()

	def edit_window_delete (self, window, event):
		window.hide_on_delete ()
		return True

	def load_resource_edit_store (self, date_time):
		return
		self.resource_edit_store.clear ()
		self.cursor.execute("SELECT rm.id, subject, c.id, c.name, rmt.id, "
							"rmt.tag, red, green, blue, alpha, tag_id "
							"FROM resources AS rm "
							"LEFT JOIN contacts AS c "
							"ON rm.contact_id = c.id "
							"LEFT JOIN resource_tags AS rmt "
							"ON rm.tag_id = rmt.id "
							"WHERE dated_for = %s", 
							(date_time,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			subject = row[1]
			contact_id = row[2]
			contact_name = row[3]
			tag_id = row[4]
			tag_name = row[5]
			red = row[6]
			green = row[7]
			blue = row[8]
			alpha = row[9]
			tag_id = row[10]
			if tag_id == None or tag_id == 0:
				rgba = Gdk.RGBA(1, 1, 1, 0)
			else:
				rgba = Gdk.RGBA(red, green, blue, alpha)
			self.resource_edit_store.append([row_id, subject, contact_id, 
											contact_name, tag_id, tag_name, 
											rgba])

	def save_resource_edit_store_path (self, path):
		date = self.builder.get_object('calendar1').get_date()
		dated_for = calendar_to_datetime(date)
		line = self.day_detail_store[path]
		resource_id = line[0]
		subject = line[1]
		contact_id = line[2]
		tag_id = line[4]
		if contact_id == 0:
			contact_id = None
		if tag_id == 0:
			tag_id = None
		if resource_id == 0:
			self.cursor.execute("INSERT INTO resources "
								"(subject, contact_id, tag_id, "
								"date_created, dated_for) "
								"VALUES (%s, %s, %s, %s, %s)", 
								(subject, contact_id, tag_id, 
								datetime.today(), dated_for))
		else:
			self.cursor.execute("UPDATE resources "
								"SET (subject, contact_id, tag_id) = "
								"(%s, %s, %s) WHERE id = %s", 
								(subject, contact_id, tag_id, resource_id))
		self.db.commit()
		self.builder.get_object('calendar1').emit('day-selected')

	def subject_edited (self, renderer, path, text):
		self.day_detail_store[path][1] = text
		self.save_resource_edit_store_path (path)

	def tag_combo_changed (self, combo, path, tree_iter):
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
			self.day_detail_store[path][4] = int(tag_id)
			self.day_detail_store[path][5] = tag_name
			self.day_detail_store[path][6] = rgba
		self.save_resource_edit_store_path (path)

	def tags_clicked (self, button):
		import resource_management_tags
		resource_management_tags.ResourceManagementTagsGUI ()

	def textview_focus_out_event (self, textview, event):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return # nothing selected
		resource_id = model[path][0]
		notes_buffer = self.builder.get_object ('textbuffer1')
		start = notes_buffer.get_start_iter()
		end = notes_buffer.get_end_iter()
		notes = notes_buffer.get_text(start,end,True)
		self.cursor.execute("UPDATE resources SET notes = %s"
							"WHERE id = %s", (notes, resource_id))
		self.db.commit()

	def edit_calendar_day_selected (self, calendar):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return # no row selected
		date = calendar.get_date ()
		resource_id = model[path][0]
		self.cursor.execute ("UPDATE resources SET dated_for = %s "
							"WHERE id = %s", (date, resource_id))
		self.db.commit()
		self.builder.get_object('calendar1').emit('day-selected')

	def contact_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter][1].lower():
				return False # no match
		return True # it's a hit!

	def contact_combo_editing_started (self, combo_renderer, combobox, path):
		entry = combobox.get_child()
		entry.set_completion (self.contact_completion)
			
	def contact_match_selected (self, completion, model, tree_iter):
		contact_id = model[tree_iter][0]
		contact_name = model[tree_iter][1]
		self.contact_selected (contact_id, contact_name)

	def contact_combo_changed (self, combo, path, tree_iter):
		contact_id = self.contact_store[tree_iter][0]
		contact_name = self.contact_store[tree_iter][1]
		self.contact_selected (contact_id, contact_name)
			
	def contact_selected (self, contact_id, contact_name):
		selection = self.builder.get_object ('treeview-selection')
		model, path = selection.get_selected_rows ()
		model[path][2] = int(contact_id)
		model[path][3] = contact_name
		self.save_resource_edit_store_path (path)

	def new_resource_clicked (self, button):
		black = Gdk.RGBA(0, 0, 0, 1)
		self.day_detail_store.append([0, 'New Subject', 0, '', 0, '', black])
		last = self.day_detail_store.iter_n_children ()
		last -= 1 #iter_n_children starts at 1 ; set_cursor starts at 0
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(0)
		treeview.set_cursor(last , c, True)	#set the cursor to the last appended item

	def delete_resource_clicked (self, button):
		selection = self.builder.get_object ('treeview-selection')
		model, path = selection.get_selected_rows ()
		if path != []:
			resource_id = model[path][0]
			self.cursor.execute("DELETE FROM resources "
								"WHERE id = %s", (resource_id,))
			self.db.commit ()
		self.builder.get_object('calendar1').emit('day-selected')
		
	def day_selected (self, calendar):
		self.date_time = calendar_to_datetime (calendar.get_date())
		self.populate_day_detail_store ()

	def populate_day_detail_store (self):
		self.builder.get_object('textbuffer1').set_text('')
		self.day_detail_store.clear()
		self.cursor.execute("SELECT rm.id, subject, c.id, c.name, rmt.id, "
							"rmt.tag, red, green, blue, alpha, tag_id "
							"FROM resources AS rm "
							"LEFT JOIN contacts AS c "
							"ON rm.contact_id = c.id "
							"LEFT JOIN resource_tags AS rmt "
							"ON rm.tag_id = rmt.id "
							"WHERE dated_for = %s", 
							(self.date_time,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			subject = row[1]
			contact_id = row[2]
			contact_name = row[3]
			tag_id = row[4]
			tag_name = row[5]
			red = row[6]
			green = row[7]
			blue = row[8]
			alpha = row[9]
			tag_id = row[10]
			if tag_id == None or tag_id == 0:
				rgba = Gdk.RGBA(1, 1, 1, 0)
			else:
				rgba = Gdk.RGBA(red, green, blue, alpha)
			self.day_detail_store.append([row_id, subject, contact_id, 
											contact_name, tag_id, tag_name, 
											rgba])
		
	def day_detail_activated (self, treeview, path, treeviewcolumn):
		self.resource_id = self.day_detail_store[path][0]
		self.cursor.execute("SELECT notes FROM resources "
							"WHERE id = %s", (self.resource_id,))
		for row in self.cursor.fetchall():
			notes = row[0]
			self.builder.get_object('textbuffer1').set_text(notes)

	def calendar_func (self, calendar, year, month, day):
		date = "%s %s %s" % (month+1, day, year)
		date_time = datetime.strptime(date, "%m %d %Y")
		string = str()
		self.cursor.execute("SELECT subject, red, green, blue, alpha, "
							"COALESCE(' : ' || name, '') "
							"FROM resources AS rm "
							"LEFT JOIN contacts "
							"ON contacts.id = rm.contact_id "
							"JOIN resource_tags AS rmt "
							"ON rm.tag_id = rmt.id WHERE dated_for = %s "
							"AND finished != True", 
							(date_time, ))
		for row in self.cursor.fetchall():
			subject = row[0]
			red = row[1]
			green = row[2]
			blue = row[3]
			alpha = row[4]
			contact_name = row[5]
			hex_color = '#%02x%02x%02x%02x' %  (int(red*255),
												int(green*255),
												int(blue*255),
												int(alpha*255))
			string += "<span foreground='%s' weight='bold'>%s%s</span>\n" % (
											hex_color, subject, contact_name)
		return string

	def resource_management_clicked (self,button):
		import resource_management
		resource_management.ResourceManagementGUI()

	def window_key_press_event (self, window, event):
		treeview = self.builder.get_object('treeview2')
		keyname = Gdk.keyval_name(event.keyval)
		path, col = treeview.get_cursor()
		# only visible columns!!
		columns = [c for c in treeview.get_columns() if c.get_visible()]
		colnum = columns.index(col)
		if keyname=="Tab":
			if colnum + 1 < len(columns):
				next_column = columns[colnum + 1]
			else:
				tmodel = treeview.get_model()
				titer = tmodel.iter_next(tmodel.get_iter(path))
				if titer is None:
					titer = tmodel.get_iter_first()
					path = tmodel.get_path(titer)
					next_column = columns[0]
			GLib.timeout_add(10, treeview.set_cursor, path, next_column, True)


			

