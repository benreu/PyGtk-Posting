# invoice_hub.py
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

UI_FILE = ui_directory + "/invoice_hub.ui"


class InvoiceHubGUI(Gtk.Builder):
	def __init__(self, invoice_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.invoice_id = invoice_id
		EvinceDocument.init()
		self.view = EvinceView.View()
		self.get_object('pdf_view_scrolled_window').add(self.view)
		window = self.get_object('window')
		window.show_all()
		window.set_title("Invoice hub (%s)" % invoice_id)
		self.populate_items()
		self.populate_metadata ()
		DB.rollback()

	def populate_items(self):
		store = self.get_object('invoice_items_store')
		c = DB.cursor()
		c.execute("SELECT "
						"ili.id, "
						"ili.qty,  "
						"ili.qty::text,  "
						"ili.product_id, "
						"p.name, "
						"p.ext_name, "
						"ili.remark, "
						"ili.price, "
						"ili.price::text, "
						"ili.ext_price, "
						"ili.ext_price::text, "
						"ili.tax, "
						"ili.tax::text, "
						"ili.sort, "
						"ili.canceled "
					"FROM invoice_items AS ili "
					"JOIN products AS p ON p.id = ili.product_id "
					"WHERE ili.invoice_id = %s "
					"ORDER BY ili.sort, ili.id", (self.invoice_id,))
		for row in c.fetchall():
			store.append(row)
		c.close()

	def populate_metadata (self):
		c = DB.cursor()
		c.execute("SELECT i.id::text, "
							"i.name, "
							"format_date(i.date_created), "
							"i.date_created::text, "
							"format_date(i.dated_for), "
							"i.dated_for::text, "
							"format_date(i.date_printed), "
							"i.date_printed::text, "
							"format_date(i.date_paid), "
							"i.date_paid::text, "
							"i.doc_type, "
							"i.tax::money, "
							"i.subtotal::money, "
							"i.total::money, "
							"i.amount_due::money, "
							"i.comments, "
							"c.name, "
							"i.pdf_data "
							"FROM invoices AS i "
							"JOIN contacts AS c ON c.id = i.customer_id "
							"WHERE i.id = %s", (self.invoice_id,))
		for row in c.fetchall():
			self.get_object('invoice_number_entry').set_text(row[0])
			self.get_object('invoice_name_entry').set_text(row[1])
			self.get_object('date_created_entry').set_text(row[2])
			self.get_object('date_created_entry').set_tooltip_text(row[3])
			self.get_object('dated_for_entry').set_text(row[4])
			self.get_object('dated_for_entry').set_tooltip_text(row[5])
			self.get_object('date_printed_entry').set_text(row[6])
			self.get_object('date_printed_entry').set_tooltip_text(row[7])
			self.get_object('date_paid_entry').set_text(row[8])
			self.get_object('date_paid_entry').set_tooltip_text(row[9])
			self.get_object('invoice_type_entry').set_text(row[10])
			self.get_object('tax_entry').set_text(row[11])
			self.get_object('subtotal_entry').set_text(row[12])
			self.get_object('total_entry').set_text(row[13])
			self.get_object('discounted_total_entry').set_text(row[14])
			self.get_object('comments_textbuffer').set_text(row[15])
			self.get_object('customer_name_entry').set_text(row[16])
			self.populate_pdf_viewer(row[17])
		c.close()

	def populate_pdf_viewer (self, bytes):
		with tempfile.NamedTemporaryFile() as pdf_contents:
			pdf_contents.file.write(bytes)
			file_url = 'file://' + pdf_contents.name
			doc = EvinceDocument.Document.factory_get_document(file_url)
		self.model = EvinceView.DocumentModel()
		self.model.set_document(doc)
		self.view.set_model(self.model)

	def date_difference_calculate_clicked (self, button):
		store = self.get_object('difference_between_store')
		primary = self.get_object('primary_date_combo').get_active_id()
		secondary = self.get_object('secondary_date_combo').get_active_id()
		c = DB.cursor()
		c.execute("WITH cte AS (SELECT %s - %s AS diff "
						"FROM invoices WHERE id = '%s') "
					"SELECT diff::float, "
						"make_interval(days => diff)::text FROM cte" %
					(secondary, primary, self.invoice_id))
		for row in c.fetchall():
			difference = row[0]
			difference_formatted = row[1]
			store.append([primary, '-', 
							secondary, '=', 
							difference, difference_formatted])
		DB.rollback()

	def amount_difference_calculate_clicked (self, button):
		store = self.get_object('difference_between_store')
		primary = self.get_object('primary_amount_combo').get_active_id()
		secondary = self.get_object('secondary_amount_combo').get_active_id()
		c = DB.cursor()
		c.execute("WITH cte AS (SELECT %s - %s AS diff "
						"FROM invoices WHERE id = '%s') "
					"SELECT diff::float, diff::money FROM cte" %
					(secondary, primary, self.invoice_id))
		for row in c.fetchall():
			difference = row[0]
			difference_formatted = row[1]
			store.append([primary, '-', 
							secondary, '=', 
							difference, difference_formatted])
		DB.rollback()

	def invoice_history_activated (self, menuitem):
		selection = self.get_object('serial_number_treeselection')
		model, path = selection.get_selected_rows()
		invoice_id = model[path][0]
		if not self.invoice_history or self.invoice_history.exists == False:
			from reports import invoice_history as ih
			self.invoice_history = ih.InvoiceHistoryGUI()
		combo = self.invoice_history.get_object('combobox1')
		combo.set_active_id(self.contact_id)
		store = self.invoice_history.get_object('invoice_store')
		selection = self.invoice_history.get_object('treeview-selection1')
		treeview = self.invoice_history.get_object('treeview1')
		selection.unselect_all()
		for row in store:
			if row[0] == invoice_id:
				selection.select_iter(row.iter)
				treeview.scroll_to_cell(row.path, None, False)
				break
		self.invoice_history.present()



