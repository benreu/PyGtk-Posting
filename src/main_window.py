# main_window.py
# 
# Copyright (C) 2016 reuben 
# 
# main_window.py is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# main_window.py is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib, GObject, Gdk
import os, subprocess, re
from constants import DB, ui_directory, db_name, dev_mode, modules_dir, \
						is_admin, help_dir, broadcaster

UI_FILE = ui_directory + "/main_window.ui"

invoice_window = None
ccm = None

class MainGUI :
	log_file = None
	time_clock_object = None
	keybinding = None
	prod_loc_class = None
	unpaid_invoices_window = None
	open_invoices_window = None
	open_po = None

	def __init__(self):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.window = self.builder.get_object('main_window')
		self.window.set_title('%s - PyGtk Posting' % db_name)
		self.window.show_all()
		self.set_admin_menus(dev_mode)
		about_window = self.builder.get_object('aboutdialog1')
		about_window.add_credit_section("Special thanks", ["Eli Sauder"])
		about_window.add_credit_section("Suggestions/advice from (in no particular order)", 
													["Marvin Stauffer", 
													"Melvin Stauffer", 
													"Roy Horst", 
													"Daniel Witmer", 
													"Alvin Witmer",
													"Jonathan Groff"])
		self.populate_quick_commands()
		self.populate_modules ()
		self.check_db_version ()
		if not dev_mode:
			self.connect_keybindings()
		import traceback_handler
		traceback_handler.Log()

	def present (self, keybinding):
		self.window.present()

	def populate_quick_commands(self):
		menu = self.builder.get_object('menubar1')
		import quick_command
		self.quick_command = quick_command.QuickCommandGUI(menu)
	
	def quick_command_activate (self, menuitem):
		self.quick_command.show_all()

	def check_db_version (self):
		posting_version = self.builder.get_object('aboutdialog1').get_version()
		from db import version
		version.CheckVersion(self, posting_version)

	def connect_keybindings (self):
		import keybindings
		keybindings.parent = self
		keybindings.populate_shortcuts(self)
		self.keybinding = keybindings.KeybinderInit(self)
	
	def keyboard_shortcuts_activated (self, menuitem):
		if self.keybinding:
			self.keybinding.show_window()

	def sql_window_activated (self, menuitem):
		from db import sql_window
		sql_window.SQLWindowGUI()

	def populate_modules (self):
		import importlib.util as i_utils
		cwd = os.getcwd()
		module_folder = modules_dir
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
				menuitem.connect("activate", module.GUI)
				menuitem.show()
				menu.append(menuitem)

	def finance_charge_activated (self, menuitem):
		import customer_finance_charge
		customer_finance_charge.CustomerFinanceChargeGUI()

	def password_entry_activated (self, dialog):
		dialog.response(-3)

	def credit_card_merchant_activated (self, menuitem):
		global ccm
		if ccm == None or ccm.exists == False:
			import credit_card_merchant
			ccm = credit_card_merchant.CreditCardMerchantGUI()
		else:
			ccm.window.present()

	def admin_login_clicked (self, menuitem):
		if is_admin == True:
			self.set_admin_menus (False)
			menuitem.set_label("Admin login")
		else:
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
		import constants
		constants.is_admin = value

	def blank_clicked (self, button):
		pass

	def shipping_history_activated (self, menuitem):
		from reports import shipping_history
		shipping_history.ShippingHistoryGUI()

	def deposits_report (self, menuitem):
		from reports import deposits
		deposits.DepositsGUI()

	def contact_product_view_clicked (self, button):
		import contact_product_view
		contact_product_view.ContactProductViewGUI()

	def fiscal_year_activated (self, menuitem):
		import fiscal_years
		fiscal_years.FiscalYearGUI()

	def resource_search_activated (self, menuitem):
		import resource_search
		resource_search.ResourceSearchGUI()

	def incoming_invoice_report_activated(self, menuitem):
		from reports import incoming_invoices
		incoming_invoices.IncomingInvoiceGUI()

	def mailing_list_printing_activated (self, menuitem):
		import mailing_list_printing
		mailing_list_printing.MailingListPrintingGUI()

	def duplicate_contact_finder_activated (self, menuitem):
		from admin import duplicate_contact
		duplicate_contact.DuplicateContactGUI()

	def resource_diary_activated (self, menuitem):
		import resource_diary
		resource_diary.ResourceDiaryGUI ()

	def miscellaneous_revenue_activated (self, button):
		import miscellaneous_revenue
		miscellaneous_revenue.MiscellaneousRevenueGUI ()

	def shipping_info_activated (self, menuitem):
		import shipping_info 
		shipping_info.ShippingInfoGUI()

	def module_help_activated (self, menuitem):
		module_help_dialog = self.builder.get_object('module_help_dialog')
		module_help_dialog.set_keep_above(True)
		module_help_dialog.run()
		module_help_dialog.hide()

	def contact_history (self, menuitem):
		from reports import contact_history
		contact_history.ContactHistoryGUI()

	def serial_numbers_activated (self, menuitem):
		import product_serial_numbers
		product_serial_numbers.ProductSerialNumbersGUI()

	def catalog_creator_activated (self, menuitem):
		import catalog_creator
		catalog_creator.CatalogCreatorGUI()

	def employee_info_activated (self, menuitem):
		from payroll import employee_info
		employee_info.EmployeeInfoGUI()

	def resource_tags (self, widget):
		import resource_management_tags
		resource_management_tags.ResourceManagementTagsGUI ()

	def customer_terms_clicked (self, menuitem):
		import customer_terms
		customer_terms.CustomerTermsGUI()

	def markup_rate_activated (self, widget):
		from reports import product_markup
		product_markup.ProductMarkupGUI()

	def document_history_window (self, widget):
		from reports import document_history
		document_history.DocumentHistoryGUI()

	def mailing_list_activated (self, widget):
		import mailing_lists
		mailing_lists.MailingListsGUI()

	def credit_memo_activated (self, menutiem):
		import credit_memo
		credit_memo.CreditMemoGUI()

	def resource_management (self, widget):
		import resource_management
		resource_management.ResourceManagementGUI()

	def invoice_history (self, widget):
		from reports import invoice_history
		invoice_history.InvoiceHistoryGUI()

	def statements_clicked (self, widget):
		from reports import customer_statements
		customer_statements.StatementsGUI ()

	def documents_to_invoice_clicked (self, button):
		import documents_to_invoice
		documents_to_invoice.DocumentsToInvoiceGUI()

	def incoming_invoices_activated (self, menuitem):
		import incoming_invoice
		incoming_invoice.IncomingInvoiceGUI()

	def loan_payment_clicked (self, widget):
		import loan_payment
		loan_payment.LoanPaymentGUI()

	def loans_activated (self, widget):
		import loans
		loans.LoanGUI()

	def view_log_clicked (self, menuitem):
		import view_log
		view_log.ViewLogGUI(self)

	def payment_receipt_activated (self, menuitem):
		import payment_receipt
		payment_receipt.PaymentReceiptGUI()

	def count_inventory_activated (self, menuitem):
		from reports import inventory_count
		inventory_count.InventoryCountGUI()

	def user_manual_help (self, widget):
		subprocess.Popen(["yelp", help_dir + "/index.page"])

	def create_document_clicked (self, widget):
		import documents_window
		documents_window.DocumentGUI()

	def assembled_products_clicked (self, button):
		import assembled_products
		assembled_products.AssembledProductsGUI()

	def invoice_amounts_activated (self, menuitem):
		from reports import invoice_amounts
		invoice_amounts.InvoiceAmountsGUI()

	def vendor_history_activated (self, menuitem):
		from reports import vendor_history
		vendor_history.VendorHistoryGUI()

	def manufacturing_window (self, widget):
		import manufacturing
		manufacturing.ManufacturingGUI()

	def accounts_overview_activated (self, menuitem):
		import accounts_overview
		accounts_overview.AccountsOverviewGUI()

	def product_location (self, widget = None):
		if not self.prod_loc_class:
			import product_location
			self.prod_loc_class = product_location.ProductLocationGUI()
		else:
			self.prod_loc_class.present()

	def sales_tax_report(self, widget):
		from reports import sales_tax_report
		sales_tax_report.SalesTaxReportGUI()
				
	def statements_to_print_window(self, widget):
		import statements_to_print
		statements_to_print.GUI()

	def open_job_sheets_clicked (self, button):
		import open_job_sheets
		open_job_sheets.OpenJobSheetsGUI()

	def charts_activated (self, menuitem):
		from reports import charts
		charts.ChartsGUI()

	def double_entry_transaction_clicked (self, menuitem):
		import double_entry_transaction
		double_entry_transaction.DoubleEntryTransactionGUI()

	def time_clock_tool (self, widget):
		from admin import time_clock_tool
		time_clock_tool.TimeClockToolGUI()

	def credit_card_statement(self, widget):
		import credit_card_statements
		credit_card_statements.CreditCardStatementGUI()

	def product_search (self, widget):
		import product_search
		product_search.ProductSearchGUI()
		
	def job_sheet (self, widget):
		import job_sheet
		job_sheet.JobSheetGUI()

	def vendor_payment(self, widget):
		import vendor_payment
		vendor_payment.GUI()

	def resource_calendar (self, button):
		import resource_calendar
		resource_calendar.ResourceCalendarGUI ()

	def open_invoices (self, widget):
		if self.open_invoices_window == None:
			import open_invoices
			self.open_invoices_window = open_invoices.OpenInvoicesGUI()
		else:
			self.open_invoices_window.present()

	def account_transaction_window(self, widget):
		import account_transactions
		account_transactions.GUI()

	def settings_window(self, widget):
		import settings
		settings.GUI()

	def customer_markup_percent_activated (self, menuitem):
		import customer_markup_percent
		customer_markup_percent.CustomerMarkupPercentGUI()

	def process_po(self, widget):
		import unprocessed_po
		unprocessed_po.GUI()

	def receive_orders_clicked (self, button):
		import receive_orders
		receive_orders.ReceiveOrdersGUI()

	def check_admin (self, external = True):
		"check for admin, external option to show extra alert for not being admin"
		if is_admin == False:
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
		employee_payment.EmployeePaymentGUI ()

	def pay_stub_clicked (self, button):
		from payroll import pay_stub
		pay_stub.PayStubGUI()

	def pay_stub_history (self, widget):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI()

	def backup_window (self, n):
		from db import backup_restore
		u = backup_restore.Utilities(self)
		u.backup_gui ()

	def to_do_row_activated (self, treeview, path, column):
		selection = treeview.get_selection()
		model, path = selection.get_selected_rows()
		id_ = model[path][1]
		function = model[path][2]
		function(id_)

	def loan_payment (self, id_):
		import loan_payment
		loan_payment.LoanPaymentGUI (id_)

	def populate_to_do_treeview (self):
		c = DB.cursor()
		store = self.builder.get_object('to_do_store')
		store.clear()
		red = Gdk.RGBA(1, 0, 0, 1)
		orange = Gdk.RGBA(1, 0.5, 0, 1)
		brown = Gdk.RGBA(0.5, 0.3, 0.1, 1)
		try:
			c.execute("SELECT CURRENT_DATE >= date_trunc( 'month', "
						"(SELECT statement_finish_date FROM settings) "
						"+ INTERVAL'1 month') "
						"+ ((SELECT statement_day_of_month FROM settings) "
							"* INTERVAL '1 day') "
						"- INTERVAL '1 day'")
		except Exception as e:
			DB.rollback()
			return
		if c.fetchone()[0] == True:
			store.append(["Print statements", 0, self.statement_window, orange])
		c.execute("SELECT "
					"date_trunc('day', "
						"(SELECT last_backup FROM settings)) <= "
					"date_trunc('day', "
						"CURRENT_DATE - "
							"((SELECT backup_frequency_days "
							"FROM settings) * INTERVAL '1 day'))")
		if c.fetchone()[0] == True:
			store.append(['Backup database', 0, self.backup_window, red])
		c.execute("SELECT l.id, c.name || ' loan payment' "
					"FROM loans AS l "
					"JOIN contacts AS c ON l.contact_id = c.id "
					"WHERE date_trunc"
					"(l.period, l.last_payment_date) <= "
					"date_trunc(l.period, "
						"CURRENT_DATE - "
							"(l.period_amount||' '||l.period)::interval "
					")")
		for row in c.fetchall():
			loan_id = row[0]
			reminder = row[1]
			store.append([reminder, loan_id, self.loan_payment, brown])
		c.execute("SELECT rm.id, subject, red, green, blue, alpha "
							"FROM resources AS rm "
							"JOIN resource_tags AS rmt "
							"ON rmt.id = rm.tag_id "
							"WHERE finished != True "
							"AND diary != True "
							"AND to_do = True")
		for row in c.fetchall():
			id_ = row[0]
			subject = row[1]
			rgba = Gdk.RGBA(1, 1, 1, 1)
			rgba.red = row[2]
			rgba.green = row[3]
			rgba.blue = row[4]
			rgba.alpha = row[5]
			store.append([subject, id_, self.resource_window, rgba])
		c.close()
		DB.rollback()

	def resource_window (self, id_):
		import resource_management
		resource_management.ResourceManagementGUI(id_)
		
	def focus (self, widget = None, d = None):
		c = DB.cursor()
		self.populate_to_do_treeview()
		c.execute("SELECT COUNT(id) FROM invoices "
					"WHERE (canceled, paid, posted) = (False, False, True)")
		unpaid_invoices = 0
		for row in c.fetchall():
			unpaid_invoices = "Unpaid Invoices\n          (%s)" % row[0]
		self.builder.get_object('button2').set_label(unpaid_invoices)
		c.execute("SELECT COUNT(id) FROM purchase_orders "
					"WHERE (canceled, invoiced, closed) = "
					"(False, False, True) ")
		unpaid_po = 0
		for row in c.fetchall():
			unpaid_po = "Unprocessed Orders\n               (%s)" % row[0]
		self.builder.get_object('button5').set_label(unpaid_po)
		c.execute("SELECT COUNT(id) FROM job_sheets "
					"WHERE (invoiced, completed) = (False, False)")	
		jobs = 0
		for row in c.fetchall():
			jobs = "Open Job Sheets\n           (%s)" % row[0]
		self.builder.get_object('button10').set_label(jobs)
		c.execute("SELECT COUNT(id) FROM documents "
					"WHERE (canceled, invoiced, pending_invoice) = "
					"(False, False, True)")	
		documents = 0
		for row in c.fetchall():
			documents = "Documents To Invoice\n                 (%s)" % row[0]
		self.builder.get_object('button14').set_label(documents)
		c.execute("SELECT COUNT(id) FROM purchase_orders "
					"WHERE (canceled, invoiced, received) = "
					"(False, True, False) ")	
		unreceived_po = 0
		for row in c.fetchall():
			unreceived_po = "Receive Orders\n          (%s)" % row[0]
		self.builder.get_object('button12').set_label(unreceived_po)
		c.execute("SELECT COUNT(invoices.id) FROM invoices, "
					"LATERAL (SELECT product_id FROM invoice_items "
						"WHERE invoice_items.invoice_id = "
						"invoices.id LIMIT 1) ILI "
					"WHERE (invoices.canceled, posted, active) = "
					"(False, False, True)")
		for row in c.fetchall():
			open_invoices = "Open invoices\n         (%s)" % row[0]
		self.builder.get_object('button17').set_label(open_invoices)
		c.execute("SELECT COUNT(purchase_orders.id) FROM purchase_orders, "
					"LATERAL (SELECT product_id FROM purchase_order_line_items "
						"WHERE purchase_order_line_items.purchase_order_id = "
						"purchase_orders.id LIMIT 1) ILI "
					"WHERE (purchase_orders.canceled, closed) = (False, False)")
		for row in c.fetchall():
			open_invoices = "Open POs\n         (%s)" % row[0]
		self.builder.get_object('button13').set_label(open_invoices)
		c.close()
		DB.rollback()

	def inventory_history_report (self, widget):
		from inventory import inventory_history
		inventory_history.InventoryHistoryGUI()

	def time_clock(self, widget = None):
		if self.time_clock_object == None:
			import time_clock
			self.time_clock_object = time_clock.TimeClockGUI()
		else:
			self.time_clock_object.window.present()
			self.time_clock_object.populate_employees ()
			self.time_clock_object.populate_job_store ()

	def data_import_activated (self, widget):
		from admin import data_import
		data_import.DataImportUI()

	def data_export_activated (self, widget):
		from admin import data_export
		data_export.DataExportUI()
		
	def write_check(self, widget):
		import write_check
		write_check.GUI()

	def open_pos_clicked (self, button):
		if not self.open_po:
			import open_purchase_orders
			self.open_po = open_purchase_orders.OpenPurchaseOrderGUI()
		self.open_po.window.present()

	def about_window(self, widget):
		about_window = self.builder.get_object('aboutdialog1')
		about_window.set_keep_above(True)
		about_window.run()
		about_window.hide()

	def main_reports_window (self, menuitem):
		from reports import main_reports_window
		main_reports_window.MainReportsGUI()

	def unpaid_invoices(self, widget):
		if self.unpaid_invoices_window == None:
			import unpaid_invoices
			unpaid_invoices.GUI()
		else:
			self.unpaid_invoices_window.present()

	def destroy(self, widget):
		broadcaster.emit("shutdown")
		c = DB.cursor()
		c.execute("UNLISTEN products")
		c.execute("UNLISTEN contacts")
		c.close()
		DB.close ()
		Gtk.main_quit()

	def statement_window(self, widget = None):
		import customer_statement
		customer_statement.GUI()

	def accounts_configuration(self, widget):
		import accounts_configuration
		accounts_configuration.GUI()

	def edit_tax_rate(self, widget):
		import tax_rates
		tax_rates.TaxRateGUI()

	def payment_window(self, widget):
		import customer_payment
		customer_payment.GUI()

	def products_window(self, widget):
		import products_overview
		products_overview.ProductsOverviewGUI()

	def deposit_window(self, widget):
		import deposits
		deposits.GUI()

	def bank_statement(self, widget):
		import bank_statement
		bank_statement.GUI()

	def budget_activated (self, widget):
		import budget
		budget.BudgetGUI()

	def contacts_window(self, widget):
		import contacts_overview
		contacts_overview.ContactsOverviewGUI()

	def database_tools_activated(self, widget):
		from db import database_tools
		database_tools.GUI(False)

	def new_purchase_order(self, widget = None):
		import purchase_order_window
		purchase_order_window.PurchaseOrderGUI()

	def new_invoice(self, widget = None):
		global invoice_window
		if invoice_window == None:
			import invoice_window
		invoice_window.InvoiceGUI ()

	##################   reports

	def customer_statements (self, menuitem):
		from reports import customer_statements
		customer_statements.StatementsGUI ()

	def bank_statements (self, button):
		from reports import bank_statements
		bank_statements.BankStatementsGUI()

	def manufacturing_history (self, button):
		from reports import manufacturing_history
		manufacturing_history.ManufacturingHistoryGUI()

	def product_account_relationship (self, button):
		from reports import product_account_relationship
		product_account_relationship.ProductAccountRelationshipGUI()

	def contact_history (self, button):
		from reports import contact_history
		contact_history.ContactHistoryGUI()

	def loan_payments_clicked (self, button):
		from reports import loan_payments
		loan_payments.LoanPaymentsGUI()

	def invoice_to_payment_matching (self, button):
		from reports import invoice_to_payment_matching
		invoice_to_payment_matching.GUI()

	def pay_stub_history (self, button):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI()

	def time_clock_projects (self, button):
		from reports import time_clock_project
		time_clock_project.GUI()

	def payments_received (self, button):
		from reports import payments_received
		payments_received.PaymentsReceivedGUI()
	
	def time_clock_history (self, button):
		from reports import time_clock_history
		time_clock_history.TimeClockHistoryGUI ()

	def count_inventory_clicked (self, button):
		from reports import inventory_count
		inventory_count.InventoryCountGUI()

	def pay_stub_history (self, button):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI()

	def job_sheet_history (self, button):
		from reports import job_sheet_history
		job_sheet_history.JobSheetHistoryGUI()

	def product_history (self, button):
		from reports import product_history
		product_history.ProductHistoryGUI()

	def profit_loss (self, button):
		from reports import profit_loss_report
		profit_loss_report.ProfitLossReportGUI()

	def net_worth (self, button):
		from reports import net_worth
		net_worth.NetWorthGUI()


