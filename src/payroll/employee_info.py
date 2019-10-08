# employee_info.py
#
# Copyright (C) 2016 reuben 
# 
# pygtk-posting is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# pygtk-posting is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib
from dateutils import DateTimeCalendar
from datetime import datetime
from multiprocessing import Queue, Process
from queue import Empty
import sane, psycopg2, subprocess
from constants import db, ui_directory, broadcaster

UI_FILE = ui_directory + "/payroll/employee_info.ui"

device = None

class EmployeeInfoGUI(Gtk.Builder):
	def __init__(self):
		
		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.employee_store = self.get_object('employee_store')
		self.s_s_medicare_store = self.get_object('s_s_medicare_store')
		self.federal_withholding_store = self.get_object('federal_withholding_store')
		self.state_withholding_store = self.get_object('state_withholding_store')

		self.db = db
		self.cursor = self.db.cursor()

		self.populate_employee_store ()
		self.born_calendar = DateTimeCalendar (override = True)
		self.on_payroll_since_calendar = DateTimeCalendar (override = True)
		self.born_calendar.connect("day-selected", 
								self.born_calendar_date_selected )
		self.on_payroll_since_calendar.connect ("day-selected", 
								self.on_payroll_since_calendar_date_selected)
		
		self.window = self.get_object('window1')
		self.window.show_all()
		broadcaster.connect("shutdown", self.main_shutdown)
		
		self.get_object("button5").set_label("No scanner selected")
		self.get_object("button5").set_sensitive(False)

		self.data_queue = Queue()
		self.scanner_store = self.get_object("scanner_store")
		thread = Process(target=self.get_scanners)
		thread.start()
		GLib.timeout_add(100, self.populate_scanners)

	def populate_scanners(self):
		try:
			devices = self.data_queue.get_nowait()
			for scanner in devices:
				device_id = scanner[0]
				device_manufacturer = scanner[1]
				name = scanner[2]
				given_name = scanner[3]
				self.scanner_store.append([str(device_id), device_manufacturer,
											name, given_name])
		except Empty:
			return True
		
	def get_scanners(self):
		sane.init()
		devices = sane.get_devices()
		self.data_queue.put(devices)

	def main_shutdown (self):
		# commit all changes before shutdown,
		# because committing changes releases the row lock
		self.db.commit()

	def populate_employee_store (self):
		self.populating = True
		self.employee_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE employee = True")
		for row in self.cursor.fetchall():
			self.employee_store.append(row)
		self.populating = False

	def employee_treeview_cursor_changed (self, treeview):
		if self.populating == True:
			return
		selection = self.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.employee_id = model[path][0]
		self.select_employee ()

	def select_employee (self):
		self.populating = True
		self.db.commit() # save and unlock the current employee
		cursor = self.db.cursor()
		try:
			cursor.execute("SELECT "
								"born, "
								"social_security, "
								"social_security_exempt, "
								"on_payroll_since, "
								"wage, "
								"payment_frequency, "
								"married, "
								"format_date(last_updated), "
								"state_withholding_exempt, "
								"state_credits, "
								"state_extra_withholding, "
								"fed_withholding_exempt, "
								"fed_credits, "
								"fed_extra_withholding "
							"FROM payroll.employee_info "
							"WHERE employee_id = %s "
							"ORDER BY current DESC, id DESC "
							"LIMIT 1 FOR UPDATE NOWAIT",
							(self.employee_id,))
		except psycopg2.OperationalError as e:
			self.db.rollback()
			cursor.close()
			self.get_object('box1').set_sensitive(False)
			error = str(e) + "Hint: somebody else is editing this employee info"
			self.show_message (error)
			self.populating = False
			return False
		for row in cursor.fetchall():
			self.born_calendar.set_date (row[0])
			self.get_object('entry2').set_text(row[1])
			self.get_object('checkbutton3').set_active(row[2])
			self.on_payroll_since_calendar.set_date (row[3])
			self.get_object('spinbutton6').set_value(row[4])
			self.get_object('spinbutton5').set_value(row[5])
			self.get_object('checkbutton4').set_active(row[6])
			self.get_object('label6').set_text(row[7])
			self.get_object('checkbutton2').set_active(row[8])
			self.get_object('spinbutton3').set_value(row[9])
			self.get_object('spinbutton2').set_value(row[10])
			self.get_object('checkbutton1').set_active(row[11])
			self.get_object('spinbutton4').set_value(row[12])
			self.get_object('spinbutton1').set_value(row[13])
			break
		else:
			cursor.execute("INSERT INTO payroll.employee_info (employee_id) "
								"VALUES (%s)", (self.employee_id,))
			self.db.commit()
			GLib.timeout_add(50, self.select_employee)
		self.populating = False
		self.populate_exemption_forms ()
		cursor.close()
		self.get_object('box1').set_sensitive(True)

	def populate_exemption_forms (self):
		self.s_s_medicare_store.clear()
		self.state_withholding_store.clear()
		self.federal_withholding_store.clear()
		self.cursor.execute("SELECT id, format_date(date_inserted) "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND s_s_medicare_exemption_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			self.s_s_medicare_store.append(row)
		self.cursor.execute("SELECT id, format_date(date_inserted) "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND state_withholding_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			self.state_withholding_store.append(row)
		self.cursor.execute("SELECT id, format_date(date_inserted) "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND fed_withholding_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			self.federal_withholding_store.append(row)

	def s_s_m_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		id = model[path][0]
		self.cursor.execute("SELECT s_s_medicare_exemption_pdf "
							"FROM payroll.emp_pdf_archive "
							"WHERE id = %s",
							(id ,))
		for row in self.cursor.fetchall():
			file_data = row[0]
			file_name = "/tmp/Social_security_medicare_exemption.pdf"
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.Popen("xdg-open %s" % file_name, shell = True)
			f.close()

	def federal_withholding_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		id = model[path][0]
		self.cursor.execute("SELECT fed_withholding_pdf "
							"FROM payroll.emp_pdf_archive "
							"WHERE id = %s",
							(id ,))
		for row in self.cursor.fetchall():
			file_data = row[0]
			file_name = "/tmp/Federal_withholding_exemption.pdf"
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.Popen("xdg-open %s" % file_name, shell = True)
			f.close()

	def state_withholding_row_activated (self, treeview, path, column):
		model = treeview.get_model()
		id = model[path][0]
		self.cursor.execute("SELECT state_withholding_pdf "
							"FROM payroll.emp_pdf_archive "
							"WHERE id = %s",
							(id ,))
		for row in self.cursor.fetchall():
			file_data = row[0]
			file_name = "/tmp/State_withholding_exemption.pdf"
			f = open(file_name,'wb')
			f.write(file_data)
			subprocess.Popen("xdg-open %s" % file_name, shell = True)
			f.close()

	def payments_per_year_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def state_income_status_toggled (self, checkbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def state_credits_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def state_extra_withholding_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def federal_income_status_toggled (self, checkbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def federal_credits_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def federal_extra_withholding_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def married_checkbutton_toggled (self, checkbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def social_security_entry_changed (self, entry):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def wage_spinbutton_value_changed (self, spinbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def social_security_exemption_changed (self, checkbutton):
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def scanner_combo_changed (self, combo):
		if combo.get_active() > -1:
			self.get_object("button5").set_label("Scan")
			self.get_object("button5").set_sensitive(True)

	def show_scan_pdf_dialog (self, column):
		global device
		dialog = self.get_object("dialog1")
		result = dialog.run()
		dialog.hide()
		if result != Gtk.ResponseType.ACCEPT:
			return
		if device == None:
			device_address = self.get_object("combobox1").get_active_id()
			device = sane.open(device_address)
		document = device.scan()
		path = "/tmp/posting_pdf.pdf"
		document.save(path)
		f = open(path,'rb')
		file_data = f.read()
		binary = psycopg2.Binary(file_data)
		f.close()
		self.cursor.execute("UPDATE payroll.emp_pdf_archive "
							"SET archived = True "
							"WHERE employee_id = %s "
							"AND " + column + " IS NOT NULL" ,
							(self.employee_id,))
		self.cursor.execute("INSERT INTO payroll.emp_pdf_archive "
						"( " + column + ", employee_id, date_inserted) "
						"VALUES (%s, %s, %s)", 
						(binary, self.employee_id, datetime.today()))
		self.db.commit()
		self.populate_exemption_forms ()

	def state_button_release_event (self, button, event):
		if event.button == 1:
			self.cursor.execute("SELECT state_withholding_pdf "
								"FROM payroll.emp_pdf_archive "
								"WHERE (employee_id, archived) = (%s, False) "
								"AND state_withholding_pdf IS NOT NULL",
								(self.employee_id ,))
			for row in self.cursor.fetchall():
				file_data = row[0]
				file_name = "/tmp/State_withholding_status.pdf"
				f = open(file_name,'wb')
				f.write(file_data)
				subprocess.Popen("xdg-open %s" % file_name, shell = True)
				f.close()
				break
			else:
				label = 'Do you want to add a file from the scanner?'
				self.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("state_withholding_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.get_object('label9').set_label(label)
			self.show_scan_pdf_dialog("state_withholding_pdf")
				
	def s_s_m_button_release_event (self, button, event):
		if event.button == 1:
			self.cursor.execute("SELECT s_s_medicare_exemption_pdf "
								"FROM payroll.emp_pdf_archive "
								"WHERE (employee_id, archived) = (%s, False) "
								"AND s_s_medicare_exemption_pdf IS NOT NULL",
								(self.employee_id ,))
			for row in self.cursor.fetchall():
				file_data = row[0]
				file_name = "/tmp/Social_security_and_medicare_exemption.pdf"
				f = open(file_name,'wb')
				f.write(file_data)
				subprocess.Popen("xdg-open %s" % file_name, shell = True)
				f.close()
				break
			else:
				label = 'Do you want to add a file from the scanner?'
				self.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("s_s_medicare_exemption_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.get_object('label9').set_label(label)
			self.show_scan_pdf_dialog("s_s_medicare_exemption_pdf")

	def fed_button_release_event (self, button, event):
		if event.button == 1:
			self.cursor.execute("SELECT fed_withholding_pdf "
								"FROM payroll.emp_pdf_archive "
								"WHERE (employee_id, archived) = (%s, False) "
								"AND fed_withholding_pdf IS NOT NULL",
								(self.employee_id ,))
			for row in self.cursor.fetchall():
				file_data = row[0]
				file_name = "/tmp/Federal_withholding_exemption.pdf"
				f = open(file_name,'wb')
				f.write(file_data)
				subprocess.Popen("xdg-open %s" % file_name, shell = True)
				f.close()
				break
			else: # table 
				label = 'Do you want to add a file from the scanner?'
				self.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("fed_withholding_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.get_object('label9').set_label(label)
			self.show_scan_pdf_dialog("fed_withholding_pdf")
			
	def born_calendar_date_selected (self, calendar):
		date_text = calendar.get_text()
		self.get_object('entry1').set_text(date_text)
		if self.populating == True:
			return
		self.auto_save_employee_info ()

	def born_entry_icon_released (self, entry, icon, event):
		self.born_calendar.set_relative_to(entry)
		self.born_calendar.show()

	def on_payroll_since_calendar_date_selected (self, calendar):
		date_text = calendar.get_text()
		self.get_object('entry3').set_text(date_text)
		if self.populating == True:
			return
		self.auto_save_employee_info ()
		
	def on_payroll_since_entry_icon_released (self, entry, icon, event):
		self.on_payroll_since_calendar.set_relative_to(entry)
		self.on_payroll_since_calendar.show ()

	def save_clicked (self, button):
		born = self.born_calendar.get_date ()
		social_security = self.get_object('entry2').get_text()
		social_security_exempt = self.get_object('checkbutton3').get_active()
		on_payroll_since = self.on_payroll_since_calendar.get_date ()
		wage = self.get_object('spinbutton6').get_value()
		payment_frequency = self.get_object('spinbutton5').get_value()
		married = self.get_object('checkbutton4').get_active()
		state_withholding_exempt = self.get_object('checkbutton2').get_active()
		state_credits = self.get_object('spinbutton3').get_value()
		state_extra_withholding = self.get_object('spinbutton2').get_value()
		fed_withholding_exempt = self.get_object('checkbutton1').get_active()
		fed_credits = self.get_object('spinbutton4').get_value()
		fed_extra_withholding = self.get_object('spinbutton1').get_value()
		c = self.db.cursor()
		c.execute ("INSERT INTO payroll.employee_info "
						"(born, "
						"social_security, "
						"social_security_exempt, "
						"on_payroll_since, "
						"wage, "
						"payment_frequency, "
						"married, "
						"state_withholding_exempt, "
						"state_credits, "
						"state_extra_withholding, "
						"fed_withholding_exempt, "
						"fed_credits, "
						"fed_extra_withholding, "
						"employee_id) "
					"VALUES (%s, %s, %s, %s, %s, %s, %s, "
						"%s, %s, %s, %s, %s, %s, %s) "
					"ON CONFLICT (current, employee_id) "
						"WHERE current = True "
					"DO UPDATE SET "
						"(born, "
						"social_security, "
						"social_security_exempt, "
						"on_payroll_since, "
						"wage, "
						"payment_frequency, "
						"married, "
						"state_withholding_exempt, "
						"state_credits, "
						"state_extra_withholding, "
						"fed_withholding_exempt, "
						"fed_credits, "
						"fed_extra_withholding, "
						"last_updated) "
					"= "
						"(EXCLUDED.born, "
						"EXCLUDED.social_security, "
						"EXCLUDED.social_security_exempt, "
						"EXCLUDED.on_payroll_since, "
						"EXCLUDED.wage, "
						"EXCLUDED.payment_frequency, "
						"EXCLUDED.married, "
						"EXCLUDED.state_withholding_exempt, "
						"EXCLUDED.state_credits, "
						"EXCLUDED.state_extra_withholding, "
						"EXCLUDED.fed_withholding_exempt, "
						"EXCLUDED.fed_credits, "
						"EXCLUDED.fed_extra_withholding, "
						"now()) "
					"WHERE (employee_info.employee_id, employee_info.current) = "
						"(EXCLUDED.employee_id, True) ", 
					(born,
					social_security,
					social_security_exempt,
					on_payroll_since,
					wage,
					payment_frequency,
					married,
					state_withholding_exempt,
					state_credits,
					state_extra_withholding,
					fed_withholding_exempt,
					fed_credits,
					fed_extra_withholding, 
					self.employee_id))
		c.close()
		self.get_object('treeview1').set_sensitive(True)

	def cancel_clicked (self, button):
		self.select_employee()
		self.get_object('treeview1').set_sensitive(True)

	def auto_save_employee_info (self):
		# if we ever decide to implement autosave again, the caveats are :
		# 1 locking the row
		# 2 upserts increment the id
		self.get_object('treeview1').set_sensitive(False)

	def show_message (self, message):
		dialog = Gtk.MessageDialog( self.window,
									0,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.CLOSE,
									message)
		dialog.run()
		dialog.destroy()

	def window_delete_event (self, window, event):
		# save any uncommitted changes and unlock the selected row
		self.db.commit() 


