# pay_stub.py
#
# Copyright (C) 2016 - reuben
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, GObject, Pango
from datetime import datetime
import time, calendar, subprocess
from dateutils import datetime_to_text, DateTimeCalendar, datetime_to_user_date,\
						datetime_to_time_card_format
from check_writing import get_check_number, get_written_check_amount_text
#from db.transactor import vendor_check_payment, vendor_credit_card_payment,\
#							vendor_debit_payment, post_expense_account
#from posting_functions import get_gcalccmd_result
from decimal import Decimal							
import printing
from constants import ui_directory, DB

UI_FILE = "src/payroll/pay_stub.ui"

class Item(object):#this is used by py3o library see their example for more info
	pass


		
class PayStubGUI:
	def __init__(self):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()

		self.calendar = DateTimeCalendar(DB)
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.calendar.set_today()
		self.time_sheet_copy_info = ''

		
		check_number = get_check_number(None)
		
		self.populate_employee_combobox ()
		self.window = self.builder.get_object('window1')
		self.window.show_all()
		#t = '10/3'
		#print(get_gcalccmd_result(t))
		#self.cursor.execute("DELETE FROM time_clock_entries WHERE employee_id = 179")
		#self.cursor.execute("DELETE FROM time_clock_entries WHERE employee_id = 78")
		#self.cursor.execute("UPDATE time_clock_entries SET (employee_paid,pay_stub_id) = (False,NULL) WHERE pay_stub_id  >= 750 ")
		#self.cursor.execute("INSERT INTO payroll.fed_id_binder  (date_entered,active,table_name) VALUES (CURRENT_TIMESTAMP,True,%s)",("single_daily",))
		#self.cursor.execute("DELETE FROM payroll.pay_stubs WHERE id > 329")
		#print (self.cursor.execute("SELECT payroll.complete_paystubs(%s,%s)",(49,'Jan 31 2018')))
		#DB.commit()
		
	def focus(self, winow, r):
		self.populate_bank_combo()
		self.builder.get_object('comboboxtext3').set_sensitive(True)

	def populate_bank_combo (self):
		bank_combo = self.builder.get_object('comboboxtext3')
		bank_id = bank_combo.get_active_id()
		bank_combo.remove_all()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE check_writing = True")
		for row in self.cursor.fetchall():
			bank_number = row[0]
			bank_name = row[1]
			bank_combo.append(str(bank_number), bank_name)
		bank_combo.set_active_id(bank_id)

		
	def bank_combo_changed (self, combo = None):
		bank_account = combo.get_active_id()
		if bank_account != None:
			self.builder.get_object('button2').set_sensitive(True)
			self.bank_account = bank_account
			check_number = get_check_number(bank_account)
			self.builder.get_object('entry4').set_text(str(check_number))
			self.builder.get_object('entry4').set_sensitive(True)
			self.builder.get_object('button2').set_sensitive(True)
			self.builder.get_object('button3').set_sensitive(True)		

	def employee_combo_changed (self, widget):
		employee_combo = self.builder.get_object('combobox1')
		self.employee_id = employee_combo.get_active_id()
		#print(self.employee_id)

	def populate_employee_combobox (self):
		employee_combo = self.builder.get_object('combobox1')
		self.employee_store = self.builder.get_object("employee_store")
		self.employee_store.clear()
		self.cursor.execute("SELECT DISTINCT employee_id,name " 
							"FROM time_clock_entries "
							"JOIN contacts ON contacts.id = "
							"time_clock_entries.employee_id "
							"WHERE "
							  "time_clock_entries.employee_paid = FALSE AND "
							 "DATE_TRUNC('day', time_clock_entries.stop_time) <= %s "
							  "ORDER BY employee_id ASC",(self.pay_ending_date,))

		for row in self.cursor.fetchall():
			employee_id = row[0]
			employee_name = row[1]
			self.employee_store.append ([str(employee_id), employee_name])
		self.employee_store.append ([str(0),"Print All"])
		#employee_combo.set_active_iter(0) 
		#print(employee_combo.get_id_column())

	def calendar_day_selected(self, calendar):
		self.end_date_text = calendar.get_text()
		#print(self.end_date_text)
		self.builder.get_object('entry2').set_text(self.end_date_text)
		self.pay_ending_date = calendar.get_datetime() 
		self.populate_employee_combobox ()

		
	def calendar_entry_icon_released(self, entry, icon, event):
		self.calendar.set_relative_to(entry)
		self.calendar.show()		

	def populate_py3o_self_data(self):
		pp_info = Item()
		#print(str(self.employee_id) + ' line 134')
		self.cursor.execute("SELECT "
							  "name, "
							  "address, "
							  "city, "
							  "state, "
							  "zip, "
							  "phone, "
							  "checks_payable_to, "
							  "employee_info.id, "
							  "wage "
							"FROM "
							  " payroll.employee_info JOIN public.contacts ON "
							  " payroll.employee_info.employee_id = public.contacts.id "
							" WHERE "
							  " employee_info.employee_id = %s "
							"ORDER BY payroll.employee_info.id DESC LIMIT 1 "
							,(self.employee_id,))
		#print(self.cursor.fetchall())					
		for row in self.cursor.fetchall():
		
			pp_info.ppd_end = self.end_date_text
			pp_info.temporary_copy = self.time_sheet_copy_info
			customer = Item()
			customer.name = row[0]
			self.name = row[0]
			customer.street = row[1]
			customer.city = row[2]
			customer.state = row[3]
			customer.zip = row[4]
			customer.phone = row[5]
			customer.pay_to = row[6]
			self.emp_info_id = row[7]
			wage = row[8]
			time_card = Item()
			#print(row[8])
		self.cursor.execute("SELECT ss,dentry_hrs,arrived,left_premises,"
		"over_eight,time_out FROM payroll.daily_overtime_consolidation WHERE "
		"employee_id = %s and ss <= %s",(self.employee_id,self.pay_ending_date))
		items = list()
		for row in self.cursor.fetchall():

			item = Item()
			item.hrs_today = row[1]
			item.roll_call_date = datetime_to_user_date(row[0])
			item.time_out = row[5]
			item.start_time = datetime_to_time_card_format (row[2])
			item.ending_time = datetime_to_time_card_format (row[3])
			item.over_eight = row[4]
			items.append(item)
		
		self.cursor.execute("SELECT * FROM company_info")
		company = Item()
		for row6 in self.cursor.fetchall():
			company.name = row6[1]
			company.street = row6[2]
			company.city = row6[3]
			company.state = row6[4]
			company.zip = row6[5]
			company.country = row6[6]
			company.phone = row6[7]
			company.email = row6[9]
			company.fax = row6[8]
			company.website = row6[10]
			company.tax_number = row6[11]
		pp_info.ppd_end = datetime_to_user_date(self.pay_ending_date)
		pp_info.temporary_copy = 'Temporary Copy'
		
		deductions = list()
		self.cursor.execute("SELECT description,amount FROM payroll.emp_pretax_div_ded"
		" WHERE (type,emp_id) = ('subtract',%s) AND pay_stubs_id IS NULL ",(self.employee_id,))
		for line in self.cursor.fetchall():
			deductions_item = Item()
			deductions_item.description = line[0]
			deductions_item.amount = line[1]
			deductions.append (deductions_item)

		dividends = list()
		self.cursor.execute("SELECT description,amount FROM payroll.emp_pretax_div_ded"
		" WHERE (type,emp_id) = ('add',%s) AND pay_stubs_id IS NULL ",(self.employee_id,))
		for line in self.cursor.fetchall():
			dividends_item = Item()
			dividends_item.description = line[0]
			dividends_item.amount = line[1]
			dividends.append (dividends_item)

		cash_advance = list()
		self.cursor.execute("SELECT date_inserted,amount_paid"
		" FROM payroll.emp_payments WHERE (employee_id) = (%s) AND pay_stub_id"
		" IS NULL ",(self.employee_id,))
		for line in self.cursor.fetchall():
			cash_advance_item = Item()
			cash_advance_item.date = str(datetime_to_user_date(line[0]))
			cash_advance_item.amount = line[1]
			cash_advance.append (cash_advance_item)

		self.cursor.execute("SELECT sum(amount_paid)"
		" FROM payroll.emp_payments WHERE (employee_id) = (%s) AND pay_stub_id"
		" IS NULL",(self.employee_id,))
		totals = Item()
		totals.prepayment_totals = self.cursor.fetchone()[0]
		check_number =  self.builder.get_object('entry4').get_text()
		self.cursor.execute("SELECT payroll.initiate_paystubs(%s,%s)",	  
		(self.employee_id,self.end_date_text))
		self.paystubs_id = self.cursor.fetchone()[0]		
		self.cursor.execute("SELECT payroll.complete_paystubs(%s,%s,%s)" ,
		(self.paystubs_id,check_number,self.bank_account))
		i = (self.cursor.fetchone()[0].strip('()')).split(',')
		self.wage_ttl_pmt =  i[1]
		#print(type(self.wage_ttl_pmt))
		self.emp_payments_id = i[0]
		self.cursor.execute("SELECT reg_hrs,overtime_hrs,cost_sharing,"
		"profit_sharing,s_s_withheld,medicare_withheld,state_withheld,"
		"fed_withheld,reg_ttl,overtime_ttl,pretax_payment_amnt FROM "
		"payroll.pay_stubs WHERE id = %s",(self.paystubs_id,))

		totals.chk_payment_info = '' + check_number

		for line in self.cursor.fetchall():
			totals.days_in_pp = ''
			totals.av_hr_day = ''
			totals.ttl_time_out = ''
			totals.acc_overtime = line[1]
			totals.base_pay_rate = wage
			totals.non_overtime_hrs =  line[0]
			totals.overtime_pay_rate = wage * Decimal(1.5)
			totals.reg_rate_ttl =  line[8]
			totals.overtime_rate_ttl =  line[9]
			totals.tip =  line[3]
			totals.dues =  line[2]
			totals.pretax_sub_ttl =  line[10]
			totals.ss_emp_share =  line[4]
			totals.med_emp_share =  line[5]
			totals.state_with_holding =  line[6]
			totals.federal_with_holding =  line[7]
		totals.wage_ttl_pmt =  self.wage_ttl_pmt
		totals.ttl_in_ck_fmt = get_written_check_amount_text (self.wage_ttl_pmt)
		self.data = dict(contact = customer,company = company,totals = totals,\
							items = items,pp_info = pp_info,dividends =dividends,
							deductions = deductions,cash_advance = cash_advance)
		
	def view_temp_copy(self,widget):
		if self.employee_id == str(0):
			for line in self.employee_store:
				if line[0] == 0:
					print(line[0] + ' returning')
					continue
				else:				
					self.employee_id =line[0]
					self.print_directly = True
					self.view_temporary = True
					if self.employee_id == str(0):
						print('payroll complete')
						pass
					else:
						self.populate_py3o_self_data()
						if self.wage_ttl_pmt != "0.00":
							self.print_time_sheet ()
							print(self.employee_id + ' printing temporary' )
						else:
							print(self.employee_id + ' wage total is zero this month - skipping' )
		else:
			self.print_directly = False
			self.view_temporary = True
			if self.employee_id == str(0):
				print('payroll complete')
				pass
			else:
				self.populate_py3o_self_data()
				if self.wage_ttl_pmt != "0.00":
					self.print_time_sheet ()
					print(self.employee_id + ' printing temporary' )
				else:
					print(self.employee_id + ' wage total is zero this month - skipping' )
				self.populate_employee_combobox ()
		DB.rollback()



		
	def enter_cash_advance(self,button):
		#self.print_check_clicked()
		pass

	def print_pay_close_clicked(self,button):
		if self.employee_id == str(0):
			for line in self.employee_store:
				if line[0] != 0:
					self.employee_id =line[0]
					self.print_directly = True
					check_number = get_check_number( self.bank_account)
					self.builder.get_object('entry4').set_text(str(check_number))
					self.close_pay_period_pay_balance()
				else:
					return
					
		else:
			self.print_directly = False
			self.close_pay_period_pay_balance()
			self.populate_employee_combobox ()
			check_number = get_check_number(self.bank_account)
			self.builder.get_object('entry4').set_text(str(check_number))

		
	def close_pay_period_pay_balance(self):
		self.view_temporary = False
		if self.employee_id == str(0):
			print('payroll complete')
			pass
		else:
			self.populate_py3o_self_data()
			#return

			#self.print_time_sheet ()
			if self.wage_ttl_pmt != "0.00":
				self.print_pay_check()
				DB.commit()
			else:
				DB.rollback()

	def help (self, button):
		pass
		

	def print_pay_check(self):
		from py3o.template import Template #import for every invoice or 
		#there is an error about invalid magic header numbers
		self.check_name = "/tmp/pay_check" + self.name.split()[0]
		self.check_file_odt = self.check_name +".odt"
		self.check_file_pdf = self.check_name +".pdf"
		t = Template("./templates/pay_check.odt", self.check_file_odt , True)
		t.render(self.data) #the self.data holds all the info to be passed to the template
		subprocess.call("odt2pdf " + self.check_file_odt, shell = True)
		p = printing.Operation(settings_file = 'pay_check', file_to_print = self.check_file_pdf, parent = self.window)
		if self.print_directly == False:
			result = p.print_dialog()
		else:
			result = p.print_directly()
		f = open(self.check_file_pdf,'rb')
		dat = f.read()
		f.close()
		self.cursor.execute("UPDATE payroll.emp_payments SET check_pdf = %s WHERE id = %s",(dat,self.emp_payments_id))

	def print_time_sheet(self):
		from py3o.template import Template #import for every invoice or there is
		#an error about invalid magic header numbers
		
		self.time_card_name = "/tmp/time_card_" + self.name.split()[0]
		self.time_card_odt = self.time_card_name + ".odt"
		self.time_card_pdf = self.time_card_name + ".pdf"
		
		#self.tmp_timecard_file = "/tmp/" + self.document_odt
		t = Template("./templates/time_card_template.odt", self.time_card_odt , True)
		t.render(self.data) #the self.data holds all the info to be passed to the template

		subprocess.call("odt2pdf " + self.time_card_odt, shell = True)
		p = printing.Operation(settings_file = 'time_card', file_to_print = self.time_card_pdf ,parent = self.window)
		if self.print_directly == False:
			result = p.print_dialog()
		else:
			result = p.print_directly()

		f = open(self.time_card_pdf,'rb')
		dat = f.read()
		f.close()
		self.cursor.execute("UPDATE payroll.pay_stubs SET timecard_pdf = %s WHERE id = %s",(dat,self.paystubs_id))
#dividends window code**********************************************************

	def type_renderer_changed (self, cellrenderercombo, path, treeiter):#path is treeview path 
		model = cellrenderercombo.get_property("model")
		text = model[treeiter][0]
		operator = model[treeiter][1]
		self.dividends_store[path][0] = text
		self.dividends_store[path][3] = operator
		
	def add_row_clicked (self, button):
		self.dividends_store.append(["","", '0.00',"",None,True,])
		pass

	def delete_row_clicked (self,button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path != []:
			tree_iter = model.get_iter(path)
			self.dividends_store.remove(tree_iter)	
	
	def launch_dividends_window (self, button):
		self.window2 = self.builder.get_object("window2")
		self.dividends_store = self.builder.get_object("dividends_store")
		self.populate_employee_dividends_combobox()
		self.populate_dividends_store ()
		self.view_paid_entries = self.builder.get_object("checkbutton1")
		self.view_paid_entries = False
		self.window2.show_all()

	def view_paid_entries (self, togglebutton):
		self.view_paid_entries = not self.view_paid_entries
		#self.employee_id = employee_combo.get_active_id()
		self.dividends_store.clear()
		self.populate_dividends_store ()

	def description_edited (self, cellrenderertext, path, text):
		self.dividends_store[path][1] = text


	def amount_edited (self, cellrenderertext, path, text):
		self.dividends_store[path][2] = text

	def amount_editing_started (self, cellrenderer, celleditable, path):
		celleditable.set_numeric(True)

	def dividends_employee_combo_changed (self, widget):
		employee_combo = self.builder.get_object('comboboxtext4')
		self.employee_id = employee_combo.get_active_id()
		self.dividends_store.clear()
		self.populate_dividends_store ()


	def populate_employee_dividends_combobox (self):
		dividends_employee_combo = self.builder.get_object('comboboxtext4')
		dividends_employee_combo.remove_all()
		self.cursor.execute("SELECT DISTINCT employee_id,name " 
							"FROM time_clock_entries "
							"JOIN contacts ON contacts.id = "
							"time_clock_entries.employee_id "
							"WHERE "
							  "time_clock_entries.employee_paid = FALSE AND "
							 "DATE_TRUNC('day', time_clock_entries.stop_time) <= %s "
							  "ORDER BY employee_id ASC",(self.pay_ending_date,))
		dividends_employee_combo.append (str(0),"Print All")
		for row in self.cursor.fetchall():
			self.employee_id = row[0]
			employee_name = row[1]
			dividends_employee_combo.append (str(self.employee_id), employee_name)

	def populate_dividends_store(self):
		self.cursor.execute("SELECT id,amount,description,pay_stubs_id,type "
							"FROM payroll.emp_pretax_div_ded WHERE emp_id"
							"= %s ",(self.employee_id,))
		for row in self.cursor.fetchall():
			paid =  row[3]
			entry_id = row[0]
			amount = str(row[1])
			description = row[2]
			types = row[4]
			if self.view_paid_entries == False:
				if paid == None:
					self.dividends_store.append([types,description,amount,"",entry_id,not paid])
			else:
				self.dividends_store.append([types,description,amount,"",entry_id,not paid])

	def save_dividends (self, button):
		for row in self.dividends_store:
			types = row[0]
			description = row[1]
			amount = row[2]
			entry_id  = row[4]
			print(entry_id)
			paid = row[5]
			
			if paid == False:
				return
			if entry_id == 0:
				self.cursor.execute("INSERT INTO payroll.emp_pretax_div_ded "
				" (emp_id,amount,description,type) VALUES (%s,%s,%s,%s)"
				,(self.employee_id,amount,description,types))
			else:
				self.cursor.execute("UPDATE payroll.emp_pretax_div_ded "
				"SET (amount,description,type) = (%s,%s,%s) WHERE id = %s "
				,(amount,description,types,entry_id))
		DB.commit()

#end dividends window code******************************************************


	def view_posted_checks (self, menuitem):
		self.cursor.execute("SELECT check_pdf,employee_id FROM payroll.emp_payments WHERE pay_stub_id > 136")
		for line in self.cursor.fetchall():
			file_data = line[0]
			emp_id = line[1]
			f = open("/tmp/test"+ str(emp_id),'wb')
			f.write(file_data)
			subprocess.call("xdg-open /tmp/test" + str(emp_id), shell = True)
			f.close()

	