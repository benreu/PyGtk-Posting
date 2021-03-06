# pay_stub_history.py
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
from constants import ui_directory, DB

UI_FILE = ui_directory + "/reports/pay_stub_history.ui"

class PayStubHistoryGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.cursor = DB.cursor()
		self.employee_id = None

		self.employee_store= self.builder.get_object('employee_store')
		self.history_store = self.builder.get_object('pay_stub_history_store')
		self.populate_employee_store ()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def destroy (self, widget):
		self.cursor.close()

	def focus_in_event (self, window, event):
		self.populate_employee_store ()

	def populate_employee_store (self):
		self.employee_store.clear()
		self.cursor.execute("SELECT employee_id::text, name "
							"FROM payroll.pay_stubs "
							"JOIN contacts "
							"ON contacts.id = pay_stubs.employee_id "
							"GROUP BY employee_id, name ORDER BY name")
		for row in self.cursor.fetchall():
			self.employee_store.append(row)
		DB.rollback()

	def employee_combo_changed (self, combo):
		employee_id = combo.get_active_id()
		if employee_id != None:
			self.employee_id = employee_id
			self.populate_pay_stub_history_store ()

	def view_all_toggled (self, checkbutton):
		self.populate_pay_stub_history_store ()

	def populate_pay_stub_history_store (self):
		self.history_store.clear()
		if self.builder.get_object('checkbutton1').get_active() == True:
			self.cursor.execute("SELECT "
									"payroll.pay_stubs.id, "
									"name, "
									"format_date(date_inserted), "
									"regular_hours, "
									"overtime_hours, "
									"cost_sharing_hours, "
									"profit_sharing_hours, "
									"0.00 "
								"FROM pay_stubs "
								"JOIN contacts "
								"ON contacts.id = pay_stubs.employee_id")
		elif self.employee_id != None:
			self.cursor.execute("SELECT "
									"payroll.pay_stubs.id, "
									"name, "
									"format_date(date_inserted), "
									"regular_hours, "
									"overtime_hours, "
									"cost_sharing_hours, "
									"profit_sharing_hours, "
									"0.00 "
								"FROM pay_stubs "
								"JOIN contacts "
								"ON contacts.id = pay_stubs.employee_id "
								"WHERE employee_id = %s", (self.employee_id,))
		else:
			return # select all off and no employee selected
		for row in self.cursor.fetchall():
			self.history_store.append(row)
		DB.rollback()







		
		
