# statements_to_print.py
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

from gi.repository import Gtk, Gdk, GLib
import os, sys, subprocess, psycopg2
from datetime import datetime, date
from dateutils import datetime_to_text
import printing

#Comment the first line and uncomment the second before installing
#or making the tarball (alternatively, use project variables)
UI_FILE = "src/statements_to_print.ui"

class GUI:
	def __init__(self, db):

		self.db = db
		self.cursor = self.db.cursor()
		self.print_select_all = True

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.statement_liststore = self.builder.get_object('statement_liststore')
		self.populate_unprinted_statement_treestore ()
		
		self.window = self.builder.get_object('window1')			
		self.window.show_all()

	def print_all_selected_statements(self, widget):
		for row in self.statement_liststore:
			statement_id = row[0]
			if row[5] == False:
				continue
			self.cursor.execute("SELECT name, pdf FROM statements WHERE id = %s", (statement_id ,))
			for cell in self.cursor.fetchall():
				file_ = "/tmp/" + cell[0]+ ".pdf"
				file_data = cell[1]
				f = open(file_,'wb')
				f.write(file_data)
				f.close()
				p = printing.PrintDialog (file_)
				result = p.run_print_dialog(self.window)
				if result == Gtk.PrintOperationResult.APPLY :
					self.cursor.execute("UPDATE statements SET (printed, print_date) = (True, %s) WHERE id = %s", (datetime.today(), statement_id))
		self.db.commit()
		self.builder.get_object('window1').destroy()

	def print_cell_toggled(self, widget, path):
		self.statement_liststore[path][5] = not self.statement_liststore[path][5]#toggle the button state

	def view_statement_clicked(self, widget):
		model, path = self.builder.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		statement_id = model[path][0]
		self.cursor.execute("SELECT * FROM statements WHERE id = %s", (statement_id ,))
		for cell in self.cursor.fetchall():
			file_ = "/tmp/" + cell[1]+ ".pdf"
			file_data = cell[6]
			f = open(file_,'wb')
			f.write(file_data)
			f.close()
			subprocess.call("xdg-open " + file_, shell = True)
		
	def print_statement_clicked(self, widget):
		model, path = self.builder.get_object('treeview-selection1').get_selected_rows()
		if path == []:
			return
		tree_iter = model.get_iter(path)
		statement_id = model.get_value(tree_iter, 0)
		self.cursor.execute("SELECT * FROM statements WHERE id = %s", (statement_id ,))
		for cell in self.cursor.fetchall():
			file_ = "/tmp/" + cell[1]+ ".pdf"
			file_data = cell[6]
			f = open(file_,'wb')
			f.write(file_data)
			f.close()
			p = printing.PrintDialog (file_)
			result = p.run_print_dialog(self.window)
			if result == Gtk.PrintOperationResult.APPLY :
				self.cursor.execute("UPDATE statements SET (printed, print_date) = (True, %s) WHERE id = %s", (datetime.today(), statement_id))
		self.db.commit()
		self.populate_unprinted_statement_treestore ()

	def populate_unprinted_statement_treestore(self):
		self.statement_liststore.clear()
		self.cursor.execute("SELECT id, name, date_inserted, customer_id, amount FROM statements WHERE printed = False")
		for row in self.cursor.fetchall():
			id_ = row[0]
			name = row[1]
			date = row[2]
			datetext = datetime_to_text(date)
			customer_id = row[3]
			self.cursor.execute("SELECT name FROM contacts WHERE id = %s", (customer_id,))
			customer_name = self.cursor.fetchone()[0]
			amount = row[4]
			amount = '${:,.2f}'.format(amount)
			self.statement_liststore.append([id_, name, datetext, customer_name, amount, True])




		