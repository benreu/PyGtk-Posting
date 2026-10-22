# settings.py
#
# Copyright (C) 2016 - reuben
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

from gi.repository import Gtk, GLib
import ipaddress, threading
from db import transactor
from db_connection import DB
from constants import ui_directory
import credentials, emailing, zebra

UI_FILE = ui_directory + "/settings.ui"

# What each way of encrypting an SMTP connection is nearly always spoken on.
# Crossing two of them over - TLS on 587, STARTTLS on 465 - fails in the TLS
# handshake with "wrong version number", which names neither setting and reads
# like a broken server
STANDARD_SMTP_PORTS = {'tls': 465, 'starttls': 587, 'none': 25}
SECURITY_LABELS = {'tls': 'TLS', 'starttls': 'STARTTLS', 'none': 'None'}

class GUI():
	def __init__(self, setting_container = None):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.document_type_id = 0

		cursor = DB.cursor()
		cursor.execute("SELECT "
								"print_direct, "
								"statement_day_of_month, "
								"email_when_possible, "
								"enforce_exact_payment, "
								"accrual_based, "
								"cost_decrease_alert * 100, "
								"backup_frequency_days, "
								"date_format, "
								"timestamp_format, "
								"request_po_attachment, "
								"finance_rate * 100 * 365 "
							"FROM public.settings")
		for row in cursor.fetchall():
			self.builder.get_object('checkbutton1').set_active(row[0])
			self.builder.get_object('spinbutton1').set_value(row[1])
			self.builder.get_object('checkbutton5').set_active(row[2])
			self.builder.get_object('checkbutton6').set_active(row[3])
			if row[4] == False:
				self.builder.get_object('radiobutton1').set_active(True)
			else:
				self.builder.get_object('radiobutton2').set_active(True)
			self.builder.get_object('spinbutton4').set_value(row[5])
			self.builder.get_object('spinbutton5').set_value(row[6])
			self.builder.get_object('entry7').set_text(row[7])
			self.builder.get_object('entry8').set_text(row[8])
			self.builder.get_object('checkbutton2').set_active(row[9])
			self.builder.get_object('spinbutton6').set_value(row[10])
		cursor.close()
		self.load_precision()
		self.time_clock_store = self.builder.get_object('time_clock_projects_store')
		self.document_type_store = self.builder.get_object('document_type_store')
		self.populate_time_clock_projects ()
		self.setting_store = self.builder.get_object('setting_store')
		if setting_container != None:
			stack = self.builder.get_object('settings_stack')
			stack.set_visible_child(self.builder.get_object(setting_container))
		self.populate_all_widgets ()
		self.populate_columns()
		self.populate_document_types()
		self.zebra_printer_id = 0
		self.populate_zebra_printers()
		self.mail_account_id = 0
		self.mail_account_loading = False
		self.populate_mail_accounts()
		DB.rollback()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		pass

	def load_precision (self):
		cursor = DB.cursor()
		cursor.execute("SELECT qty_prec, price_prec "
							"FROM settings.purchase_order")
		for row in cursor.fetchall():
			qty_prec = row[0]
			price_prec = row[1]
			self.builder.get_object('spinbutton2').set_value(qty_prec)
			self.builder.get_object('adjustment3').set_lower(qty_prec)
			self.builder.get_object('spinbutton3').set_value(price_prec)
			self.builder.get_object('adjustment4').set_lower(price_prec)
		cursor.close()

	def precision_save_clicked (self, button):
		dialog = self.builder.get_object('precision_dialog')
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			qty_prec = self.builder.get_object('spinbutton2').get_value_as_int()
			price_prec = self.builder.get_object('spinbutton3').get_value_as_int()
			cursor = DB.cursor()
			cursor.execute("UPDATE settings.purchase_order "
								"SET (qty_prec, price_prec) = (%s, %s)",
								(qty_prec, price_prec))
			cursor.execute("ALTER TABLE public.purchase_order_items "
								"ALTER COLUMN qty "
								"TYPE numeric(12,"+ str(qty_prec) +");")
			cursor.execute("ALTER TABLE public.purchase_order_items "
								"ALTER COLUMN price "
								"TYPE numeric(12,"+ str(price_prec) +");")
			cursor.close()
			DB.commit()
			self.load_precision ()
		dialog.hide()

	def date_entry_changed (self, entry):
		format = entry.get_text()
		cursor = DB.cursor()
		try:
			cursor.execute("UPDATE public.settings "
								"SET date_format = %s "
								"RETURNING format_date(CURRENT_DATE)",
								(format,))
			formatted_date = cursor.fetchone()[0]
			cursor.close()
			DB.commit()
		except Exception:
			cursor.close()
			DB.rollback()
			formatted_date = "#Error"
		self.builder.get_object('label49').set_text(formatted_date)

	def date_with_time_changed (self, entry):
		format = entry.get_text()
		cursor = DB.cursor()
		try:
			cursor.execute("UPDATE public.settings "
								"SET timestamp_format = %s "
								"RETURNING format_timestamp(CURRENT_TIMESTAMP)",
								(format,))
			formatted_date = cursor.fetchone()[0]
			cursor.close()
			DB.commit()
		except Exception:
			cursor.close()
			DB.rollback()
			formatted_date = "#Error"
		self.builder.get_object('label51').set_text(formatted_date)

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def select_spinbutton_value (self, spinbutton):
		spinbutton.select_region(0, -1)

	def finance_fee_value_changed (self, spinbutton):
		finance_rate = spinbutton.get_value()
		cursor = DB.cursor()
		cursor.execute("UPDATE settings "
							"SET finance_rate = ((%s/100)/365)",
							(finance_rate,))
		cursor.close()
		DB.commit()


	def cost_decrease_alert_spinbutton_changed (self, spinbutton):
		percent = spinbutton.get_value()
		cursor = DB.cursor()
		cursor.execute("UPDATE settings "
							"SET cost_decrease_alert = (%s/100)", (percent,))
		cursor.close()
		DB.commit()

	def populate_columns (self):
		cursor = DB.cursor()
		store = self.builder.get_object('invoice_columns_store')
		cursor.execute("SELECT id, column_name, visible "
							"FROM settings.invoice_columns ORDER BY id")
		for row in cursor.fetchall():
			store.append(row)
		store = self.builder.get_object('po_columns_store')
		cursor.execute("SELECT id, column_name, visible "
							"FROM settings.po_columns ORDER BY id")
		for row in cursor.fetchall():
			store.append(row)
		store = self.builder.get_object('document_columns_store')
		cursor.execute("SELECT id, column_name, visible "
							"FROM settings.document_columns ORDER BY id")
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()

	def request_po_attachment_toggled (self, togglebutton):
		active = togglebutton.get_active()
		cursor = DB.cursor()
		cursor.execute("UPDATE settings "
							"SET request_po_attachment = %s",
							(active,))
		cursor.close()
		DB.commit()

	def invoice_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('invoice_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		cursor = DB.cursor()
		cursor.execute("UPDATE settings.invoice_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		cursor.close()
		DB.commit()

	def document_column_name_edited (self, cellrenderertext, path, text):
		store = self.builder.get_object('document_columns_store')
		id_ = store[path][0]
		cursor = DB.cursor()
		cursor.execute("UPDATE settings.document_columns "
							"SET column_name = %s "
							"WHERE id = %s", (text, id_))
		cursor.close()
		DB.commit()
		store[path][1] = text

	def document_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('document_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		cursor = DB.cursor()
		cursor.execute("UPDATE settings.document_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		cursor.close()
		DB.commit()

	def po_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('po_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		cursor = DB.cursor()
		cursor.execute("UPDATE settings.po_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		cursor.close()
		DB.commit()

	def exact_payment_checkbutton_toggled (self, checkbutton):
		cursor = DB.cursor()
		cursor.execute("UPDATE settings SET enforce_exact_payment = %s",
													(checkbutton.get_active(),))
		cursor.close()
		DB.commit()

	def accrual_based_togglebutton_clicked (self, togglebutton):
		cursor = DB.cursor()
		cursor.execute("SELECT accrual_based FROM settings")
		accrual = cursor.fetchone()[0]
		if togglebutton.get_active() == True and accrual == False:
			dialog = self.builder.get_object('accrual_dialog')
			result = dialog.run()
			if result == Gtk.ResponseType.ACCEPT:
				cursor.execute("UPDATE settings SET accrual_based = True")
				cursor.execute("ALTER TABLE public.settings "
									"ADD CONSTRAINT accrual_irreversible "
									"CHECK (accrual_based = True);")
				cursor.close()
				transactor.switch_to_accrual_based()
				DB.commit()
			else:
				cursor.close()
				self.builder.get_object('radiobutton1').set_active(True)
			dialog.hide()
		else:
			cursor.close()
			if accrual == True:
				togglebutton.set_active(True)

	def add_time_clock_project(self, widget):
		project_text = widget.get_text()
		if project_text == "":
			return
		cursor = DB.cursor()
		cursor.execute("INSERT INTO time_clock_projects "
							"(name, start_date, permanent, active) VALUES "
							"(%s, CURRENT_DATE, True, True)", (project_text,))
		cursor.close()
		DB.commit()
		widget.set_text("")
		self.populate_time_clock_projects ()

	def populate_time_clock_projects(self):
		self.time_clock_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name FROM time_clock_projects "
							"WHERE (permanent, active) = (True, True)")
		for row in cursor.fetchall():
			self.time_clock_store.append(row)
		cursor.close()

	def end_time_clock_project(self, widget):
		model, path = self.builder.get_object('treeview-selection4').get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			project_id = model.get_value(treeiter, 0)
			cursor = DB.cursor()
			cursor.execute("UPDATE time_clock_projects "
								"SET (active, stop_date) = "
								"(False, CURRENT_DATE) "
								"WHERE id = %s", (project_id, ))
			cursor.close()
			DB.commit()
			self.populate_time_clock_projects ()

	def populate_all_widgets(self):
		cursor = DB.cursor()
		cursor.execute("SELECT * FROM company_info")
		for row in cursor.fetchall():
			self.builder.get_object('entry15').set_text(row[1])
			self.builder.get_object('entry16').set_text(row[2])
			self.builder.get_object('entry17').set_text(row[3])
			self.builder.get_object('entry18').set_text(row[4])
			self.builder.get_object('entry19').set_text(row[5])
			self.builder.get_object('entry20').set_text(row[6])
			self.builder.get_object('entry21').set_text(row[7])
			self.builder.get_object('entry22').set_text(row[8])
			self.builder.get_object('entry23').set_text(row[9])
			self.builder.get_object('entry24').set_text(row[10])
			self.builder.get_object('entry25').set_text(row[11])
		cursor.close()
		self.populate_time_clock_projects ()

	def direct_print_toggled (self, checkbutton):
		cursor = DB.cursor()
		cursor.execute("UPDATE settings SET print_direct = %s",
													[checkbutton.get_active()])
		cursor.close()
		DB.commit()

	def email_when_possible(self, widget):
		cursor = DB.cursor()
		cursor.execute("UPDATE settings SET email_when_possible = %s",
														[widget.get_active()])
		cursor.close()
		DB.commit()

	def backup_days_spinbutton_changed (self, spinbutton):
		days = spinbutton.get_value_as_int()
		cursor = DB.cursor()
		cursor.execute("UPDATE settings "
							"SET backup_frequency_days = %s", (days,))
		cursor.close()
		DB.commit()

	def statement_date_changed (self, spinbutton):
		day_of_month = spinbutton.get_value_as_int()
		cursor = DB.cursor()
		cursor.execute("UPDATE settings "
							"SET statement_day_of_month = %s", (day_of_month,))
		cursor.close()
		DB.commit()

	def save_company_info(self, widget):
		name = self.builder.get_object('entry15').get_text()
		street = self.builder.get_object('entry16').get_text()
		city = self.builder.get_object('entry17').get_text()
		state = self.builder.get_object('entry18').get_text()
		zip_ = self.builder.get_object('entry19').get_text()
		country = self.builder.get_object('entry20').get_text()
		phone = self.builder.get_object('entry21').get_text()
		fax = self.builder.get_object('entry22').get_text()
		email = self.builder.get_object('entry23').get_text()
		website = self.builder.get_object('entry24').get_text()
		tax_number = self.builder.get_object('entry25').get_text()

		cursor = DB.cursor()
		cursor.execute("UPDATE company_info SET "
							"(name, street, city, state, zip, country, phone, "
							"fax, email, website, tax_number) = "
							"(%s, %s, %s ,%s, %s, %s, %s, %s, %s, %s, %s)",
							(name, street, city, state, zip_, country, phone,
							fax, email, website, tax_number))
		cursor.close()
		DB.commit()

	def populate_document_types(self):
		self.document_type_store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name FROM document_types")
		for row in cursor.fetchall():
			self.document_type_store.append(row)
		cursor.close()
		DB.rollback()

	def add_document_type_clicked (self, widget):
		document_type_entry = self.builder.get_object('entry2')
		document_type_name = document_type_entry.get_text()
		text1 = self.builder.get_object('entry3').get_text()
		text2 = self.builder.get_object('entry4').get_text()
		text3 = self.builder.get_object('entry5').get_text()
		text4 = self.builder.get_object('entry6').get_text()
		text5 = self.builder.get_object('entry26').get_text()
		text6 = self.builder.get_object('entry27').get_text()
		text7 = self.builder.get_object('entry28').get_text()
		text8 = self.builder.get_object('entry29').get_text()
		text9 = self.builder.get_object('entry30').get_text()
		text10 = self.builder.get_object('entry31').get_text()
		text11 = self.builder.get_object('entry32').get_text()
		text12 = self.builder.get_object('entry33').get_text()

		cursor = DB.cursor()
		cursor.execute("INSERT INTO document_types "
							"(name, text1, text2, text3, text4, text5, text6, "
							"text7, text8, text9, text10, text11, text12) "
							"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s, %s, %s)",
							(document_type_name, text1, text2, text3,
							text4, text5, text6, text7, text8, text9,
							text10, text11, text12))
		cursor.close()
		DB.commit()
		self.populate_document_types ()
		document_type_entry.set_text("")

	def delete_document_type_clicked (self, widget):
		pass

	def document_type_row_activate (self, treeview, path, treeviewcolumn):
		treeiter = self.document_type_store.get_iter(path)
		self.document_type_id = self.document_type_store.get_value(treeiter, 0)
		cursor = DB.cursor()
		cursor.execute("SELECT * FROM document_types WHERE id = %s",
							(self.document_type_id,))
		for row in cursor.fetchall():
			self.builder.get_object('entry3').set_text(row[2])
			self.builder.get_object('entry4').set_text(row[3])
			self.builder.get_object('entry5').set_text(row[4])
			self.builder.get_object('entry6').set_text(row[5])
			self.builder.get_object('entry26').set_text(row[6])
			self.builder.get_object('entry27').set_text(row[7])
			self.builder.get_object('entry28').set_text(row[8])
			self.builder.get_object('entry29').set_text(row[9])
			self.builder.get_object('entry30').set_text(row[10])
			self.builder.get_object('entry31').set_text(row[11])
			self.builder.get_object('entry32').set_text(row[12])
			self.builder.get_object('entry33').set_text(row[13])
		cursor.close()

	def document_type_py30_text_changed (self, widget):
		text1 = self.builder.get_object('entry3').get_text()
		text2 = self.builder.get_object('entry4').get_text()
		text3 = self.builder.get_object('entry5').get_text()
		text4 = self.builder.get_object('entry6').get_text()
		text5 = self.builder.get_object('entry26').get_text()
		text6 = self.builder.get_object('entry27').get_text()
		text7 = self.builder.get_object('entry28').get_text()
		text8 = self.builder.get_object('entry29').get_text()
		text9 = self.builder.get_object('entry30').get_text()
		text10 = self.builder.get_object('entry31').get_text()
		text11 = self.builder.get_object('entry32').get_text()
		text12 = self.builder.get_object('entry33').get_text()

		cursor = DB.cursor()
		cursor.execute("UPDATE document_types SET "
							"(text1, text2, text3, text4, text5, text6, text7, "
							"text8, text9, text10, text11, text12) = "
							"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s) WHERE id = %s",
							(text1, text2, text3, text4, text5, text6, text7,
							text8, text9, text10, text11, text12,
							self.document_type_id))
		cursor.close()
		DB.commit()
		
		
		
	

	def populate_zebra_printers (self, select_id = None):
		"Refill the printer list; select_id, when given, is re-selected afterwards."
		store = self.builder.get_object('zebra_printer_store')
		selection = self.builder.get_object('zebra_printer_selection')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name, host, port "
							"FROM settings.zebra_printers ORDER BY name")
		for row in cursor.fetchall():
			tree_iter = store.append(row)
			if row[0] == select_id:
				selection.select_iter(tree_iter)
		cursor.close()
		DB.rollback()

	def zebra_printer_selection_changed (self, selection):
		model, tree_iter = selection.get_selected()
		if tree_iter == None:
			return
		self.zebra_printer_id = model[tree_iter][0]
		self.builder.get_object('zebra_printer_name_entry').set_text(model[tree_iter][1])
		self.builder.get_object('zebra_printer_host_entry').set_text(model[tree_iter][2])
		self.builder.get_object('zebra_printer_port_spinbutton').set_value(model[tree_iter][3])

	def zebra_printer_new_clicked (self, button):
		self.builder.get_object('zebra_printer_selection').unselect_all()
		self.zebra_printer_id = 0
		self.builder.get_object('zebra_printer_name_entry').set_text('')
		self.builder.get_object('zebra_printer_host_entry').set_text('')
		self.builder.get_object('zebra_printer_port_spinbutton').set_value(9100)
		self.builder.get_object('zebra_printer_name_entry').grab_focus()

	def zebra_printer_form (self):
		"The form's name, host and port; None when they cannot make a printer."
		name = self.builder.get_object('zebra_printer_name_entry').get_text().strip()
		host = self.builder.get_object('zebra_printer_host_entry').get_text().strip()
		port = self.builder.get_object('zebra_printer_port_spinbutton').get_value_as_int()
		if name == '':
			self.show_message("The printer needs a name.")
			return None
		# the column is inet, so a hostname or a subnet would be refused by the
		# database anyway; checking here keeps the message readable and the
		# connection out of an aborted transaction
		try:
			ipaddress.ip_address(host)
		except ValueError:
			self.show_message("'%s' is not an IP address." % host)
			return None
		return name, host, port

	def zebra_printer_save_clicked (self, button):
		form = self.zebra_printer_form()
		if form == None:
			return
		name, host, port = form
		cursor = DB.cursor()
		if self.zebra_printer_id == 0:
			cursor.execute("INSERT INTO settings.zebra_printers "
								"(name, host, port) VALUES (%s, %s, %s) "
								"RETURNING id", (name, host, port))
			self.zebra_printer_id = cursor.fetchone()[0]
		else:
			cursor.execute("UPDATE settings.zebra_printers "
								"SET (name, host, port) = (%s, %s, %s) "
								"WHERE id = %s",
								(name, host, port, self.zebra_printer_id))
		cursor.close()
		DB.commit()
		self.populate_zebra_printers(self.zebra_printer_id)

	def zebra_printer_delete_clicked (self, button):
		if self.zebra_printer_id == 0:
			return
		cursor = DB.cursor()
		cursor.execute("DELETE FROM settings.zebra_printers WHERE id = %s",
							(self.zebra_printer_id,))
		cursor.close()
		DB.commit()
		self.zebra_printer_new_clicked(button)
		self.populate_zebra_printers()

	def zebra_printer_test_clicked (self, button):
		# the form, not the saved row, so an address can be tried before saving
		form = self.zebra_printer_form()
		if form == None:
			return
		name, host, port = form
		status = self.builder.get_object('zebra_printer_status_label')
		try:
			# a wrong address should not hang the window for the default 10s
			zebra.send_to_printer(host, port, zebra.test_label(name, host, port),
									timeout = 3)
		except zebra.ZebraError as e:
			self.show_message(str(e))
			return
		status.set_text("Test label sent to %s:%s" % (host, port))

	def populate_mail_accounts (self, select_id = None):
		"Refill the account list; select_id, when given, is re-selected after."
		store = self.builder.get_object('mail_account_store')
		selection = self.builder.get_object('mail_account_selection')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT id, name, from_address, smtp_host, active "
							"FROM settings.mail_accounts ORDER BY name")
		for row in cursor.fetchall():
			tree_iter = store.append(row)
			if row[0] == select_id:
				selection.select_iter(tree_iter)
		cursor.close()
		DB.rollback()

	def mail_account_selection_changed (self, selection):
		model, tree_iter = selection.get_selected()
		if tree_iter == None:
			return
		self.mail_account_id = model[tree_iter][0]
		cursor = DB.cursor()
		cursor.execute("SELECT name, from_name, from_address, smtp_host, "
							"smtp_port, smtp_security, smtp_user, imap_host, "
							"imap_port, imap_user, sent_folder "
						"FROM settings.mail_accounts WHERE id = %s",
						(self.mail_account_id,))
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		if row == None:
			return
		(name, from_name, from_address, smtp_host, smtp_port, smtp_security,
			smtp_user, imap_host, imap_port, imap_user, sent_folder) = row
		# the security combo follows its port around, so what is being put
		# into the form is not a choice anybody just made
		self.mail_account_loading = True
		self.builder.get_object('mail_account_name_entry').set_text(name)
		self.builder.get_object('mail_account_from_name_entry').set_text(from_name)
		self.builder.get_object('mail_account_from_address_entry').set_text(from_address)
		self.builder.get_object('mail_account_smtp_host_entry').set_text(smtp_host)
		self.builder.get_object('mail_account_smtp_port_spinbutton').set_value(smtp_port)
		self.builder.get_object('mail_account_security_combo').set_active_id(smtp_security)
		self.builder.get_object('mail_account_smtp_user_entry').set_text(smtp_user)
		self.builder.get_object('mail_account_imap_host_entry').set_text(imap_host)
		self.builder.get_object('mail_account_imap_port_spinbutton').set_value(imap_port)
		self.builder.get_object('mail_account_imap_user_entry').set_text(imap_user)
		self.builder.get_object(
				'mail_account_sent_folder_combo').get_child().set_text(sent_folder)
		self.mail_account_loading = False
		self.update_mail_account_status()

	def mail_account_security_changed (self, combo):
		'''Move the port to the one that choice is spoken on, unless a port
		was deliberately typed.

		465 is implicit TLS and 587 is STARTTLS. Crossed over, the connection
		dies in the handshake with "wrong version number" - which mentions
		neither the port nor the security setting, so the obvious reading is
		that the server or the password is at fault. Nothing then gets as far
		as checking the password, and before this the password could not be
		saved at all in that state.'''
		security = combo.get_active_id()
		if security == None or self.mail_account_loading:
			return
		spinbutton = self.builder.get_object('mail_account_smtp_port_spinbutton')
		if spinbutton.get_value_as_int() in STANDARD_SMTP_PORTS.values():
			spinbutton.set_value(STANDARD_SMTP_PORTS[security])

	def security_mismatch_hint (self, acct):
		"what to add to a connection failure when the pair looks crossed over"
		standard = STANDARD_SMTP_PORTS.get(acct.smtp_security)
		if standard == None or acct.smtp_port == standard:
			return ''
		for security, port in STANDARD_SMTP_PORTS.items():
			if port == acct.smtp_port:
				return ("\n\nPort %s is %s, not %s. Crossed over, the "
						"connection fails while encrypting, which is what this "
						"looks like." % (acct.smtp_port,
										SECURITY_LABELS[security],
										SECURITY_LABELS[acct.smtp_security]))
		return ''

	def mail_account_new_clicked (self, button):
		self.builder.get_object('mail_account_selection').unselect_all()
		self.mail_account_id = 0
		for widget in ('mail_account_name_entry', 'mail_account_from_name_entry',
						'mail_account_from_address_entry',
						'mail_account_smtp_host_entry',
						'mail_account_smtp_user_entry',
						'mail_account_imap_host_entry',
						'mail_account_imap_user_entry'):
			self.builder.get_object(widget).set_text('')
		self.builder.get_object('mail_account_smtp_port_spinbutton').set_value(587)
		self.builder.get_object('mail_account_imap_port_spinbutton').set_value(993)
		self.builder.get_object('mail_account_security_combo').set_active_id('starttls')
		self.builder.get_object(
						'mail_account_sent_folder_combo').get_child().set_text('')
		self.builder.get_object('mail_account_status_label').set_text('')
		self.builder.get_object('mail_account_name_entry').grab_focus()

	def mail_account_form (self):
		'''The form as a mail account, or None when it cannot make one. The
		hosts are not checked the way the Zebra printer host is: that column
		is inet and a label printer is on the LAN, where a mail server is
		named rather than numbered and ipaddress would refuse it outright.'''
		get = lambda widget: self.builder.get_object(widget).get_text().strip()
		acct = emailing.Account()
		acct.id = self.mail_account_id
		acct.name = get('mail_account_name_entry')
		acct.from_name = get('mail_account_from_name_entry')
		acct.from_address = get('mail_account_from_address_entry')
		acct.smtp_host = get('mail_account_smtp_host_entry')
		acct.smtp_port = self.builder.get_object(
							'mail_account_smtp_port_spinbutton').get_value_as_int()
		acct.smtp_security = self.builder.get_object(
							'mail_account_security_combo').get_active_id() or 'starttls'
		acct.smtp_user = get('mail_account_smtp_user_entry')
		acct.imap_host = get('mail_account_imap_host_entry')
		acct.imap_port = self.builder.get_object(
							'mail_account_imap_port_spinbutton').get_value_as_int()
		acct.imap_user = get('mail_account_imap_user_entry')
		acct.sent_folder = (self.builder.get_object(
					'mail_account_sent_folder_combo').get_active_text() or '').strip()
		if acct.name == '':
			self.show_message("The account needs a name.")
			return None
		if not emailing.valid_address(acct.from_address):
			self.show_message("'%s' is not an email address to send from."
								% acct.from_address)
			return None
		if acct.smtp_host == '':
			self.show_message("The account needs an SMTP server to send through.")
			return None
		return acct

	def mail_account_save_clicked (self, button):
		acct = self.mail_account_form()
		if acct == None:
			return
		warning = self.orphaned_password_warning(acct)
		values = (acct.name, acct.from_name, acct.from_address, acct.smtp_host,
					acct.smtp_port, acct.smtp_security, acct.smtp_user,
					acct.imap_host, acct.imap_port, acct.imap_user,
					acct.sent_folder)
		cursor = DB.cursor()
		# saving an account is what puts it in use, and only one may be: the
		# unique index on (active) WHERE active refuses a second one, so the
		# others are stood down first, in the same transaction
		cursor.execute("UPDATE settings.mail_accounts SET active = False "
							"WHERE active")
		if self.mail_account_id == 0:
			cursor.execute("INSERT INTO settings.mail_accounts "
								"(name, from_name, from_address, smtp_host, "
								"smtp_port, smtp_security, smtp_user, "
								"imap_host, imap_port, imap_user, "
								"sent_folder, active) "
								"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, True) RETURNING id", values)
			self.mail_account_id = cursor.fetchone()[0]
		else:
			cursor.execute("UPDATE settings.mail_accounts SET "
								"(name, from_name, from_address, smtp_host, "
								"smtp_port, smtp_security, smtp_user, "
								"imap_host, imap_port, imap_user, "
								"sent_folder, active) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"True) WHERE id = %s",
								values + (self.mail_account_id,))
		cursor.close()
		DB.commit()
		self.populate_mail_accounts(self.mail_account_id)
		self.set_mail_account_status("Saved. This is the account Posting sends "
									"from." + warning)

	def orphaned_password_warning (self, acct):
		'''Secrets are keyed on user and host, so changing either leaves the
		stored password under the old key where nothing will look for it.
		Said out loud here, because the alternative is a send that fails days
		later for no visible reason.'''
		if self.mail_account_id == 0:
			return ''
		cursor = DB.cursor()
		cursor.execute("SELECT smtp_host, smtp_user, imap_host, imap_user "
						"FROM settings.mail_accounts WHERE id = %s",
						(self.mail_account_id,))
		row = cursor.fetchone()
		cursor.close()
		DB.rollback()
		if row == None:
			return ''
		smtp_host, smtp_user, imap_host, imap_user = row
		changed = ((smtp_host, smtp_user) != (acct.smtp_host, acct.smtp_user)
					and credentials.have_password('smtp', smtp_host, smtp_user))
		changed = changed or ((imap_host, imap_user) !=
								(acct.imap_host, acct.imap_user)
					and credentials.have_password('imap', imap_host, imap_user))
		if not changed:
			return ''
		return ("\n\nThe saved password was stored under the old user name or "
				"server, so press Set password again.")

	def mail_account_delete_clicked (self, button):
		if self.mail_account_id == 0:
			return
		cursor = DB.cursor()
		cursor.execute("DELETE FROM settings.mail_accounts WHERE id = %s",
							(self.mail_account_id,))
		cursor.close()
		DB.commit()
		self.mail_account_new_clicked(button)
		self.populate_mail_accounts()
		# the keyring is deliberately left alone: the same mailbox may be
		# configured in another database from this workstation, and Forget
		# password is there for removing it on purpose
		self.set_mail_account_status("Account deleted. Any password it had is "
									"still in this computer's login keyring.")

	def mail_account_password_clicked (self, button):
		acct = self.mail_account_form()
		if acct == None:
			return
		if acct.smtp_user == '' and acct.imap_user == '':
			self.show_message("Fill in the user name the server knows you by "
								"first.\n\nA server that needs no login needs "
								"no password either.")
			return
		dialog = emailing.PasswordDialog(self.window, acct)
		password = dialog.get_password()
		if password == None:
			return
		self.run_mail_account_check(acct,
			lambda: self.store_checked_password(acct, password),
			"Checking the password...",
			on_error = lambda e: self.password_check_failed(acct, password, e))

	def password_check_failed (self, acct, password, error):
		'''What a failed check means. Returns whether it has been dealt with.

		A server that answered and said no means the password is wrong, so
		nothing is stored and the message says so - otherwise the only sign is
		a different complaint later, from Test or from a send, about no
		password being saved, and the two never connect up.

		Anything else means the password was never tested: the server was
		down, the port or the security setting was wrong, the network was
		out. Refusing to store it then would leave somebody whose server is
		unreachable unable to set a password at all, so it is offered.'''
		if isinstance(error, emailing.MailAuthError):
			self.show_message("%s\n\nNothing was saved on this computer. If "
								"the password is right, check the user name: "
								"many servers want the whole email address "
								"rather than just the part before the @."
								% error)
			return True
		dialog = Gtk.MessageDialog(message_type = Gtk.MessageType.QUESTION,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup(GLib.markup_escape_text(
						"%s%s\n\nThe password has not been checked, so it has "
						"not been saved. Save it on this computer anyway?"
						% (error, self.security_mismatch_hint(acct))))
		response = dialog.run()
		dialog.destroy()
		if response == Gtk.ResponseType.YES:
			self.run_mail_account_check(acct,
					lambda: self.store_unchecked_password(acct, password),
					"Saving the password...")
		return True

	def store_unchecked_password (self, acct, password):
		"worker thread: keep a password that could not be tested"
		self.save_password(acct, password)
		return ("Saved on this computer, untested. Press Test once the server "
				"can be reached.")

	def store_checked_password (self, acct, password):
		"worker thread: test the password, then keep it only if it worked"
		emailing.verify_login(acct, password)
		self.save_password(acct, password)
		return "The password works and is saved on this computer."

	def save_password (self, acct, password):
		"worker thread: into the login keyring, under each server it is for"
		if acct.smtp_user != '':
			credentials.store_password('smtp', acct.smtp_host, acct.smtp_user,
										password)
		if acct.imap_host != '' and acct.imap_user != '':
			credentials.store_password('imap', acct.imap_host, acct.imap_user,
										password)

	def mail_account_forget_clicked (self, button):
		acct = self.mail_account_form()
		if acct == None:
			return
		forgotten = []
		try:
			if credentials.clear_password('smtp', acct.smtp_host, acct.smtp_user):
				forgotten.append('SMTP')
			if credentials.clear_password('imap', acct.imap_host, acct.imap_user):
				forgotten.append('IMAP')
		except credentials.CredentialError as e:
			self.show_message(str(e))
			return
		if forgotten == []:
			self.set_mail_account_status("There was no password saved on this "
										"computer to forget.")
		else:
			# and not update_mail_account_status () after it: that would
			# overwrite this with its own "no password is saved" the instant it
			# was shown, so the one thing the user pressed the button to find
			# out never appeared
			self.set_mail_account_status("The %s password is no longer saved on "
										"this computer." % ' and '.join(forgotten))

	def mail_account_test_clicked (self, button):
		# the form, not the saved row, so a server can be tried before saving,
		# with the password this workstation actually has
		acct = self.mail_account_form()
		if acct == None:
			return
		self.listed_folders = []
		self.run_mail_account_check(acct, lambda: self.check_login(acct),
									"Logging in...",
									on_success = self.fill_sent_folders)

	def check_login (self, acct):
		'''worker thread: log in with the password stored on this
		workstation, and while connected ask what the folders are called, so
		the Sent folder can be chosen from the server's own list rather than
		typed from memory'''
		password = ''
		if acct.smtp_user != '':
			password = credentials.password('smtp', acct.smtp_host,
											acct.smtp_user)
		elif acct.imap_user != '':
			password = credentials.password('imap', acct.imap_host,
											acct.imap_user)
		emailing.verify_login(acct, password)
		if acct.imap_host == '':
			return "Logged in. Mail can be sent from this computer."
		imap_password = password
		if acct.imap_user != '' and acct.imap_user != acct.smtp_user:
			imap_password = credentials.password('imap', acct.imap_host,
													acct.imap_user)
		self.listed_folders = emailing.list_folders(acct, imap_password)
		return ("Logged in. Mail can be sent from this computer, and %s "
				"folders were found." % len(self.listed_folders))

	def fill_sent_folders (self):
		'''Main thread: offer the folders the server just named, and pick the
		one it says is Sent when nothing has been chosen yet.

		Typed from memory this gets a capital letter or a namespace prefix
		wrong, the APPEND is refused, and every message goes out with its copy
		unfiled - so the list comes from the server.'''
		combo = self.builder.get_object('mail_account_sent_folder_combo')
		combo.remove_all()
		for flags, name in self.listed_folders:
			combo.append_text(name)
		if (combo.get_active_text() or '').strip() != '':
			return # already chosen; the list is there to change it
		guess = emailing.likely_sent_folder(self.listed_folders)
		if guess != '':
			combo.get_child().set_text(guess)
			self.set_mail_account_status("%s is where copies of sent mail will "
										"be filed. Press Save to keep it."
										% guess)

	def run_mail_account_check (self, acct, work, busy_text, on_error = None,
								on_success = None):
		'''Run work on a worker thread and report what it says in the status
		label. Everything it does blocks - a keyring lookup waits on a prompt
		when the keyring is locked, and a server that is not answering waits
		for the timeout - so none of it may happen on the main loop.

		on_error, when given, is handed whatever was raised and returns
		whether it has reported it; the plain error dialog is shown when it
		has not.'''
		buttons = ('mail_account_password_button', 'mail_account_test_button',
					'mail_account_forget_button')
		for name in buttons:
			self.builder.get_object(name).set_sensitive(False)
		self.set_mail_account_status(busy_text)

		def report (message, error):
			for name in buttons:
				self.builder.get_object(name).set_sensitive(True)
			if error != None:
				# the true state, not a blank: after a failed Set password the
				# one thing worth knowing is that nothing got saved
				self.update_mail_account_status()
				if on_error == None or not on_error(error):
					self.show_message(message)
			else:
				# and no update_mail_account_status () after it, which would
				# overwrite this with its own wording the moment it was shown
				self.set_mail_account_status(message)
				if on_success != None:
					on_success()
			return False # idle_add: once, never re-armed

		def run ():
			try:
				message, error = work(), None
			except Exception as e:
				message, error = str(e), e
			GLib.idle_add(report, message, error)

		threading.Thread(target = run, daemon = True).start()

	def set_mail_account_status (self, text):
		self.builder.get_object('mail_account_status_label').set_text(text)

	def update_mail_account_status (self):
		'''Say whether this workstation can send. Asked of the keyring
		without unlocking it and without reading the secret, so it is safe on
		the main loop and cannot put up a prompt.'''
		get = lambda widget: self.builder.get_object(widget).get_text().strip()
		host, user = get('mail_account_smtp_host_entry'), get('mail_account_smtp_user_entry')
		if user == '':
			return # a server that needs no login has nothing to report
		if credentials.have_password('smtp', host, user):
			if credentials.locked('smtp', host, user):
				self.set_mail_account_status("A password is saved on this "
									"computer, but the login keyring is locked.")
			else:
				self.set_mail_account_status("A password is saved on this "
													"computer.")
		else:
			self.set_mail_account_status("No password is saved on this computer, "
								"so mail cannot be sent from it yet. Press "
								"Set password.")

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		# a typed host or a socket error is not markup
		dialog.set_markup (GLib.markup_escape_text(message))
		dialog.run()
		dialog.destroy()
