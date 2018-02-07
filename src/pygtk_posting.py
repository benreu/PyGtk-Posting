#!/usr/bin/python3
#
# pygtk_posting.py
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
from gi.repository import Gtk, GLib, GObject
from datetime import datetime, date
import os, sys, subprocess, psycopg2, re
from db import database_tools
from db.database_tools import check_for_database

UI_FILE = "src/pygtk_posting.ui"

invoice_window = None
ccm = None


class GUI (GObject.GObject):
	"The main class that does all the heavy lifting"
	__gsignals__ = { 
	'products_changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()) , 
	'contacts_changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ())
	}
	expense_acc = Gtk.TreeStore(int, str)
	revenue_acc = Gtk.TreeStore(int, str)
	product_expense_acc = Gtk.TreeStore(str, str)
	product_inventory_acc = Gtk.TreeStore(str, str)
	product_revenue_acc = Gtk.TreeStore(str, str)
	admin = False
	log_file = None
	def __init__(self):
		GObject.GObject.__init__(self)
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		try:
			variable = sys.argv[1]
			if 'database ' in variable:
				database_to_connect = re.sub('database ', '', variable)
				log_variable = sys.argv[2]
				if log_variable != 'None':
					self.log_file = variable
			else:
				database_to_connect = None
				self.log_file = variable
		except Exception as e:
			print ("%s when trying to retrieve sys args" % e)
			database_to_connect = None
			self.set_admin_menus(True) # started from Anjuta, developer mode
			database_tools.dev_mode = True
			self.builder.get_object('menuitem35').set_label("Admin logout")

		self.window = self.builder.get_object('main_window')
		self.window.show_all()
		about_window = self.builder.get_object('aboutdialog1')
		about_window.add_credit_section("Special thanks", ["Eli Sauder"])
		about_window.add_credit_section("Suggestions/advice from (in no particular order)", 
													["Marvin Stauffer", 
													"Melvin Stauffer", 
													"Roy Horst", 
													"Daniel Witmer", 
													"Alvin Witmer",
													"Jonathan Groff"])
		result, db_connection, self.db_name = check_for_database(database_to_connect)
		if result == True:
			self.db = db_connection
			self.cursor = self.db.cursor()
			self.window.set_title('PyGtk Posting (%s)' % self.db_name)
			self.window.connect("focus-in-event", self.focus) #connect the focus signal only if we successfully connect
			self.cursor.execute("LISTEN products")
			self.cursor.execute("LISTEN contacts")
			self.cursor.execute("LISTEN accounts")
			GLib.timeout_add_seconds(1, self.listen_postgres)
			self.populate_accounts()
			self.populate_modules ()
		else:
			database_tools.GUI("", True)
		self.unpaid_invoices_window = None
		self.open_invoices_window = None

	def sql_window_activated (self, menuitem):
		from db import sql_window
		sql_window.SQLWindowGUI(self.db)
		
	def listen_postgres (self):
		if self.db.closed == 1:
			return False
		self.db.poll()
		while self.db.notifies:
			notify = self.db.notifies.pop(0)
			if "product" in notify.payload:
				self.emit('products_changed')
			elif "contact" in notify.payload:
				self.emit('contacts_changed')
			elif "account" in notify.payload:
				self.populate_accounts()
		return True

	def populate_accounts (self):
		self.expense_acc.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = self.expense_acc.append(None,[number, name])
			self.populate_child_expense(number, parent)
		#################################################
		self.product_expense_acc.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 3 "
							"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = self.product_expense_acc.append(None,[number, name])
			if self.populate_child_product_expense(number, parent) == True:
				show = True
			if show == False:
				self.product_expense_acc.remove(parent)
		##################################################
		self.product_revenue_acc.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = self.product_revenue_acc.append(None,[number, name])
			if self.populate_child_product_revenue (number, parent) == True:
				show = True
			if show == False:
				self.product_revenue_acc.remove(parent)
		##################################################
		self.revenue_acc.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 4 "
							"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			parent = self.revenue_acc.append(None,[number, name])
			self.populate_child_revenue (number, parent)
		##################################################
		self.product_inventory_acc.clear()
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE type = 1 "
							"AND parent_number IS NULL")
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			show = False
			parent = self.product_inventory_acc.append(None,[number, name])
			if self.populate_child_product_inventory(number, parent) == True:
				show = True
			if show == False:
				self.product_inventory_acc.remove(parent)
			
	def populate_child_product_inventory (self, number, parent):
		show = False
		self.cursor.execute("SELECT number, name, inventory_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				self.product_inventory_acc.append(parent,[number, name])
			elif row[3] == True:
				p = self.product_inventory_acc.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_inventory(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					self.product_inventory_acc.remove(p)
		return show
			
	def populate_child_revenue (self, number, parent):
		show = False
		self.cursor.execute("SELECT number, name, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			p = self.revenue_acc.append(parent,[number, name])
			self.populate_child_revenue(number, p)
			
	def populate_child_product_revenue (self, number, parent):
		show = False
		self.cursor.execute("SELECT number, name, revenue_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				show = True
				self.product_revenue_acc.append(parent,[number, name])
			elif row[3] == True:
				p = self.product_revenue_acc.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_revenue(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					self.product_revenue_acc.remove(p)
		return show
			
	def populate_child_product_expense (self, number, parent):
		show = False
		self.cursor.execute("SELECT number, name, expense_account, is_parent "
							"FROM gl_accounts WHERE parent_number = %s",
							(number,))
		for row in self.cursor.fetchall():
			number = str(row[0])
			name = row[1]
			if row[2] == True:
				p = self.product_expense_acc.append(parent,[number, name])
				show = True
			elif row[3] == True:
				p = self.product_expense_acc.append(parent,[number, name])
				c_show = False
				if self.populate_child_product_expense(number, p) == True:
					show = True
					c_show = True
				if c_show == False:
					self.product_expense_acc.remove(p)
		return show
			
	def populate_child_expense (self, number, parent):
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"parent_number = %s", (number,))
		for row in self.cursor.fetchall():
			number = row[0]
			name = row[1]
			p = self.expense_acc.append(parent,[number, name])
			self.populate_child_expense(number, p)

	def populate_modules (self):
		import importlib.util as i_utils
		cwd = os.getcwd()
		module_folder = cwd + "/src/modules/"
		files = os.listdir(module_folder)
		menu = self.builder.get_object('menu11')
		for file_ in files:
			if file_.endswith(".py") and file_ != "__init__.py":
				file_name = file_.strip(".py")
				f_path = module_folder+file_
				spec = i_utils.spec_from_file_location(file_name , f_path)
				module = i_utils.module_from_spec(spec)
				spec.loader.exec_module(module)
				file_label = file_name.capitalize()
				file_label = file_label.replace("_", " ") 
				menuitem = Gtk.MenuItem.new_with_label(file_label)
				menuitem.connect("activate", module.GUI, self.db )
				menuitem.show()
				menu.append(menuitem)

	def password_entry_activated (self, dialog):
		dialog.response(-3)

	def time_clock_projects (self, menuitem):
		from reports import time_clock_project
		time_clock_project.GUI(self.db)

	def credit_card_merchant_activated (self, menuitem):
		global ccm
		if ccm == None or ccm.exists == False:
			import credit_card_merchant
			ccm = credit_card_merchant.CreditCardMerchantGUI(self.db)
		else:
			ccm.window.present()

	def admin_login_clicked (self, menuitem):
		if menuitem.get_label() == "Admin logout":
			self.set_admin_menus (False)
			menuitem.set_label("Admin login")
			return
		self.check_admin (False)

	def set_admin_menus (self, value):
		self.builder.get_object('menuitem10').set_sensitive(value)
		self.builder.get_object('menuitem67').set_sensitive(value)
		self.builder.get_object('menuitem21').set_sensitive(value)
		self.builder.get_object('menuitem45').set_sensitive(value)
		self.builder.get_object('menuitem55').set_sensitive(value)
		self.builder.get_object('menuitem50').set_sensitive(value)
		self.builder.get_object('menuitem74').set_sensitive(value)
		self.builder.get_object('menuitem76').set_sensitive(value)
		self.builder.get_object('menuitem64').set_sensitive(value)
		self.builder.get_object('menuitem49').set_sensitive(value)
		self.builder.get_object('menuitem80').set_sensitive(value)
		self.admin = value

	def blank_clicked (self, button):
		pass

	def deposits_activated (self, menuitem):
		from reports import deposits
		deposits.DepositsGUI(self.db)

	def fiscal_year_activated (self, menuitem):
		import fiscal_years
		fiscal_years.FiscalYearGUI(self.db)

	def resource_search_activated (self, menuitem):
		import resource_search
		resource_search.ResourceSearchGUI(self.db)

	def incoming_invoice_report_activated(self, menuitem):
		from reports import incoming_invoices
		incoming_invoices.IncomingInvoiceGUI(self.db)

	def duplicate_contact_finder_activated (self, menuitem):
		from admin import duplicate_contact
		duplicate_contact.DuplicateContactGUI(self.db)

	def customer_history_activated (self, menuitem):
		from reports import customer_history
		customer_history.CustomerHistoryGUI(self)

	def resource_diary_activated (self, menuitem):
		import resource_diary
		resource_diary.ResourceDiaryGUI (self.db)

	def miscellaneous_revenue_activated (self, button):
		import miscellaneous_revenue
		miscellaneous_revenue.MiscellaneousRevenueGUI (self)

	def module_help_activated (self, menuitem):
		module_help_dialog = self.builder.get_object('module_help_dialog')
		module_help_dialog.set_keep_above(True)
		module_help_dialog.run()
		module_help_dialog.hide()

	def serial_numbers_activated (self, menuitem):
		import product_serial_numbers
		product_serial_numbers.ProductSerialNumbersGUI(self)

	def catalog_creator_activated (self, menuitem):
		import catalog_creator
		catalog_creator.CatalogCreatorGUI(self)

	def employee_info_activated (self, menuitem):
		from payroll import employee_info
		employee_info.EmployeeInfoGUI(self.db)

	def resource_tags (self, widget):
		import resource_management_tags
		resource_management_tags.ResourceManagementTagsGUI (self.db)

	def payments_received_activated (self, menuitem):
		from reports import payments_received
		payments_received.PaymentsReceivedGUI(self.db)

	def customer_terms_clicked (self, menuitem):
		import contact_terms
		contact_terms.ContactTermsGUI(self.db)
				
	def time_clock_history (self, widget):
		from reports import time_clock_history
		time_clock_history.TimeClockHistoryGUI (self.db)

	def document_reports_window (self, widget):
		print ("not done yet")

	def resource_management (self, widget):
		import resource_management
		resource_management.ResourceManagementGUI(self.db)

	def statements_clicked (self, widget):
		from reports import statements
		statements.StatementsGUI (self.db)

	def documents_to_invoice_clicked (self, button):
		import documents_to_invoice
		documents_to_invoice.DocumentsToInvoiceGUI(self.db)

	def incoming_invoices_activated (self, menuitem):
		import incoming_invoice
		incoming_invoice.IncomingInvoiceGUI(self)

	def loan_payment_clicked (self, widget):
		import loan_payment
		loan_payment.LoanPaymentGUI(self.db)

	def view_log_clicked (self, menuitem):
		import view_log
		view_log.ViewLogGUI(self.db, self)

	def payment_receipt_activated (self, menuitem):
		import payment_receipt
		payment_receipt.PaymentReceiptGUI(self.db)

	def count_inventory_activated (self, menuitem):
		from reports import inventory_count
		inventory_count.InventoryCountGUI(self.db)

	def user_manual_help (self, widget):
		subprocess.Popen("yelp ./help/pygtk_posting.page", shell = True)

	def create_document_clicked (self, widget):
		import documents_window
		documents_window.DocumentGUI(self)

	def assembled_products_clicked (self, button):
		import assembled_products
		assembled_products.AssembledProductsGUI(self)

	def invoice_amounts_activated (self, menuitem):
		from reports import invoice_amounts
		invoice_amounts.InvoiceAmountsGUI(self.db)

	def vendor_history_activated (self, menuitem):
		from reports import vendor_history
		vendor_history.VendorHistoryGUI(self)

	def manufacturing_window (self, widget):
		import manufacturing
		manufacturing.ManufacturingGUI(self)

	def accounts_overview_activated (self, menuitem):
		import accounts_overview
		accounts_overview.AccountsOverviewGUI(self)

	def product_location_window(self, widget):
		import product_location
		product_location.ProductLocationGUI(self)

	def sales_tax_report(self, widget):
		from reports import sales_tax_report
		sales_tax_report.SalesTaxReportGUI(self.db)
				
	def statements_to_print_window(self, widget):
		import statements_to_print
		statements_to_print.GUI(self.db)
				
	def jobs_to_invoice_window(self, widget):
		import jobs_to_invoice
		jobs_to_invoice.GUI(self.db)

	def double_entry_transaction_clicked (self, menuitem):
		import double_entry_transaction
		double_entry_transaction.DoubleEntryTransactionGUI(self.db)

	def time_clock_tool (self, widget):
		from admin import time_clock_tool
		time_clock_tool.TimeClockToolGUI(self.db)

	def credit_card_statement(self, widget):
		import credit_card_statements
		credit_card_statements.CreditCardStatementGUI(self.db)

	def product_search (self, widget):
		import product_search
		product_search.ProductSearchGUI(self)
		
	def job_sheet (self, widget):
		import job_sheet
		job_sheet.JobSheetGUI(self)

	def vendor_payment(self, widget):
		import vendor_payment
		vendor_payment.GUI(self.db)

	def product_transactions_clicked (self, widget):
		from reports import product_transactions
		product_transactions.ProductTransactionsGUI(self.db)

	def resource_calendar (self, button):
		import resource_calendar
		resource_calendar.ResourceCalendarGUI (self.db)

	def open_invoices (self, widget):
		if self.open_invoices_window == None:
			import open_invoices
			open_invoices.OpenInvoicesGUI(self)
		else:
			self.open_invoices_window.present()

	def account_transaction_window(self, widget):
		import account_transactions
		account_transactions.GUI(self.db)

	def contact_transactions(self, widget):
		from reports import contact_transactions
		contact_transactions.GUI(self)

	def settings_window(self, widget):
		import settings
		settings.GUI(self.db)

	def customer_markup_percent_activated (self, menuitem):
		import customer_markup_percent
		customer_markup_percent.CustomerMarkupPercentGUI(self)

	def process_po(self, widget):
		import unprocessed_po
		unprocessed_po.GUI(self)

	def receive_orders_clicked (self, button):
		import receive_orders
		receive_orders.ReceiveOrdersGUI(self.db)

	def check_admin (self, external = True):
		"check for admin, external option to show extra alert for not being admin"
		if self.admin == False:
			dialog = self.builder.get_object('admin_dialog')
			self.builder.get_object('label21').set_visible(external)
			result = dialog.run()
			dialog.hide()
			text = self.builder.get_object('entry2').get_text().lower()
			self.builder.get_object('entry2').set_text('')
			self.builder.get_object('menuitem35').set_label("Admin logout")
			if result == Gtk.ResponseType.ACCEPT and text == 'admin':
				self.set_admin_menus (True)
				return True #updated to admin
			return False #not admin, and not updated
		return True #admin already to begin with

	def employee_time (self, widget):
		import employee_payment
		employee_payment.EmployeePaymentGUI (self.db)

	def pay_stub_clicked (self, button):
		from payroll import pay_stub
		pay_stub.PayStubGUI(self.db)

	def pay_stub_history (self, widget):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI(self.db)

	def job_sheet_history (self, widget):
		from reports import job_sheet_history
		job_sheet_history.JobSheetHistoryGUI(self.db)

	def backup_window (self):
		from db import backup_restore
		u = backup_restore.Utilities(self)
		u.backup_gui (self.db_name)

	def to_do_row_activated (self, treeview, path, column):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		function = model[path][1]
		function()

	def populate_to_do_treeview (self):
		store = self.builder.get_object('to_do_store')
		store.clear()
		self.cursor.execute("SELECT date_trunc( 'month', "
								"(SELECT statement_finish_date FROM settings)) "
								"= date_trunc('month', CURRENT_DATE)")
		if self.cursor.fetchone()[0] == False:
			store.append(["Print statements", self.statement_window])
		
	def focus (self, widget = None, d = None):
		self.populate_to_do_treeview()
		self.cursor.execute("SELECT COUNT(id) FROM invoices WHERE (canceled, paid, posted) = (False, False, True)")
		unpaid_invoices = 0
		for row in self.cursor.fetchall():
			unpaid_invoices = row[0]
		self.builder.get_object('button2').set_label("Unpaid Invoices\n          (%s)" % unpaid_invoices)
		self.cursor.execute("SELECT COUNT(id) FROM purchase_orders WHERE (canceled, invoiced, closed) = (False, False, True) ")	
		unpaid_po = 0
		for row in self.cursor.fetchall():
			unpaid_po = row[0]
		self.builder.get_object('button5').set_label("Unprocessed Orders\n               (%s)" % unpaid_po)
		self.cursor.execute("SELECT COUNT(id) FROM job_sheets WHERE (invoiced, completed) = (False, True)")	
		jobs = 0
		for row in self.cursor.fetchall():
			jobs = row[0]
		self.builder.get_object('button10').set_label("Jobs To Invoice\n           (%s)" % jobs)
		self.cursor.execute("SELECT COUNT(id) FROM documents WHERE (canceled, invoiced, pending_invoice) = (False, False, True)")	
		documents = 0
		for row in self.cursor.fetchall():
			documents = row[0]
		self.builder.get_object('button14').set_label("Documents To Invoice\n                 (%s)" % documents)
		self.cursor.execute("SELECT COUNT(id) FROM purchase_orders WHERE (canceled, invoiced, received) = (False, True, False) ")	
		unreceived_po = 0
		for row in self.cursor.fetchall():
			unreceived_po = row[0]
		self.builder.get_object('button12').set_label("Receive Orders\n          (%s)" % unreceived_po)
		self.cursor.execute("SELECT COUNT(invoices.id) FROM invoices, "
							"LATERAL (SELECT product_id FROM invoice_line_items "
								"WHERE invoice_line_items.invoice_id = "
								"invoices.id LIMIT 1) ILI "
							"WHERE (invoices.canceled, posted, active) = (False, False, True)")
		for row in self.cursor.fetchall():
			open_invoices = row[0]
		self.builder.get_object('button17').set_label("Open invoices\n         (%s)" % open_invoices)
		self.cursor.execute("SELECT COUNT(purchase_orders.id) FROM purchase_orders, "
							"LATERAL (SELECT product_id FROM purchase_order_line_items "
								"WHERE purchase_order_line_items.purchase_order_id = "
								"purchase_orders.id LIMIT 1) ILI "
							"WHERE (purchase_orders.canceled, closed) = (False, False)")
		for row in self.cursor.fetchall():
			open_invoices = row[0]
		self.builder.get_object('button13').set_label("Open POs\n         (%s)" % open_invoices)
		#print self.window.get_size()

	def inventory_history_report (self, widget):
		from inventory import inventory_history
		inventory_history.InventoryHistoryGUI(self.db)

	def time_clock(self, widget):
		import time_clock
		time_clock.TimeClockGUI(self.db)

	def xlwttest(self, widget):
		import testxlwt
		testxlwt.testxlwt_ui(self.db)

	def kit_products_activated (self, db):
		import kit_products
		kit_products.KitProductsGUI(self)

	def external_data_import(self, widget):
		import external_data_import
		external_data_import.external_data_import_ui(self.db)
		
	def write_check(self, widget):
		import write_check
		write_check.GUI(self.db)

	def open_pos_clicked (self, button):
		import open_purchase_orders
		open_purchase_orders.OpenPurchaseOrderGUI(self)

	def about_window(self, widget):
		about_window = self.builder.get_object('aboutdialog1')
		about_window.set_keep_above(True)
		about_window.run()
		about_window.hide()

	def main_reports_window (self, menuitem):
		from reports import main_reports_window
		main_reports_window.MainReportsGUI(self)

	def unpaid_invoices(self, widget):
		if self.unpaid_invoices_window == None:
			import unpaid_invoices
			unpaid_invoices.GUI(self)
		else:
			self.unpaid_invoices_window.present()

	def destroy(self, window):
		Gtk.main_quit()
		self.cursor.execute("UNLISTEN products")
		self.cursor.execute("UNLISTEN contacts")
		self.db.close ()

	def statement_window(self, widget = None):
		import customer_statement
		customer_statement.GUI(self.db)

	def accounts_configuration(self, widget):
		import accounts_configuration
		accounts_configuration.GUI(self.db)

	def edit_tax_rate(self, widget):
		import tax_rates
		tax_rates.TaxRateGUI(self.db)

	def payment_window(self, widget):
		import customer_payment
		customer_payment.GUI(self)

	def products_window(self, widget):
		import products
		products.ProductsGUI(self)

	def deposit_window(self, widget):
		import deposits
		deposits.GUI(self.db)

	def bank_statement(self, widget):
		import bank_statement
		bank_statement.GUI(self)

	def contacts_window(self, widget):
		import contacts
		contacts.GUI(self)

	def database_tools_activated(self, widget):
		database_tools.GUI(self.db, False)

	def new_purchase_order(self, widget):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI(self)

	def new_invoice(self, widget):
		global invoice_window
		if invoice_window == None:
			import invoice_window
		invoice_window.InvoiceGUI (self)


def main():
	
	app = GUI()
	Gtk.main()

		
if __name__ == "__main__":	
	sys.exit(main())
