# tax_rate.py
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

from gi.repository import Gtk

UI_FILE = "src/tax_rates.ui"

class TaxRateGUI:
	def __init__(self, db):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)
		self.db = db
		self.cursor = self.db.cursor()
		
		self.tax_store = self.builder.get_object("tax_store")
		self.account_store = self.builder.get_object("tax_received_account_store")
		
		window = self.builder.get_object('window1')
		window.show_all()
		
		self.populate_tax_rates_store()
		self.populate_account_store()
		self.new()
		
	def destroy(self, window):
		return True

	def populate_account_store (self):
		self.cursor.execute("SELECT number, name FROM gl_accounts WHERE "
							"(is_parent, type) = (False, 5) ORDER BY name")
		for row in self.cursor.fetchall():
			account_number = str(row[0])
			account_name = row[1]
			self.account_store.append([account_number, account_name])
		self.builder.get_object('treeview-selection').unselect_all()

	def populate_tax_rates_store(self):
		self.tax_store.clear()
		self.cursor.execute("SELECT tr.id, tr.name, rate, standard, exemption, "
							"tax_letter, COALESCE(gl_accounts.name, '') "
							"FROM tax_rates AS tr "
							"LEFT JOIN gl_accounts "
							"ON gl_accounts.number = tr.tax_received_account "
							"WHERE deleted = False "
							"ORDER BY tr.name")
		for row in self.cursor.fetchall():
			tax_id = str(row[0])
			tax_name = row[1]
			tax_rate = str(row[2])
			default = row[3]
			exemption = row[4]
			tax_letter = row[5]
			tax_account = row[6]
			self.tax_store.append([tax_id, tax_name, tax_rate, 
									default, exemption, tax_letter, tax_account])

	def row_activate(self, treeview, path, treeviewcolumn):
		treeiter = self.tax_store.get_iter(path)
		self.serial_number = self.tax_store.get_value(treeiter, 0)
		if self.tax_store.get_value(treeiter, 3) == True:
			self.builder.get_object('button2').set_sensitive(False)
		else:
			self.builder.get_object('button2').set_sensitive(True)
		self.cursor.execute("SELECT name, rate, exemption, "
							"exemption_template_path, tax_letter, "
							"tax_received_account FROM tax_rates "
							"WHERE id = (%s)",[self.serial_number])
		for row in self.cursor.fetchall():
			self.builder.get_object('entry3').set_text(row[0])
			tax_rate = str(row[1])
			self.builder.get_object('spinbutton5').set_value(row[1])
			self.builder.get_object('checkbutton1').set_active(row[2])
			template_path = row[3]
			if template_path != None :
				self.builder.get_object('filechooserbutton1').set_filename( 
														template_path)
			else:
				self.builder.get_object('filechooserbutton1').unselect_all()
			self.builder.get_object('entry1').set_text(row[4])
			self.builder.get_object('combobox1').set_active_id(str(row[5]))

	def update_default(self, cell_renderer, path):
		selected_path = Gtk.TreePath(path)
		for row in self.tax_store:
			#print row[2]
			if row.path == selected_path:
				row[3] = True
				self.cursor.execute("UPDATE tax_rates SET standard = True "
									"WHERE id = (%s)",[row[0]])
			else:
				row[3] = False
				self.cursor.execute("UPDATE tax_rates SET standard = False "
									"WHERE id = %s",[row[0]])
		self.db.commit()

	def exemption_checkbutton_toggled (self, checkbutton):
		active = checkbutton.get_active()
		self.builder.get_object('filechooserbutton1').set_sensitive(active)
		self.builder.get_object('spinbutton5').set_sensitive(not active)
		if active == True:
			self.cursor.execute("SELECT exemption_template_path FROM tax_rates "
								"WHERE id = %s", (self.serial_number,))
			for row in self.cursor.fetchall():
				template_path = row[0]
				if template_path != None :
					self.builder.get_object('filechooserbutton1').set_filename( 
														template_path)
			self.builder.get_object('spinbutton5').set_value(0.00)
		else:
			self.cursor.execute("SELECT rate FROM tax_rates WHERE id = %s", 
								(self.serial_number,))
			for row in self.cursor.fetchall():
				self.builder.get_object('spinbutton5').set_value(float(row[0]))
			self.builder.get_object('filechooserbutton1').unselect_all ()
				
	def new(self, button = None):
		self.serial_number = 0
		self.builder.get_object('entry3').set_text("New tax rate")
		self.builder.get_object('spinbutton5').set_value(10.00)
		self.builder.get_object('checkbutton1').set_active(False)
		self.builder.get_object('filechooserbutton1').unselect_all()
		self.builder.get_object('combobox1').set_active(1)

	def save(self, widget):		
		name = self.builder.get_object('entry3').get_text()
		rate = self.builder.get_object('spinbutton5').get_text()
		tax_letter = self.builder.get_object('entry1').get_text()
		exemption = self.builder.get_object('checkbutton1').get_active()
		file_path = self.builder.get_object('filechooserbutton1').get_filename()
		tax_account = self.builder.get_object('combobox1').get_active_id()
		if exemption == False:
			file_path = None
		if self.serial_number == 0:
			self.cursor.execute("INSERT INTO tax_rates (name, rate, standard, "
								"exemption, exemption_template_path, deleted, "
								"tax_letter, tax_received_account) "
								"VALUES (%s, %s, False, %s, %s, False, %s, %s)",
								(name, rate, exemption, file_path, tax_letter, 
								tax_account))
		else:
			self.cursor.execute("UPDATE tax_rates SET (name, rate, "
								"exemption, exemption_template_path, "
								"tax_letter, tax_received_account) "
								"= (%s, %s, %s, %s, %s, %s) "
								"WHERE id = %s",
								(name, rate, exemption, file_path, tax_letter, 
								tax_account, self.serial_number))
		self.db.commit()
		self.populate_tax_rates_store ()
			
	def delete(self, widget):
		try:
			self.cursor.execute("UPDATE tax_rates set deleted = true WHERE id = %s",
												(self.serial_number,))
			self.db.commit()
		except Exception as e:
			print (e)
			self.builder.get_object('label5').set_label(str(e))
			dialog = self.builder.get_object('dialog1')
			dialog.run()
			dialog.hide()
			self.db.rollback()
		self.populate_tax_rates_store()
	

	
