# purchase_order_hub.py
#
# Copyright (C) 2020 - Reuben
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

import gi
gi.require_version('EvinceView', '3.0')
from gi.repository import EvinceView, EvinceDocument
from gi.repository import Gtk
import subprocess, tempfile
from constants import ui_directory, DB

UI_FILE = ui_directory + "/purchase_order_hub.ui"


class PurchaseOrderHubGUI(Gtk.Builder):
	def __init__(self, po_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.po_id = po_id
		EvinceDocument.init()
		self.pdf_view = EvinceView.View()
		self.get_object('pdf_view_scrolled_window').add(self.pdf_view)
		self.attachment_view = EvinceView.View()
		self.get_object('attachment_scrolled_window').add(self.attachment_view)
		window = self.get_object('window')
		window.show_all()
		window.set_title("PO hub (%s)" % po_id)
		self.populate_items()
		self.populate_metadata ()
		DB.rollback()

	def populate_items(self):
		store = self.get_object('purchase_order_items_store')
		c = DB.cursor()
		c.execute("SELECT "
						"poi.id, "
						"poi.qty,  "
						"poi.qty::text,  "
						"poi.product_id, "
						"p.name, "
						"p.ext_name, "
						"poi.remark, "
						"poi.price, "
						"poi.price::text, "
						"poi.ext_price, "
						"poi.ext_price::text, "
						"poi.sort, "
						"poi.canceled "
					"FROM purchase_order_items AS poi "
					"JOIN products AS p ON p.id = poi.product_id "
					"WHERE poi.purchase_order_id = %s "
					"ORDER BY poi.sort, poi.id", (self.po_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()

	def populate_metadata (self):
		c = DB.cursor()
		c.execute("SELECT po.id::text, "
							"po.name, "
							"format_date(po.date_created), "
							"po.date_created::text, "
							"COALESCE(format_date(po.date_printed), 'N/A'), "
							"po.date_printed::text, "
							"COALESCE(format_date(po.date_paid), 'N/A'), "
							"po.date_paid::text, "
							"po.total::money, "
							"po.amount_due::money, "
							"po.invoice_description, "
							"COALESCE(po.comments, ''), "
							"c.name, "
							"po.closed, "
							"po.received, "
							"po.invoiced, "
							"po.pdf_data, "
							"po.attached_pdf "
							"FROM purchase_orders AS po "
							"JOIN contacts AS c ON c.id = po.vendor_id "
							"WHERE po.id = %s", (self.po_id,))
		for row in c.fetchall():
			self.get_object('invoice_number_entry').set_text(row[0])
			self.get_object('invoice_name_entry').set_text(row[1])
			self.get_object('date_created_entry').set_text(row[2])
			self.get_object('date_created_entry').set_tooltip_text(row[3])
			self.get_object('date_printed_entry').set_text(row[4])
			self.get_object('date_printed_entry').set_tooltip_text(row[5])
			self.get_object('date_paid_entry').set_text(row[6])
			self.get_object('date_paid_entry').set_tooltip_text(row[7])
			self.get_object('total_entry').set_text(row[8])
			self.get_object('discounted_total_entry').set_text(row[9])
			self.get_object('description_entry').set_text(row[10])
			self.get_object('comments_textbuffer').set_text(row[11])
			self.get_object('customer_name_entry').set_text(row[12])
			self.get_object('po_posted_checkbutton').set_active(row[13])
			self.get_object('po_received_checkbutton').set_active(row[14])
			self.get_object('po_invoiced_checkbutton').set_active(row[15])
			self.populate_pdf_viewer(row[16])
			self.populate_attachment(row[17])
		c.close()

	def populate_pdf_viewer (self, bytes):
		with tempfile.NamedTemporaryFile() as pdf_contents:
			pdf_contents.file.write(bytes)
			file_url = 'file://' + pdf_contents.name
			doc = EvinceDocument.Document.factory_get_document(file_url)
		self.model = EvinceView.DocumentModel()
		self.model.set_document(doc)
		self.pdf_view.set_model(self.model)

	def populate_attachment (self, bytes):
		if bytes == None:
			return
		with tempfile.NamedTemporaryFile() as pdf_contents:
			pdf_contents.file.write(bytes)
			file_url = 'file://' + pdf_contents.name
			doc = EvinceDocument.Document.factory_get_document(file_url)
		self.model = EvinceView.DocumentModel()
		self.model.set_document(doc)
		self.attachment_view.set_model(self.model)

	def date_difference_calculate_clicked (self, button):
		store = self.get_object('difference_between_store')
		primary = self.get_object('primary_date_combo').get_active_id()
		secondary = self.get_object('secondary_date_combo').get_active_id()
		c = DB.cursor()
		c.execute("WITH cte AS (SELECT %s - %s AS diff "
						"FROM purchase_orders WHERE id = '%s') "
					"SELECT diff::float, "
						"make_interval(days => diff)::text FROM cte" %
					(secondary, primary, self.po_id))
		for row in c.fetchall():
			difference = row[0]
			difference_formatted = row[1]
			store.append([primary, '-', 
							secondary, '=', 
							difference, difference_formatted])
		DB.rollback()



