#
# Copyright (C) 2018 reuben 
# 
# invoice_to_payment_matching is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# invoice_to_payment_matching is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
gi.require_version('GooCanvas', '2.0')
from gi.repository import Gtk, Gdk, GooCanvas
import main

UI_FILE = main.ui_directory + "/reports/invoice_to_payment_matching.ui"

class GUI:
	def __init__(self, db):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		c = db.cursor()

		self.customer_store = self.builder.get_object('customer_store')
		self.customer_store.clear()
		c.execute("SELECT id::text, name, ext_name FROM contacts "
					"WHERE customer = True ORDER BY name")
		for row in c.fetchall():
			self.customer_store.append(row)
		sw = self.builder.get_object('scrolledwindow1')
		self.canvas = GooCanvas.Canvas()
		sw.add(self.canvas)
		self.canvas.set_property("automatic-bounds", True)
		self.canvas.set_property("bounds-padding", 10)

		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		
		window = self.builder.get_object('window')
		window.show_all()

	def populate_invoices (self):
		c = self.db.cursor()
		root = self.canvas.get_root_item()
		previous_position = 25.0
		c.execute("SELECT "
				"'Invoice '||id::text||' '||format_date(dated_for)||' '||amount_due::money, "
				"amount_due::float, "
				"id "
				"FROM invoices "
				"WHERE (canceled, posted, customer_id) = (False, True, %s) "
				"ORDER BY dated_for", (self.customer_id,))
		for row in c.fetchall():
			amount = row[1]
			parent1 = GooCanvas.CanvasGroup(parent = root)
			GooCanvas.CanvasRect   (parent = parent1, 
									x=50,
									y = previous_position ,
									width=300,
									height=amount,
									stroke_color="black")
			t = GooCanvas.CanvasText (parent = parent1,
									text = row[0], 
									x=340,
									y=previous_position + (amount / 2), 
									anchor = GooCanvas.CanvasAnchorType.EAST)
			t.connect("button-release-event", self.invoice_clicked, row[2])
			previous_position += amount
		self.canvas.set_size_request(800,  previous_position + 100)

	def populate_payments (self):
		c = self.db.cursor()
		root = self.canvas.get_root_item()
		previous_position = 25.0
		c.execute("SELECT * FROM "
					"(SELECT "
					"'Payment '||payment_info(id)||' '||format_date(date_inserted)||' '||amount::money, "
					"amount::float, "
					"id, "
					"date_inserted AS dated "
					"FROM payments_incoming "
					"WHERE customer_id = %s "
					") s "
				"UNION "
					"(SELECT "
					"'Credit Memo '||id::text||' '||format_date(dated_for)||' '||amount_owed::money, "
					"amount_owed::float, "
					"id, "
					"dated_for AS dated "
					"FROM credit_memos WHERE customer_id = %s "
					") "
				"ORDER BY dated", (self.customer_id, self.customer_id))
		for row in c.fetchall():
			amount = row[1]
			parent1 = GooCanvas.CanvasGroup(parent = root)
			GooCanvas.CanvasRect   (parent = parent1, 
									x=350,
									y = previous_position ,
									width=400,
									height=amount,
									stroke_color="black")
			t = GooCanvas.CanvasText (parent = parent1,
									text = row[0], 
									x=360,
									y=previous_position + (amount / 2), 
									anchor = GooCanvas.CanvasAnchorType.WEST)
			t.connect("button-release-event", self.po_clicked, row[2])
			previous_position += amount
		if previous_position + 100 > self.canvas.get_size_request().height:
			self.canvas.set_size_request(800,  previous_position)

	def customer_changed (self, combobox):
		customer_id = combobox.get_active_id()
		if customer_id != None:
			self.customer_id = customer_id
			group = GooCanvas.CanvasGroup()
			self.canvas.set_root_item(group)
			self.populate_invoices ()
			self.populate_payments ()

	def customer_match_selected (self, entrycompletion, treemodel, treeiter):
		self.customer_id = treemodel[treeiter][0]
		group = GooCanvas.CanvasGroup()
		self.canvas.set_root_item(group)
		self.populate_invoices ()
		self.populate_payments ()

	def customer_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter_][1].lower():
				return False
		return True

	def invoice_clicked (self, canvas_1, canvas_2, event, invoice_id):
		print (invoice_id)
		
	def po_clicked (self, canvas_1, canvas_2, event, po_id):
		print (po_id)
		
	def slider_value_changed (self, slider, scrolltype, arg):
		self.canvas.set_scale(slider.get_value())

	def on_window_destroy(self, window):
		Gtk.main_quit()

def main():
	app = GUI()
	Gtk.main()
		
if __name__ == "__main__":
	sys.exit(main())

