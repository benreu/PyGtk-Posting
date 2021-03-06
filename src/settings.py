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
from db import transactor
from constants import ui_directory, DB

UI_FILE = ui_directory + "/settings.ui"

class GUI():
	def __init__(self, setting_container = None):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.document_type_id = 0

		self.cursor.execute("SELECT "
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
		for row in self.cursor.fetchall():
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
		DB.rollback()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def load_precision (self):
		self.cursor.execute("SELECT qty_prec, price_prec "
							"FROM settings.purchase_order")
		for row in self.cursor.fetchall():
			qty_prec = row[0]
			price_prec = row[1]
			self.builder.get_object('spinbutton2').set_value(qty_prec)
			self.builder.get_object('adjustment3').set_lower(qty_prec)
			self.builder.get_object('spinbutton3').set_value(price_prec)
			self.builder.get_object('adjustment4').set_lower(price_prec)

	def precision_save_clicked (self, button):
		dialog = self.builder.get_object('precision_dialog')
		result = dialog.run()
		if result == Gtk.ResponseType.ACCEPT:
			qty_prec = self.builder.get_object('spinbutton2').get_value_as_int()
			price_prec = self.builder.get_object('spinbutton3').get_value_as_int()
			self.cursor.execute("UPDATE settings.purchase_order "
								"SET (qty_prec, price_prec) = (%s, %s)", 
								(qty_prec, price_prec))
			self.cursor.execute("ALTER TABLE public.purchase_order_items "
								"ALTER COLUMN qty "
								"TYPE numeric(12,"+ str(qty_prec) +");")
			self.cursor.execute("ALTER TABLE public.purchase_order_items "
								"ALTER COLUMN price "
								"TYPE numeric(12,"+ str(price_prec) +");")
			DB.commit()
			self.load_precision ()
		dialog.hide()

	def date_entry_changed (self, entry):
		format = entry.get_text()
		try:
			self.cursor.execute("UPDATE public.settings "
								"SET date_format = %s "
								"RETURNING format_date(CURRENT_DATE)", 
								(format,))
			formatted_date = self.cursor.fetchone()[0]
			DB.commit()
		except Exception:
			DB.rollback()
			formatted_date = "#Error"
		self.builder.get_object('label49').set_text(formatted_date)

	def date_with_time_changed (self, entry):
		format = entry.get_text()
		try:
			self.cursor.execute("UPDATE public.settings "
								"SET timestamp_format = %s "
								"RETURNING format_timestamp(CURRENT_TIMESTAMP)", 
								(format,))
			formatted_date = self.cursor.fetchone()[0]
			DB.commit()
		except Exception:
			DB.rollback()
			formatted_date = "#Error"
		self.builder.get_object('label51').set_text(formatted_date)

	def spinbutton_focus_in_event (self, spinbutton, event):
		GLib.idle_add(spinbutton.select_region, 0, -1)

	def select_spinbutton_value (self, spinbutton):
		spinbutton.select_region(0, -1)

	def finance_fee_value_changed (self, spinbutton):
		finance_rate = spinbutton.get_value()
		self.cursor.execute("UPDATE settings "
							"SET finance_rate = ((%s/100)/365)", 
							(finance_rate,))
		DB.commit()


	def cost_decrease_alert_spinbutton_changed (self, spinbutton):
		percent = spinbutton.get_value()
		self.cursor.execute("UPDATE settings "
							"SET cost_decrease_alert = (%s/100)", (percent,))
		DB.commit()

	def populate_columns (self):
		store = self.builder.get_object('invoice_columns_store')
		self.cursor.execute("SELECT id, column_name, visible "
							"FROM settings.invoice_columns ORDER BY id")
		for row in self.cursor.fetchall():
			store.append(row)
		store = self.builder.get_object('po_columns_store')
		self.cursor.execute("SELECT id, column_name, visible "
							"FROM settings.po_columns ORDER BY id")
		for row in self.cursor.fetchall():
			store.append(row)
		store = self.builder.get_object('document_columns_store')
		self.cursor.execute("SELECT id, column_name, visible "
							"FROM settings.document_columns ORDER BY id")
		for row in self.cursor.fetchall():
			store.append(row)

	def request_po_attachment_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.cursor.execute("UPDATE settings "
							"SET request_po_attachment = %s",
							(active,))
		DB.commit()

	def invoice_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('invoice_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		self.cursor.execute("UPDATE settings.invoice_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		DB.commit()

	def document_column_name_edited (self, cellrenderertext, path, text):
		store = self.builder.get_object('document_columns_store')
		id_ = store[path][0]
		self.cursor.execute("UPDATE settings.document_columns "
							"SET column_name = %s "
							"WHERE id = %s", (text, id_))
		DB.commit()
		store[path][1] = text

	def document_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('document_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		self.cursor.execute("UPDATE settings.document_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		DB.commit()

	def po_column_visible_toggled (self, toggle, path):
		store = self.builder.get_object('po_columns_store')
		active = not toggle.get_active()
		id_ = store[path][0]
		store[path][2] = active
		self.cursor.execute("UPDATE settings.po_columns SET visible = %s "
							"WHERE id = %s", (active, id_))
		DB.commit()

	def exact_payment_checkbutton_toggled (self, checkbutton):
		self.cursor.execute("UPDATE settings SET enforce_exact_payment = %s",
													(checkbutton.get_active(),))
		DB.commit()

	def accrual_based_togglebutton_clicked (self, togglebutton):
		self.cursor.execute("SELECT accrual_based FROM settings")
		accrual = self.cursor.fetchone()[0]
		if togglebutton.get_active() == True and accrual == False:
			dialog = self.builder.get_object('accrual_dialog')
			result = dialog.run()
			if result == Gtk.ResponseType.ACCEPT:
				self.cursor.execute("UPDATE settings SET accrual_based = True")
				self.cursor.execute("ALTER TABLE public.settings "
									"ADD CONSTRAINT accrual_irreversible "
									"CHECK (accrual_based = True);")
				transactor.switch_to_accrual_based()
				DB.commit()
			else:
				self.builder.get_object('radiobutton1').set_active(True)
			dialog.hide()
		elif accrual == True:
			togglebutton.set_active(True)

	def add_time_clock_project(self, widget):
		project_text = widget.get_text()
		if project_text == "":
			return
		self.cursor.execute("INSERT INTO time_clock_projects "
							"(name, start_date, permanent, active) VALUES "
							"(%s, CURRENT_DATE, True, True)", (project_text,))
		DB.commit()
		widget.set_text("")
		self.populate_time_clock_projects ()

	def populate_time_clock_projects(self):
		self.time_clock_store.clear()		
		self.cursor.execute("SELECT id, name FROM time_clock_projects "
							"WHERE (permanent, active) = (True, True)")
		for row in self.cursor.fetchall():
			self.time_clock_store.append(row)

	def end_time_clock_project(self, widget):
		model, path = self.builder.get_object('treeview-selection4').get_selected_rows()
		if path != []:
			treeiter = model.get_iter(path)
			project_id = model.get_value(treeiter, 0)
			self.cursor.execute("UPDATE time_clock_projects "
								"SET (active, stop_date) = "
								"(False, CURRENT_DATE) "
								"WHERE id = %s", (project_id, ))
			DB.commit()
			self.populate_time_clock_projects ()

	def populate_all_widgets(self):
		self.cursor.execute("SELECT * FROM company_info")
		for row in self.cursor.fetchall():
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
		self.populate_time_clock_projects ()

	def direct_print_toggled (self, checkbutton):
		self.cursor.execute("UPDATE settings SET print_direct = %s",
													[checkbutton.get_active()])	
		DB.commit()

	def email_when_possible(self, widget):
		self.cursor.execute("UPDATE settings SET email_when_possible = %s", 
														[widget.get_active()])	
		DB.commit()

	def backup_days_spinbutton_changed (self, spinbutton):
		days = spinbutton.get_value_as_int()
		self.cursor.execute("UPDATE settings "
							"SET backup_frequency_days = %s", (days,))
		DB.commit()

	def statement_date_changed (self, spinbutton):
		day_of_month = spinbutton.get_value_as_int()
		self.cursor.execute("UPDATE settings "
							"SET statement_day_of_month = %s", (day_of_month,))
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
		
		self.cursor.execute("UPDATE company_info SET "
							"(name, street, city, state, zip, country, phone, "
							"fax, email, website, tax_number) = "
							"(%s, %s, %s ,%s, %s, %s, %s, %s, %s, %s, %s)", 
							(name, street, city, state, zip_, country, phone, 
							fax, email, website, tax_number))
		DB.commit()

	def populate_document_types(self):
		self.document_type_store.clear()
		self.cursor.execute("SELECT id, name FROM document_types")
		for row in self.cursor.fetchall():
			self.document_type_store.append(row)
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

		self.cursor.execute("INSERT INTO document_types "
							"(name, text1, text2, text3, text4, text5, text6, "
							"text7, text8, text9, text10, text11, text12) "
							"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s, %s, %s)", 
							(document_type_name, text1, text2, text3, 
							text4, text5, text6, text7, text8, text9, 
							text10, text11, text12))
		DB.commit()
		self.populate_document_types ()
		document_type_entry.set_text("")

	def delete_document_type_clicked (self, widget):
		pass

	def document_type_row_activate (self, treeview, path, treeviewcolumn):
		treeiter = self.document_type_store.get_iter(path)
		self.document_type_id = self.document_type_store.get_value(treeiter, 0)
		self.cursor.execute("SELECT * FROM document_types WHERE id = %s", 
							(self.document_type_id,))
		for row in self.cursor.fetchall():
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

		self.cursor.execute("UPDATE document_types SET "
							"(text1, text2, text3, text4, text5, text6, text7, "
							"text8, text9, text10, text11, text12) = "
							"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
							"%s, %s) WHERE id = %s", 
							(text1, text2, text3, text4, text5, text6, text7, 
							text8, text9, text10, text11, text12, 
							self.document_type_id))
		DB.commit()
		
		
		
	
