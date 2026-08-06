# payment_entry_panel.py
#
# Copyright (C) 2026 - reuben
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

from gi.repository import Gtk, GObject
from db_connection import DB

class PaymentMethodEntry (GObject.GObject):
	'''Check/credit-card/cash entry cluster, shared by
	miscellaneous_revenue.py and customer_payment.py. Exposes `box` as a
	single packable widget to drop into either window's layout.'''

	__gtype_name__ = 'PaymentMethodEntry'

	__gsignals__ = {
		'changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ()),
	}

	def __init__ (self):
		GObject.GObject.__init__(self)

		self.payment_type_id = 0

		self.box = Gtk.Grid()

		self.check_entry = Gtk.Entry()
		self.credit_account_combo = Gtk.ComboBoxText()
		self.cash_entry = Gtk.Entry()
		self.credit_account_combo.set_sensitive(False)
		self.cash_entry.set_sensitive(False)
		for entry in (self.check_entry, self.cash_entry):
			entry.set_alignment(1)
		self.check_entry.connect('changed', self._check_number_changed)
		self.credit_account_combo.connect('changed', self._credit_account_changed)
		self.populate_credit_account_combo()

		check_radio = Gtk.RadioButton()
		credit_radio = Gtk.RadioButton.new_from_widget(check_radio)
		cash_radio = Gtk.RadioButton.new_from_widget(check_radio)
		check_radio.set_active(True)
		self.check_radio = check_radio
		check_radio.connect('toggled', self._check_toggled)
		credit_radio.connect('toggled', self._credit_toggled)
		cash_radio.connect('toggled', self._cash_toggled)

		rows = (
			('Check number', check_radio, self.check_entry),
			('Transfer to', credit_radio, self.credit_account_combo),
			('Cash', cash_radio, self.cash_entry),
		)
		for row_index, (text, radio, entry) in enumerate(rows):
			label = Gtk.Label(label = text)
			label_box = Gtk.Box()
			label_box.pack_start(label, True, True, 0)
			label_box.pack_end(radio, False, True, 0)
			self.box.attach(label_box, 0, row_index, 1, 1)
			self.box.attach(entry, 1, row_index, 1, 1)
		self.box.show_all()

	def populate_credit_account_combo (self):
		account_id = self.credit_account_combo.get_active_id()
		self.credit_account_combo.remove_all()
		cursor = DB.cursor()
		cursor.execute("SELECT number::text, name FROM gl_accounts "
							"WHERE deposits = True ORDER BY number")
		for row in cursor.fetchall():
			self.credit_account_combo.append(row[0], row[1])
		cursor.close()
		self.credit_account_combo.set_active_id(account_id)
		DB.rollback()

	# -- payment method --
	# NOTE: only the check toggle emits 'changed' below, matching the
	# pre-existing behavior of the two windows this replaces, where
	# switching to credit/cash does not re-run validation on its own.
	# The credit-card account combo does emit 'changed' on selection,
	# since an account must be picked before posting is allowed.

	def _check_toggled (self, widget):
		self.check_entry.set_sensitive(True)
		self.credit_account_combo.set_sensitive(False)
		self.cash_entry.set_sensitive(False)
		self.payment_type_id = 0
		self.emit('changed')

	def _credit_toggled (self, widget):
		self.check_entry.set_sensitive(False)
		self.credit_account_combo.set_sensitive(True)
		self.cash_entry.set_sensitive(False)
		self.payment_type_id = 1

	def _cash_toggled (self, widget):
		self.check_entry.set_sensitive(False)
		self.credit_account_combo.set_sensitive(False)
		self.cash_entry.set_sensitive(True)
		self.payment_type_id = 2

	def _check_number_changed (self, entry):
		self.emit('changed')

	def _credit_account_changed (self, combo):
		self.emit('changed')

	def reset (self):
		self.check_entry.set_text('')
		self.cash_entry.set_text('')
		self.credit_account_combo.set_active_id(None)
		self.check_radio.set_active(True)

	def get_payment_text (self):
		if self.payment_type_id == 0:
			return self.check_entry.get_text()
		elif self.payment_type_id == 1:
			return self.credit_account_combo.get_active_text() or ''
		return self.cash_entry.get_text()

	def get_credit_card_account_number (self):
		return self.credit_account_combo.get_active_id()

	def check_number_missing (self):
		return self.payment_type_id == 0 and self.check_entry.get_text() == ''

	def credit_card_account_missing (self):
		return (self.payment_type_id == 1 and
					self.credit_account_combo.get_active_id() is None)
