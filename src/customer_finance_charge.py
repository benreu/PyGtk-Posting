# customer_finance_charge.py
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
import subprocess, re
import printing
from db_connection import DB
from constants import ui_directory, help_dir, template_dir

UI_FILE = ui_directory + "/customer_finance_charge.ui"

class Item(object):
	pass

class CustomerFinanceChargeGUI:
	def __init__(self):

		self.builder = Gtk.Builder()
		self.builder.add_from_file(UI_FILE)
		self.builder.connect_signals(self)

		self.customer_id = None

		self.customer_store = self.builder.get_object('customer_store')
		self.finance_charge_store = self.builder.get_object('finance_charge_store')
		customer_completion = self.builder.get_object('customer_completion')
		customer_completion.set_match_func(self.customer_match_func)
		self.customer_combobox_populate()

		self.window = self.builder.get_object('window1')
		self.window.show_all()

	def help_button_clicked(self, widget):
		subprocess.Popen(["yelp", help_dir + "/finance_charge.page"])

	def payment_window(self, widget):
		import customer_payment
		customer_payment.GUI(customer_id=self.customer_id)

	def _render_pdf(self, doc_number, date_text, balance_due, total_fee, rate):
		c = DB.cursor()

		c.execute("SELECT * FROM contacts WHERE id = %s", (self.customer_id,))
		customer = Item()
		for row in c.fetchall():
			customer.name = row[1]
			name = row[1]
			customer.ext_name = row[2]
			customer.street = row[3]
			customer.city = row[4]
			customer.state = row[5]
			customer.zip = row[6]
			customer.phone = row[8]
			customer.email = row[9]

		company = Item()
		c.execute("SELECT * FROM company_info")
		for row in c.fetchall():
			company.name = row[1]
			company.street = row[2]
			company.city = row[3]
			company.state = row[4]
			company.zip = row[5]
			company.phone = row[7]
			company.email = row[9]
		c.close()

		items = []
		for i in self.finance_charge_store:
			item = Item()
			item.invoice_id = i[0]
			item.name = i[1]
			item.date = i[3]
			item.amount_unpaid = '${:,.2f}'.format(float(i[4]))
			item.fee = '${:,.2f}'.format(float(i[6]))
			items.append(item)

		split_name = name.split(' ')
		name_abbrev = ''.join(s[0:3] for s in split_name).lower()
		doc_date = re.sub('[, ]', '_', date_text).strip('_')

		document = Item()
		document.number = str(doc_number)
		document.date = date_text
		document.balance_due = '${:,.2f}'.format(balance_due)
		document.rate = '{:.4f}%'.format(rate * 100 * 365)
		document.total = '${:,.2f}'.format(total_fee)

		pdf_name = "FinChg_{}_{}_{}.pdf".format(doc_number, name_abbrev, doc_date)
		pdf_path = "/tmp/" + pdf_name

		from jinja2 import Environment, FileSystemLoader
		import weasyprint
		env = Environment(loader=FileSystemLoader(template_dir))
		template = env.get_template('finance_charge_template.html')
		html = template.render(items=items, document=document,
								contact=customer, company=company)
		weasyprint.HTML(string=html).write_pdf(pdf_path)
		return pdf_path

	def _store_totals(self):
		balance_due = sum(float(i[4]) for i in self.finance_charge_store)
		total_fee = sum(float(i[6]) for i in self.finance_charge_store)
		c = DB.cursor()
		c.execute("SELECT finance_rate, format_date(CURRENT_DATE) FROM settings")
		rate, date_text = c.fetchone()
		c.close()
		return balance_due, total_fee, float(rate), date_text

	def view_statement_clicked(self, button):
		balance_due, total_fee, rate, date_text = self._store_totals()
		pdf_path = self._render_pdf("preview", date_text, balance_due, total_fee, rate)
		subprocess.Popen(["xdg-open", pdf_path])

	def print_statement_clicked(self, button):
		balance_due, total_fee, rate, date_text = self._store_totals()

		c = DB.cursor()
		c.execute("INSERT INTO invoices "
					"(customer_id, name, dated_for, total, amount_due, "
					"posted, finance_charge, finance_rate) "
					"VALUES (%s, %s, CURRENT_DATE, %s, %s, True, True, %s) "
					"RETURNING id",
					(self.customer_id,
					'Finance Charge ' + date_text,
					total_fee, total_fee, rate))
		invoice_id = c.fetchone()[0]
		c.close()

		pdf_path = self._render_pdf(invoice_id, date_text, balance_due, total_fee, rate)

		p = printing.Operation(settings_file='finance_charge')
		p.set_parent(self.window)
		p.set_file_to_print(pdf_path)
		result = p.print_dialog()
		if result == Gtk.PrintOperationResult.APPLY:
			from db import transactor
			transactor.post_finance_charge(invoice_id)
			with open(pdf_path, 'rb') as fp:
				pdf_data = fp.read()
			c = DB.cursor()
			c.execute("UPDATE invoices "
						"SET (pdf_data, date_printed) = (%s, CURRENT_DATE) "
						"WHERE id = %s",
						(pdf_data, invoice_id))
			c.close()
			DB.commit()
			self.customer_combobox_populate()
			self.finance_charge_store.clear()
			self.builder.get_object('combobox-entry').set_text("")
		else:
			DB.rollback()

	def customer_combobox_populate(self):
		self.customer_store.clear()
		c = DB.cursor()
		c.execute("WITH table2 AS "
					"( "
					"SELECT id, "
						"(SELECT COALESCE(SUM(amount_due), 0.0) "
						"AS invoices_total FROM invoices "
						"WHERE (canceled, posted, customer_id) = "
						"(False, True, c.id)), "
						"(SELECT amount + amount_owed AS payments_total FROM "
							"(SELECT COALESCE(SUM(amount), 0.0) AS amount "
							"FROM payments_incoming "
							"WHERE (customer_id, misc_income) = (c.id, False)"
							") pi, "
							"(SELECT COALESCE(SUM(amount_owed), 0.0) "
								"AS amount_owed "
							"FROM credit_memos WHERE (customer_id, posted) "
								"= (c.id, True)"
							") cm "
						"), "
					"name, ext_name FROM contacts AS c "
					"WHERE customer = True ORDER by name"
					") "
					"SELECT "
						"id::text, "
						"name, "
						"ext_name, "
						"(invoices_total - payments_total)::money "
							"AS balance_due, "
						"((invoices_total - payments_total) * "
							"(SELECT finance_rate FROM settings) * 365.0 / 12)::money "
								"AS finance_fee "
					"FROM table2 "
					"WHERE (invoices_total - payments_total) > 0 "
					"ORDER BY name, ext_name")
		for row in c.fetchall():
			self.customer_store.append(row)
		c.close()
		DB.rollback()

	def focus(self, window, event):
		self.customer_combobox_populate()

	def customer_combobox_changed(self, combo):
		active = self.builder.get_object('combobox1').get_active()
		if active == -1:
			return
		self.customer_id = self.customer_store[active][0]
		self.builder.get_object('label2').set_label(str(self.customer_store[active][3]))
		self.populate_finance_charge_store()

	def customer_match_func(self, completion, key, iter):
		split_search_text = key.split()
		for text in split_search_text:
			if text not in self.customer_store[iter][1].lower():
				return False
		return True

	def customer_match_selected(self, completion, model, iter):
		customer_id = model[iter][0]
		self.builder.get_object('combobox1').set_active_id(customer_id)

	def populate_finance_charge_store(self):
		self.finance_charge_store.clear()
		c_id = self.customer_id
		c = DB.cursor()
		c.execute("WITH invoice_cte AS "
					"(SELECT i.id, i.name, i.dated_for, i.finance_charge, "
						"(CASE WHEN SUM(i.amount_due) OVER (ORDER BY i.id) > "
							"p.amount "
						"THEN LEAST(SUM(i.amount_due) OVER (ORDER BY i.id) "
							"- p.amount, i.amount_due) "
						"ELSE 0.00 "
						"END) AS amount_unpaid "
					"FROM invoices i "
					"CROSS JOIN "
						"(SELECT amount + amount_owed AS amount FROM "
							"(SELECT SUM(amount) AS amount "
							"FROM payments_incoming WHERE customer_id = %s "
							") pi, "
							"(SELECT "
								"COALESCE(SUM(-amount_owed), 0.00) AS amount_owed "
							"FROM credit_memos "
							"WHERE (posted, customer_id) = (True, %s) "
							") cm "
						") p "
					"WHERE customer_id = %s ORDER BY i.id ) "
					"SELECT "
						"id::text, "
						"name, "
						"dated_for::text, "
						"format_date(dated_for), "
						"amount_unpaid, "
						"amount_unpaid::text, "
						"ROUND(amount_unpaid * (SELECT finance_rate FROM settings) * 365.0 / 12 * "
						"GREATEST(1, FLOOR( "
							"CASE "
								"WHEN t.pay_in_days_active THEN "
									"(CURRENT_DATE - dated_for - t.pay_in_days) / 30.0 "
								"WHEN t.pay_by_day_of_month_active THEN "
									"(CURRENT_DATE - date_trunc('month', dated_for)::date "
									"- (t.pay_by_day_of_month - 1)) / 30.0 "
								"ELSE (CURRENT_DATE - dated_for) / 30.0 "
							"END "
						")), 2), "
						"ROUND(amount_unpaid * (SELECT finance_rate FROM settings) * 365.0 / 12 * "
						"GREATEST(1, FLOOR( "
							"CASE "
								"WHEN t.pay_in_days_active THEN "
									"(CURRENT_DATE - dated_for - t.pay_in_days) / 30.0 "
								"WHEN t.pay_by_day_of_month_active THEN "
									"(CURRENT_DATE - date_trunc('month', dated_for)::date "
									"- (t.pay_by_day_of_month - 1)) / 30.0 "
								"ELSE (CURRENT_DATE - dated_for) / 30.0 "
							"END "
						")), 2)::text "
					"FROM invoice_cte "
					"CROSS JOIN "
						"(SELECT pay_in_days, pay_by_day_of_month, "
							"pay_in_days_active, pay_by_day_of_month_active, cash_only "
						"FROM contacts "
						"JOIN terms_and_discounts "
							"ON contacts.terms_and_discounts_id = terms_and_discounts.id "
						"WHERE contacts.id = %s "
						") t "
					"WHERE amount_unpaid != 0.00 "
					"AND (finance_charge = False OR finance_charge IS NULL) "
					"AND ("
						"(t.cash_only) "
						"OR (t.pay_in_days_active "
							"AND (CURRENT_DATE - dated_for) > t.pay_in_days) "
						"OR (t.pay_by_day_of_month_active "
							"AND CURRENT_DATE > "
							"date_trunc('month', dated_for)::date "
							"+ (t.pay_by_day_of_month - 1)) "
					") ",
					(c_id, c_id, c_id, c_id))
		for row in c.fetchall():
			self.finance_charge_store.append(row)
		total_fee = sum(float(i[6]) for i in self.finance_charge_store)
		self.builder.get_object('label3').set_label('${:,.2f}'.format(total_fee))
		self.builder.get_object('button3').set_sensitive(True)
		c.close()
		DB.rollback()
