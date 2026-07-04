# invoice_create.py
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
import os, subprocess, psycopg2
from urllib.parse import quote
from datetime import datetime, timedelta
from db import transactor
import printing
from constants import DB, template_dir


class Item(object):
    pass


class Setup:
    def __init__(self, store, contact_id, comment, date,
                 invoice_id, parent, doc_type="Invoice"):
        self.contact_id = contact_id
        self.store = store
        self.comment = comment
        self.date = date
        self.invoice_id = invoice_id
        self.doc_type = doc_type
        self.parent = parent
        self.create_pdf()

    def create_pdf(self):
        cursor = DB.cursor()
        cursor.execute(
            "SELECT c.name, c.ext_name, c.address, c.city, c.state, c.zip, "
            "c.fax, c.phone, c.email, c.label, c.tax_number, i.name "
            "FROM contacts AS c "
            "JOIN invoices AS i ON i.customer_id = c.id "
            "WHERE i.id = %s", [self.invoice_id])
        customer = Item()
        for row in cursor.fetchall():
            customer.name = row[0]
            customer.ext_name = row[1]
            customer.street = row[2]
            customer.city = row[3]
            customer.state = row[4]
            customer.zip = row[5]
            customer.fax = row[6]
            customer.phone = row[7]
            customer.email = row[8]
            customer.label = row[9]
            customer.tax_exempt_number = row[10]
            invoice_name = row[11]

        company = Item()
        cursor.execute("SELECT * FROM company_info")
        for row in cursor.fetchall():
            company.name = row[1]
            company.street = row[2]
            company.city = row[3]
            company.state = row[4]
            company.zip = row[5]
            company.country = row[6]
            company.phone = row[7]
            company.fax = row[8]
            company.email = row[9]
            company.website = row[10]
            company.tax_number = row[11]

        items = []
        for i in self.store:
            item = Item()
            item.qty = i[1]
            item.product = i[3]
            item.ext_name = (" , " + i[4]) if i[4] else ""
            item.remark = (" : " + i[5]) if i[5] else ""
            item.price = i[6]
            item.tax_letter = i[11]
            item.tax = i[7]
            item.ext_price = i[8]
            items.append(item)

        terms = Item()
        cursor.execute(
            "SELECT plus_date, text1, text2, text3, text4 "
            "FROM contacts "
            "JOIN terms_and_discounts "
            "ON contacts.terms_and_discounts_id = terms_and_discounts.id "
            "WHERE contacts.id = %s", (self.contact_id,))
        for row in cursor.fetchall():
            plus_date = row[0]
            terms.plus_date = plus_date
            terms.text1 = row[1]
            terms.text2 = row[2]
            terms.text3 = row[3]
            terms.text4 = row[4]

        document = Item()
        cursor.execute(
            "WITH _subtotal AS "
            "(SELECT SUM(ext_price) AS ep FROM invoice_items WHERE invoice_id = %s), "
            "_tax AS "
            "(SELECT SUM(tax) FROM invoice_items WHERE invoice_id = %s) "
            "UPDATE invoices SET (subtotal, tax, total) = "
            "((SELECT * FROM _subtotal), (SELECT * FROM _tax), "
            "(SELECT * FROM _subtotal) + (SELECT * FROM _tax)) "
            "WHERE id = %s "
            "RETURNING subtotal::money, tax::money, total::money",
            (self.invoice_id, self.invoice_id, self.invoice_id))
        for row in cursor.fetchall():
            document.subtotal = row[0]
            document.tax = row[1]
            document.total = row[2]

        document.comment = self.comment
        document.document_status = ''

        date_plus_thirty = self.date + timedelta(days=plus_date)
        cursor.execute("SELECT format_date(%s), format_date(%s)",
                       (date_plus_thirty, self.date))
        for row in cursor.fetchall():
            payment_due_text = row[0]
            date_text = row[1]

        if self.doc_type == "Invoice":
            document.payment_due = payment_due_text
        else:
            terms.plus_date = ''
            terms.text1 = ''
            terms.text2 = ''
            terms.text3 = ''
            terms.text4 = ''

        document.date = date_text
        document.name = invoice_name
        document.number = str(self.invoice_id)
        document.type = self.doc_type

        self.document_name = document.name
        self.document_pdf = document.name + ".pdf"
        self.invoice_pdf = "/tmp/" + self.document_pdf

        cursor.execute(
            "SELECT p.name, sn.serial_number "
            "FROM serial_numbers AS sn "
            "JOIN invoice_items AS ii ON ii.id = sn.invoice_item_id "
            "JOIN products AS p ON p.id = sn.product_id "
            "WHERE ii.invoice_id = %s "
            "ORDER BY p.name, sn.serial_number",
            (self.invoice_id,))
        serial_rows = cursor.fetchall()
        serial_numbers = [{'product': r[0], 'number': r[1]} for r in serial_rows]

        from jinja2 import Environment, FileSystemLoader
        import weasyprint

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('invoice_template.html')
        html = template.render(
            items=items,
            document=document,
            contact=customer,
            terms=terms,
            company=company,
            serial_numbers=serial_numbers,
        )
        weasyprint.HTML(string=html).write_pdf(self.invoice_pdf)
        cursor.close()

    def save(self):
        pass  # PDF already written in create_pdf

    def view(self):
        subprocess.Popen(["xdg-open", self.invoice_pdf])

    def print_dialog(self, window):
        p = printing.Operation(settings_file="invoice")
        p.set_parent(window)
        p.set_file_to_print(self.invoice_pdf)
        result = p.print_dialog()
        if result == Gtk.PrintOperationResult.APPLY:
            cursor = DB.cursor()
            cursor.execute("UPDATE invoices SET date_printed = CURRENT_DATE "
                           "WHERE id = %s", (self.invoice_id,))
            cursor.close()
        return result

    def print_directly(self, window):
        p = printing.Operation(settings_file="invoice")
        p.set_parent(window)
        p.set_file_to_print(self.invoice_pdf)
        result = p.print_directly()
        cursor = DB.cursor()
        if result == Gtk.PrintOperationResult.APPLY:
            cursor.execute("UPDATE invoices SET date_printed = CURRENT_DATE "
                           "WHERE id = %s", (self.invoice_id,))
        cursor.close()

    def email(self, email, total):
        cursor = DB.cursor()
        cursor.execute("SELECT name FROM contacts WHERE id = %s",
                       (self.contact_id,))
        name_row = cursor.fetchone()
        cursor.close()
        total = '${:.2f}'.format(float(total)) if total is not None else ''
        customer_name = name_row[0] if name_row else ''
        subject = "Invoice %s" % (self.invoice_id,)
        body = quote(
            "Hi %s,\n\n"
            "Your invoice #%s for the amount of %s is attached. "
            "Please pay at your earliest convenience.\n\n"
            "Delete all copies of this email if you are not the correct recipient."
            % (customer_name, self.invoice_id, total))
        subprocess.Popen(["thunderbird",
                          "-compose",
                          "to=" + email +
                          ",subject=" + subject + ","
                          "body=" + body + ","
                          "attachment=" + self.invoice_pdf])

    def post(self):
        with open(self.invoice_pdf, 'rb') as f:
            binary = psycopg2.Binary(f.read())
        cursor = DB.cursor()
        cursor.execute(
            "UPDATE invoices SET (name, pdf_data, posted, amount_due, dated_for) "
            "= (%s, %s, %s, total, %s) "
            "WHERE id = %s RETURNING gl_entries_id, total",
            (self.document_name, binary, True, self.date, self.invoice_id))
        for row in cursor.fetchall():
            gl_entries_id = row[0]
            total = row[1]
        self.total = total
        cursor.execute("SELECT accrual_based FROM settings")
        if cursor.fetchone()[0]:
            transactor.post_invoice_accounts(
                self.date, self.invoice_id, total, gl_entries_id)
        cursor.close()
