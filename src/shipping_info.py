# shipping_info.py
#
# Copyright (C) 2018 - reuben
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
from dateutils import DateTimeCalendar
from db import transactor
from db_connection import DB, broadcaster
from constants import ui_directory

UI_FILE = ui_directory + "/shipping_info.ui"

class ShippingInfoGUI(Gtk.Builder):
	shipping_description = None
	invoice_id = None
	freight_product_id = None
	bill_freight = False # whether the chosen invoice can take a freight charge
	freight_tip = '' # why it can or cannot, shown on the product combo
	incoming_invoice = None
	def __init__ (self):

		Gtk.Builder.__init__(self)
		self.add_from_file(UI_FILE)
		self.connect_signals(self)

		self.calendar = DateTimeCalendar()
		self.calendar.connect('day-selected', self.calendar_day_selected)
		self.date = None
		self.posted_answers = dict() # invoice id: bill the freight to it or not

		self.contact_store = self.get_object('contact_store')
		self.invoice_store = self.get_object('invoice_store')
		self.freight_product_store = self.get_object('freight_product_store')
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"id::text, name, ext_name "
							"FROM contacts AS c "
							"WHERE deleted = False "
							"ORDER BY name")
		for row in cursor.fetchall():
			self.contact_store.append(row)
		cursor.execute("SELECT "
								"id::text, name, ext_name "
							"FROM products "
							"WHERE (deleted, sellable) = (False, True) "
							"ORDER BY name")
		for row in cursor.fetchall():
			self.freight_product_store.append(row)
		cursor.execute("SELECT freight_product_id::text FROM settings")
		freight_product_id = cursor.fetchone()[0]
		cursor.close()
		DB.rollback()
		contact_completion = self.get_object('contact_completion')
		contact_completion.set_match_func(self.contact_match_func)
		freight_product_completion = self.get_object('freight_product_completion')
		freight_product_completion.set_match_func(self.freight_product_match_func)
		if freight_product_id != None:
			# the product freight is usually billed as. set_active_id leaves the
			# combo empty when that product is no longer sellable, so a product
			# retired since the last shipment simply has to be chosen again
			self.get_object('freight_product_combo').set_active_id(freight_product_id)
		
		self.window = self.get_object('window')
		self.window.show_all()

	def destroy (self, widget):
		if self.incoming_invoice:
			self.incoming_invoice.get_object('window1').destroy()

	def help_clicked (self, button):
		print ('please add help to shipping info')

	def contact_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.contact_store[iter_][1].lower():
				return False
		return True

	def freight_product_match_func(self, completion, key, iter_):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.freight_product_store[iter_][1].lower():
				return False
		return True

	def freight_product_combo_changed (self, combobox):
		product_id = combobox.get_active_id()
		if product_id != None:
			self.freight_product_id = product_id

	def freight_product_match_selected (self, entrycompletion, treemodel, treeiter):
		self.freight_product_id = treemodel[treeiter][0]
		self.get_object('freight_product_combo').set_active_id(self.freight_product_id)

	def contact_changed (self, combobox):
		contact_id = combobox.get_active_id()
		if contact_id != None:
			self.contact_id = contact_id
			self.populate_invoices()
			self.populate_shipping_history ()

	def contact_match_selected (self, entrycompletion, treemodel, treeiter):
		self.contact_id = treemodel[treeiter][0]
		self.populate_invoices()
		self.populate_shipping_history ()

	def invoice_match_selected (self, entrycompletion, treemodel, treeiter):
		self.invoice_id = treemodel[treeiter][0]
		self.get_object('tracking_number_entry').set_sensitive(True)
		self.set_freight_charge_state ()

	def shipping_description_changed (self, entry):
		description = entry.get_text()
		if description == '':
			self.get_object('tracking_number_entry').set_sensitive(False)
			self.shipping_description = None
		else:
			self.get_object('tracking_number_entry').set_sensitive(True)
			self.shipping_description = description

	def populate_invoices (self):
		self.invoice_id = None
		self.bill_freight = False # no invoice chosen, nothing to bill freight to
		self.posted_answers.clear() # another contact, another set of invoices
		self.freight_tip = ("Choose the invoice the freight belongs on. A "
							"shipment entered with a description instead of an "
							"invoice is recorded without a charge")
		self.update_freight_combo_state ()
		self.get_object('invoice_id_entry').set_text('')
		self.get_object('shipping_description_entry').set_sensitive(True)
		self.invoice_store.clear()
		cursor = DB.cursor()
		# only the invoices a freight charge can still go on. A paid one is
		# settled, one closed onto a statement would never be picked up by any
		# statement again, and shipping_info.invoice_id is unique, so an invoice
		# that already carries a shipment would fail its insert - which happens
		# after the carrier payment has been committed. A posted invoice is
		# listed: set_freight_charge_state asks about those
		cursor.execute("SELECT "
								"i.id::text, i.name "
							"FROM invoices AS i "
							"WHERE (i.canceled, i.paid, i.customer_id) = "
								"(False, False, %s) "
								"AND i.statement_id IS NULL "
								"AND NOT EXISTS (SELECT 1 FROM shipping_info "
													"WHERE invoice_id = i.id) "
							"ORDER BY i.id"
							, (self.contact_id,))
		for row in cursor.fetchall():
			self.invoice_store.append(row)
		cursor.close()
		DB.rollback()

	def tracking_number_changed (self, entry):
		self.get_object('incoming_invoice_button').set_sensitive(True)

	def invoice_changed (self, combobox):
		invoice_id = combobox.get_active_id()
		if invoice_id != None:
			self.invoice_id = invoice_id
			self.get_object('tracking_number_entry').set_sensitive(True)
			self.set_freight_charge_state ()

	def set_freight_charge_state (self):
		'''which invoices may be billed for freight, and the tooltip saying why
		not. A paid invoice is settled and its receivable is already offset,
		which is why resync_invoice_accounts skips it: a line would raise the
		total with no revenue under it. An invoice closed onto a statement is
		worse. The statement has frozen its own amount and its pdf, and
		close_invoices_and_payments only ever picks up invoices with no
		statement_id, so the charge would appear on that statement and on every
		later one: never. A posted invoice is fair game, the invoice window
		edits those too, but it has usually been sent, so it is asked about'''
		cursor = DB.cursor()
		cursor.execute("SELECT paid, statement_id IS NOT NULL, posted "
							"FROM invoices WHERE id = %s", (self.invoice_id,))
		paid, on_statement, posted = cursor.fetchone()
		cursor.close()
		DB.rollback()
		normal_tip = ("The freight paid on the payment tab is billed to invoice "
						"%s as this product" % self.invoice_id)
		if paid == True:
			self.bill_freight = False
			tip = ("Invoice %s is already paid, the freight cannot be billed "
					"to it" % self.invoice_id)
		elif on_statement == True:
			self.bill_freight = False
			tip = ("Invoice %s is on a printed statement, the freight cannot be "
					"billed to it: no statement would ever pick it up"
					% self.invoice_id)
		elif posted == True:
			self.bill_freight = self.posted_invoice_accepted ()
			if self.bill_freight == True:
				tip = normal_tip
			else:
				tip = ("You chose not to bill the freight to invoice %s, which "
						"is already posted" % self.invoice_id)
		else:
			self.bill_freight = True
			tip = normal_tip
		self.freight_tip = tip
		self.update_freight_combo_state ()

	def update_freight_combo_state (self):
		'''the whole freight row follows the invoice's own state: with no invoice
		chosen, or one that cannot take the charge, there is nothing to decide and
		the row says so by greying out. The product combo answers to the check
		button as well, since an invoice that may be billed is no use if the user
		has switched the charge off for this shipment'''
		self.get_object('bill_freight_check').set_sensitive(self.bill_freight)
		combo = self.get_object('freight_product_combo')
		combo.set_sensitive(self.freight_is_billable ())
		if self.get_object('bill_freight_check').get_active() == False:
			combo.set_tooltip_text("The freight on this shipment is not being "
									"billed to the invoice")
		else:
			combo.set_tooltip_text(self.freight_tip)

	def freight_is_billable (self):
		'''the invoice will take the charge and the user has not switched it off'''
		return (self.bill_freight == True
				and self.get_object('bill_freight_check').get_active() == True)

	def bill_freight_toggled (self, checkbutton):
		# deliberately not saved: it is a decision per shipment, and the box
		# comes up checked again on the next window
		self.update_freight_combo_state ()

	def posted_invoice_accepted (self):
		'''asked once per invoice: invoice_changed and invoice_match_selected
		both land in set_freight_charge_state, and either may fire for one pick'''
		if self.invoice_id not in self.posted_answers:
			self.posted_answers[self.invoice_id] = self.confirm_posted_invoice ()
		return self.posted_answers[self.invoice_id]

	def confirm_posted_invoice (self):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.WARNING,
									buttons = Gtk.ButtonsType.YES_NO)
		dialog.set_transient_for(self.window)
		dialog.set_markup ("Invoice %s is already posted and may have been sent "
							"to the customer.\n\nBill the freight to it anyway?"
							% self.invoice_id)
		result = dialog.run()
		dialog.destroy()
		return result == Gtk.ResponseType.YES

	def incoming_invoice_clicked (self, button):
		if not self.incoming_invoice:
			import incoming_invoice
			self.incoming_invoice = incoming_invoice.IncomingInvoiceGUI()
			box = self.incoming_invoice.get_object('box1')
			window = self.incoming_invoice.get_object('window1')
			window.remove(box)
			window.hide() # do not destroy and thereby disconnect signals
			self.get_object('payment_box').add(box)
			stack = self.get_object('stack1')
			stack.set_visible_child(self.get_object('payment_box'))
			self.incoming_invoice.connect('invoice_applied', self.incoming_invoice_applied)
			text = self.get_object('shipping_description_entry').get_text()
			self.incoming_invoice.set_shipping_description(text)
			self.incoming_invoice.set_date(self.date)
		else:
			text = self.get_object('shipping_description_entry').get_text()
			self.incoming_invoice.set_shipping_description(text)
			self.incoming_invoice.set_date(self.date)
			stack = self.get_object('stack1')
			stack.set_visible_child(self.get_object('payment_box'))

	def incoming_invoice_applied (self, incoming_invoice_object):
		self.incoming_invoice_id = incoming_invoice_object.invoice_id
		c = DB.cursor()
		tracking_number = self.get_object('tracking_number_entry').get_text()
		try:
			c.execute("INSERT INTO shipping_info "
						"(date_shipped, tracking_number, reason, "
							"contact_id, invoice_id, incoming_invoice_id) "
						"VALUES (%s, %s, %s, %s, %s, %s)", 
						(self.date, tracking_number, self.shipping_description,
						self.contact_id, self.invoice_id, 
						self.incoming_invoice_id))
			billed_invoice_id = self.add_freight_charge (c, tracking_number)
			DB.commit()
		except Exception as e:
			DB.rollback()
			self.show_message(str(e))
		else:
			if billed_invoice_id != None:
				# an invoice window open on it reloads from the database. Its own
				# pg_notify arrives on this connection, where show_reload_infobar
				# takes it for the window's own edit and ignores it
				broadcaster.emit("invoices_changed", billed_invoice_id, True)
		c.close()
		self.populate_shipping_history()
		stack = self.get_object('stack1')
		stack.set_visible_child(self.get_object('shipping_box'))

	def add_freight_charge (self, cursor, tracking_number):
		'''bill the customer for the freight that was just paid. The charge rides
		in the transaction the shipping_info row is written in, so a shipment is
		never recorded with half of its paperwork, and the price is read back from
		the row incoming_invoice saved rather than from its widgets. Returns the
		invoice billed, or None when there was nothing to bill'''
		if self.invoice_id == None or self.freight_product_id == None:
			return None # a description only shipment has no invoice to bill
		if self.freight_is_billable () == False:
			return None # the invoice will not take it, or the box is cleared
		invoice_id = int(self.invoice_id) # the combo hands its id back as text
		# the payment page can sit open for a while, long enough for the invoice
		# to be paid or rolled onto a statement since it was picked. Read it back
		# rather than raise a dialog between the insert and the commit
		cursor.execute("SELECT paid OR statement_id IS NOT NULL "
							"FROM invoices WHERE id = %s", (invoice_id,))
		if cursor.fetchone()[0] == True:
			return None
		cursor.execute("SELECT amount FROM incoming_invoices WHERE id = %s",
													(self.incoming_invoice_id,))
		price = cursor.fetchone()[0]
		cursor.execute("INSERT INTO invoice_items "
							"(invoice_id, qty, product_id, remark, price, "
							"canceled, tax_rate_id) "
						"VALUES (%s, 1, %s, %s, %s, False, "
							# the exemption the rest of the invoice carries. The
							# a_check_tax_rate_id trigger swaps in the product's
							# own rate when the product is not exemptible, and
							# when this is null because the invoice has no lines
							"(SELECT tax_rate_id FROM invoice_items "
								"WHERE (invoice_id, canceled) = (%s, False) "
								"ORDER BY id LIMIT 1))",
						(invoice_id, self.freight_product_id, tracking_number, price,
						invoice_id))
		cursor.execute("UPDATE settings SET freight_product_id = %s",
														(self.freight_product_id,))
		# the totals calculate_totals would have saved had the line been typed
		# into the invoice window. resync_invoice_accounts recomputes them for a
		# posted invoice, but it leaves a draft alone and a draft still has to
		# add up: posting copies the saved total to amount due
		cursor.execute("UPDATE invoices AS i SET (subtotal, tax, total) = "
							"(t.subtotal, t.tax, t.total) "
						"FROM (SELECT COALESCE(SUM(ext_price), 0.00) AS subtotal, "
								"COALESCE(SUM(tax), 0.00) AS tax, "
								"COALESCE(SUM(ext_price) + SUM(tax), 0.00) "
									"AS total "
								"FROM invoice_items WHERE invoice_id = %s) AS t "
						"WHERE i.id = %s", (invoice_id, invoice_id))
		# follow the new line into both ledgers, the stock before the general
		# ledger the way resync_posted_invoice does it. Both leave a draft alone,
		# and the inventory half is a no-op for a product that is not tracked,
		# which a shipping product will not be; it is called so that billing the
		# freight as a stocked product still moves the stock
		from inventory import inventorying
		inventorying.resync_invoice_inventory (invoice_id)
		transactor.resync_invoice_accounts (invoice_id)
		return invoice_id

	def populate_shipping_history (self):
		store = self.get_object('shipping_history_store')
		store.clear()
		cursor = DB.cursor()
		cursor.execute("SELECT "
								"sh.id, "
								"COALESCE(sh.invoice_id, 0), "
								"COALESCE(sh.invoice_id::text, 'N/A'), "
								"sh.tracking_number, "
								"sh.date_shipped::text, "
								"format_date(sh.date_shipped), "
								"sh.reason "
							"FROM shipping_info AS sh "
							"WHERE sh.contact_id = %s ORDER BY date_shipped",
							(self.contact_id,))
		for row in cursor.fetchall():
			store.append(row)
		cursor.close()
		DB.rollback()

	def calendar_day_selected (self, calendar):
		self.date = calendar.get_date()
		day_text = calendar.get_text()
		self.get_object('entry2').set_text(day_text)
		self.get_object('contact_combo').set_sensitive(True)

	def calendar_entry_icon_released (self, widget, icon, event):
		self.calendar.set_relative_to(widget)
		self.calendar.show()

	def show_message (self, message):
		dialog = Gtk.MessageDialog(	message_type = Gtk.MessageType.ERROR,
									buttons = Gtk.ButtonsType.CLOSE)
		dialog.set_transient_for(self.window)
		dialog.set_markup (message)
		dialog.run()
		dialog.destroy()
		
	def shipping_history_clicked (self, button):
		from reports import shipping_history
		shipping_history.ShippingHistoryGUI()



