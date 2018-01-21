#
# external_data_import.py
# Copyright (C) 2016 Eli Sauder 
# 
# external_data_import is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# external_data_import is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
import xlrd
import datetime

UI_FILE = "src/external_data_import.ui"


class external_data_import_ui:
	def __init__(self, db):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		window = self.builder.get_object('window1')


		window.show_all()

	def write_xls(self,file_name, sheet_name, headings, heading_xf):
		book = xlwt.Workbook()
		sheet = book.add_sheet(sheet_name)
		rowx = 0
		for colx, value in enumerate(headings):

			sheet.write(rowx, colx, value, heading_xf)


		sheet.set_panes_frozen(True) # frozen headings instead of split panes
		sheet.set_horz_split_pos(rowx+1) # in general, freeze after last heading row
		sheet.set_remove_splits(True) # if user does unfreeze, don't leave a split there
		#for row in data:
		#   rowx += 1
		  #  for colx, value in enumerate(row):
		  #      sheet.write(rowx, colx, value, data_xfs[colx])
		book.save(file_name)
		

	def create_import_template(self,widget):
		mkd = datetime.date
		hdngs = ['name', 'ext_name', 'address', 'city', 'state', 'zip', 'fax', 'phone', 'email', 'label', 'tax_number', 'vendor', 'customer', 'employee', 'another_role', 'custom1', 'custom2', 'custom3', 'custom4', 'notes', 'active', 'price_level']#,['name', 'ext_name', 'address', 'city', 'state', 'zip', 'fax', 'phone', 'email', 'label', 'tax_number', 'vendor', 'customer', 'employee', 'another_role', 'custom1', 'custom2', 'custom3', 'custom4', 'notes', 'active', 'price_level']
		#kinds =  'date    text          int         price         money    text'.split()
		#data = [
		  #  [mkd(2007, 7, 1), 'ABC', 1000, 1.234567, 1234.57, ''],
		  #  [mkd(2007, 12, 31), 'XYZ', -100, 4.654321, -465.43, 'Goods returned'],
		   # ] + [
		  #      [mkd(2008, 6, 30), 'PQRCD', 100, 2.345678, 234.57, ''],
		   # ] * 100

		heading_xf = ezxf('font: bold on; align: wrap on, vert centre, horiz center')
		#rowheight_xf = ezxf('row: height 5000')
		#kind_to_xf_map = {
		  #  'date': ezxf(num_format_str='yyyy-mm-dd'),
		  #  'int': ezxf(num_format_str='#,##0'),
		  #  'money': ezxf('font: italic on; pattern: pattern solid, fore-colour grey25',
		   #     num_format_str='$#,##0.00'),
		  #  'price': ezxf(num_format_str='#0.000000'),
		    #'text': ezxf(),
		 #   }
		#data_xfs = [kind_to_xf_map[k] for k in kinds]
		print (str(self.xcx + "/contacts"))
		self.write_xls(str(self.xcx + "/contacts"), 'Demo', hdngs, heading_xf)# hdngs, data, heading_xf, data_xfs)

	def test2(self,widget):
		ws = xlrd.open_workbook(str(self.xcx))
		sheet = self.builder.get_object('entry1').get_text()
		print (sheet)
		wi = ws.sheet_by_name(str(sheet)).row_values(1,0,25000) 
		
		print (wi)
		ws.release_resources()#Don't know if this is needed or what it does for sure....implented at a time when the programmer was having a problem with his entire system freezing up

		
	def getfilename(self,widget):
		xx = self.builder.get_object('filechooserbutton1')
		self.xcx = xx.get_filename()
		print (self.xcx)
		
	def destroy(self, window):
		self.builder.get_object('window1').hide()
		return True


