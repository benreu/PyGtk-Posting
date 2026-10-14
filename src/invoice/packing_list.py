# packing_list.py
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

import subprocess
from db_connection import DB
from constants import template_dir
from invoice.invoice_create import Item


class Setup:
    '''A pick sheet for an invoice: what to pull, and nothing about money.

    Read only by construction, which is why this is a module of its own and not
    a flag on invoice_create.Setup - that one rewrites the invoice's subtotal,
    tax and total as it builds, and carries post () and the two print methods
    that stamp date_printed. None of that may happen for a packing list, so
    there is no code here that could. The header read below is deliberately the
    twin of invoice_create.create_pdf (): keep the two recognisable.'''

    def __init__(self, store, invoice_id, date, comment = ''):
        self.store = store
        self.invoice_id = invoice_id
        self.date = date
        # taken as an argument, not read from invoices.comments: the window
        # saves that on a typing pause, so the column can be a sentence behind
        # what the picker is looking at. invoice_window.live_comment () is the
        # one place it comes from, the same as for the printed invoice
        self.comment = comment
        self.create_pdf()

    def create_pdf(self):
        cursor = DB.cursor()
        # the contact is reached through invoices.customer_id rather than taken
        # as an argument, so the sheet cannot name a customer the invoice row
        # disagrees with - which it briefly does after an invoice is transferred
        cursor.execute(
            "SELECT c.name, c.address, c.city, c.state, c.zip, i.name, "
            "sa.id, sa.address, sa.city, sa.state, sa.zip, "
            "COALESCE(sc.name, '') "
            "FROM contacts AS c "
            "JOIN invoices AS i ON i.customer_id = c.id "
            "LEFT JOIN contact_shipping_addresses AS sa "
            "ON sa.id = i.shipping_address_id "
            "LEFT JOIN shipping_carriers AS sc "
            "ON sc.id = sa.shipping_carrier_id "
            "WHERE i.id = %s", (self.invoice_id,))
        customer = Item()
        shipping = None
        invoice_name = ''  # set before the loop: the invoice may be gone
        for row in cursor.fetchall():
            customer.name = row[0]
            customer.street = row[1]  # contacts calls it address, company_info street
            customer.city = row[2]
            customer.state = row[3]
            customer.zip = row[4]
            invoice_name = row[5]
            if row[6] != None:  # the invoice names a shipping address
                shipping = Item()
                shipping.name = row[0]
                shipping.street = row[7]
                shipping.city = row[8]
                shipping.state = row[9]
                shipping.zip = row[10]
                shipping.carrier = row[11]

        company = Item()
        # named columns, not SELECT *: a new company_info column must not be able
        # to shift the address out from under these
        cursor.execute("SELECT name, street, city, state, zip FROM company_info")
        for row in cursor.fetchall():
            company.name = row[0]
            company.street = row[1]
            company.city = row[2]
            company.state = row[3]
            company.zip = row[4]

        document = Item()
        document.number = str(self.invoice_id)
        document.comment = self.comment
        cursor.execute("SELECT format_date(%s)", (self.date,))
        document.date = cursor.fetchone()[0]

        # read off the live store, not invoice_items: the store is already
        # filtered of canceled lines and carries the on screen row order
        items = []
        for i in self.store:
            item = Item()
            item.qty = i[1]
            item.unit = i[13]
            item.product = i[3]
            item.ext_name = (" , " + i[4]) if i[4] else ""
            item.remark = (" : " + i[5]) if i[5] else ""
            items.append(item)

        # never "/tmp/<invoices.name>.pdf" - that is the invoice's own file, and
        # invoice_create.post () reads that exact path back into invoices.pdf_data.
        # invoices.name defaults to '', so fall back to the id for a sane filename
        stem = invoice_name or ("Inv_%s" % self.invoice_id)
        self.document_name = stem + "_packing_list"
        self.document_pdf = self.document_name + ".pdf"
        self.packing_list_pdf = "/tmp/" + self.document_pdf

        cursor.close()
        DB.rollback()  # before the render: WeasyPrint must not hold a snapshot open

        from jinja2 import Environment, FileSystemLoader
        import weasyprint

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('packing_list_template.html')
        self.html = template.render(
            items=items,
            document=document,
            contact=customer,
            shipping=shipping,
            company=company,
        )
        weasyprint.HTML(string=self.html).write_pdf(self.packing_list_pdf)

    def view(self):
        subprocess.Popen(["xdg-open", self.packing_list_pdf])
