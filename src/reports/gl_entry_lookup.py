# gl_entry_lookup.py
#
# Copyright (C) 2018 - Reuben
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
from db_connection import DB
from constants import ui_directory
import admin_utils

UI_FILE = ui_directory + "/reports/gl_entry_lookup.ui"

'''Which document produced a general ledger entry. Nothing in gl_entries says
so: the link runs the other way, from a document line to the entry that values
it, through seventeen columns spread over twelve tables, so the answer is always
a reverse search. Each branch below searches one of those columns.

Every branch selects exactly eight expressions in this order:

	source_type   the machine key the dispatcher switches on
	label         what the Type column shows. Kept separate from source_type
	              because two source types can read the same to a user, and
	              because translating the label must not break dispatch
	gl_entry_id   the entry this branch resolved, always w.id
	source_id     the document to open, or NULL when nothing opens it
	aux_id        a second handle the opener needs, or NULL. For a payment or a
	              deposit it is the customer, because PaymentsReceivedGUI
	              ignores a payment id unless it is given a customer id too.
	              For an inventory row it is the product
	number        what the Number column shows, as text. Spelling out
	              "Invoice 1043" against "Count 12" is the point: this column
	              used to hold a bare id that was an invoices.id on one row and
	              an inventory_transactions.id on the next, with nothing to
	              tell them apart
	description
	contact

The amount and both dates are taken from gl_entries once, in the outer select,
so a branch never repeats them and cannot disagree with the ledger about what
was posted. The window used to show poli.price, ii.price and it.price, which
are unit prices, not the posted amount.

Every branch joins the wanted CTE rather than repeating the id list, so the
entry ids are passed as one parameter instead of once per branch.'''

SOURCE_BRANCHES = [

	# the receivable and the sales tax an invoice posts, and its lines
	"SELECT 'invoice', 'Invoice', w.id, i.id, NULL, "
		"'Invoice ' || i.id::text, 'Receivable', c.name "
	"FROM invoices AS i "
	"JOIN wanted AS w ON w.id = i.gl_entries_id "
	"JOIN contacts AS c ON c.id = i.customer_id",

	"SELECT 'invoice_tax', 'Invoice tax', w.id, i.id, NULL, "
		"'Invoice ' || i.id::text, 'Sales tax', c.name "
	"FROM invoices AS i "
	"JOIN wanted AS w ON w.id = i.gl_entries_tax_id "
	"JOIN contacts AS c ON c.id = i.customer_id",

	"SELECT 'invoice_item', 'Invoice line', w.id, i.id, NULL, "
		"'Invoice ' || i.id::text, p.name, c.name "
	"FROM invoice_items AS ii "
	"JOIN wanted AS w ON w.id = ii.gl_entries_id "
	"JOIN invoices AS i ON i.id = ii.invoice_id "
	"JOIN products AS p ON p.id = ii.product_id "
	"JOIN contacts AS c ON c.id = i.customer_id",

	# a credit memo mirrors an invoice: a header entry, a tax entry and lines.
	# A memo line names its product through the invoice line it returns
	"SELECT 'credit_memo', 'Credit memo', w.id, cm.id, NULL, "
		"'Credit memo ' || cm.id::text, 'Receivable', c.name "
	"FROM credit_memos AS cm "
	"JOIN wanted AS w ON w.id = cm.gl_entries_id "
	"JOIN contacts AS c ON c.id = cm.customer_id",

	"SELECT 'credit_memo_tax', 'Credit memo tax', w.id, cm.id, NULL, "
		"'Credit memo ' || cm.id::text, 'Sales tax', c.name "
	"FROM credit_memos AS cm "
	"JOIN wanted AS w ON w.id = cm.gl_entries_tax_id "
	"JOIN contacts AS c ON c.id = cm.customer_id",

	"SELECT 'credit_memo_item', 'Credit memo line', w.id, cm.id, NULL, "
		"'Credit memo ' || cm.id::text, p.name, c.name "
	"FROM credit_memo_items AS cmi "
	"JOIN wanted AS w ON w.id = cmi.gl_entry_id "
	"JOIN credit_memos AS cm ON cm.id = cmi.credit_memo_id "
	"JOIN invoice_items AS ii ON ii.id = cmi.invoice_item_id "
	"JOIN products AS p ON p.id = ii.product_id "
	"JOIN contacts AS c ON c.id = cm.customer_id",

	# the payable a purchase order posts, and its lines
	"SELECT 'purchase_order', 'Purchase order', w.id, po.id, NULL, "
		"'PO ' || po.id::text, 'Payable', v.name "
	"FROM purchase_orders AS po "
	"JOIN wanted AS w ON w.id = po.gl_entries_id "
	"JOIN contacts AS v ON v.id = po.vendor_id",

	"SELECT 'purchase_order_item', 'PO line', w.id, po.id, NULL, "
		"'PO ' || po.id::text, p.name, v.name "
	"FROM purchase_order_items AS poli "
	"JOIN wanted AS w ON w.id = poli.gl_entries_id "
	"JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
	"JOIN products AS p ON p.id = poli.product_id "
	"JOIN contacts AS v ON v.id = po.vendor_id",

	# a customer payment posts twice: once when it is taken and again when it
	# is deposited, so the same payment answers for two different entries
	"SELECT 'payment', 'Payment', w.id, p.id, p.customer_id, "
		"'Payment ' || p.id::text, payment_info(p.id), c.name "
	"FROM payments_incoming AS p "
	"JOIN wanted AS w ON w.id = p.gl_entries_id "
	"JOIN contacts AS c ON c.id = p.customer_id",

	# One deposit slip banks many payments at once - deposits.py stamps the one
	# entry Deposit.bank returned onto every payment in the batch - so this is
	# many documents to one entry and has to aggregate. Listing a row per
	# payment would also put the deposit total against each of them, because
	# the amount comes from the entry, not from the payment.
	"SELECT 'deposit', 'Deposit', w.id, "
		"CASE WHEN count(*) = 1 THEN min(p.id) ELSE NULL END, "
		"CASE WHEN count(DISTINCT p.customer_id) = 1 "
			"THEN min(p.customer_id) ELSE NULL END, "
		"'Payment ' || string_agg(DISTINCT p.id::text, ', '), "
		"CASE WHEN count(*) = 1 THEN 'Deposited - ' || min(payment_info(p.id)) "
			"ELSE 'Deposit of ' || count(*)::text || ' payments' END, "
		"string_agg(DISTINCT c.name, ', ') "
	"FROM payments_incoming AS p "
	"JOIN wanted AS w ON w.id = p.gl_entries_deposit_id "
	"JOIN contacts AS c ON c.id = p.customer_id "
	"GROUP BY w.id",

	# a vendor bill: the credit leg, and one debit leg per expense split
	"SELECT 'incoming_invoice', 'Incoming invoice', w.id, ii.id, NULL, "
		"'Incoming invoice ' || ii.id::text, "
		"COALESCE(ii.description, ''), ct.name "
	"FROM incoming_invoices AS ii "
	"JOIN wanted AS w ON w.id = ii.gl_entry_id "
	"JOIN contacts AS ct ON ct.id = ii.contact_id",

	"SELECT 'incoming_invoice_expense', 'Incoming invoice expense', w.id, "
		"ii.id, NULL, 'Incoming invoice ' || ii.id::text, "
		"CASE WHEN iie.remark = '' THEN COALESCE(ii.description, '') "
			"ELSE iie.remark END, ct.name "
	"FROM incoming_invoices_gl_entry_expenses_ids AS iie "
	"JOIN wanted AS w ON w.id = iie.gl_entry_expense_id "
	"JOIN incoming_invoices AS ii ON ii.id = iie.incoming_invoices_id "
	"JOIN contacts AS ct ON ct.id = ii.contact_id",

	# a loan and its payments. No window opens any of these by id, so source_id
	# stays null and the drill down falls back to the whole transaction
	"SELECT 'loan', 'Loan', w.id, NULL, NULL, "
		"'Loan ' || l.id::text, l.description, c.name "
	"FROM loans AS l "
	"JOIN wanted AS w ON w.id = l.gl_entries_id "
	"JOIN contacts AS c ON c.id = l.contact_id",

	"SELECT 'loan_payment_principal', 'Loan payment principal', w.id, "
		"NULL, NULL, 'Loan ' || lp.loan_id::text, l.description, c.name "
	"FROM loan_payments AS lp "
	"JOIN wanted AS w ON w.id = lp.gl_entries_principal_id "
	"JOIN loans AS l ON l.id = lp.loan_id "
	"JOIN contacts AS c ON c.id = lp.contact_id",

	"SELECT 'loan_payment_interest', 'Loan payment interest', w.id, "
		"NULL, NULL, 'Loan ' || lp.loan_id::text, l.description, c.name "
	"FROM loan_payments AS lp "
	"JOIN wanted AS w ON w.id = lp.gl_entries_interest_id "
	"JOIN loans AS l ON l.id = lp.loan_id "
	"JOIN contacts AS c ON c.id = lp.contact_id",

	"SELECT 'loan_payment_total', 'Loan payment', w.id, "
		"NULL, NULL, 'Loan ' || lp.loan_id::text, l.description, c.name "
	"FROM loan_payments AS lp "
	"JOIN wanted AS w ON w.id = lp.gl_entries_total_id "
	"JOIN loans AS l ON l.id = lp.loan_id "
	"JOIN contacts AS c ON c.id = lp.contact_id",

	# Every entry hanging off a stock movement: cost of goods sold on a sale,
	# the cost a credit memo puts back, stock received against a purchase
	# order, a manufacturing transfer, a count, a location transfer and a hand
	# adjustment. One branch rather than seven, resolving the second hop with a
	# CASE, because inventory_transactions has six nullable parent columns and
	# only a check constraint saying at least one is set - nothing stops two
	# being set at once. Deciding the type in one ordered CASE makes a row
	# resolve to exactly one kind no matter what the columns hold, which seven
	# separate branches could not promise. It also fixes what this window used
	# to show: COALESCE(ii.invoice_id, it.id), a number that was an invoices.id
	# on one row and an inventory_transactions.id on the next.
	"SELECT "
		"CASE WHEN it.invoice_line_id IS NOT NULL "
				"THEN 'inventory_invoice_cogs' "
			"WHEN it.purchase_order_item_id IS NOT NULL "
				"THEN 'inventory_po_receipt' "
			"WHEN it.credit_memo_item_id IS NOT NULL "
				"THEN 'inventory_credit_memo_cogs' "
			"WHEN it.manufacturing_id IS NOT NULL "
				"THEN 'inventory_manufacturing' "
			"WHEN it.count_summary_id IS NOT NULL THEN 'inventory_count' "
			"WHEN it.transfer_id IS NOT NULL THEN 'inventory_transfer' "
			"ELSE 'inventory_adjustment' END, "
		"CASE WHEN it.invoice_line_id IS NOT NULL "
				"THEN 'Invoice cost of goods' "
			"WHEN it.purchase_order_item_id IS NOT NULL THEN 'PO receipt' "
			"WHEN it.credit_memo_item_id IS NOT NULL "
				"THEN 'Credit memo cost returned' "
			"WHEN it.manufacturing_id IS NOT NULL THEN 'Manufacturing' "
			"WHEN it.count_summary_id IS NOT NULL THEN 'Inventory count' "
			"WHEN it.transfer_id IS NOT NULL THEN 'Inventory transfer' "
			"ELSE 'Inventory adjustment' END, "
		"w.id, "
		"CASE WHEN it.invoice_line_id IS NOT NULL THEN ii.invoice_id "
			"WHEN it.purchase_order_item_id IS NOT NULL "
				"THEN poli.purchase_order_id "
			"WHEN it.credit_memo_item_id IS NOT NULL "
				"THEN cmi.credit_memo_id "
			"WHEN it.manufacturing_id IS NOT NULL THEN it.manufacturing_id "
			"WHEN it.count_summary_id IS NOT NULL THEN it.count_summary_id "
			"WHEN it.transfer_id IS NOT NULL THEN it.transfer_id "
			"ELSE NULL END, "
		"it.product_id, "
		"CASE WHEN it.invoice_line_id IS NOT NULL "
				"THEN 'Invoice ' || ii.invoice_id::text "
			"WHEN it.purchase_order_item_id IS NOT NULL "
				"THEN 'PO ' || poli.purchase_order_id::text "
			"WHEN it.credit_memo_item_id IS NOT NULL "
				"THEN 'Credit memo ' || cmi.credit_memo_id::text "
			"WHEN it.manufacturing_id IS NOT NULL "
				"THEN 'Project ' || it.manufacturing_id::text "
			"WHEN it.count_summary_id IS NOT NULL "
				"THEN 'Count ' || it.count_summary_id::text "
			"WHEN it.transfer_id IS NOT NULL "
				"THEN 'Transfer ' || it.transfer_id::text "
			"ELSE 'Adjustment ' || it.id::text END, "
		"CASE WHEN it.reason IS NULL OR it.reason = '' THEN p.name "
			"ELSE p.name || ' - ' || it.reason END, "
		"COALESCE(cust.name, vend.name, memo_cust.name, '') "
	"FROM inventory_transactions AS it "
	"JOIN wanted AS w ON w.id = it.gl_entries_id "
	"JOIN products AS p ON p.id = it.product_id "
	"LEFT JOIN invoice_items AS ii ON ii.id = it.invoice_line_id "
	"LEFT JOIN invoices AS i ON i.id = ii.invoice_id "
	"LEFT JOIN contacts AS cust ON cust.id = i.customer_id "
	"LEFT JOIN purchase_order_items AS poli "
		"ON poli.id = it.purchase_order_item_id "
	"LEFT JOIN purchase_orders AS po ON po.id = poli.purchase_order_id "
	"LEFT JOIN contacts AS vend ON vend.id = po.vendor_id "
	"LEFT JOIN credit_memo_items AS cmi ON cmi.id = it.credit_memo_item_id "
	"LEFT JOIN credit_memos AS cm ON cm.id = cmi.credit_memo_id "
	"LEFT JOIN contacts AS memo_cust ON memo_cust.id = cm.customer_id",

	]

'''Payroll and vendor payments resolve only at transaction granularity, so they
have to wait until every branch above has had its say.

Payroll keeps no gl_entries pointer at all - emp_payments points at the
gl_transaction - and a vendor payment settles several purchase orders with one
bank entry, so purchase_orders.gl_transaction_payment_id is the only link and it
is many documents to one entry. Both aggregate, because one transaction can
carry several employees or several orders, and a plain join would return the
same entry once per document.'''

TRANSACTION_BRANCHES = [

	"SELECT 'payroll_payment', 'Payroll', ge.id, NULL, NULL, "
		"'Pay stub ' || string_agg(DISTINCT ep.pay_stub_id::text, ', '), "
		"COALESCE(ge.transaction_description, 'Employee payment'), "
		"string_agg(DISTINCT e.name, ', ') "
	"FROM gl_entries AS ge "
	"JOIN wanted AS w ON w.id = ge.id "
	"JOIN payroll.emp_payments AS ep "
		"ON ep.account_transaction_id = ge.gl_transaction_id "
	"JOIN contacts AS e ON e.id = ep.employee_id "
	"WHERE NOT EXISTS (SELECT 1 FROM tier_1 "
		"WHERE gl_entry_id = ge.id) "
	"GROUP BY ge.id, ge.transaction_description",

	# source_id stays null when several orders share the entry, so the drill
	# down falls back to the transaction rather than opening an arbitrary one
	"SELECT 'vendor_payment', 'Vendor payment', ge.id, "
		"CASE WHEN count(DISTINCT po.id) = 1 THEN min(po.id) ELSE NULL END, "
		"NULL, "
		"'PO ' || string_agg(DISTINCT po.id::text, ', '), "
		"COALESCE(ge.transaction_description, 'Vendor payment'), "
		"string_agg(DISTINCT v.name, ', ') "
	"FROM gl_entries AS ge "
	"JOIN wanted AS w ON w.id = ge.id "
	"JOIN purchase_orders AS po "
		"ON po.gl_transaction_payment_id = ge.gl_transaction_id "
	"JOIN contacts AS v ON v.id = po.vendor_id "
	"WHERE NOT EXISTS (SELECT 1 FROM tier_1 "
		"WHERE gl_entry_id = ge.id) "
	"GROUP BY ge.id, ge.transaction_description",

	]

'''What wrote the entry, read off gl_entries itself, for the postings that keep
no pointer back to any document: a bank charge, a voided check, a hand written
journal entry, a bank to credit card transfer, a card fee, a cash or check
deposit, the payable leg of a vendor payment, miscellaneous revenue. Added by
0.7.33; null on everything posted before it, and no backfill was possible, so an
older entry of these kinds still falls through to the last branch of all.

This resolves last of the three, because it is the weakest evidence: it names the
kind of posting but carries no document to open. A vendor payment is the case
that matters - the transaction branch above can offer the purchase order it
settled, so it has to have first refusal, or the drill down would lose a document
it could have opened.'''

SOURCE_TYPE_BRANCH = (
	"SELECT ge.source_type, "
		"CASE ge.source_type "
			"WHEN 'bank_charge' THEN 'Bank charge' "
			"WHEN 'voided_check' THEN 'Voided check' "
			"WHEN 'journal_entry' THEN 'Journal entry' "
			"WHEN 'bank_to_credit_card_transfer' THEN 'Card transfer' "
			"WHEN 'credit_card_fee_reward' THEN 'Card fee or reward' "
			"WHEN 'deposit_cash' THEN 'Cash deposit' "
			"WHEN 'deposit_check' THEN 'Check deposit' "
			"WHEN 'vendor_payment' THEN 'Vendor payment' "
			"WHEN 'misc_revenue' THEN 'Miscellaneous revenue' "
			"ELSE ge.source_type END, "
		"ge.id, ge.source_id, NULL, "
		"CASE WHEN ge.check_number IS NOT NULL "
				"THEN 'Check ' || ge.check_number::text "
			"ELSE 'Transaction ' || ge.gl_transaction_id::text END, "
		"COALESCE(ge.transaction_description, ''), "
		"COALESCE(ct.name, '') "
	"FROM gl_entries AS ge "
	"JOIN wanted AS w ON w.id = ge.id "
	"LEFT JOIN gl_transactions AS gt ON gt.id = ge.gl_transaction_id "
	"LEFT JOIN contacts AS ct ON ct.id = gt.contact_id "
	"WHERE ge.source_type IS NOT NULL "
		"AND NOT EXISTS (SELECT 1 FROM earlier WHERE gl_entry_id = ge.id)")


BRANCH_COLUMNS = ("source_type", "label", "gl_entry_id", "source_id",
					"aux_id", "number", "description", "contact")

def wrap_branch (body):
	'''name and type every branch's columns identically.

	Both halves are load bearing. A bare SELECT of literals and expressions has
	no column names to offer, so without the alias list the CTEs below could not
	say "gl_entry_id" at all. And an untyped NULL in one branch resolves to text,
	which then collides with the bigint the next branch puts in the same column -
	"UNION types text and integer cannot be matched". Casting here fixes both for
	every branch at once, so a new branch can write a plain NULL and not have to
	remember either rule.'''
	return ("SELECT b.source_type::varchar, b.label::varchar, "
				"b.gl_entry_id::bigint, b.source_id::bigint, "
				"b.aux_id::bigint, b.number::varchar, "
				"b.description::varchar, b.contact::varchar "
			"FROM (" + body + ") AS b (" + ", ".join(BRANCH_COLUMNS) + ")")


def open_source (source_type, source_id, aux_id):
	'''open the document a lookup row came from. Returns False when nothing
	opens this kind of row, so the caller can fall back to the transaction.
	Grouped by opener rather than by source type: the receivable entry, the tax
	entry and a line entry of one invoice all open the same invoice.

	The read only hubs rather than the editors, because a double click in a
	report should not drop the user into an editable invoice.'''
	if source_id == 0:
		return False
	if source_type in ('invoice', 'invoice_tax', 'invoice_item',
						'inventory_invoice_cogs'):
		import invoice_hub
		invoice_hub.InvoiceHubGUI(source_id)
	elif source_type in ('purchase_order', 'purchase_order_item',
						'inventory_po_receipt', 'vendor_payment'):
		import purchase_order_hub
		purchase_order_hub.PurchaseOrderHubGUI(source_id)
	elif source_type in ('incoming_invoice', 'incoming_invoice_expense'):
		import incoming_invoice_edit
		incoming_invoice_edit.EditIncomingInvoiceGUI(source_id)
	elif source_type in ('payment', 'deposit'):
		if aux_id == 0:
			return False # the window ignores a payment without its customer
		from reports import payments_received
		payments_received.PaymentsReceivedGUI(aux_id, source_id)
	else:
		# a credit memo, a loan payment, a pay stub, a count, a transfer, a
		# manufacturing project, a hand adjustment, a journal entry: no window
		# opens any of these by id
		return False
	return True


def build_query ():
	'''the branches are chained so that each one only sees the entries no
	earlier one could resolve, strongest evidence first: a branch that can name
	the document, then one that can only name the transaction, then one that can
	only name the kind of posting. UNION ALL rather than UNION throughout,
	because the branches are meant to be mutually exclusive - a duplicate row is
	a data problem worth seeing rather than one a UNION quietly folds away.

	The last branch is the point of the whole query. Any entry nothing could
	resolve - a hand written journal entry, a bank charge, anything posted
	before 0.7.33 by a window that kept no pointer back - still comes out as a
	row naming its transaction, so selecting an entry can no longer open an
	empty window with no explanation, which is what it did before.'''
	tier_1 = " UNION ALL ".join(map(wrap_branch, SOURCE_BRANCHES))
	tier_2 = " UNION ALL ".join(map(wrap_branch, TRANSACTION_BRANCHES))
	tier_3 = wrap_branch(SOURCE_TYPE_BRANCH)
	return (
		"WITH wanted AS (SELECT id FROM gl_entries WHERE id IN %s), "
		"tier_1 AS (" + tier_1 + "), "
		"tier_2 AS (" + tier_2 + "), "
		"earlier AS (SELECT gl_entry_id FROM tier_1 "
			"UNION ALL SELECT gl_entry_id FROM tier_2), "
		"tier_3 AS (" + tier_3 + "), "
		"resolved AS (SELECT * FROM tier_1 "
			"UNION ALL SELECT * FROM tier_2 "
			"UNION ALL SELECT * FROM tier_3) "
		"SELECT r.label, r.number, r.description, ge.amount::float, "
			"r.contact, ge.date_inserted::text, "
			"format_date(ge.date_inserted), "
			"COALESCE(r.source_id, 0), r.source_type, r.gl_entry_id, "
			"COALESCE(r.aux_id, 0) "
		"FROM resolved AS r "
		"JOIN gl_entries AS ge ON ge.id = r.gl_entry_id "
		"UNION ALL "
		"SELECT 'Journal entry', "
			"'Transaction ' || ge.gl_transaction_id::text, "
			"COALESCE(ge.transaction_description, ''), "
			"ge.amount::float, COALESCE(ct.name, ''), "
			"ge.date_inserted::text, format_date(ge.date_inserted), "
			"0, 'journal_entry', ge.id, 0 "
		"FROM gl_entries AS ge "
		"JOIN wanted AS w ON w.id = ge.id "
		"LEFT JOIN gl_transactions AS gt ON gt.id = ge.gl_transaction_id "
		"LEFT JOIN contacts AS ct ON ct.id = gt.contact_id "
		"WHERE NOT EXISTS (SELECT 1 FROM resolved "
			"WHERE gl_entry_id = ge.id) "
		"ORDER BY 6, 10")


class GlEntryLookupGUI :
	def __init__ (self, entry_ids):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		amount_column = self.builder.get_object('amount_column')
		amount_renderer = self.builder.get_object('amount_renderer')
		amount_column.set_cell_data_func(amount_renderer, self.amount_cell_func)

		self.window = self.builder.get_object('window')
		self.populate_lookup_store (entry_ids)
		self.window.show_all()

	def amount_cell_func (self, column, cellrenderer, model, iter1, data):
		amount = '{:,.2f}'.format(model.get_value(iter1, 3))
		cellrenderer.set_property("text", amount)

	def populate_lookup_store (self, entry_ids):
		store = self.builder.get_object('lookup_store')
		store.clear()
		c = DB.cursor()
		c.execute(build_query(), (tuple(entry_ids),))
		for row in c.fetchall():
			store.append(row)
		c.close()
		DB.rollback()

	def treeview_button_release_event (self, widget, event):
		if event.button == 3:
			menu = self.builder.get_object('lookup_menu')
			menu.popup_at_pointer()

	def treeview_row_activated (self, treeview, path, column):
		store = self.builder.get_object('lookup_store')
		self.open_row (store[path])

	def open_source_activated (self, menuitem):
		selection = self.builder.get_object('treeview').get_selection()
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		self.open_row (model[paths[0]])

	def edit_gl_entry_activated (self, menuitem):
		selection = self.builder.get_object('treeview').get_selection()
		model, paths = selection.get_selected_rows()
		if paths == []:
			return
		self.edit_gl_entry (model[paths[0]][9])

	def open_row (self, row):
		if open_source(row[8], row[7], row[10]) == True:
			return
		# nothing opens this kind of row, so show the whole balanced
		# transaction instead. For an entry posted before the source columns
		# existed that is the only thing there is to show
		self.edit_gl_entry (row[9])

	def edit_gl_entry (self, gl_entry_id):
		'''the entry editor is admin gated everywhere else it is opened from,
		and it is a real editor, so a report window must not be the one place
		that opens it unguarded'''
		if admin_utils.check_admin(self.window) == False:
			return
		from admin import edit_gl_entry
		edit_gl_entry.EditGlEntryGUI(gl_entry_id)
