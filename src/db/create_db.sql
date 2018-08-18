-- create.sql
--
-- Copyright (C) 2016 - reuben
--
-- This program is free software, you can redistribute it and/or modify
-- it under the terms of the GNU Lesser General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY, without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program. If not, see <http://www.gnu.org/licenses/>.


CREATE SCHEMA payroll;
CREATE SCHEMA settings;
CREATE SCHEMA sql;


CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;
COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';



CREATE TABLE public.terms_and_discounts (
    id bigserial primary key,
    name character varying NOT NULL,
    cash_only boolean NOT NULL,
    discount_percent integer NOT NULL,
    pay_in_days smallint NOT NULL,
    pay_by_day_of_month smallint NOT NULL,
    pay_in_days_active boolean NOT NULL,
    pay_by_day_of_month_active boolean NOT NULL,
    standard boolean NOT NULL,
    markup_percent integer NOT NULL,
    plus_date smallint NOT NULL,
    text1 character varying DEFAULT '' NOT NULL,
    text2 character varying DEFAULT '' NOT NULL,
    text3 character varying DEFAULT '' NOT NULL,
    text4 character varying DEFAULT '' NOT NULL,
    deleted boolean DEFAULT false NOT NULL
);

CREATE TABLE public.customer_markup_percent (
    id bigserial primary key,
    name character varying NOT NULL,
    markup_percent integer NOT NULL,
    standard boolean DEFAULT false NOT NULL,
    deleted boolean DEFAULT false NOT NULL
);

CREATE TABLE public.contacts (
    id bigserial primary key,
    name character varying DEFAULT ''::character varying NOT NULL,
    ext_name character varying DEFAULT ''::character varying NOT NULL,
    address character varying DEFAULT ''::character varying NOT NULL,
    city character varying DEFAULT ''::character varying NOT NULL,
    state character varying DEFAULT ''::character varying NOT NULL,
    zip character varying DEFAULT ''::character varying NOT NULL,
    fax character varying DEFAULT ''::character varying NOT NULL,
    phone character varying DEFAULT ''::character varying NOT NULL,
    email character varying DEFAULT ''::character varying NOT NULL,
    label character varying DEFAULT ''::character varying NOT NULL,
    tax_number character varying DEFAULT ''::character varying NOT NULL,
    vendor boolean DEFAULT false NOT NULL,
    customer boolean DEFAULT false NOT NULL,
    employee boolean DEFAULT false NOT NULL,
    custom1 character varying DEFAULT ''::character varying NOT NULL,
    custom2 character varying DEFAULT ''::character varying NOT NULL,
    custom3 character varying DEFAULT ''::character varying NOT NULL,
    custom4 character varying DEFAULT ''::character varying NOT NULL,
    notes character varying DEFAULT ''::character varying NOT NULL,
    active boolean,
    deleted boolean DEFAULT false NOT NULL,
    terms_and_discounts_id integer NOT NULL REFERENCES public.terms_and_discounts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    service_provider boolean DEFAULT false NOT NULL,
    checks_payable_to character varying DEFAULT ''::character varying NOT NULL,
    markup_percent_id integer NOT NULL REFERENCES public.customer_markup_percent(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE payroll.employee_info (
    id bigserial primary key,
    employee_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_created date NOT NULL,
    born date NOT NULL,
    social_security character varying NOT NULL,
    social_security_exempt boolean NOT NULL,
    on_payroll_since date,
    wage numeric(12,2) NOT NULL,
    payment_frequency smallint NOT NULL,
    married boolean NOT NULL,
    last_updated date NOT NULL,
    state_income_status boolean NOT NULL,
    state_credits smallint NOT NULL,
    state_extra_withholding numeric(12,2) NOT NULL,
    fed_income_status boolean NOT NULL,
    fed_credits smallint NOT NULL,
    fed_extra_withholding numeric(12,2) NOT NULL,
    s_s_medicare_exemption bytea,
    fed_witholding_status bytea,
    state_status bytea,
    document bytea,
    current boolean DEFAULT true NOT NULL
);

CREATE TABLE payroll.tax_table (
    id bigserial primary key,
    tax_term date NOT NULL,
    s_s_percent numeric(12,5) NOT NULL,
    s_s_surcharge numeric(12,2) NOT NULL,
    medicare_percent numeric(12,5) NOT NULL,
    medicare_surcharge numeric(12,2) NOT NULL,
    state_standard_reduction numeric(12,2) NOT NULL,
    state_tax_credit numeric(12,2) NOT NULL,
    fed_standard_reduction numeric(12,2) NOT NULL,
    fed_tax_credit numeric(12,2) NOT NULL,
    unemployment_wage_base numeric(12,2) NOT NULL,
    unemployment_tax_rate numeric(12,5) NOT NULL,
    unemployment_surcharge numeric(12,5) NOT NULL,
    annual_filing_threshhold numeric(12,2) NOT NULL,
    quarterly_filing_threshhold numeric(12,2) NOT NULL,
    monthly_deposit numeric(12,2) NOT NULL,
    daily_deposit numeric(12,2) NOT NULL
);

CREATE TABLE payroll.pay_stubs (
    id bigserial primary key,
    employee_id bigint  NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_inserted date NOT NULL,
    regular_hours numeric(12,2) NOT NULL,
    overtime_hours numeric(12,2) NOT NULL,
    cost_sharing numeric(12,2) NOT NULL,
    profit_sharing numeric(12,2) NOT NULL,
    pdf_data bytea,
    hourly_wage numeric(12,2) NOT NULL,
    tax_table_id bigint NOT NULL REFERENCES payroll.tax_table(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    s_s_withheld numeric(12,2) NOT NULL,
    medicare_withheld numeric(12,2) NOT NULL,
    state_withheld numeric(12,2) NOT NULL,
    fed_withheld numeric(12,2) NOT NULL,
    unemployment_liability numeric(12,6) NOT NULL,
    regular_hrs_total numeric(12,2) NOT NULL,
    overtime_hrs_total numeric(12,2) NOT NULL,
    tips_dividends_total numeric(12,2) NOT NULL,
    gross_payment_amnt numeric(12,2) NOT NULL,
    employee_info_id bigint NOT NULL REFERENCES payroll.employee_info(id) ON DELETE RESTRICT
);

CREATE TABLE public.gl_accounts (
    id bigserial,
    name character varying NOT NULL,
    type smallint NOT NULL,
    number bigint PRIMARY KEY,
    parent_number bigint REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    is_parent boolean DEFAULT false NOT NULL,
    expense_account boolean DEFAULT false NOT NULL,
    bank_account boolean DEFAULT false NOT NULL,
    credit_card_account boolean DEFAULT false NOT NULL,
    revenue_account boolean DEFAULT false NOT NULL,
    cash_account boolean DEFAULT false NOT NULL,
    inventory_account boolean DEFAULT false NOT NULL,
    deposits boolean DEFAULT false NOT NULL,
    check_writing boolean DEFAULT false NOT NULL
);

CREATE TABLE public.gl_account_flow (
    id serial primary key,
    function character varying NOT NULL,
    account bigint NOT NULL REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE public.gl_transactions (
    id bigserial primary key,
    date_inserted date DEFAULT now() NOT NULL,
    contact_id bigint REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    loan_payment boolean DEFAULT false
);

CREATE TABLE public.gl_entries (
    id bigserial primary key,
    date_inserted date DEFAULT now() NOT NULL,
    amount numeric(12,2) NOT NULL,
    debit_account bigint REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    credit_account bigint REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    reconciled boolean DEFAULT false NOT NULL,
    transaction_description character varying,
    fees_rewards boolean DEFAULT false NOT NULL,
    check_number smallint,
    loan_payment boolean DEFAULT false NOT NULL,
    date_reconciled date,
    gl_transaction_id bigint NOT NULL REFERENCES public.gl_transactions(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT credit_or_debit_is_not_null CHECK (((credit_account IS NOT NULL) OR (debit_account IS NOT NULL)))
);

CREATE TABLE payroll.employee_payments (
    id bigserial primary key,
    employee_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_inserted date NOT NULL,
    amount_paid numeric(12,2) NOT NULL,
    account_transaction_id bigint REFERENCES public.gl_transactions(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    pay_stub_id bigint REFERENCES payroll.pay_stubs(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE payroll.employee_pdf_archive (
    id bigserial primary key,
    employee_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    s_s_medicare_exemption_pdf bytea,
    fed_withholding_pdf bytea,
    state_withholding_pdf bytea,
    archived boolean DEFAULT false NOT NULL,
    date_inserted date
);

CREATE TABLE public.tax_rates (
    id serial primary key,
    name character varying NOT NULL,
    rate numeric(12,2) NOT NULL,
    standard boolean NOT NULL,
    exemption boolean NOT NULL DEFAULT False,
    exemption_template_path character varying,
    deleted boolean NOT NULL DEFAULT False,
    tax_letter character varying NOT NULL,
    tax_received_account bigint NOT NULL REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE public.products (
    id bigserial primary key,
    name character varying DEFAULT ''::character varying NOT NULL,
    description character varying DEFAULT ''::character varying NOT NULL,
    barcode character varying NOT NULL DEFAULT currval( 'products_id_seq'::regclass),
    unit character varying NOT NULL,
    product_groups_id integer,
    cost numeric(12,2) DEFAULT 0.00 NOT NULL,
    tax_rate_id smallint NOT NULL REFERENCES public.tax_rates(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    deleted boolean DEFAULT false NOT NULL,
    sellable boolean DEFAULT true NOT NULL,
    purchasable boolean DEFAULT false NOT NULL,
    min_inventory smallint DEFAULT 0 NOT NULL,
    reorder_qty smallint DEFAULT 0 NOT NULL,
    tax_exemptible boolean DEFAULT false NOT NULL,
    manufactured boolean DEFAULT false NOT NULL,
    weight numeric(12,3) DEFAULT 0.00 NOT NULL,
    tare numeric(12,3) DEFAULT 0.00 NOT NULL,
    ext_name character varying DEFAULT ''::character varying NOT NULL,
    stock boolean DEFAULT true NOT NULL,
    default_expense_account bigint NOT NULL REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    inventory_enabled boolean DEFAULT false NOT NULL,
    revenue_account bigint NOT NULL REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    expense boolean DEFAULT false NOT NULL,
    manufacturer_sku character varying DEFAULT ''::character varying NOT NULL,
    job boolean DEFAULT false NOT NULL,
    inventory_account bigint REFERENCES public.gl_accounts(number) ON UPDATE CASCADE ON DELETE RESTRICT,
    serial_number bigint DEFAULT 0,
    catalog boolean DEFAULT false NOT NULL,
    catalog_order integer DEFAULT 0,
    image bytea,
    invoice_serial_numbers boolean DEFAULT false NOT NULL,
    CONSTRAINT inventory_account_is_applied CHECK (((inventory_account IS NOT NULL) OR (inventory_enabled = false))),
    CONSTRAINT products_manufacturer_sku_check CHECK ((manufacturer_sku IS NOT NULL)),
    CONSTRAINT products_serial_number_check CHECK ((serial_number IS NOT NULL))
);

CREATE TABLE public.company_info (
    id serial primary key,
    name character varying DEFAULT '' NOT NULL,
    street character varying DEFAULT '' NOT NULL,
    city character varying DEFAULT '' NOT NULL,
    state character varying DEFAULT '' NOT NULL,
    zip character varying DEFAULT '' NOT NULL,
    country character varying DEFAULT '' NOT NULL,
    phone character varying DEFAULT '' NOT NULL,
    fax character varying DEFAULT '' NOT NULL,
    email character varying DEFAULT '' NOT NULL,
    website character varying DEFAULT '' NOT NULL,
    tax_number character varying DEFAULT '' NOT NULL
);

CREATE TABLE public.contact_individuals (
    id bigserial primary key,
    name character varying DEFAULT '' NOT NULL,
    address character varying DEFAULT '' NOT NULL,
    city character varying DEFAULT '' NOT NULL,
    state character varying DEFAULT '' NOT NULL,
    zip character varying DEFAULT '' NOT NULL,
    fax character varying DEFAULT '' NOT NULL,
    phone character varying DEFAULT '' NOT NULL,
    email character varying DEFAULT '' NOT NULL,
    website character varying DEFAULT '' NOT NULL,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    role character varying DEFAULT '' NOT NULL,
    extension character varying DEFAULT '' NOT NULL
);

CREATE TABLE public.statements (
    id bigserial primary key,
    name character varying,
    date_inserted date DEFAULT now() NOT NULL,
    customer_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    amount numeric(12,2) DEFAULT 0.00 NOT NULL,
    print_date date ,
    pdf bytea,
    printed boolean DEFAULT False NOT NULL
);

CREATE TABLE public.payments_incoming (
    id bigserial primary key,
    date_inserted date DEFAULT now() NOT NULL,
    amount numeric(12,2) DEFAULT 0.00 NOT NULL,
    comments character varying DEFAULT '' NOT NULL,
    payment_text character varying DEFAULT '' NOT NULL,
    closed boolean DEFAULT false NOT NULL,
    customer_id integer NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    check_payment boolean DEFAULT false NOT NULL,
    check_deposited boolean DEFAULT false NOT NULL,
    cash_payment boolean DEFAULT false NOT NULL,
    credit_card_payment boolean DEFAULT false NOT NULL,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    misc_income boolean DEFAULT false NOT NULL,
    gl_entries_deposit_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    payment_receipt_pdf bytea,
    statement_id bigint REFERENCES public.statements(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.invoices (
    id bigserial primary key,
    name character varying DEFAULT '' NOT NULL,
    customer_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    paid boolean DEFAULT false NOT NULL,
    canceled boolean DEFAULT false  NOT NULL,
    active boolean DEFAULT true NOT NULL,
    date_paid date,
    date_printed date,
    date_created date DEFAULT now() NOT NULL,
    subtotal numeric(12,2) DEFAULT 0.00 NOT NULL,
    tax numeric(12,2) DEFAULT 0.00 NOT NULL,
    total numeric(12,2) DEFAULT 0.00 NOT NULL,
    pdf_data bytea,
    posted boolean DEFAULT FALSE NOT NULL,
    doc_type character varying,
    comments character varying,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    amount_due numeric(12,2) DEFAULT 0.00 NOT NULL,
    gl_entries_tax_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    payments_incoming_id bigint REFERENCES public.payments_incoming(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    statement_id bigint REFERENCES public.statements(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    dated_for date
);

CREATE TABLE public.invoice_items (
    id bigserial primary key,
    invoice_id bigint NOT NULL REFERENCES public.invoices(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty numeric(12,2) DEFAULT 0 NOT NULL,
    remark character varying DEFAULT '' NOT NULL,
    price numeric(12,2) DEFAULT 0 NOT NULL,
    tax numeric(12,2) DEFAULT 0.0 NOT NULL,
    ext_price numeric(12,2) DEFAULT 0.0 NOT NULL,
    canceled boolean DEFAULT FALSE NOT NULL,
    product_id integer NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    imported boolean DEFAULT FALSE NOT NULL,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    tax_rate_id integer NOT NULL REFERENCES public.tax_rates(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.credit_memos (
    id bigserial primary key,
    name character varying,
    customer_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_created date NOT NULL,
    date_printed date,
    total numeric(12,2) DEFAULT 0.00 NOT NULL,
    tax numeric(12,2) DEFAULT 0.00 NOT NULL,
    amount_owed numeric(12,2) DEFAULT 0.00 NOT NULL,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    gl_entries_tax_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    statement_id bigint REFERENCES public.statements(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    posted boolean DEFAULT false NOT NULL
);

CREATE TABLE public.credit_memo_items (
    id bigserial primary key,
    credit_memo_id bigint NOT NULL REFERENCES public.credit_memos(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty numeric(12,1) NOT NULL,
    invoice_item_id bigint NOT NULL REFERENCES public.invoice_items(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    price numeric(12,2) NOT NULL,
    date_returned date NOT NULL,
    tax numeric(12,2) NOT NULL
);

CREATE TABLE public.customer_tax_exemptions (
    id bigserial primary key,
    customer_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    tax_rate_id bigint NOT NULL REFERENCES public.tax_rates(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    pdf_data bytea,
    pdf_available boolean DEFAULT false NOT NULL
);

CREATE TABLE public.document_types (
    id serial primary key,
    name character varying DEFAULT '' NOT NULL,
    text1 character varying DEFAULT '' NOT NULL,
    text2 character varying DEFAULT '' NOT NULL,
    text3 character varying DEFAULT '' NOT NULL,
    text4 character varying DEFAULT '' NOT NULL,
    text5 character varying DEFAULT '' NOT NULL,
    text6 character varying DEFAULT '' NOT NULL,
    text7 character varying DEFAULT '' NOT NULL,
    text8 character varying DEFAULT '' NOT NULL,
    text9 character varying DEFAULT '' NOT NULL,
    text10 character varying DEFAULT '' NOT NULL,
    text11 character varying DEFAULT '' NOT NULL,
    text12 character varying DEFAULT '' NOT NULL
);

CREATE TABLE public.documents (
    id bigserial primary key,
    name character varying,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    invoiced boolean DEFAULT FALSE NOT NULL,
    canceled boolean DEFAULT FALSE NOT NULL,
    closed boolean DEFAULT FALSE NOT NULL,
    printed boolean DEFAULT FALSE NOT NULL,
    dated_for date NOT NULL,
    date_printed date,
    date_created date NOT NULL,
    subtotal numeric(12,2),
    tax numeric(12,2),
    total numeric(12,2),
    pdf_data bytea,
    document_type_id smallint REFERENCES public.document_types(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    pending_invoice boolean DEFAULT FALSE NOT NULL,
    invoice_id integer REFERENCES public.invoices(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    comments character varying
);

CREATE TABLE public.document_lines (
    id bigserial primary key,
    document_id bigint REFERENCES public.documents(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty numeric(12,2) DEFAULT 0 NOT NULL,
    product_id bigint REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    min numeric(12,2) DEFAULT 0 NOT NULL,
    max numeric(12,2) DEFAULT 0 NOT NULL,
    retailer_id integer REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    type_1 boolean DEFAULT FALSE NOT NULL,
    type_2 character varying DEFAULT '' NOT NULL,
    type_3 character varying DEFAULT '' NOT NULL,
    type_4 character varying DEFAULT '' NOT NULL,
    priority character varying DEFAULT '' NOT NULL,
    remark character varying DEFAULT '' NOT NULL,
    price numeric(12,4) DEFAULT 0 NOT NULL,
    tax numeric(12,2) DEFAULT 0 NOT NULL,
    ext_price numeric(12,2) DEFAULT 0 NOT NULL,
    canceled boolean DEFAULT False NOT NULL,
    tax_description character varying DEFAULT '' NOT NULL,
    finished numeric(12,2) DEFAULT 0 NOT NULL,
    qa_contact_id integer REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    s_price numeric(12,4) DEFAULT 0 NOT NULL
);

CREATE TABLE public.files (
    id bigserial primary key,
    file_data bytea NOT NULL,
    contact_id smallint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    name character varying NOT NULL,
    date_inserted date NOT NULL
);

CREATE TABLE public.fiscal_years (
    id serial primary key,
    name character varying NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    active boolean NOT NULL
);

CREATE TABLE public.incoming_invoices (
    id bigserial primary key,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    paid boolean DEFAULT FALSE NOT NULL,
    canceled boolean DEFAULT FALSE NOT NULL,
    date_paid date ,
    date_created date DEFAULT now() NOT NULL,
    description character varying,
    amount numeric(12,2),
    attached_pdf bytea
);

CREATE TABLE public.locations (
    id serial primary key,
    name character varying NOT NULL
);

CREATE TABLE public.purchase_orders (
    id bigserial primary key,
    name character varying DEFAULT '' NOT NULL,
    vendor_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    paid boolean DEFAULT False NOT NULL,
    canceled boolean DEFAULT False NOT NULL,
    closed boolean DEFAULT False NOT NULL,
    printed boolean DEFAULT False NOT NULL,
    date_paid date,
    date_printed date,
    date_created date DEFAULT now() NOT NULL,
    received boolean DEFAULT False NOT NULL,
    total numeric(12,2),
    pdf_data bytea,
    tax numeric(12,2),
    surcharge numeric(12,2),
    comments character varying,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    invoice_description character varying DEFAULT ''::character varying,
    invoiced boolean DEFAULT False NOT NULL,
    amount_due numeric(12,2),
    attached_pdf bytea
);

CREATE TABLE public.purchase_order_line_items (
    id bigserial primary key,
    purchase_order_id bigint NOT NULL REFERENCES public.purchase_orders(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty numeric(12,0) NOT NULL,
    remark character varying,
    price numeric(12,5),
    ext_price numeric(12,2),
    canceled boolean DEFAULT False NOT NULL,
    received smallint,
    product_id integer REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    expense_account smallint REFERENCES public.gl_accounts(number) ON UPDATE RESTRICT ON DELETE RESTRICT,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    order_number character varying,
    hold boolean DEFAULT false NOT NULL
);

CREATE TABLE public.job_types (
    id serial primary key,
    name character varying NOT NULL
);

CREATE TABLE public.job_sheets (
    id bigserial primary key,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    job_type_id integer REFERENCES public.job_types(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    description character varying NOT NULL,
    total numeric(12,2),
    date_inserted date DEFAULT now() NOT NULL,
    invoiced boolean DEFAULT False NOT NULL,
    completed boolean DEFAULT False NOT NULL,
    time_clock boolean DEFAULT False NOT NULL
);

CREATE TABLE public.job_sheet_line_items (
    id bigserial primary key,
    job_sheet_id integer REFERENCES public.job_sheets(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty numeric(12,2) NOT NULL,
    product_id bigint REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    remark character varying
);

CREATE TABLE public.time_clock_projects (
    id bigserial primary key,
    name character varying NOT NULL,
    total_time bigint,
    start_date date NOT NULL,
    stop_date date,
    active boolean DEFAULT True NOT NULL,
    permanent boolean DEFAULT False NOT NULL,
    job_sheet_id bigint REFERENCES public.job_sheets(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.time_clock_entries (
    id bigserial primary key,
    start_time timestamp with time zone,
    stop_time timestamp with time zone,
    employee_id integer NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    project_id integer NOT NULL REFERENCES public.time_clock_projects(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    invoiced boolean DEFAULT False,
    employee_paid boolean DEFAULT False,
    actual_seconds bigint,
    adjusted_seconds bigint,
    pay_stub_id integer REFERENCES payroll.pay_stubs(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    invoice_line_id bigint REFERENCES public.invoice_items(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    running boolean NOT NULL DEFAULT FALSE
);

CREATE TABLE public.manufacturing_projects (
    id bigserial primary key,
    name character varying NOT NULL,
    product_id integer NOT NULL REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    time_clock_projects_id integer REFERENCES public.time_clock_projects(id) ON DELETE RESTRICT,
    qty integer NOT NULL,
    active boolean NOT NULL DEFAULT True
);

CREATE TABLE public.inventory_transactions (
    id bigserial primary key,
    product_id integer REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_inserted date NOT NULL,
    location_id integer NOT NULL REFERENCES public.locations(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty_in integer DEFAULT 0 NOT NULL,
    qty_out integer DEFAULT 0 NOT NULL,
    invoice_line_id bigint REFERENCES public.invoice_items(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    purchase_order_line_id bigint REFERENCES public.purchase_order_line_items(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    manufacturing_id bigint REFERENCES public.manufacturing_projects(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    price numeric(12,6) NOT NULL,
    gl_entries_id bigint REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    reason character varying,
    CONSTRAINT check_transaction_not_null CHECK (((invoice_line_id IS NOT NULL) OR (purchase_order_line_id IS NOT NULL) OR (manufacturing_id IS NOT NULL) OR (reason IS NOT NULL)))
);

CREATE TABLE public.loans (
    id bigserial primary key,
    description character varying NOT NULL,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_received date NOT NULL,
    amount numeric(12,2) NOT NULL,
    period character varying NOT NULL,
    finished boolean DEFAULT false NOT NULL,
    gl_entries_id bigint NOT NULL REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    last_payment_date date NOT NULL
);

CREATE TABLE public.loan_payments (
    id bigserial primary key,
    loan_id bigint NOT NULL REFERENCES public.loans(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    gl_entries_principal_id bigint NOT NULL REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    gl_entries_interest_id bigint NOT NULL REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    gl_entries_total_id bigint NOT NULL REFERENCES public.gl_entries(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.mailing_lists (
    id serial primary key,
    name character varying NOT NULL,
    active boolean DEFAULT true NOT NULL,
    date_inserted date DEFAULT now() NOT NULL
);

CREATE TABLE public.mailing_list_register (
    id bigserial primary key,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    active boolean DEFAULT true NOT NULL,
    mailing_list_id bigint NOT NULL REFERENCES public.mailing_lists(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_inserted date DEFAULT now() NOT NULL
);

CREATE TABLE public.phone_blacklist (
    number character varying NOT NULL,
    date_called date,
    blocked_calls integer
);

CREATE TABLE public.product_assembly_items (
    id bigserial primary key,
    manufactured_product_id integer REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    qty smallint NOT NULL,
    assembly_product_id integer REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    remark character varying,
    alternative_to_id integer
);

CREATE TABLE public.product_location (
    id bigserial primary key,
    product_id integer NOT NULL REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    rack character varying NOT NULL,
    cart character varying NOT NULL,
    shelf character varying NOT NULL,
    cabinet character varying NOT NULL,
    drawer character varying NOT NULL,
    locator_visible boolean NOT NULL DEFAULT false,
    location_id integer NOT NULL REFERENCES public.locations(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    aisle character varying NOT NULL,
    bin character varying NOT NULL
);

CREATE TABLE public.products_markup_prices (
    id bigserial primary key,
    product_id bigint NOT NULL REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    markup_id bigint NOT NULL REFERENCES public.customer_markup_percent(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    price numeric(12,2) NOT NULL
);

CREATE TABLE public.resource_tags (
    id serial primary key,
    tag character varying NOT NULL,
    red double precision NOT NULL,
    green double precision NOT NULL,
    blue double precision NOT NULL,
    alpha double precision NOT NULL,
    finished boolean DEFAULT false NOT NULL,
    phone_default boolean DEFAULT false NOT NULL
);

CREATE TABLE public.resources (
    id bigserial primary key,
    parent_id integer REFERENCES public.resources(id) ON DELETE RESTRICT,
    subject character varying,
    contact_id integer REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_created date DEFAULT now() NOT NULL,
    dated_for date,
    notes character varying DEFAULT ''::character varying,
    tag_id integer REFERENCES public.resource_tags(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    diary boolean ,
    phone_number character varying,
    call_received_time timestamp with time zone,
    to_do boolean DEFAULT false,
    timed_seconds interval second
);

CREATE TABLE public.serial_numbers (
    id bigserial primary key,
    product_id bigint NOT NULL REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_inserted date DEFAULT now() NOT NULL,
    serial_number character varying NOT NULL,
    invoice_item_id bigint REFERENCES public.invoice_items(id) ON UPDATE RESTRICT ON DELETE SET NULL,
    purchase_order_line_item_id bigint REFERENCES public.purchase_order_line_items(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    manufacturing_id bigint REFERENCES public.manufacturing_projects(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.serial_number_history (
    id bigserial primary key,
    serial_number_id bigint NOT NULL REFERENCES public.serial_numbers(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    description character varying,
    date_inserted date DEFAULT now() NOT NULL,
    contact_id bigint NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    credit_memo_item_id bigint REFERENCES public.credit_memo_items(id) ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE public.settings (
    id serial primary key,
    print_direct boolean NOT NULL,
    enforce_exact_payment boolean NOT NULL,
    refresh_documents_price_on_import boolean NOT NULL,
    email_when_possible boolean NOT NULL,
    version character varying NOT NULL,
    accrual_based boolean DEFAULT false NOT NULL,
    statement_finish_date date NOT NULL,
    cost_decrease_alert numeric(5,2) NOT NULL,
    last_backup date NOT NULL,
    backup_frequency_days integer NOT NULL,
    statement_day_of_month integer NOT NULL,
    date_format character varying NOT NULL,
    timestamp_format character varying NOT NULL,
    request_po_attachment boolean NOT NULL,
    major_version smallint NOT NULL,
    minor_version smallint NOT NULL
);

CREATE TABLE public.vendor_product_numbers (
    id bigserial primary key,
    vendor_id integer NOT NULL REFERENCES public.contacts(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    vendor_sku character varying DEFAULT ''::character varying NOT NULL,
    product_id integer NOT NULL REFERENCES public.products(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    vendor_barcode character varying DEFAULT ''::character varying NOT NULL,
    qty smallint DEFAULT 0 NOT NULL,
    price numeric(12,2) DEFAULT 0 NOT NULL,
    deleted boolean DEFAULT false NOT NULL
);

CREATE TABLE settings.document_columns (
    id bigserial primary key,
    column_id character varying NOT NULL,
    column_name character varying NOT NULL,
    visible boolean NOT NULL
);

CREATE TABLE settings.invoice_columns (
    id serial primary key,
    column_id character varying NOT NULL,
    column_name character varying NOT NULL,
    visible boolean NOT NULL
);

CREATE TABLE settings.po_columns (
    id serial primary key,
    column_id character varying NOT NULL,
    column_name character varying NOT NULL,
    visible boolean NOT NULL
);

CREATE TABLE settings.purchase_order (
    id serial primary key,
    qty_prec integer NOT NULL,
    price_prec integer NOT NULL
);

CREATE TABLE sql.history (
    name character varying NOT NULL,
    command character varying NOT NULL,
    date_inserted date NOT NULL,
    current boolean
);


ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT gl_entries_id_unique UNIQUE (gl_entries_id);

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_gl_entries_id_unique UNIQUE (gl_entries_id);

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_gl_entries_tax_id_unique UNIQUE (gl_entries_tax_id);

ALTER TABLE ONLY public.phone_blacklist
    ADD CONSTRAINT phone_blacklist_pkey PRIMARY KEY (number);

ALTER TABLE ONLY public.product_location
    ADD CONSTRAINT product_location_product_id_location_id_key UNIQUE (product_id, location_id);

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_barcode_key UNIQUE (barcode);

ALTER TABLE ONLY public.resources
    ADD CONSTRAINT resources_dated_for_diary_key UNIQUE (dated_for, diary);

ALTER TABLE ONLY public.serial_numbers
    ADD CONSTRAINT serial_numbers_product_id_serial_number_key UNIQUE (product_id, serial_number);

ALTER TABLE ONLY public.vendor_product_numbers
    ADD CONSTRAINT vendor_product_numbers_vendor_id_product_id_key UNIQUE (vendor_id, product_id);

ALTER TABLE ONLY sql.history
    ADD CONSTRAINT current_column_unique UNIQUE (current);

ALTER TABLE ONLY sql.history
    ADD CONSTRAINT history_pkey PRIMARY KEY (name);
    

CREATE FUNCTION public.after_accounts_edited() RETURNS trigger
    LANGUAGE plpgsql
    AS ' DECLARE table_record gl_accounts%ROWTYPE; DECLARE parents integer; BEGIN FOR table_record IN (SELECT * FROM gl_accounts ) LOOP UPDATE gl_accounts SET is_parent = True WHERE number = table_record.parent_number; SELECT COUNT (id) FROM gl_accounts WHERE parent_number = table_record.number INTO parents; IF parents = 0 THEN UPDATE gl_accounts SET is_parent = False WHERE id = table_record.id; END  IF; END LOOP; RETURN OLD; END; ';


CREATE FUNCTION public.after_gl_entries_inserted() RETURNS trigger
    LANGUAGE plpgsql
    AS ' DECLARE new_date date;BEGIN IF NEW.date_inserted IS NULL THEN SELECT date_inserted FROM gl_transactions WHERE gl_transactions.id = NEW.gl_transaction_id INTO new_date; UPDATE gl_entries SET date_inserted = new_date WHERE id = NEW.id; END IF; RETURN NEW; END;';

CREATE FUNCTION public.before_accounts_edited() RETURNS trigger
    LANGUAGE plpgsql
    AS ' DECLARE counter integer; BEGIN SELECT COUNT (id) FROM public.gl_entries WHERE debit_account = NEW.parent_number INTO counter; IF counter > 0 THEN RAISE EXCEPTION ''Account % is not allowed as a parent -> already used in gl_entries'', NEW.parent_number; END IF; SELECT COUNT (id) FROM public.gl_entries WHERE credit_account = NEW.parent_number INTO counter; IF counter > 0 THEN RAISE EXCEPTION ''Account % is not allowed as a parent -> already used in gl_entries'', NEW.parent_number; END IF; SELECT COUNT (id) FROM gl_account_flow WHERE account = NEW.parent_number INTO counter; IF counter > 0 THEN RAISE EXCEPTION ''Account % is not allowed as a parent-> already used in gl_account_flow'', NEW.parent_number; END IF; RETURN NEW; END;';

CREATE FUNCTION public.calculate_invoice_item() RETURNS trigger
    LANGUAGE plpgsql
    AS ' 
  BEGIN 
    UPDATE invoice_items SET ext_price = (qty*price) WHERE id = NEW.id;
    UPDATE invoice_items SET tax = (((SELECT rate FROM tax_rates WHERE id = NEW.tax_rate_id) * ext_price) / 100) WHERE id = NEW.id;
  RETURN NEW; 
  END; 
';

CREATE FUNCTION public.check_tax_rate_id() RETURNS trigger
    LANGUAGE plpgsql
    AS ' 
  BEGIN 
    IF (SELECT tax_exemptible FROM products WHERE id = NEW.product_id) = FALSE OR NEW.tax_rate_id IS NULL THEN 
       NEW.tax_rate_id = (SELECT tax_rates.id FROM tax_rates JOIN products ON tax_rates.id = products.tax_rate_id WHERE products.id = NEW.product_id);
    END IF;
  RETURN NEW;
  END;
';

CREATE FUNCTION public.format_date(date_in date) RETURNS character varying
    LANGUAGE sql
    AS ' 
	SELECT to_char(date_in, (SELECT date_format FROM settings))
	';

CREATE FUNCTION public.format_timestamp(timestamp_in timestamp with time zone) RETURNS character varying
    LANGUAGE sql
    AS ' 
	SELECT to_char(timestamp_in, (SELECT timestamp_format FROM settings))
	';

CREATE FUNCTION public.payment_info(payments_incoming_id bigint) RETURNS character varying
    LANGUAGE plpgsql
    AS '
 DECLARE table_record payments_incoming%ROWTYPE; 
BEGIN SELECT * FROM payments_incoming WHERE id = payments_incoming_id INTO table_record; 
IF table_record.check_payment = True THEN 
RETURN ''Check ''::varchar || table_record.payment_text; 
						ELSEIF table_record.cash_payment = True THEN 
							RETURN ''Cash ''::varchar || table_record.payment_text; 
						ELSEIF table_record.credit_card_payment = True THEN 
							RETURN ''Credit card ''::varchar || table_record.payment_text; 
						ELSE RETURN ''''; 
						END IF;
						END; 
						';

CREATE FUNCTION public.process_invoice_barcode(_barcode character varying, _invoice_id bigint, OUT invoice_item_id bigint) RETURNS bigint
    LANGUAGE plpgsql
    AS ' 
DECLARE _product_id BIGINT; _tax_rate_id BIGINT; 
BEGIN 
SELECT id, tax_rate_id INTO _product_id, _tax_rate_id FROM products WHERE (barcode, deleted) = (_barcode, FALSE); 
IF FOUND THEN 
IF EXISTS (SELECT id FROM invoice_items WHERE (invoice_id, product_id)= (_invoice_id, _product_id)) THEN 
UPDATE invoice_items SET qty = qty + 1 
WHERE (invoice_id, product_id) = (_invoice_id, _product_id) RETURNING id INTO invoice_item_id; 
ELSE 
INSERT INTO invoice_items (invoice_id, product_id, tax_rate_id) 
VALUES (_invoice_id, _product_id, _tax_rate_id) RETURNING id INTO invoice_item_id; 
END IF; 
ELSE 
invoice_item_id = 0; 
END IF; 
RETURN; 
END 
';

CREATE FUNCTION public.update_time_entry_seconds() RETURNS trigger
    LANGUAGE plpgsql
    AS ' DECLARE seconds integer; BEGIN SELECT EXTRACT (''epoch'' FROM stop_time - start_time) INTO seconds FROM time_clock_entries WHERE id = OLD.id; UPDATE time_clock_entries SET (actual_seconds, adjusted_seconds) = (seconds, seconds) WHERE id = OLD.id; RETURN OLD; END; ';


CREATE RULE account_changed_rule AS
    ON UPDATE TO public.gl_accounts DO
 NOTIFY accounts, 'account_changed';

CREATE RULE account_inserted_rule AS
    ON INSERT TO public.gl_accounts DO
 NOTIFY accounts, 'account_inserted';

CREATE RULE contact_changed_rule AS
    ON UPDATE TO public.contacts DO
 NOTIFY contacts, 'contact_changed';

CREATE RULE contact_inserted_rule AS
    ON INSERT TO public.contacts DO
 NOTIFY contacts, 'contact_inserted';

CREATE RULE default_tax_rate_not_deleteable AS
    ON DELETE TO public.tax_rates
   WHERE (old.standard = true) DO INSTEAD NOTHING;

CREATE RULE on_list_delete_set_list_register_false AS
    ON UPDATE TO public.mailing_lists
   WHERE (new.active = false) DO INSTEAD UPDATE public.mailing_list_register SET active = false
  WHERE (mailing_list_register.mailing_list_id = old.id);

CREATE RULE product_changed_rule AS
    ON UPDATE TO public.products DO
 NOTIFY products, 'product_changed';

CREATE RULE product_inserted_rule AS
    ON INSERT TO public.products DO
 NOTIFY products, 'product_inserted';

CREATE RULE time_clock_entries_inserted_rule AS
    ON INSERT TO public.time_clock_entries DO
 NOTIFY time_clock_entries, 'time_clock_entry_inserted';

CREATE RULE time_clock_entries_updated_rule AS
    ON UPDATE TO public.time_clock_entries DO
 NOTIFY time_clock_entries, 'time_clock_entry_updated';

CREATE TRIGGER a_check_tax_rate_id BEFORE INSERT OR UPDATE OF tax_rate_id ON public.invoice_items FOR EACH ROW WHEN ((pg_trigger_depth() < 1)) EXECUTE PROCEDURE public.check_tax_rate_id();

CREATE TRIGGER after_accounts_edited AFTER INSERT OR UPDATE OF number, parent_number ON public.gl_accounts FOR EACH STATEMENT EXECUTE PROCEDURE public.after_accounts_edited();

CREATE TRIGGER after_gl_entries_inserted_trigger AFTER INSERT ON public.gl_entries FOR EACH ROW EXECUTE PROCEDURE public.after_gl_entries_inserted();

CREATE TRIGGER b_calculate_invoice_item AFTER INSERT OR UPDATE OF qty, product_id, price, tax_rate_id ON public.invoice_items FOR EACH ROW WHEN (((pg_trigger_depth() < 1) AND (new.tax_rate_id IS NOT NULL))) EXECUTE PROCEDURE public.calculate_invoice_item();

CREATE TRIGGER before_accounts_edited BEFORE INSERT OR UPDATE OF number, parent_number ON public.gl_accounts FOR EACH ROW EXECUTE PROCEDURE public.before_accounts_edited();

CREATE TRIGGER start_time_changed_trigger AFTER UPDATE OF start_time ON public.time_clock_entries FOR EACH ROW EXECUTE PROCEDURE public.update_time_entry_seconds();

CREATE TRIGGER stop_time_changed_trigger AFTER UPDATE OF stop_time ON public.time_clock_entries FOR EACH ROW EXECUTE PROCEDURE public.update_time_entry_seconds();





