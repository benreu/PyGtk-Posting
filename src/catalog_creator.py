# catalog_creator.py
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

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio
import subprocess
import main

UI_FILE = main.ui_directory + "/catalog_creator.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class CatalogCreatorGUI(Gtk.Builder):
	preview_image = None
	preview_size = 0
	def __init__ (self, main):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		self.handler_id = main.connect("products_changed", self.populate_products)
		self.product_store = self.get_object('product_store')
		self.populate_products ()
		self.populate_price_levels ()
		product_completion = self.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.catalog_store = self.get_object('catalog_store')
		
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)	
		treeview = self.get_object('treeview1')
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.MOVE)
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.MOVE)
		treeview.drag_dest_set_target_list([enforce_target])
		
		self.window = self.get_object('window1')
		self.window.show_all()
		
		scale = self.get_object('scale1')
		for i in [16, 32, 64, 128, 256]:
			scale.add_mark(i, Gtk.PositionType.BOTTOM, str(i))

	def window_destroy (self, window):
		self.main.disconnect(self.handler_id)

	def populate_products (self, m=None, d=None):
		self.product_store.clear()
		self.cursor.execute ("SELECT id::text, name, ext_name FROM products "
							"WHERE (sellable, deleted) = (True, False) "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			self.product_store.append(row)

	def populate_price_levels (self):
		default = None
		price_level_store = self.get_object('price_level_store')
		self.cursor.execute("SELECT id::text, name, standard "
							"FROM customer_markup_percent "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			price_level_store.append(row)
			if row[2] == True:
				default = row[0]
		if default:
			self.get_object('price_level_combo').set_active_id(default)

	def product_combobox_changed (self, combo):
		product_id = combo.get_active_id()
		if product_id != None:
			self.cursor.execute("UPDATE products SET catalog = True"
								" WHERE id = %s", (product_id,))
			self.db.commit()
			GLib.idle_add ( self.load_catalog_clicked )
			combo.set_active(-1)

	def product_completion_match_selected (self, combo, model, iter_):
		product_id = model[iter_][0]
		self.cursor.execute("UPDATE products SET catalog = True"
								" WHERE id = %s", (product_id,))
		self.db.commit()
		GLib.idle_add ( self.load_catalog_clicked )

	def show_product_preview_activated (self, menuitem):
		selection = self.get_object("treeview-selection1")
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("SELECT image FROM products WHERE id = %s", (row_id,))
		for row in self.cursor.fetchall():
			image_bytes = row[0]
			if image_bytes == None:
				self.image == None
			else:
				self.image = image_bytes
				self.show_image ()
			window = self.get_object('image_window')
			window.show_all()
			window.present()

	def show_image (self):
		if self.image != None:
			byte_in = GLib.Bytes(self.image.tobytes())
			input_in = Gio.MemoryInputStream.new_from_bytes(byte_in)
			pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_in, 
															self.preview_size, 
															self.preview_size, 
															True)
			self.get_object('image2').set_from_pixbuf(pixbuf)

	def image_window_size_allocate (self, widget, rectangle):
		width = rectangle.width - 5
		if width != self.preview_size:
			self.preview_size = width
			self.show_image ()

	def image_window_delete_event (self, window, event):
		window.hide()
		return True

	def load_catalog_clicked (self, button = None):
		markup_id = self.get_object('price_level_combo').get_active_id()
		scale = self.get_object('scale1')
		size = scale.get_value()
		self.catalog_store.clear()
		description = self.get_object('description_checkbutton').get_active()
		self.cursor.execute("SELECT "
								"p.id, "
								"barcode, "
								"p.name, "
								"ext_name, "
								"CASE WHEN %s THEN description ELSE '' END, "
								"COALESCE(price, 0.00), "
								"image "
							"FROM products AS p "
							"LEFT JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id "
							"LEFT JOIN customer_markup_percent AS cmp "
							"ON cmp.id = pmp.markup_id "
							"WHERE (catalog, cmp.id) = (True, %s) "
							"ORDER BY catalog_order", 
							(description, markup_id))
		for row in self.cursor.fetchall():
			p_id = row[0]
			barcode = row[1]
			name = row[2]
			ext_name = row[3]
			description = row[4]
			price = row[5]
			image_bytes = row[6]
			if image_bytes == None:
				pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,
												True, 8, size, size)
			else:
				byte_in = GLib.Bytes(image_bytes.tobytes())
				input_in = Gio.MemoryInputStream.new_from_bytes(byte_in)
				pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_in, size, size, True)
			self.catalog_store.append([p_id, barcode, name, ext_name, description, price, pixbuf])

	def product_match_func(self, completion, key, tree_iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.product_store[tree_iter][1].lower():
				return False
		return True

	def treeview_button_release_event (self, treeview, event):
		if event.button == 3:
			menu = self.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		selection = self.get_object("treeview-selection1")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][0]
		import product_hub
		product_hub.ProductHubGUI(self.main, product_id)

	def drag_data_received (self, treeview, drag_context, x,y, data,info, time):
		store = treeview.get_model()
		source_path = data.get_text()
		source_iter = store.get_iter(source_path)
		treeview = self.get_object('treeview1')
		dest_path = treeview.get_dest_row_at_pos(x, y)
		if dest_path != None:
			dest_iter = store.get_iter(dest_path[0])
			if dest_path[1] == Gtk.TreeViewDropPosition.BEFORE:
				store.move_before(source_iter, dest_iter)
			else:
				store.move_after(source_iter, dest_iter)
		treeview.emit_stop_by_name("drag-data-received")
		self.db.commit()

	def drag_data_get (self, treeview, drag_context, data, info, time):
		model, path = treeview.get_selection().get_selected_rows()
		data.set_text(str(path[0]), -1)

	def catalog_rows_reordered (self, store, path, treeiter, pointer):
		for index, row in enumerate(store):
			product_id = row[0]
			self.cursor.execute("UPDATE products SET catalog_order = %s "
								"WHERE id = %s", (index, product_id))
		self.db.commit()

	def update_image_clicked (self, button):
		selection = self.get_object("treeview-selection1")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][0]
		dialog = self.get_object('filechooserdialog1')
		response = dialog.run()
		if response == Gtk.ResponseType.ACCEPT:
			filename = dialog.get_filename()
			f = open(filename,'rb')
			file_data = f.read ()
			f.close()
			self.cursor.execute("UPDATE products SET image = %s "
								"WHERE id = %s", (file_data, product_id))
		self.db.commit()
		dialog.hide()
	
	def remove_product_clicked (self, button):
		selection = self.get_object("treeview-selection1")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][0]
		self.cursor.execute("UPDATE products SET catalog = False"
								" WHERE id = %s", (product_id,))
		self.db.commit()
		GLib.idle_add ( self.load_catalog_clicked )
	
	def populate_template_clicked (self, button):
		markup_id = self.get_object('price_level_combo').get_active_id()
		from py3o.template import Template 
		product_list = dict()
		self.cursor.execute("SELECT "
								"'name'||p.id, p.name, "
								"'price'||p.id, price::money, "
								"'barcode'||p.id, p.barcode "
							"FROM products AS p "
							"JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id "
							"JOIN customer_markup_percent AS cmp "
							"ON cmp.id = pmp.markup_id "
							"WHERE (p.catalog, cmp.id) = (True, %s)",
							(markup_id,))
		for row in self.cursor.fetchall():
			name_id = row[0]
			name = row[1]
			price_id = row[2]
			price = row[3]
			barcode_id = row[4]
			barcode = row[5]
			product_list[name_id] = name
			product_list[price_id] = price
			product_list[barcode_id] = barcode
		catalog_file = "/tmp/catalog.odt"
		t = Template(main.template_dir+"/catalog_template.odt", catalog_file , False)
		try:
			t.render(product_list) #the product_list holds all the catalog info
		except Exception as e:
			print (e)
			dialog = Gtk.MessageDialog(self.window,
										0,
										Gtk.MessageType.ERROR,
										Gtk.ButtonsType.CLOSE,
										e)
			dialog.run()
			dialog.destroy()
			return
		subprocess.Popen(["soffice", catalog_file])

	def image_area_draw (self, drawing_area, cr):
		image = GdkPixbuf.Pixbuf.new_from_file("/home/reuben/reuben.jpg")
		Gdk.cairo_set_source_pixbuf(cr, image, 1, 1)
		cr.paint()

		
