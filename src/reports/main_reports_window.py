# main_reports_window.py
#
# Copyright (C) 2017 - reuben
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

from gi.repository import Gtk
import main

UI_FILE = main.ui_directory + "/reports/main_reports_window.ui"

class MainReportsGUI:
	def __init__(self, main):

		self.main = main
		self.db = main.db
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def bank_statements_clicked (self, button):
		from reports import bank_statements
		bank_statements.BankStatementsGUI(self.db)

	def manufacturing_history_clicked (self, button):
		from reports import manufacturing_history
		manufacturing_history.ManufacturingHistoryGUI(self.main)

	def product_account_relationship_clicked (self, button):
		from reports import product_account_relationship
		product_account_relationship.ProductAccountRelationshipGUI(self.main)

	def contact_history_clicked (self, button):
		from reports import contact_history
		contact_history.ContactHistoryGUI(self)

	def vendor_history_clicked (self, menuitem):
		from reports import vendor_history
		vendor_history.VendorHistoryGUI(self.main)

	def loan_payments_clicked (self, button):
		from reports import loan_payments
		loan_payments.LoanPaymentsGUI(self.db)

	def statements_clicked (self, button):
		from reports import statements
		statements.StatementsGUI(self.db)

	def product_transactions_clicked (self, button):
		from reports import product_transactions
		product_transactions.ProductTransactionsGUI(self.main)

	def invoice_to_payment_matching (self, button):
		from reports import invoice_to_payment_matching
		invoice_to_payment_matching.GUI(self.db)

	def pay_stub_history (self, button):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI(self.db)

	def job_sheet_history_clicked (self, button):
		from reports import job_sheet_history
		job_sheet_history.JobSheetHistoryGUI(self.db)

	def time_clock_projects_clicked (self, button):
		from reports import time_clock_project
		time_clock_project.GUI(self.db)

	def payments_received_clicked (self, button):
		from reports import payments_received
		payments_received.PaymentsReceivedGUI(self.db)
	
	def time_clock_history_clicked(self, button):
		from reports import time_clock_history
		time_clock_history.TimeClockHistoryGUI (self.db)

	def statements_clicked (self, button):
		from reports import statements
		statements.StatementsGUI (self.db)

	def count_inventory_clicked (self, button):
		from reports import inventory_count
		inventory_count.InventoryCountGUI(self.db)

	def invoice_amounts_clicked (self, button):
		from reports import invoice_amounts
		invoice_amounts.InvoiceAmountsGUI(self.db)

	def pay_stub_history (self, button):
		from reports import pay_stub_history
		pay_stub_history.PayStubHistoryGUI(self.db)

	def job_sheet_history (self, button):
		from reports import job_sheet_history
		job_sheet_history.JobSheetHistoryGUI(self.db)

	def product_history_clicked (self, button):
		from reports import product_history
		product_history.ProductHistoryGUI(self.main)

	def profit_loss_clicked (self, button):
		from reports import profit_loss_report
		profit_loss_report.ProfitLossReportGUI(self.db)

	def net_worth_clicked (self, button):
		from reports import net_worth
		net_worth.NetWorthGUI(self.db)



		

		
		
