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
import psycopg2, time, subprocess
import uno, unohelper
from com.sun.star.connection import NoConnectException
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
from com.sun.star.text.TextContentAnchorType import AS_CHARACTER
from com.sun.star.awt.FontWeight import BOLD, NORMAL
from com.sun.star.awt import Size
import main

UI_FILE = main.ui_directory + "/catalog_creator.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass

class CatalogCreatorGUI:
	preview_image = None
	preview_size = 0
	def __init__ (self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		main.connect("products_changed", self.populate_products)
		self.product_store = self.builder.get_object('product_store')
		self.populate_products ()
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.catalog_store = self.builder.get_object('catalog_store')
		
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)	
		treeview = self.builder.get_object('treeview1')
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.MOVE)
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.MOVE)
		treeview.drag_dest_set_target_list([enforce_target])
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		
		scale = self.builder.get_object('scale1')
		for i in [16, 32, 64, 128, 256]:
			scale.add_mark(i, Gtk.PositionType.BOTTOM, str(i))

	def populate_products (self, m=None, d=None):
		self.product_store.clear()
		self.cursor.execute ("SELECT id, name, ext_name FROM products "
							"WHERE (sellable, deleted) = (True, False) ORDER BY name")
		for row in self.cursor.fetchall():
			p_id = str(row[0])
			name = row[1]
			ext_name = row[2]
			self.product_store.append([p_id, name, ext_name])

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
		selection = self.builder.get_object("treeview-selection1")
		model, path = selection.get_selected_rows()
		if path == []:
			return
		row_id = model[path][0]
		self.cursor.execute("SELECT image FROM products WHERE id = %s", (row_id,))
		for row in self.cursor.fetchall():
			image_bytes = row[0]
			if image_bytes == None:
				self.preview_image == None
			else:
				self.preview_image = image_bytes
				self.show_preview ()

	def pane_size_allocate (self, pane, rectangle):
		'runs at window.show_all(), initializing self.preview_size'
		size = rectangle.width - pane.get_position() - 7
		if size != self.preview_size:
			self.preview_size = size
			self.show_preview ()

	def show_preview (self):
		if self.preview_image != None:
			byte_in = GLib.Bytes(self.preview_image.tobytes())
			input_in = Gio.MemoryInputStream.new_from_bytes(byte_in)
			pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_in, 
															self.preview_size, 
															self.preview_size, 
															True)
			self.builder.get_object('image2').set_from_pixbuf(pixbuf)

	def load_catalog_clicked (self, button = None):
		scale = self.builder.get_object('scale1')
		size = scale.get_value()
		self.catalog_store.clear()
		self.cursor.execute("SELECT p.id, barcode, p.name, ext_name, description, "
							"COALESCE(price, 0.00), image FROM products AS p "
							"LEFT JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id "
							"LEFT JOIN customer_markup_percent AS cmp "
							"ON cmp.id = pmp.markup_id "
							"WHERE (catalog, standard) = (True, True) "
							"ORDER BY catalog_order")
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
			menu = self.builder.get_object('menu1')
			menu.popup(None, None, None, None, event.button, event.time)
			menu.show_all()

	def product_hub_activated (self, menuitem):
		selection = self.builder.get_object("treeview-selection1")
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
		treeview = self.builder.get_object('treeview1')
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
		selection = self.builder.get_object("treeview-selection1")
		model, path = selection.get_selected_rows ()
		if path == []:
			return
		product_id = model[path][0]
		dialog = self.builder.get_object('filechooserdialog1')
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
		
	def populate_template_clicked (self, button):
		from py3o.template import Template 
		product_list = dict()
		self.cursor.execute("SELECT "
							"'name'||p.barcode, p.name, "
							"'price'||p.barcode, price::money "
							"FROM products AS p "
							"JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id "
							"JOIN customer_markup_percent AS cmp "
							"ON cmp.id = pmp.markup_id "
							"WHERE (p.catalog, cmp.standard) = (True, True)")
		for row in self.cursor.fetchall():
			name_id = row[0]
			name = row[1]
			price_id = row[2]
			price = row[3]
			product_list[name_id] = name
			product_list[price_id] = price
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

	def generate_catalog_clicked (self, button):
		self.get_office_socket_connection ()
		start_time = time.time ()
		self.cursor.execute("SELECT name, phone, street, "
							"city||' '||state||' '||zip FROM company_info")
		for row in self.cursor.fetchall():
			company_name = row[0]
			company_phone = row[1]
			company_street = row[2]
			company_city_zip = row[3]
		doc = self.desktop.loadComponentFromURL( "private:factory/swriter","_blank", 0, () )
		currentStyle = doc.CurrentController.getViewCursor().PageStyleName
		styleName = doc.getStyleFamilies().getByName("PageStyles").getByName(currentStyle)
		styleName.TopMargin = 1000
		styleName.BottomMargin = 1000
		styleName.FooterIsOn = True
		styleName.FooterHeight  = 900
		#styleName.FooterMargin = 1000
		FooterText = styleName.FooterText
		cursor = FooterText.createTextCursor()
		table = doc.createInstance("com.sun.star.text.TextTable")
		table.initialize(2, 2)
		FooterText.insertTextContent(cursor, table, 0)
		table.TopMargin = 2500
		oBorder = table.TableBorder
		line = oBorder.TopLine
		line.OuterLineWidth = 0
		line.InnerLineWidth = 0
		line.LineDistance = 0
		oBorder.RightLine = line
		oBorder.TopLine = line
		oBorder.LeftLine = line
		oBorder.BottomLine = line
		oBorder.HorizontalLine = line
		oBorder.VerticalLine = line
		table.TableBorder = oBorder
		table.getCellByName("A1").setString(company_name)
		cursor = table.getCellByName("A2").createTextCursor()
		cursor.CharWeight = BOLD
		cursor.ParaAdjust = 3
		cursor.setString(company_phone)
		cursor = table.getCellByName("B1").createTextCursor()
		cursor.CharWeight = NORMAL
		cursor.setString(company_street)
		cursor = table.getCellByName("B2").createTextCursor()
		cursor.ParaAdjust = 3
		cursor.setString(company_city_zip)
		text = doc.Text
		cursor = text.createTextCursor()
		self.builder.get_object("window1").present()
		self.cursor.execute("SELECT p.id, barcode, p.name, ext_name, description, "
							"price, image FROM products AS p "
							"JOIN products_markup_prices AS pmp "
							"ON pmp.product_id = p.id "
							"JOIN customer_markup_percent AS cmp "
							"ON cmp.id = pmp.markup_id "
							"WHERE (catalog, standard) = (True, True) "
							"ORDER BY catalog_order")
		tupl = self.cursor.fetchall()
		rows = float(len(tupl))
		for index, row in enumerate(tupl):
			p_id = row[0]
			barcode = row[1]
			name = row[2]
			ext_name = row[3]
			description = row[4]
			price = row[5]
			image_string = row[6]
			table = doc.createInstance( "com.sun.star.text.TextTable" )
			table.initialize( 2,3)
			text.insertTextContent( cursor, table, 0 )
			columns = table.TableColumnSeparators
			columns[0].Position = 2400
			columns[1].Position = 8500
			table.TableColumnSeparators = columns

			mergeCursor = table.createCursorByCellName("A1")
			mergeCursor.goDown(1,True)
			mergeCursor.mergeRange ()

			mergeCursor = table.createCursorByCellName("B2")
			#mergeCursor.goDown(1,True)
			mergeCursor.goRight(1,True)
			mergeCursor.mergeRange ()

			table.getCellByName("B1").setString(name)
			table.getCellByName("C1").setString('${:,.2f}'.format(price))
			table.getCellByName("B2").setString(description)

			if image_string != None:
				imageURL = '/tmp/%s.jpg' % p_id
				with open(imageURL, 'wb') as f:
					f.write(image_string)
				img = doc.createInstance('com.sun.star.text.TextGraphicObject') 
				img.GraphicURL = "file://%s"%imageURL 
				img.AnchorType = AS_CHARACTER
				img.Width = 2000 # hackery to get original size to work ???
				img.Height = 2000
				imageCell = table.getCellByName("A1")
				cellCursor = imageCell.createTextCursor()
				imageCell.insertTextContent(cellCursor, img, False)
				w = img.ActualSize.Width
				h = img.ActualSize.Height
				v = max(w, h, 4000)
				division = v / 4000
				width = int(w / division)
				height = int(h / division)
				imageSize = Size(width, height)
				img.setSize(imageSize)

			progress = float(index+1) / rows
			self.builder.get_object("progressbar1").set_fraction(progress)
			while Gtk.events_pending():
				Gtk.main_iteration()
		progress = "100 %% - %s seconds" % round(time.time() - start_time, 1)
		self.builder.get_object("progressbar1").set_text(progress)

	def get_office_socket_connection (self):
		subprocess.Popen("soffice "
						"'--accept=socket,host=localhost,port=2002;urp;' "
						"--nologo --nodefault", shell=True)		
		localContext = uno.getComponentContext()
		resolver = localContext.ServiceManager.createInstanceWithContext(
						'com.sun.star.bridge.UnoUrlResolver', localContext )
		connection_url = 'uno:socket,host=localhost,port=2002;urp;StarOffice.ServiceManager'
		result = False
		while result == False:
			try:
				smgr = resolver.resolve( connection_url )
				result = True
			except NoConnectException:
				subprocess.Popen("soffice "
								"'--accept=socket,host=localhost,port=2002;urp;' "
								"--nologo --nodefault", shell=True)
				time.sleep(.25)
		remoteContext = smgr.getPropertyValue( 'DefaultContext' )
		self.desktop = smgr.createInstanceWithContext( 'com.sun.star.frame.Desktop', 
																remoteContext)



			
			
