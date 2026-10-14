# trial_balance.py
#
# Copyright (C) 2026 - Reuben Rissler
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
from datetime import date
from decimal import Decimal
import psycopg2
from dateutils import DateTimeCalendar
from db_connection import DB
from db import ledger
from constants import ui_directory, ACCOUNT_TYPES

UI_FILE = ui_directory + "/reports/trial_balance.ui"


def money (value):
	return '${:,.2f}'.format(value)


class TrialBalanceGUI (Gtk.Builder):
	def __init__ (self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.store = self.get_object("trial_balance_store")
		self.start_date = None
		self.end_date = None
		self.start_text = ''
		self.end_text = ''
		self.rows = [] # the last result, kept so the hide toggle need not re-query
		self.loading = True # suppresses the populate the opening set_date calls fire
		self.status_parts = []
		self.status_error = False

		# override = True because a trial balance date is a reporting cut, not a
		# posting date. Without it DateTimeCalendar refuses any date outside an
		# active fiscal year and re-pops itself every two seconds, which for a
		# company whose fiscal years stop short of today is every date
		self.start_calendar = DateTimeCalendar(override = True)
		self.start_calendar.set_relative_to(self.get_object('start_date_entry'))
		self.start_calendar.connect('day-selected', self.start_date_selected)
		self.end_calendar = DateTimeCalendar(override = True)
		self.end_calendar.set_relative_to(self.get_object('end_date_entry'))
		self.end_calendar.connect('day-selected', self.end_date_selected)

		# before the set_date calls below: they reach the date handlers, which
		# populate, and a failure there puts a dialog transient for this window
		self.window = self.get_object("window")

		start_date, end_date, dated_by_fiscal_year = self.default_dates ()
		self.start_calendar.set_date(start_date)
		self.end_calendar.set_date(end_date)
		self.loading = False
		self.populate_trial_balance ()
		if dated_by_fiscal_year == False:
			self.append_status("No fiscal year is marked active, so the dates "
								"opened on this year so far rather than on a "
								"year end.")

		self.window.show_all()

	def default_dates (self):
		'''the active fiscal year, so that a trial balance at year end is the
		report opening rather than something to set up first. active is not
		unique - fiscal_years.py toggles it a row at a time and a company here
		may have every year since 2015 marked active - so this prefers the
		active year that contains today and falls back to the latest one'''
		cursor = DB.cursor()
		cursor.execute("SELECT start_date, end_date FROM fiscal_years "
							"WHERE active = True "
							"ORDER BY (CURRENT_DATE BETWEEN start_date "
								"AND end_date) DESC, start_date DESC "
							"LIMIT 1")
		result = cursor.fetchone()
		cursor.close()
		DB.rollback()
		if result == None:
			today = date.today()
			return date(today.year, 1, 1), today, False
		return result[0], result[1], True

	def start_date_selected (self, calendar):
		self.start_date = calendar.get_date()
		self.start_text = calendar.get_text()
		self.get_object('start_date_entry').set_text(self.start_text)
		if self.loading == False:
			self.populate_trial_balance ()

	def end_date_selected (self, calendar):
		self.end_date = calendar.get_date()
		self.end_text = calendar.get_text()
		self.get_object('end_date_entry').set_text(self.end_text)
		if self.loading == False:
			self.populate_trial_balance ()

	def reload_clicked (self, button):
		self.populate_trial_balance ()

	def hide_empty_toggled (self, checkbutton):
		self.show_rows () # from the cache: hiding a row is not a different query

	def populate_trial_balance (self):
		if self.start_date == None or self.end_date == None:
			return
		if self.start_date > self.end_date:
			self.store.clear()
			self.clear_totals ()
			self.set_status("The start date is after the end date, so there is "
							"no period to report on.", error = True)
			return
		# the two date handlers are connected with calendar.connect rather than
		# through connect_signals, so they are outside the proxy that absorbs
		# database errors in autoconnected handlers - the same note dateutils
		# carries on its own day_selected
		try:
			self.rows = ledger.account_balances(self.start_date, self.end_date)
		except psycopg2.Error as e:
			DB.rollback()
			self.rows = []
			self.store.clear()
			self.clear_totals ()
			self.set_status("The ledger could not be read: %s"
							% str(e).strip(), error = True)
			return
		DB.rollback()
		self.show_rows ()

	def show_rows (self):
		'''the totals are accumulated over every account, before the hide filter,
		so what the footer says does not depend on what is on screen. The filter
		only drops accounts that are zero in all four figures, which contribute
		nothing to any total anyway'''
		hide_empty = self.get_object('hide_empty_checkbutton').get_active()
		self.store.clear()
		opening_total = Decimal()
		debits_total = Decimal()
		credits_total = Decimal()
		closing_total = Decimal()
		for number, name, type_, is_parent, opening, debits, credits in self.rows:
			closing = opening + debits - credits
			opening_total += opening
			debits_total += debits
			credits_total += credits
			closing_total += closing
			if hide_empty and not (opening or debits or credits or closing):
				continue
			self.store.append([number,
								name,
								ACCOUNT_TYPES.get(type_, 'Type %s' % type_),
								money(opening), float(opening),
								money(debits), float(debits),
								money(credits), float(credits),
								money(closing), float(closing)])
		self.get_object('opening_total_label').set_label(money(opening_total))
		self.get_object('period_debits_total_label').set_label(money(debits_total))
		self.get_object('period_credits_total_label').set_label(money(credits_total))
		self.get_object('closing_total_label').set_label(money(closing_total))
		self.report_balance (opening_total, debits_total, credits_total,
								closing_total)

	def report_balance (self, opening_total, debits_total, credits_total,
						closing_total):
		'''every account's balance signed and added together comes to zero when
		each transaction's two halves are both present, there being no year end
		closing entries to carry anything out of the ledger. So a non zero total
		is not a rounding artifact: it is the money in entries whose other half
		was never written.

		Whether that happened in this period is a separate question, and the one
		worth answering, because a company carrying an old one sided entry would
		otherwise be told its ledger is broken every time it closes a year.
		Debits less credits for the period is closing less opening identically,
		so the period columns disagreeing is exactly an entry dated in the
		period going unmatched'''
		if closing_total == 0:
			self.set_status("In balance at %s." % self.end_text)
		else:
			self.set_status("Out of balance by %s at %s. The ledger holds one "
							"sided entries whose other half is missing."
							% (money(abs(closing_total)), self.end_text),
							error = True)
		period_difference = debits_total - credits_total
		if period_difference != 0:
			self.append_status("The period's own debits and credits differ by "
								"%s, so an entry dated in this period is one of "
								"them." % money(abs(period_difference)))
		elif opening_total != 0:
			self.append_status("The period's debits and credits agree, so all "
								"of it was already there at %s."
								% self.start_text)

	def set_status (self, message, error = False):
		self.status_parts = [message]
		self.status_error = error
		self.render_status ()

	def append_status (self, message):
		self.status_parts.append(message)
		self.render_status ()

	def render_status (self):
		'''the sentences are held as text and the markup applied to the joined
		whole, so that appending one cannot land inside a span or carry a
		database error message\'s own characters into the markup parser'''
		text = ' '.join(self.status_parts)
		label = self.get_object('balance_status_label')
		if self.status_error == True:
			label.set_markup("<span foreground='#d40000'>%s</span>"
								% GLib.markup_escape_text(text))
		else:
			label.set_label(text)

	def clear_totals (self):
		for label in ('opening_total_label', 'period_debits_total_label',
						'period_credits_total_label', 'closing_total_label'):
			self.get_object(label).set_label(money(Decimal()))

	def report_hub_clicked (self, button):
		# the footer totals live in labels, so like net_worth and
		# profit_loss_report they are not carried into the PDF or the xls
		treeview = self.get_object('trial_balance_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def start_date_icon_released (self, entry, icon, event):
		self.start_calendar.show()

	def end_date_icon_released (self, entry, icon, event):
		self.end_calendar.show()
