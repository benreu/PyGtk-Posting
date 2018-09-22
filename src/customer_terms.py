# customer_terms.py
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

from gi.repository import Gtk, GLib
import main

UI_FILE = main.ui_directory + "/customer_terms.ui"

class CustomerTermsGUI:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.db = db
		self.cursor = db.cursor()
		self.terms_store = self.builder.get_object('terms_store')
		self.populate_terms_store()
		self.new_button_clicked ()
		unselect = self.builder.get_object('treeview-selection1').unselect_all
		GLib.idle_add(unselect)
		
		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def term_combo_changed (self, combo):
		term_id = combo.get_active_id()
		if term_id == self.terms_id or term_id == None:
			self.builder.get_object('button4').set_sensitive(False)
		else:
			self.builder.get_object('button4').set_sensitive(True)

	def populate_terms_store (self):
		self.terms_store.clear()
		self.cursor.execute("SELECT id::text, name, standard FROM "
							"terms_and_discounts WHERE deleted = False "
							"ORDER BY name")
		for row in self.cursor.fetchall():
			term_id = row[0]
			term_name = row[1]
			term_default = row[2]
			self.terms_store.append([term_id, term_name, term_default])

	def terms_row_activated (self, treeview, path, treeview_column):
		self.terms_id = self.terms_store[path][0]
		self.cursor.execute("SELECT name, cash_only, "
							"discount_percent, pay_in_days_active, "
							"pay_in_days, pay_by_day_of_month_active, "
							"pay_by_day_of_month, standard, plus_date, text1, "
							"text2, text3, text4 FROM terms_and_discounts "
							"WHERE id = %s", (self.terms_id,))
		for row in self.cursor.fetchall():
			name = row[0]
			cash_only = row[1]
			discount_percent = row[2]
			paid_in_days_active = row[3]
			paid_in_days = row[4]
			paid_by_day_of_month_active = row[5]
			paid_by_day_of_month = row[6]
			default = row[7]
			plus_date = row[8]
			text1 = row[9]
			text2 = row[10]
			text3 = row[11]
			text4 = row[12]
			self.builder.get_object('entry1').set_text(name)
			self.builder.get_object('cash_only').set_active(cash_only)
			self.builder.get_object('spinbutton1').set_value(discount_percent)
			self.builder.get_object('radiobutton1').set_active(paid_in_days_active)
			self.builder.get_object('spinbutton2').set_value(paid_in_days)
			self.builder.get_object('radiobutton2').set_active(paid_by_day_of_month_active)
			self.builder.get_object('spinbutton3').set_value(paid_by_day_of_month)
			self.builder.get_object('button1').set_sensitive(not default)
			self.builder.get_object('spinbutton5').set_value(plus_date)
			self.builder.get_object('entry2').set_text(text1)
			self.builder.get_object('entry3').set_text(text2)
			self.builder.get_object('entry4').set_text(text3)
			self.builder.get_object('entry5').set_text(text4)

	def cash_only_toggled (self, togglebutton):
		active = togglebutton.get_active()
		#self.builder.get_object('grid2').set_visible(not active)

	def paid_by_day_of_month_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('spinbutton3').set_sensitive(active)
		
	def paid_within_days_toggled (self, togglebutton):
		active = togglebutton.get_active()
		self.builder.get_object('spinbutton2').set_sensitive(active)

	def delete_button_clicked (self, button):
		selection = self.builder.get_object('treeview-selection1')
		model, path = selection.get_selected_rows()
		if path == []:
			return
		term_id = model[path][0]
		try:
			self.cursor.execute("DELETE FROM terms_and_discounts "
								"WHERE id = %s", (term_id,))
			self.db.rollback()
			self.cursor.execute("UPDATE terms_and_discounts "
								"SET deleted = True "
								"WHERE id = %s", (term_id,))
		except Exception as e:
			self.db.rollback()
			self.builder.get_object('label6').set_label(str(e))
			self.builder.get_object('button4').set_sensitive(False)
			dialog = self.builder.get_object('dialog1')
			result = dialog.run()
			dialog.hide()
			if result == Gtk.ResponseType.ACCEPT:
				new_term_id = self.builder.get_object('combobox1').get_active_id()
				self.cursor.execute("UPDATE contacts "
									"SET terms_and_discounts_id = %s "
									"WHERE terms_and_discounts_id = %s",
									(new_term_id, term_id))
				self.cursor.execute("UPDATE terms_and_discounts "
									"SET deleted = True "
									"WHERE id = %s", (term_id,))
		self.db.commit()
		self.populate_terms_store()

	def new_button_clicked (self, button = None):
		self.terms_id = 0
		self.builder.get_object('entry1').set_text("New term & discount")
		self.builder.get_object('spinbutton1').set_text("2")
		self.builder.get_object('radiobutton1').set_active(True)
		self.builder.get_object('spinbutton2').set_text("30")
		self.builder.get_object('spinbutton3').set_text("0")

	def save_button_clicked (self, button):
		term_name = self.builder.get_object('entry1').get_text()
		cash_only = self.builder.get_object('cash_only').get_active()
		discount = self.builder.get_object('spinbutton1').get_value()
		paid_in_days_active = self.builder.get_object('radiobutton1').get_active()
		paid_in_days = self.builder.get_object('spinbutton2').get_value()
		paid_by_day_month_active = self.builder.get_object('radiobutton2').get_active()
		paid_by_day_month = self.builder.get_object('spinbutton3').get_value()
		plus_date = self.builder.get_object('spinbutton5').get_value()
		text1 = self.builder.get_object('entry2').get_text()
		text2 = self.builder.get_object('entry3').get_text()
		text3 = self.builder.get_object('entry4').get_text()
		text4 = self.builder.get_object('entry5').get_text()
		if self.terms_id == 0:
			self.cursor.execute("INSERT INTO terms_and_discounts "
								"(name, cash_only, "
								"discount_percent, pay_in_days_active, "
								"pay_in_days, pay_by_day_of_month_active, "
								"pay_by_day_of_month, standard, plus_date, "
								"text1, text2, text3, text4) VALUES "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s)"
								"RETURNING id", (term_name, cash_only, 
								discount, paid_in_days_active, 
								paid_in_days, paid_by_day_month_active, 
								paid_by_day_month, False, plus_date, 
								text1, text2, text3, text4))
			self.terms_id = self.cursor.fetchone()[0]
		else:
			self.cursor.execute("UPDATE terms_and_discounts "
								"SET (name, cash_only, "
								"discount_percent, pay_in_days_active, "
								"pay_in_days, pay_by_day_of_month_active, "
								"pay_by_day_of_month, plus_date, text1, text2, "
								"text3, text4) = "
								"(%s, %s, %s, %s, %s, %s, %s, %s, %s, "
								"%s, %s, %s) "
								"WHERE id = %s", (term_name, cash_only, 
								discount, paid_in_days_active, 
								paid_in_days, paid_by_day_month_active, 
								paid_by_day_month, plus_date, 
								text1, text2, text3, text4, self.terms_id))
		self.db.commit()
		self.populate_terms_store ()

	def default_toggled (self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		for row in self.terms_store:
			if row.path == selected_path:
				row[2] = True
				self.cursor.execute("UPDATE terms_and_discounts SET "
									"standard = True WHERE id = (%s)",[row[0]])
			else:
				row[2] = False
				self.cursor.execute("UPDATE terms_and_discounts SET "
									"standard = False WHERE id = %s",[row[0]])
		self.db.commit()









		
		
