# resource_calendar.py
# Copyright (C) 2017 reuben 
# 
# resource_calendar is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# resource_calendar is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, GLib
from datetime import datetime
from dateutils import calendar_to_datetime, \
						set_calendar_from_datetime, \
						calendar_to_text
from constants import ui_directory, DB
from main import get_apsw_connection
try:
	import holidays
	us_holidays = holidays.US()
except ImportError as e:
	us_holidays = None
	print (e, ", please install from "
			"https://github.com/dr-prodigy/python-holidays")

UI_FILE = ui_directory + "/resources/resource_calendar.ui"


class ResourceCalendarGUI:
	where_clause = ''
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.date_time = datetime.today ()
		self.day_detail_store = self.builder.get_object('day_detail_store')
		self.category_store = self.builder.get_object('category_store')
		self.contact_store = self.builder.get_object('contact_store')
		self.type_store = self.builder.get_object('type_store')
		self.contact_completion = self.builder.get_object('contact_completion')
		self.contact_completion.set_match_func(self.contact_match_func)
		
		self.window = self.builder.get_object('window')
		self.window.maximize()
		self.window.show_all()

		self.popover = self.builder.get_object('popover_window')
		self.populate_stores ()
		self.calendar = self.builder.get_object('calendar1')
		self.calendar.set_detail_func(self.calendar_func)
		today = datetime.today()
		set_calendar_from_datetime(self.calendar, today)
		
		GLib.idle_add(self.set_widget_sizes)

	def set_widget_sizes (self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'pane1'")
		self.builder.get_object('pane1').set_position(c.fetchone()[0])
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'pane2'")
		self.builder.get_object('pane2').set_position(c.fetchone()[0])
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'show_details_checkbutton'")
		active = bool(c.fetchone()[0])
		self.builder.get_object('show_detail_checkbutton').set_active(active)
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'row_height_value'")
		value = c.fetchone()[0]
		self.builder.get_object('row_height_spinbutton').set_value(value)
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'row_width_value'")
		value = c.fetchone()[0]
		self.builder.get_object('row_width_spinbutton').set_value(value)
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'edit_window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT size FROM resource_calendar "
					"WHERE widget_id = 'edit_window_height'")
		height = c.fetchone()[0]
		self.builder.get_object('popover_window').resize(width, height)
		c.execute("SELECT widget_id, size FROM resource_calendar WHERE "
					"widget_id IN "
						"('subject_column', "
						"'qty_column', "
						"'type_column', "
						"'contact_column', " 
						"'category_column')")
		for row in c.fetchall():
			width = row[1]
			column = self.builder.get_object(row[0])
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()
		GLib.timeout_add(20, self.center_calendar_horizontal_scroll)

	def center_calendar_horizontal_scroll (self):
		adjustment = self.builder.get_object('calendar_width_scroll_adjustment')
		upper = adjustment.get_upper()
		page_size = adjustment.get_page_size()
		adjustment.set_value ((upper - page_size) / 2)

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		position = self.builder.get_object('pane1').get_position()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('pane1', ?)", (position,))
		position = self.builder.get_object('pane2').get_position()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('pane2', ?)", (position,))
		active = self.builder.get_object('show_detail_checkbutton').get_active()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('show_details_checkbutton', ?)", (active,))
		value = self.builder.get_object('row_height_spinbutton').get_value()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('row_height_value', ?)", (value,))
		value = self.builder.get_object('row_width_spinbutton').get_value()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('row_width_value', ?)", (value,))
		width, height = self.builder.get_object('popover_window').get_size()
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('edit_window_width', ?)", (width,))
		c.execute("REPLACE INTO resource_calendar (widget_id, size) "
					"VALUES ('edit_window_height', ?)", (height,))
		for column in ['subject_column', 
						'qty_column', 
						'type_column', 
						'contact_column', 
						'category_column']:
			try:
				width = self.builder.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO resource_calendar (widget_id, size) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def destroy (self, widget):
		self.cursor.close()

	def populate_stores (self):
		self.contact_store.clear()
		self.cursor.execute("SELECT id::text, name, ext_name FROM contacts "
							"WHERE deleted = False ORDER BY name")
		for row in self.cursor.fetchall():
			self.contact_store.append(row)
		self.category_store.clear()
		self.cursor.execute("SELECT id::text, tag, red, green, blue, alpha "
							"FROM resource_tags WHERE finished = False "
							"ORDER BY tag")
		for row in self.cursor.fetchall():
			tag_id = row[0]
			tag_name = row[1]
			rgba = Gdk.RGBA(1, 1, 1, 1)
			rgba.red = row[2]
			rgba.green = row[3]
			rgba.blue = row[4]
			rgba.alpha = row[5]
			self.category_store.append([tag_id, tag_name])
		self.type_store.clear()
		self.cursor.execute("SELECT id::text, name FROM resource_types "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.type_store.append(row)
		DB.rollback()

	def row_height_value_changed (self, spinbutton):
		value = spinbutton.get_value_as_int()
		self.calendar.set_detail_height_rows(value)
		self.calendar.queue_resize()

	def row_width_value_changed (self, spinbutton):
		value = spinbutton.get_value_as_int()
		self.calendar.set_detail_width_chars(value)
		self.calendar.queue_resize()

	def details_toggled (self, togglebutton):
		visible = togglebutton.get_active()
		self.builder.get_object('details_box').set_visible(visible)

	def calendar_scroll_event (self, widget, event):
		if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
			return False # let the calendar change the month, else
		# explicitly redirect scroll events to the calendar scrolled window
		event.window = self.builder.get_object('scrolled_window').get_window()
		event.put()
		return True

	def calendar_button_release_event (self, calendar, event):
		if event.button == 3:
			self.popover.show_all ()

	def subject_edited (self, renderer, path, text):
		row_id = self.day_detail_store[path][0]
		self.day_detail_store[path][1] = text
		self.cursor.execute("UPDATE resources SET subject = %s "
							"WHERE id = %s", (text, row_id))
		DB.commit()

	def qty_edited (self, cellrenderertext, path, text):
		row_id = self.day_detail_store[path][0]
		self.day_detail_store[path][2] = int(text)
		self.cursor.execute("UPDATE resources SET qty = %s "
							"WHERE id = %s", (text, row_id))
		DB.commit()

	def type_changed (self, cellrenderercombo, path, treeiter):
		row_id = self.day_detail_store[path][0]
		type_id = self.type_store[treeiter][0]
		type_name = self.type_store[treeiter][1]
		self.day_detail_store[path][3] = int(type_id)
		self.day_detail_store[path][4] = type_name
		self.cursor.execute("UPDATE resources SET resource_type_id = %s "
							"WHERE id = %s", (type_id, row_id))
		DB.commit()

	def tag_combo_changed (self, combo, path, tree_iter):
		row_id = self.day_detail_store[path][0]
		tag_id = self.category_store[tree_iter][0]
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
			self.day_detail_store[path][7] = int(tag_id)
			self.day_detail_store[path][8] = tag_name
			self.day_detail_store[path][9] = rgba
		self.cursor.execute("UPDATE resources SET tag_id = %s "
							"WHERE id = %s", (tag_id, row_id))
		DB.commit()

	def edit_calendar_day_selected (self, calendar):
		selection = self.builder.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return # no row selected
		date = calendar.get_date ()
		resource_id = model[path][0]
		self.cursor.execute ("UPDATE resources SET dated_for = %s "
							"WHERE id = %s", (date, resource_id))
		DB.commit()
		calendar.emit('day-selected')

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
		row_id = model[path][0]
		model[path][5] = int(contact_id)
		model[path][6] = contact_name
		self.cursor.execute ("UPDATE resources SET contact_id = %s "
							"WHERE id = %s", (contact_id, row_id))
		DB.commit()

	def new_resource_clicked (self, button):
		black = Gdk.RGBA(0, 0, 0, 1)
		self.cursor.execute("INSERT INTO resources "
							"(subject, dated_for, diary) "
							"VALUES ('New subject', %s, False) "
							"RETURNING id", (self.date_time,))
		row_id = self.cursor.fetchone()[0]
		DB.commit()
		iter = self.day_detail_store.append([row_id, 
											'New Subject', 
											0, 
											0, 
											'', 
											0, 
											'', 
											0, 
											'', 
											black])
		path = self.day_detail_store.get_path(iter)
		treeview = self.builder.get_object('treeview2')
		c = treeview.get_column(0)
		treeview.set_cursor(path, c, True)

	def delete_resource_clicked (self, button):
		selection = self.builder.get_object ('treeview-selection')
		model, path = selection.get_selected_rows ()
		if path != []:
			resource_id = model[path][0]
			self.cursor.execute("DELETE FROM resources "
								"WHERE id = %s", (resource_id,))
			DB.commit ()
		self.calendar.emit('day-selected')
	
	def previous_month_clicked (self, button):
		date = self.calendar.get_date()
		if date.month == 0: # switch to December of previous year
			self.calendar.select_month (11, date.year - 1)
		else:
			self.calendar.select_month (date.month - 1, date.year)
		self.calendar.emit('day-selected')

	def following_month_clicked (self, button):
		date = self.calendar.get_date()
		if date.month == 11: # switch to January of following year
			self.calendar.select_month (0, date.year + 1)
		else:
			self.calendar.select_month (date.month + 1, date.year)
		self.calendar.emit('day-selected')
	
	def day_selected (self, calendar):
		self.date_time = calendar_to_datetime (calendar.get_date())
		date_formatted = datetime.strftime(self.date_time, "%B %Y")
		self.builder.get_object('date_label').set_text(date_formatted)
		self.populate_day_detail_store ()
		self.populate_day_statistics ()

	def populate_day_detail_store (self):
		self.day_detail_store.clear()
		self.cursor.execute("SELECT "
							"rm.id, "
							"rm.subject, "
							"rm.qty, "
							"ry.id, "
							"ry.name, "
							"c.id, "
							"c.name, "
							"rt.id, "
							"rt.tag, "
							"red, "
							"green, "
							"blue, "
							"alpha, "
							"tag_id "
							"FROM resources AS rm "
							"LEFT JOIN contacts AS c "
							"ON rm.contact_id = c.id "
							"LEFT JOIN resource_tags AS rt "
							"ON rm.tag_id = rt.id "
							"LEFT JOIN resource_types AS ry "
							"ON ry.id = rm.resource_type_id "
							"WHERE dated_for = %s", 
							(self.date_time,))
		for row in self.cursor.fetchall():
			row_id = row[0]
			subject = row[1]
			qty = row[2]
			type_id = row[3]
			type_name = row[4]
			contact_id = row[5]
			contact_name = row[6]
			tag_id = row[7]
			tag_name = row[8]
			red = row[9]
			green = row[10]
			blue = row[11]
			alpha = row[12]
			tag_id = row[13]
			if tag_id == None or tag_id == 0:
				rgba = Gdk.RGBA(1, 1, 1, 0)
			else:
				rgba = Gdk.RGBA(red, green, blue, alpha)
			self.day_detail_store.append([row_id, subject, qty, type_id,
											type_name, contact_id, 
											contact_name, tag_id, tag_name, 
											rgba])
		DB.rollback()

	def populate_day_statistics (self):
		c = DB.cursor()
		listbox = self.builder.get_object('listbox')
		listbox_width = listbox.get_allocated_size()[0].width
		for child in listbox.get_children():
			listbox.remove(child)
		section_label = Gtk.Label(xalign = 0)
		section_label.set_markup('<b>Total</b>')
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, 
						margin_start = 5,
						margin_top = 5)
		hbox.pack_start(section_label, False, False, 0)
		listbox.add(hbox)
		c.execute("SELECT COALESCE(SUM(qty), 0)::text "
					"FROM resources "
					"WHERE dated_for = %s ", 
					(self.date_time,))
		for row in c.fetchall():
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, 
							spacing=10, 
							margin_start = 15)
			qty_label = Gtk.Label(label = row[0], xalign = 1)
			hbox.pack_start(qty_label, False, False, 0)
			listbox.add(hbox)
		listbox.show_all()
		while Gtk.events_pending(): # get the allocated size of the qty label
			Gtk.main_iteration()
		qty_label_width = qty_label.get_allocated_size()[0].width
		section_label = Gtk.Label(xalign = 0)
		section_label.set_markup('<b>Group by Category</b>')
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin_start = 5)
		hbox.pack_start(section_label, False, False, 0)
		listbox.add(hbox)
		c.execute("SELECT COALESCE(SUM(qty), 0)::text, "
					"rt.tag::text "
					"FROM resources AS r "
					"JOIN resource_tags AS rt ON rt.id = r.tag_id "
					"AND dated_for = %s WHERE finished = False "
					"GROUP BY rt.id ORDER BY rt.tag", 
					(self.date_time,))
		for row in c.fetchall():
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, 
							spacing=10, 
							margin_start = 15)
			qty_label = Gtk.Label(label = row[0], xalign = 1)
			qty_label.set_size_request(qty_label_width, -1)
			name_label = Gtk.Label(label = row[1])
			hbox.pack_start(qty_label, False, False, 0)
			hbox.pack_start(name_label, False, False, 0)
			listbox.add(hbox)
		section_label = Gtk.Label(xalign = 0)
		section_label.set_markup('<b>Group by Type</b>')
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin_start = 5)
		hbox.pack_start(section_label, False, False, 0)
		listbox.add(hbox)
		c.execute("SELECT COALESCE(SUM(qty), 0)::text, "
					"rt.name::text "
					"FROM resources AS r "
					"JOIN resource_types AS rt "
					"ON rt.id = r.resource_type_id "
					"AND dated_for = %s GROUP BY rt.id ORDER BY rt.name", 
					(self.date_time,))
		for row in c.fetchall():
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, 
							spacing=10, 
							margin_start = 15)
			qty_label = Gtk.Label(label = row[0], xalign = 1)
			qty_label.set_size_request(qty_label_width, -1)
			name_label = Gtk.Label(label = row[1])
			hbox.pack_start(qty_label, False, False, 0)
			hbox.pack_start(name_label, False, False, 0)
			listbox.add(hbox)
		section_label = Gtk.Label(xalign = 0)
		section_label.set_markup('<b>Group by Category and Type</b>')
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin_start = 5)
		hbox.pack_start(section_label, False, False, 0)
		listbox.add(hbox)
		c.execute("SELECT COALESCE(SUM(qty), 0)::text, "
					"rt.name::text, "
					"rc.tag::text "
					"FROM resources AS r "
					"JOIN resource_types AS rt "
					"ON rt.id = r.resource_type_id "
					"JOIN resource_tags AS rc ON rc.id = r.tag_id "
					"WHERE dated_for = %s AND finished = False "
					"GROUP BY rt.id, rc.id ORDER BY rt.name, rc.tag", 
					(self.date_time,))
		for row in c.fetchall():
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, 
							spacing=10, 
							margin_start = 15)
			qty_label = Gtk.Label(label = row[0], xalign = 1)
			qty_label.set_size_request(qty_label_width, -1)
			type_label = Gtk.Label(label = row[1], xalign = 0)
			type_label.set_size_request(listbox_width * .4, -1)
			category_label = Gtk.Label(label = row[2])
			hbox.pack_start(qty_label, False, False, 0)
			hbox.pack_start(type_label, False, False, 0)
			hbox.pack_start(category_label, False, False, 0)
			listbox.add(hbox)
		listbox.show_all()
		c.close()
		DB.rollback()

	def get_holiday_description (self, date):
		if us_holidays is None:
			return ''
		descriptor = us_holidays.get(date)
		if descriptor :
			color = '#000000ff'
			return "<span foreground='%s' weight='bold'>%s</span>\n" % (
															color, descriptor)
		return ''

	def calendar_func (self, calendar, year, month, day):
		date = "%s %s %s" % (month+1, day, year)
		date_time = datetime.strptime(date, "%m %d %Y")
		string = str()
		string += self.get_holiday_description (date_time)
		self.cursor.execute("SELECT subject, red, green, blue, alpha, "
							"COALESCE(' : ' || name, '') "
							"FROM resources AS rm "
							"LEFT JOIN contacts "
							"ON contacts.id = rm.contact_id "
							"JOIN resource_tags AS rmt "
							"ON rm.tag_id = rmt.id WHERE dated_for = '%s' "
							"AND finished != True %s" % 
							(date_time, self.where_clause))
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
		DB.rollback()
		return string

	def resource_management_activated (self,button):
		from resources import resource_management
		resource_management.ResourceManagementGUI()

	def resource_categories_activated (self, menuitem):
		from resources import resource_categories
		resource_categories.ResourceCategoriesGUI()

	def window_focus_in_event (self, window, event):
		self.builder.get_object('popover_window').hide()
		self.populate_day_statistics()

	def popover_window_delete_event (self, window, event):
		window.hide()
		return True

	def popover_key_press_event (self, window, event):
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

	# filtering tools

	def type_combo_filter_changed (self, combobox):
		self.generate_where_clause ()

	def contact_combo_filter_changed (self, combobox):
		self.generate_where_clause ()

	def category_combo_filter_changed (self, combobox):
		self.generate_where_clause ()

	def generate_where_clause (self):
		type_id = self.builder.get_object('type_combo').get_active_id()
		contact_id = self.builder.get_object('contact_combo').get_active_id()
		category_id = self.builder.get_object('category_combo').get_active_id()
		self.where_clause = ''
		if type_id != None:
			self.where_clause += 'AND resource_type_id = %s' % type_id
		if contact_id != None:
			self.where_clause += 'AND contact_id = %s' % contact_id
		if category_id != None:
			self.where_clause += 'AND tag_id = %s' % category_id
		self.calendar.queue_resize()

	def type_filter_match_selected (self, completion, treemodel, treeiter):
		active_id = treemodel[treeiter][0]
		self.builder.get_object('type_combo').set_active_id(active_id)

	def contact_filter_selected (self, completion, treemodel, treeiter):
		active_id = treemodel[treeiter][0]
		self.builder.get_object('contact_combo').set_active_id(active_id)

	def category_filter_match_selected (self, completion, treemodel, treeiter):
		active_id = treemodel[treeiter][0]
		self.builder.get_object('category_combo').set_active_id(active_id)

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()




