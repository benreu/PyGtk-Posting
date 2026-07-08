# Copyright (C) 2016 reuben 
# 
# unpaid_invoices is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# unpaid_invoices is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
from db import transactor
from dateutils import DateTimeCalendar
import subprocess, decimal, tempfile, os, shutil, psycopg2

from constants import ui_directory, DB
from sqlite_utils import get_apsw_connection

UI_FILE = ui_directory + "/unpaid_invoices.ui"

class GUI (Gtk.Builder):
	def __init__(self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)
		self.cursor = DB.cursor()

		self.store = self.get_object('unpaid_invoice_store')
		self.window = self.get_object('window')
		self.set_window_layout_from_settings()
		self.window.show_all()

		self.date_calendar = DateTimeCalendar()
		self.date_calendar.connect("day-selected", self.date_selected)

	def set_window_layout_from_settings(self):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'window_width'")
		width = c.fetchone()[0]
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'window_height'")
		height = c.fetchone()[0]
		self.window.resize(width, height)
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'sort_column'")
		sort_column = c.fetchone()[0]
		c.execute("SELECT value FROM unpaid_invoices "
					"WHERE widget_id = 'sort_type'")
		sort_type = Gtk.SortType(c.fetchone()[0])
		store = self.get_object('unpaid_invoice_store')
		store.set_sort_column_id(sort_column, sort_type)
		c.execute("SELECT widget_id, value FROM unpaid_invoices WHERE "
					"widget_id IN ('number_column', "
									"'invoice_column', "
									"'customer_column', "
									"'date_column', "
									"'amount_column')")
		for row in c.fetchall():
			column = self.get_object(row[0])
			width = row[1]
			if width == 0:
				column.set_visible(False)
			else:
				column.set_fixed_width(width)
		sqlite.close()

	def save_window_layout_activated (self, menuitem):
		sqlite = get_apsw_connection()
		c = sqlite.cursor()
		width, height = self.window.get_size()
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('window_width', ?)", (width,))
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('window_height', ?)", (height,))
		tuple_ = self.get_object('unpaid_invoice_store').get_sort_column_id()
		sort_column = tuple_[0]
		if sort_column == None:
			sort_column = 0
			sort_type = 0
		else:
			sort_type = tuple_[1].numerator
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('sort_column', ?)", (sort_column,))
		c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
					"VALUES ('sort_type', ?)", (sort_type,))
		for column in ['number_column', 
						'invoice_column', 
						'customer_column', 
						'date_column', 
						'amount_column']:
			try:
				width = self.get_object(column).get_width()
			except Exception as e:
				self.show_message("On column %s\n %s" % (column, str(e)))
				continue
			c.execute("REPLACE INTO unpaid_invoices (widget_id, value) "
						"VALUES (?, ?)", (column, width))
		sqlite.close()

	def present (self):
		self.window.present()

	def window_delete_event (self, window, event):
		window.hide()
		return True
	
	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def contact_hub_activated (self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][2]
		import contact_hub
		contact_hub.ContactHubGUI(customer_id)

	def reprint_invoice_activated(self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_iter = model.get_iter(path[0])
		invoice_id = model.get_value(tree_iter, 0)
		c = DB.cursor()
		c.execute("SELECT pdf_data FROM invoices WHERE id = %s", (invoice_id,))
		row = c.fetchone()
		c.close()
		DB.rollback()
		if row is None or row[0] is None:
			self.show_message("No saved PDF found for this invoice.")
			return
		pdf_data = bytes(row[0])

		from gi.repository import Gio
		import printing
		print_op = printing.Operation(settings_file="invoice")
		print_op.set_parent(self.window)
		stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes(pdf_data))
		print_op.set_bytes_to_print(stream)
		result = print_op.print_dialog()

		if result == Gtk.PrintOperationResult.APPLY:
			c = DB.cursor()
			c.execute("UPDATE invoices SET date_printed = CURRENT_DATE "
						"WHERE id = %s", (invoice_id,))
			c.execute("INSERT INTO invoice_reprints (invoice_id, pdf_data) "
						"VALUES (%s, %s)", (invoice_id, psycopg2.Binary(pdf_data)))
			DB.commit()
			c.close()
			self.populate_unpaid_invoices()

	def show_reprint_history_activated(self, menuitem):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		tree_iter = model.get_iter(path[0])
		customer_id = model.get_value(tree_iter, 2)
		customer_name = model.get_value(tree_iter, 3)

		c = DB.cursor()
		c.execute("SELECT r.id, i.id, i.name, format_timestamp(r.time_printed), "
					"r.time_printed::text "
					"FROM invoice_reprints AS r "
					"JOIN invoices AS i ON i.id = r.invoice_id "
					"WHERE i.customer_id = %s "
					"AND (i.canceled, i.paid, i.posted) = (False, False, True) "
					"ORDER BY r.time_printed DESC", (customer_id,))
		rows = c.fetchall()
		c.close()
		DB.rollback()

		if not rows:
			self.show_message("No reprints found for this customer's unpaid invoices.")
			return

		history_window = Gtk.Window()
		history_window.set_title("Reprint history - %s" % customer_name)
		history_window.set_transient_for(self.window)
		history_window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
		history_window.set_default_size(380, 320)
		history_window.set_border_width(10)
		vbox = Gtk.VBox(spacing=6)
		history_window.add(vbox)

		history_store = Gtk.ListStore(int, int, str, str, str)
		for reprint_id, invoice_number, invoice_name, formatted, raw in rows:
			history_store.append(
				[reprint_id, invoice_number, invoice_name, formatted, raw])
		treeview = Gtk.TreeView(model=history_store)
		number_column = Gtk.TreeViewColumn(
			"Number", Gtk.CellRendererText(), text=1)
		number_column.set_sort_column_id(1)
		invoice_column = Gtk.TreeViewColumn(
			"Invoice", Gtk.CellRendererText(), text=2)
		invoice_column.set_sort_column_id(2)
		reprinted_column = Gtk.TreeViewColumn(
			"Reprinted", Gtk.CellRendererText(), text=3)
		reprinted_column.set_sort_column_id(4)
		treeview.append_column(number_column)
		treeview.append_column(invoice_column)
		treeview.append_column(reprinted_column)
		scrolled = Gtk.ScrolledWindow()
		scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
		scrolled.add(treeview)
		vbox.pack_start(scrolled, True, True, 0)

		button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
		view_button = Gtk.Button(label="View PDF")
		close_button = Gtk.Button(label="Close")
		button_box.pack_start(close_button, False, False, 0)
		button_box.pack_end(view_button, False, False, 0)
		vbox.pack_start(button_box, False, False, 0)

		def on_view_clicked(_):
			history_selection = treeview.get_selection()
			history_model, history_iter = history_selection.get_selected()
			if history_iter is None:
				return
			reprint_id = history_model.get_value(history_iter, 0)
			invoice_name = history_model.get_value(history_iter, 2)
			c2 = DB.cursor()
			c2.execute("SELECT pdf_data FROM invoice_reprints WHERE id = %s",
						(reprint_id,))
			pdf_row = c2.fetchone()
			c2.close()
			DB.rollback()
			if pdf_row is None:
				return
			file_name = "%s_reprint_%s.pdf" % (invoice_name, reprint_id)
			with open("/tmp/" + file_name, 'wb') as f:
				f.write(bytes(pdf_row[0]))
			subprocess.call("xdg-open /tmp/" + file_name, shell=True)

		view_button.connect("clicked", on_view_clicked)
		close_button.connect("clicked", lambda _: history_window.destroy())
		history_window.show_all()

	def invoice_chart_clicked (self, button):
		window = Gtk.Window()
		box = Gtk.VBox()
		window.add (box)
		from matplotlib.figure import Figure
		from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
		from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar
		figure = Figure(figsize=(4, 4), dpi=100)
		canvas = FigureCanvas(figure)  # a Gtk.DrawingArea
		canvas.set_size_request(900, 600)
		box.pack_start(canvas, True, True, 0)
		toolbar = NavigationToolbar(canvas, window)
		box.pack_start(toolbar, False, False, 0)
		plot = figure.add_subplot(111)
		labels = list()
		fractions = list()
		unpaid = 0
		cursor = DB.cursor()
		cursor.execute("SELECT SUM(amount_due), c.name FROM invoices "
							"JOIN contacts AS c ON c.id = invoices.customer_id "
							"WHERE (canceled, paid, posted) = "
							"(False, False, True) GROUP BY customer_id, c.name "
							"ORDER BY c.name")
		for row in cursor.fetchall():
			customer_total = row[0]
			customer_name = row[1]
			fractions.append(customer_total)
			labels.append(customer_name)
			unpaid += 1
		if unpaid == 0:
			labels.append("None")
			fractions.append(1.00)
		cursor.close()
		plot.pie (fractions, labels=labels, autopct='%1.f%%', radius=0.9)
		window.set_title ('Unpaid invoices pie chart')
		window.set_icon_name ('pygtk-posting')
		window.show_all()
		DB.rollback()

	def unpaid_chart_window_delete_event (self, window, event):
		window.hide()
		return True

	def date_entry_icon_released (self, entry, icon, position):
		self.date_calendar.set_relative_to(entry)
		self.date_calendar.show_all()

	def date_selected (self, calendar):
		self.date = calendar.get_date()
		self.cancel_confirm_button.set_sensitive(True)
		self.cancel_confirm_button.set_label("Yes, cancel invoice")
		self.cancel_entry.set_text(calendar.get_text())

	def cancel_dialog (self, widget):
		cancel_window = Gtk.Window()
		cancel_window.set_title("Cancel Invoice")
		cancel_window.set_transient_for(self.window)
		cancel_window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
		cancel_window.set_default_size(400, 300)
		cancel_window.set_icon_name("pygtk-posting")
		cancel_window.set_border_width(10)

		vbox = Gtk.VBox(spacing=6)
		cancel_window.add(vbox)

		date_box = Gtk.Box(spacing=6)
		date_label = Gtk.Label(label="Date ")
		date_entry = Gtk.Entry()
		date_entry.set_editable(False)
		date_entry.set_icon_from_stock(Gtk.EntryIconPosition.PRIMARY, "gtk-find")
		date_entry.connect("icon-release", self.date_entry_icon_released)
		date_box.pack_start(date_label, False, False, 0)
		date_box.pack_start(date_entry, False, False, 0)
		vbox.pack_start(date_box, False, False, 0)

		message = ("Do you want to cancel %s ?\nThis is not reversible!"
					% self.invoice_name)
		message_label = Gtk.Label(label=message)
		message_label.set_valign(Gtk.Align.CENTER)
		message_label.set_vexpand(True)
		vbox.pack_start(message_label, True, True, 0)

		button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
		no_button = Gtk.Button(label="No, go back")
		yes_button = Gtk.Button(label="No date selected")
		yes_button.set_sensitive(False)
		button_box.pack_start(no_button, False, False, 0)
		button_box.pack_end(yes_button, False, False, 0)
		vbox.pack_start(button_box, False, False, 0)

		self.cancel_entry = date_entry
		self.cancel_confirm_button = yes_button

		def on_no_clicked(_):
			cancel_window.destroy()

		def on_yes_clicked(_):
			transactor.cancel_invoice(self.date, self.invoice_id)
			self.cursor.execute("UPDATE invoices SET canceled = True "
								"WHERE id = %s"
								"; "
								"UPDATE serial_numbers "
								"SET invoice_item_id = NULL "
								"WHERE invoice_item_id IN "
								"(SELECT id FROM invoice_items "
								"WHERE invoice_id = %s)",
								(self.invoice_id, self.invoice_id))
			DB.commit()
			self.populate_unpaid_invoices ()
			cancel_window.destroy()

		no_button.connect("clicked", on_no_clicked)
		yes_button.connect("clicked", on_yes_clicked)

		cancel_window.show_all()

		
	def view_invoice(self, widget):
		treeselection = self.get_object('treeview-selection')
		model, path = treeselection.get_selected_rows ()
		if path != []:
			tree_iter = model.get_iter(path[0])
			invoice_id = model.get_value(tree_iter, 0)
			self.cursor.execute("SELECT name, pdf_data FROM invoices "
								"WHERE id = %s", (invoice_id,))
			for cell in self.cursor.fetchall():
				file_name = cell[0] + ".pdf"
				file_data = cell[1]
				f = open("/tmp/" + file_name,'wb')
				f.write(file_data)
				subprocess.call("xdg-open /tmp/" + str(file_name), shell = True)
				f.close()
			DB.rollback()

	def focus(self, window, event):
		self.populate_unpaid_invoices()

	def populate_unpaid_invoices(self):
		unpaid_invoice_amount = decimal.Decimal()
		treeview_selection = self.get_object('treeview-selection')
		model, path = treeview_selection.get_selected_rows()
		model.clear()
		c = DB.cursor()
		c.execute("SELECT "
						"i.id, "
						"i.name, "
						"c.id, "
						"c.name, "
						"format_date(dated_for), "
						"dated_for::text, "
						"amount_due::text, "
						"amount_due::float, "
						"COALESCE(r.reprint_count, 0) "
					"FROM invoices AS i "
					"JOIN contacts AS c ON i.customer_id = c.id "
					"LEFT JOIN (SELECT invoice_id, COUNT(*) AS reprint_count "
						"FROM invoice_reprints GROUP BY invoice_id) AS r "
						"ON r.invoice_id = i.id "
					"WHERE (i.canceled, i.paid, i.posted) = "
					"(False, False, True) "
					"ORDER BY i.id")
		tupl = c.fetchall()
		for row in tupl:
			model.append(row)
			unpaid_invoice_amount += decimal.Decimal(row[6])
		if path != [] and tupl != []:
			treeview_selection.select_path(path)
			self.get_object('treeview1').scroll_to_cell(path)
		c.execute("SELECT "
					"COALESCE(i.amount_due - (pi.amount + cm.amount), 0.00)::money "
					"FROM (SELECT SUM(amount_due) AS amount_due FROM invoices "
					"WHERE (posted, canceled, active) = (True, False, True)) i, "
					"(SELECT SUM(amount) AS amount FROM payments_incoming "
					"WHERE misc_income = False) pi, "
					"(SELECT SUM(amount_owed) AS amount FROM credit_memos "
					"WHERE posted = True) cm ")
		unpaid = c.fetchone()[0]
		self.get_object('AR_balance_label').set_label(unpaid)
		l = '${:,.2f}'.format(unpaid_invoice_amount)
		self.get_object('unpaid_invoices_label').set_label(l)
		c.close()
		DB.rollback()

	def row_activated(self, treeview, path, treeviewcolumn):
		treeiter = self.store.get_iter(path)
		self.invoice_id = self.store.get_value(treeiter, 0)
		self.invoice_name = self.store.get_value(treeiter, 1)
		self.contact_id = self.store.get_value(treeiter, 2)
		self.get_object('button1').set_sensitive(True)
		self.get_object('button2').set_sensitive(True)
		self.get_object('button4').set_sensitive(True)
		self.get_object('edit_invoice').set_sensitive(True)
		self.get_object('customer_invoices_pdf_menuitem').set_sensitive(True)

	def payment_window (self, widget):
		selection = self.get_object('treeview-selection')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		customer_id = model[path][2]
		import customer_payment
		customer_payment.GUI(customer_id)

	def edit_invoice_clicked (self, button):
		treeselection = self.get_object('treeview-selection')
		model, path = treeselection.get_selected_rows ()
		if path != []:
			import invoice_window
			invoice_id = model[path][0]
			c = DB.cursor()
			c.execute("SELECT CURRENT_DATE - date_created FROM invoices "
						"WHERE id = %s", (invoice_id,))
			days = c.fetchone()[0]
			if days > 30:
				dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.INFO,
											buttons = Gtk.ButtonsType.OK)
				dialog.set_transient_for(self.window)
				dialog.set_markup ("This invoice was created more than \n"
									"30 days ago. The date will not be editable.")
				dialog.run()
				dialog.destroy()
				invoice_window.InvoiceGUI(invoice_id, date_editable = False)
			else:
				invoice_window.InvoiceGUI(invoice_id)

	def new_statement (self, widget):
		new_statement.GUI()

	def customer_invoices_pdf_clicked(self, widget):
		import threading
		from gi.repository import GLib
		c = DB.cursor()
		c.execute("SELECT i.id, i.pdf_data, ct.name FROM invoices AS i "
					"JOIN contacts AS ct ON ct.id = i.customer_id "
					"WHERE i.customer_id = %s "
					"AND (i.canceled, i.paid, i.posted) = (False, False, True) "
					"ORDER BY i.id",
					(self.contact_id,))
		invoices = c.fetchall()
		c.close()
		DB.rollback()
		if not invoices:
			self.show_message("No unpaid invoices found for this customer.")
			return
		customer_name = invoices[0][2]

		progress_window = Gtk.Window()
		progress_window.set_title("Generating customer invoices PDF")
		progress_window.set_transient_for(self.window)
		progress_window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
		progress_window.set_default_size(420, 260)
		progress_window.set_border_width(10)
		vbox = Gtk.VBox(spacing=6)
		progress_window.add(vbox)
		scrolled = Gtk.ScrolledWindow()
		scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
		text_view = Gtk.TextView()
		text_view.set_editable(False)
		text_view.set_wrap_mode(Gtk.WrapMode.WORD)
		text_buf = text_view.get_buffer()
		scrolled.add(text_view)
		vbox.pack_start(scrolled, True, True, 0)
		button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
		view_button = Gtk.Button(label="View PDF")
		view_button.set_sensitive(False)
		email_button = Gtk.Button(label="Send via email")
		email_button.set_sensitive(False)
		close_button = Gtk.Button(label="Close")
		button_box.pack_start(close_button, False, False, 0)
		button_box.pack_end(email_button, False, False, 0)
		button_box.pack_end(view_button, False, False, 0)
		vbox.pack_start(button_box, False, False, 0)
		progress_window.show_all()

		pdf_result = [None]

		def log(msg):
			def _append():
				text_buf.insert(text_buf.get_end_iter(), msg + "\n")
				text_view.scroll_to_iter(text_buf.get_end_iter(), 0, False, 0, 0)
				return False
			GLib.idle_add(_append)

		def finish():
			def _enable():
				if pdf_result[0]:
					view_button.set_sensitive(True)
					email_button.set_sensitive(True)
				return False
			GLib.idle_add(_enable)

		def on_view_clicked(_):
			subprocess.Popen(["xdg-open", pdf_result[0]])

		def on_email_clicked(_):
			c = DB.cursor()
			c.execute("SELECT name, email FROM contacts WHERE id = %s",
						(self.contact_id,))
			row = c.fetchone()
			c.close()
			DB.rollback()
			if row is not None and row[1]:
				name, addr = row
				to = "%s <%s>" % (name, addr)
			else:
				to = ""
			subprocess.Popen(["thunderbird", "-compose",
								"to=%s,subject=Unpaid invoices,attachment=%s"
								% (to, pdf_result[0])])

		view_button.connect("clicked", on_view_clicked)
		email_button.connect("clicked", on_email_clicked)
		close_button.connect("clicked", lambda _: progress_window.destroy())

		def generate():
			from pypdf import PdfWriter, PdfReader, Transformation
			from reportlab.pdfgen import canvas as rl_canvas
			from reportlab.lib.pagesizes import letter
			import io as _io
			log("Found %d unpaid invoice(s) for %s" % (len(invoices), customer_name))
			try:
				invoice_pages = []
				for inv_id, pdf_bytes, _ in invoices:
					if pdf_bytes is None:
						log("Invoice %s: no PDF data, skipping" % inv_id)
						continue
					log("Reading invoice %s..." % inv_id)
					reader = PdfReader(_io.BytesIO(bytes(pdf_bytes)))
					if reader.pages:
						invoice_pages.append((inv_id, reader.pages[0]))
				if not invoice_pages:
					log("No invoice pages found, aborting.")
					return
				page_w, page_h = letter
				margin = 18
				gap = 6
				cell_w = (page_w - 2 * margin - gap) / 2
				cell_h = (page_h - 2 * margin - gap) / 2
				positions = [
					(margin, margin + gap + cell_h),
					(margin + gap + cell_w, margin + gap + cell_h),
					(margin, margin),
					(margin + gap + cell_w, margin),
				]
				writer = PdfWriter()
				num_pages = (len(invoice_pages) + 3) // 4
				for g in range(num_pages):
					log("Building page %d of %d..." % (g + 1, num_pages))
					group = invoice_pages[g * 4 : g * 4 + 4]
					output_page = writer.add_blank_page(page_w, page_h)
					borders = []
					for i, (inv_id, inv_page) in enumerate(group):
						cell_x, cell_y = positions[i]
						mb = inv_page.mediabox
						pw = float(mb.width)
						ph = float(mb.height)
						scale = min(cell_w / pw, cell_h / ph)
						draw_w = pw * scale
						draw_h = ph * scale
						img_x = cell_x + (cell_w - draw_w) / 2
						img_y = cell_y + (cell_h - draw_h) / 2
						tx = img_x - scale * float(mb.left)
						ty = img_y - scale * float(mb.bottom)
						output_page.merge_transformed_page(
							inv_page, Transformation((scale, 0, 0, scale, tx, ty)))
						borders.append((img_x, img_y, draw_w, draw_h))
					border_buf = _io.BytesIO()
					cnv = rl_canvas.Canvas(border_buf, pagesize=letter)
					cnv.setStrokeColorRGB(0, 0, 0)
					cnv.setLineWidth(0.5)
					for (img_x, img_y, draw_w, draw_h) in borders:
						cnv.rect(img_x, img_y, draw_w, draw_h)
					cnv.save()
					border_buf.seek(0)
					output_page.merge_page(PdfReader(border_buf).pages[0])
				safe_name = "".join(ch if ch.isalnum() or ch in (' ', '_', '-') else '_'
									for ch in customer_name).strip()
				output_path = "/tmp/%s_unpaid_invoices.pdf" % safe_name
				log("Saving PDF...")
				with open(output_path, 'wb') as f:
					writer.write(f)
				pdf_result[0] = output_path
				log("Done.")
			except Exception as e:
				log("Error: %s" % str(e))
			finally:
				finish()

		threading.Thread(target=generate, daemon=True).start()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()

