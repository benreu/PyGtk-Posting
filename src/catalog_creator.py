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

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
import psycopg2, time, subprocess
import uno, unohelper
from com.sun.star.connection import NoConnectException
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
from com.sun.star.text.TextContentAnchorType import AS_CHARACTER
from com.sun.star.uno import XComponentContext
from com.sun.star.awt import Size

UI_FILE = "src/catalog_creator.ui"

class CatalogCreatorGUI:
	def __init__ (self, main):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.main = main
		self.db = main.db
		self.cursor = self.db.cursor()
		#main.connect("products_changed", self.populate_products)
		self.product_store = self.builder.get_object('product_store')
		self.populate_products ()
		product_completion = self.builder.get_object('product_completion')
		product_completion.set_match_func(self.product_match_func)
		self.catalog_store = self.builder.get_object('catalog_store')
		self.populate_catalog_store ()
		
		dnd = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		#dnd = ('text/uri-list', Gtk.TargetFlags(1), 129)
		#self.treeview.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, [], Gdk.DragAction.COPY)	
		treeview = self.builder.get_object('treeview1')
		treeview.drag_source_set( Gdk.ModifierType.BUTTON1_MASK ,[dnd], Gdk.DragAction.MOVE)
		
		enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags(1), 129)
		treeview.drag_dest_set(Gtk.DestDefaults.ALL, [enforce_target], Gdk.DragAction.MOVE)
		treeview.drag_dest_set_target_list([enforce_target])
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

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
		GLib.idle_add ( self.populate_catalog_store )

	def product_completion_match_selected (self, combo, model, iter_):
		product_id = model[iter_][0]
		self.cursor.execute("UPDATE products SET catalog = True"
								" WHERE id = %s", (product_id,))
		self.db.commit()
		GLib.idle_add ( self.populate_catalog_store )

	def populate_catalog_store (self):
		self.catalog_store.clear()
		self.cursor.execute("SELECT p.id, barcode, p.name, ext_name, description, "
							"price FROM products AS p "
							"JOIN products_terms_prices AS ptp "
							"ON ptp.product_id = p.id "
							"JOIN terms_and_discounts AS tad "
							"ON tad.id = ptp.term_id "
							"WHERE (catalog, standard) = (True, True) "
							"ORDER BY catalog_order")
		for row in self.cursor.fetchall():
			p_id = row[0]
			barcode = row[1]
			name = row[2]
			ext_name = row[3]
			description = row[4]
			price = row[5]
			self.catalog_store.append([p_id, barcode, name, ext_name, description, price])

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

	def image_area_draw (self, drawing_area, cr):
		image = GdkPixbuf.Pixbuf.new_from_file("/home/reuben/reuben.jpg")
		Gdk.cairo_set_source_pixbuf(cr, image, 1, 1)
		cr.paint()

	def generate_catalog_clicked (self, button):
		self.get_office_socket_connection ()
		start_time = time.time ()
		doc = self.desktop.loadComponentFromURL( "private:factory/swriter","_blank", 0, () )
		currentStyle = doc.CurrentController.getViewCursor().PageStyleName
		styleName = doc.getStyleFamilies().getByName("PageStyles").getByName(currentStyle)
		styleName.TopMargin = 1000
		styleName.BottomMargin = 1250
		#styleName.Width = 20000
		text = doc.Text
		cursor = text.createTextCursor()
		self.cursor.execute("SELECT p.id, barcode, p.name, ext_name, description, "
							"price, image FROM products AS p "
							"JOIN products_terms_prices AS ptp "
							"ON ptp.product_id = p.id "
							"JOIN terms_and_discounts AS tad "
							"ON tad.id = ptp.term_id "
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
			#table.Width = 500
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

			imageURL = '/tmp/%s.jpg' % p_id
			with open(imageURL, 'wb') as f:
				f.write(image_string)
			img = doc.createInstance('com.sun.star.text.TextGraphicObject') 
			img.GraphicURL = "file://%s"%imageURL 
			img.AnchorType = AS_CHARACTER
			img.Width = 4000
			img.Height = 4000
			imageCell = table.getCellByName("A1")
			cellCursor = imageCell.createTextCursor()
			imageCell.insertTextContent(cellCursor, img, False)

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



			
			
