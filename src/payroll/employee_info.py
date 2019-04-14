# employee_info.py
#
# main.py
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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from dateutils import DateTimeCalendar, date_to_user_format
from datetime import datetime
from multiprocessing import Queue, Process
from queue import Empty
import sane, psycopg2, subprocess
import main

UI_FILE = main.ui_directory + "/payroll/employee_info.ui"

device = None

class EmployeeInfoGUI:
	def __init__(self):
		
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.employee_store = self.builder.get_object('employee_store')
		self.s_s_medicare_store = self.builder.get_object('s_s_medicare_store')
		self.federal_withholding_store = self.builder.get_object('federal_withholding_store')
		self.state_withholding_store = self.builder.get_object('state_withholding_store')

		self.db = main.db
		self.cursor = self.db.cursor()

		self.populate_employee_store ()
		self.born_calendar = DateTimeCalendar (self.db)
		self.on_payroll_since_calendar = DateTimeCalendar (self.db)
		self.born_calendar.connect("day-selected", 
								self.born_calendar_date_selected )
		self.on_payroll_since_calendar.connect ("day-selected", 
								self.on_payroll_since_calendar_date_selected)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

		
		self.builder.get_object("button5").set_label("No scanner selected")
		self.builder.get_object("button5").set_sensitive(False)

		#self.data_queue = Queue()
		#self.scanner_store = self.builder.get_object("scanner_store")
		#thread = Process(target=self.get_scanners)
		#thread.start()
		
		#GLib.timeout_add(100, self.populate_scanners)

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

	def populate_employee_store (self):
		self.populating = True
		self.employee_store.clear()
		self.cursor.execute("SELECT id, name FROM contacts "
							"WHERE employee = True")
		for row in self.cursor.fetchall():
			employee_id = row[0]
			employee_name = row[1]
			self.employee_store.append([employee_id, employee_name])
		self.populating = False

	def employee_treeview_cursor_changed (self, treeview):
		if self.populating == True:
			return
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		self.employee_id = model[path][0]
		self.employee_selected ()

	def employee_selected (self):
		self.populating = True
		self.cursor.execute("SELECT COALESCE(born, '1970-1-1'), "
							"COALESCE (social_security, ''), "
							"COALESCE (social_security_exempt, False), "
							"COALESCE (on_payroll_since, '1970-1-1'), "
							"COALESCE (wage, 10.00), "
							"COALESCE (payment_frequency, 10), "
							"COALESCE (married, False), "
							"COALESCE (last_updated, '1970-1-1'), "
							"COALESCE (state_withholding_exempt, False), "
							"COALESCE (state_credits, 0), "
							"COALESCE (state_extra_withholding, 0.00), "
							"COALESCE (fed_withholding_exempt, False), "
							"COALESCE (fed_credits, 0), "
							"COALESCE (fed_extra_withholding, 0.00) "
							"FROM payroll.employee_info WHERE employee_id = %s",
							(self.employee_id,))
		for row in self.cursor.fetchall():
			self.born_calendar.set_date (row[0])
			self.builder.get_object('entry2').set_text(row[1])
			self.builder.get_object('checkbutton3').set_active(row[2])
			self.on_payroll_since_calendar.set_date (row[3])
			self.builder.get_object('spinbutton6').set_value(row[4])
			self.builder.get_object('spinbutton5').set_value(row[5])
			self.builder.get_object('checkbutton4').set_active(row[6])
			self.builder.get_object('label6').set_text(row[7])
			self.builder.get_object('checkbutton2').set_active(row[8])
			self.builder.get_object('spinbutton3').set_value(row[9])
			self.builder.get_object('spinbutton2').set_value(row[10])
			self.builder.get_object('checkbutton1').set_active(row[11])
			self.builder.get_object('spinbutton4').set_value(row[12])
			self.builder.get_object('spinbutton1').set_value(row[13])
			break
		else:
			self.cursor.execute("INSERT INTO payroll.employee_info (employee_id) "
								"VALUES (%s)", (self.employee_id,))
			self.db.commit()
			GLib.timeout_add(50, self.employee_selected)
		self.populating = False
		self.populate_exemption_forms ()

	def populate_exemption_forms (self):
		self.s_s_medicare_store.clear()
		self.state_withholding_store.clear()
		self.federal_withholding_store.clear()
		self.cursor.execute("SELECT id, date_inserted "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND s_s_medicare_exemption_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			id = row[0]
			date_formatted = date_to_user_format(row[1])
			self.s_s_medicare_store.append([id, date_formatted])
		self.cursor.execute("SELECT id, date_inserted "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND state_withholding_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			id = row[0]
			date_formatted = date_to_user_format(row[1])
			self.state_withholding_store.append([id, date_formatted])
		self.cursor.execute("SELECT id, date_inserted "
							"FROM payroll.emp_pdf_archive "
							"WHERE employee_id = %s "
							"AND fed_withholding_pdf IS NOT NULL "
							"ORDER BY id", 
							(self.employee_id,))
		for row in self.cursor.fetchall():
			id = row[0]
			date_formatted = date_to_user_format(row[1])
			self.federal_withholding_store.append([id, date_formatted])

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

	def payment_frequency_value_changed (self, spinbutton):
		if self.populating == True:
			return
		payment_frequency = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (payment_frequency, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(payment_frequency, datetime.today(),
							self.employee_id))
		self.db.commit()

	def state_income_status_toggled (self, checkbutton):
		if self.populating == True:
			return
		status = checkbutton.get_active ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (state_withholding_exempt, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(status, datetime.today(), self.employee_id))
		self.db.commit()

	def state_credits_value_changed (self, spinbutton):
		if self.populating == True:
			return
		state_credits = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (state_credits, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(state_credits, datetime.today(), self.employee_id))
		self.db.commit()

	def state_extra_withholding_value_changed (self, spinbutton):
		if self.populating == True:
			return
		state_withholding = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (state_extra_withholding, last_updated) = "
							"(%s, %s) "
							"WHERE employee_id = %s", 
							(state_withholding, datetime.today(), 
							self.employee_id))
		self.db.commit()

	def federal_income_status_toggled (self, checkbutton):
		if self.populating == True:
			return
		status = checkbutton.get_active ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (fed_withholding_exempt, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(status, datetime.today(), self.employee_id))
		self.db.commit()

	def federal_credits_value_changed (self, spinbutton):
		if self.populating == True:
			return
		federal_credits = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (fed_credits, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(federal_credits, datetime.today(), self.employee_id))
		self.db.commit()

	def federal_extra_withholding_value_changed (self, spinbutton):
		if self.populating == True:
			return
		fed_withholding = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (fed_extra_withholding, last_updated) = "
							"(%s, %s) "
							"WHERE employee_id = %s", 
							(fed_withholding, datetime.today(), 
							self.employee_id))
		self.db.commit()

	def married_checkbutton_toggled (self, checkbutton):
		if self.populating == True:
			return
		married = checkbutton.get_active ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (married, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(married, datetime.today(), self.employee_id))
		self.db.commit()

	def social_security_entry_changed (self, entry):
		if self.populating == True:
			return
		s_s = entry.get_text ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (social_security, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(s_s, datetime.today(), self.employee_id))
		self.db.commit()

	def wage_spinbutton_value_changed (self, spinbutton):
		if self.populating == True:
			return
		wage = spinbutton.get_value ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (wage, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(wage, datetime.today(), self.employee_id))
		self.db.commit()

	def social_security_exemption_changed (self, checkbutton):
		if self.populating == True:
			return
		exemption = checkbutton.get_active ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (social_security_exempt, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(exemption, datetime.today(), self.employee_id))
		self.db.commit()

	def scanner_combo_changed (self, combo):
		if combo.get_active() > -1:
			self.builder.get_object("button5").set_label("Scan")
			self.builder.get_object("button5").set_sensitive(True)

	def show_scan_pdf_dialog (self, column):
		global device
		dialog = self.builder.get_object("dialog1")
		result = dialog.run()
		dialog.hide()
		if result != Gtk.ResponseType.ACCEPT:
			return
		if device == None:
			device_address = self.builder.get_object("combobox1").get_active_id()
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
				self.builder.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("state_withholding_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.builder.get_object('label9').set_label(label)
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
				self.builder.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("s_s_medicare_exemption_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.builder.get_object('label9').set_label(label)
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
				self.builder.get_object('label9').set_label(label)
				self.show_scan_pdf_dialog("fed_withholding_pdf")
		elif event.button == 3:
			label = 'Do you want to update the file from the scanner?'
			self.builder.get_object('label9').set_label(label)
			self.show_scan_pdf_dialog("fed_withholding_pdf")
			
	def born_calendar_date_selected (self, calendar):
		date_text = calendar.get_text()
		self.builder.get_object('entry1').set_text(date_text)
		if self.populating == True:
			return
		date = calendar.get_date ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (born, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(date, datetime.today(), self.employee_id))
		self.db.commit()

	def born_entry_icon_released (self, entry, icon, event):
		self.born_calendar.set_relative_to(entry)
		self.born_calendar.show()

	def on_payroll_since_calendar_date_selected (self, calendar):
		date_text = calendar.get_text()
		self.builder.get_object('entry3').set_text(date_text)
		if self.populating == True:
			return
		date = calendar.get_date ()
		self.cursor.execute ("UPDATE payroll.employee_info "
							"SET (on_payroll_since, last_updated) = (%s, %s) "
							"WHERE employee_id = %s", 
							(date, datetime.today(), self.employee_id))
		self.db.commit()
		
	def on_payroll_since_entry_icon_released (self, entry, icon, event):
		self.on_payroll_since_calendar.set_relative_to(entry)
		self.on_payroll_since_calendar.show ()


		
