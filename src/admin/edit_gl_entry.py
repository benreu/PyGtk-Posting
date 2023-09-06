# edit_gl_entry.py
#
# Copyright (C) 2023 - linux
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
from decimal import Decimal
from constants import ui_directory, DB, broadcaster
from accounts import all_accounts_tree

UI_FILE = ui_directory + "/admin/edit_gl_entry.ui"

class EditGlEntryGUI(Gtk.Builder):
	def __init__(self, gl_entry_id):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.get_object('debit_combo').set_property('model', all_accounts_tree)
		self.get_object('credit_combo').set_property('model', all_accounts_tree)
		self.gl_entry_id = gl_entry_id
		self.populate_gl_entry()

		self.window = self.get_object('window')
		self.window.show_all()

	def populate_gl_entry(self):
		model = self.get_object('gl_entry_store')
		c = DB.cursor()
		c.execute("SELECT id, "
					"amount::float, "
					"amount::text, "
					"date_inserted::text, "
					"format_date(date_inserted), "
					"debit_account, "
					"(SELECT name FROM gl_accounts WHERE number = debit_account), "
					"credit_account, "
					"(SELECT name FROM gl_accounts WHERE number = credit_account), "
					"(SELECT debit_account IS NOT NULL), "
					"(SELECT credit_account IS NOT NULL), "
					"transaction_description, "
					"reconciled, "
					"date_reconciled::text, "
					"format_date(date_reconciled) "
					"FROM gl_entries WHERE gl_transaction_id = "
					"(SELECT gl_transaction_id FROM gl_entries WHERE id = %s)", (self.gl_entry_id,))
		for row in c.fetchall():
			model.append(row)

	def amount_editing_started (self, cellrenderer, celleditable, path):
		celleditable.set_property('numeric', True)

	def amount_edited (self, cellrenderertext, path, text):
		model = self.get_object('gl_entry_store')
		iter_ = model.get_iter(path)
		model[iter_][1] = float(text)
		model[iter_][2] = text
		self.check_amount_validity()

	def date_edited (self, cellrenderertext, path, text):
		model = self.get_object('gl_entry_store')
		c = DB.cursor()
		try:
			c.execute("SELECT %s::date::text, format_date(%s)", (text, text))
		except Exception as e:
			DB.rollback()
			self.show_error_dialog(str(e))
			return
		for row in c.fetchall():
			date = row[0]
			date_formatted = row[1]
			iter_ = model.get_iter(path)
			model[iter_][3] = date
			model[iter_][4] = date_formatted

	def debit_combo_changed (self, cellrenderercombo, path, treeiter):
		account_number = all_accounts_tree[treeiter][0]
		account_name = all_accounts_tree[treeiter][1]
		model = self.get_object('gl_entry_store')
		iter_ = model.get_iter()
		model[iter_][5] = account_number
		model[iter_][6] = account_name

	def credit_combo_changed (self, cellrenderercombo, path, treeiter):
		account_number = all_accounts_tree[treeiter][0]
		account_name = all_accounts_tree[treeiter][1]
		model = self.get_object('gl_entry_store')
		iter_ = model.get_iter()
		model[iter_][7] = account_number
		model[iter_][8] = account_name

	def description_edited (self, cellrenderertext, path, text):
		model = self.get_object('gl_entry_store')
		model[path][11] = text

	def reconcile_date_edited (self, cellrenderertext, path, text):
		model = self.get_object('gl_entry_store')
		if text == '':
			iter_ = model.get_iter(path)
			model[iter_][12] = False
			model[iter_][13] = ''
			model[iter_][14] = ''
			return
		c = DB.cursor()
		try:
			c.execute("SELECT %s::date::text, format_date(%s)", (text, text))
		except Exception as e:
			DB.rollback()
			self.show_error_dialog(str(e))
			return
		for row in c.fetchall():
			date = row[0]
			date_formatted = row[1]
			iter_ = model.get_iter(path)
			model[iter_][12] = True
			model[iter_][13] = date
			model[iter_][14] = date_formatted

	def check_amount_validity (self):
		model = self.get_object('gl_entry_store')
		credit = Decimal()
		debit = Decimal()
		for row in model:
			if row[9]:
				debit += Decimal(row[2])
			if row[10]:
				credit += Decimal(row[2])
		button = self.get_object('save_button')
		if credit == debit:
			button.set_label("Save")
			button.set_sensitive(True)
		else:
			button.set_label("Credit and debit amounts do not match")
			button.set_sensitive(False)

	def save_clicked (self, button):
		c = DB.cursor()
		model = self.get_object('gl_entry_store')
		for row in model:
			row_id = row[0]
			amount = row[2]
			date = row[4]
			debit_number = row[5] or None
			credit_number = row[7] or None
			description = row[11]
			reconciled = row[12]
			date_reconciled = row[14]
			c.execute("UPDATE gl_entries SET "
						"(amount, date_inserted, debit_account, "
							"credit_account, transaction_description, "
							"reconciled, date_reconciled) = "
						"(%s, %s, %s, %s, %s, %s, %s) WHERE id = %s", 
						(amount, date, debit_number, credit_number, description, 
						reconciled, date_reconciled, row_id))
		DB.commit()
		self.window.destroy()

	def show_error_dialog (self, error):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (error)
		dialog.run()
		dialog.destroy()



