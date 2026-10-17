# unbalanced_transactions.py
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
from decimal import Decimal
import psycopg2
import admin_utils
from db_connection import DB
from db import ledger
from constants import ui_directory

UI_FILE = ui_directory + "/reports/unbalanced_transactions.ui"

ORPHAN = 'Orphan'
HEADER_CLAIMED = 'Header claimed'
MIXED = 'Mixed'
ATTACHED = 'Attached'
EMPTY = 'Empty header'

# the order they are summarized in, least entangled first: it is also the order
# somebody working through them should take
SAFETY_ORDER = (ORPHAN, HEADER_CLAIMED, MIXED, ATTACHED, EMPTY)


def money (value):
	return '${:,.2f}'.format(value)


def safety_of (lines, attached_lines, header_claimed):
	'''how far into a posted document somebody would be reaching to repair this.
	A line a document claims as its own is that document's half of the story,
	so the fix belongs to the document, not to the ledger. A loan's own entries
	are the exception and come back repairable - ledger.unbalanced_transactions
	says why'''
	if lines == 0:
		return EMPTY
	if attached_lines == 0:
		if header_claimed == True:
			return HEADER_CLAIMED
		return ORPHAN
	if attached_lines < lines:
		return MIXED
	return ATTACHED


class UnbalancedTransactionsGUI (Gtk.Builder):
	def __init__ (self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.store = self.get_object("unbalanced_store")
		self.transactions = []
		self.entries = []

		self.window = self.get_object("window")
		self.populate_unbalanced_store ()
		self.window.show_all()

	def populate_unbalanced_store (self):
		'''two queries for the whole report, the transactions and then every
		line of them at once, rather than a query per parent row'''
		try:
			self.transactions = ledger.unbalanced_transactions()
			self.entries = ledger.transaction_entries(
								[row[0] for row in self.transactions])
		except psycopg2.Error as e:
			DB.rollback()
			self.transactions = []
			self.entries = []
			self.store.clear()
			self.set_status("The ledger could not be read: %s"
							% str(e).strip(), error = True)
			return
		DB.rollback()
		self.show_rows ()

	def show_rows (self):
		self.store.clear()
		lines_by_transaction = {}
		for entry in self.entries:
			lines_by_transaction.setdefault(entry[1], []).append(entry)
		counts = {}
		gross = Decimal()
		net = Decimal()
		for (transaction_id, date, lines, debits, credits, first_line_date,
				last_line_date, reconciled_lines, attached_lines,
				header_claimed) in self.transactions:
			imbalance = debits - credits
			gross += abs(imbalance)
			net += imbalance
			safety = safety_of(lines, attached_lines, header_claimed)
			counts[safety] = counts.get(safety, 0) + 1
			parent = self.store.append(None, [
					transaction_id,
					0,
					'Txn %s' % transaction_id,
					str(date),
					self.format_date(date),
					self.line_summary(lines, reconciled_lines),
					money(debits), float(debits),
					money(credits), float(credits),
					money(imbalance), float(imbalance),
					safety,
					self.reconciled_summary(lines, reconciled_lines),
					'',
					'',
					self.date_span(date, first_line_date, last_line_date)])
			for entry in lines_by_transaction.get(transaction_id, []):
				self.append_entry (parent, entry)
		self.get_object('transaction_count_label').set_label(
								str(len(self.transactions)))
		self.get_object('gross_total_label').set_label(money(gross))
		self.get_object('net_total_label').set_label(money(net))
		self.get_object('safety_summary_label').set_label(
			'   '.join('%s %s' % (name, counts[name])
						for name in SAFETY_ORDER if name in counts))
		self.report_findings (counts, net)

	def append_entry (self, parent, entry):
		(entry_id, transaction_id, date, amount, debit_account, debit_name,
			credit_account, credit_name, reconciled, check_number,
			description, document) = entry
		self.store.append(parent, [
				transaction_id,
				entry_id,
				'Entry %s' % entry_id,
				str(date),
				self.format_date(date),
				self.account_summary(debit_account, debit_name,
										credit_account, credit_name),
				money(amount) if debit_account else '',
				float(amount) if debit_account else 0.00,
				money(amount) if credit_account else '',
				float(amount) if credit_account else 0.00,
				'', 0.00,
				'',
				'Reconciled' if reconciled else '',
				document,
				self.hint(check_number, description),
				''])

	def hint (self, check_number, description):
		'''transaction_description is blank on almost every line in a real
		ledger, and where it is filled in it is a payee name rather than a
		reason, so the check number shares the column with it'''
		parts = []
		if check_number:
			parts.append('Check %s' % check_number)
		if description:
			parts.append(description)
		return ' \u00b7 '.join(parts)

	def account_summary (self, debit_account, debit_name, credit_account,
							credit_name):
		'''a line names one account or two. Two means it balances on its own,
		which is worth seeing plainly next to the siblings that do not'''
		debit = '%s %s' % (debit_account, debit_name) if debit_account else ''
		credit = '%s %s' % (credit_account, credit_name) if credit_account else ''
		if debit and credit:
			return '%s → %s' % (debit, credit)
		return debit or credit or 'no account'

	def line_summary (self, lines, reconciled_lines):
		if lines == 0:
			return 'no lines at all'
		if lines == 1:
			return '1 line'
		return '%s lines' % lines

	def reconciled_summary (self, lines, reconciled_lines):
		if reconciled_lines == 0:
			return ''
		if reconciled_lines == lines:
			return 'Reconciled'
		return '%s of %s reconciled' % (reconciled_lines, lines)

	def date_span (self, header_date, first_line_date, last_line_date):
		'''lines dated apart are a different defect from a missing half - a
		document whose two halves were filed into different periods - and it
		would otherwise be invisible behind the imbalance'''
		if first_line_date == None:
			return ''
		if first_line_date != last_line_date:
			return '%s to %s' % (self.format_date(first_line_date),
									self.format_date(last_line_date))
		if first_line_date != header_date:
			return 'lines %s' % self.format_date(first_line_date)
		return ''

	def format_date (self, date):
		if date == None:
			return ''
		return date.strftime('%m-%d-%Y')

	def report_findings (self, counts, net):
		repairable = counts.get(ORPHAN, 0)
		entangled = counts.get(ATTACHED, 0) + counts.get(HEADER_CLAIMED, 0)
		message = ("Net %s, which is what the trial balance is out by, less "
					"anything dated outside the period it was run for. "
					% money(net))
		if repairable:
			message += ("%s of these can be put right here: nothing is "
						"re-deriving them from a document that the repair "
						"would then contradict. " % repairable)
		if entangled:
			message += ("%s are a posted invoice or purchase order's own "
						"entries; writing their missing half by hand would "
						"change that document's ledger footprint behind its "
						"back, so fix the document instead. " % entangled)
		if counts.get(EMPTY, 0):
			message += ("%s are journal headers with no lines at all, which "
						"cost the ledger nothing but are nothing either. "
						% counts[EMPTY])
		self.set_status(message.strip())

	def set_status (self, message, error = False):
		label = self.get_object('status_label')
		if error == True:
			label.set_markup("<span foreground='#d40000'>%s</span>"
								% GLib.markup_escape_text(message))
		else:
			label.set_label(message)

	def reload_clicked (self, button):
		self.populate_unbalanced_store ()

	def expand_all_clicked (self, button):
		self.get_object('unbalanced_treeview').expand_all()

	def collapse_all_clicked (self, button):
		self.get_object('unbalanced_treeview').collapse_all()

	def report_hub_clicked (self, button):
		# the footer totals live in labels, so they are not carried into the
		# pdf or the xls; and export_to_xls walks the model flat, so only the
		# pdf keeps the lines under their transaction
		treeview = self.get_object('unbalanced_treeview')
		from reports import report_hub
		report_hub.ReportHubGUI(treeview)

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.get_object('right_click_menu')
			menu.popup_at_pointer()

	def edit_gl_entry_activated (self, menuitem):
		'''the editor works on whichever transaction the entry belongs to, so
		any one line of it opens all of them together'''
		model, paths = self.get_object('unbalanced_selection').get_selected_rows()
		if paths == []:
			return
		entry_id = model[paths[0]][1]
		if entry_id == 0:
			tree_iter = model.get_iter(paths[0])
			if not model.iter_has_child(tree_iter):
				self.show_message("This transaction has no entries to edit.")
				return
			entry_id = model[model.iter_children(tree_iter)][1]
		if not admin_utils.check_admin(self.window):
			return
		from admin import edit_gl_entry
		edit_gl_entry.EditGlEntryGUI(entry_id)

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
