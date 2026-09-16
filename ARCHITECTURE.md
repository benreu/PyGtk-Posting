# PyGtk-Posting Architecture Documentation

## System Architecture Overview

PyGtk-Posting follows a traditional desktop application architecture with a three-tier design:

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                          │
│                         (GTK3 UI)                               │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │ Main Window  │ Invoice UI   │ Reports UI   │  Admin UI    │ │
│  │ (Glade XML)  │ (Glade XML)  │ (Glade XML)  │ (Glade XML)  │ │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘ │
└─────────┼──────────────┼──────────────┼──────────────┼─────────┘
          │              │              │              │
          │              └──────┬───────┘              │
          │                     │                      │
┌─────────▼─────────────────────▼──────────────────────▼─────────┐
│                     BUSINESS LOGIC LAYER                        │
│                        (Python Modules)                         │
│  ┌───────────┬───────────┬────────────┬──────────┬──────────┐  │
│  │  Invoice  │  Reports  │ Inventory  │  Payroll │  Admin   │  │
│  │  Module   │  Module   │  Module    │  Module  │  Module  │  │
│  └─────┬─────┴─────┬─────┴──────┬─────┴─────┬────┴────┬─────┘  │
│        │           │            │           │         │        │
│        └─────────┬─┴────────────┴───────────┴─────────┘        │
│                  │                                              │
│        ┌─────────▼─────────┐                                   │
│        │  Transactor       │   (Accounting Transaction Logic)  │
│        │  (db/transactor)  │                                   │
│        └─────────┬─────────┘                                   │
└──────────────────┼──────────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────────┐
│                     DATA ACCESS LAYER                           │
│                    (Database Drivers)                           │
│  ┌──────────────────────────┬──────────────────────────┐       │
│  │     psycopg2            │         APSW             │       │
│  │  (PostgreSQL Driver)    │    (SQLite Driver)       │       │
│  └───────────┬──────────────┴────────────┬─────────────┘       │
└──────────────┼───────────────────────────┼─────────────────────┘
               │                           │
┌──────────────▼──────────────┐  ┌─────────▼────────────────────┐
│      PostgreSQL Database    │  │    SQLite Database           │
│     (Business Data)         │  │   (User Preferences)         │
│  ┌───────────────────────┐  │  │  ┌────────────────────────┐ │
│  │ - gl_accounts         │  │  │  │ - postgres_conn        │ │
│  │ - gl_transactions     │  │  │  │ - settings             │ │
│  │ - gl_entries          │  │  │  │ - keybindings          │ │
│  │ - contacts            │  │  │  │ - window_positions     │ │
│  │ - products            │  │  │  │ - db_connections       │ │
│  │ - invoices            │  │  │  └────────────────────────┘ │
│  │ - purchase_orders     │  │  └────────────────────────────┘ │
│  │ - payments_incoming   │  │                                 │
│  │ - payments_outgoing   │  │                                 │
│  │ - payroll.*           │  │                                 │
│  └───────────────────────┘  │                                 │
└─────────────────────────────┘                                 │
```

## Component Interactions

### 1. Application Startup Sequence

```
┌──────────┐
│  User    │
└────┬─────┘
     │ Launches application
     ▼
┌────────────────┐
│ pygtk-posting  │  (Shell wrapper script)
└───────┬────────┘
        │
        ▼
┌─────────────────┐
│   main.py       │
└───────┬─────────┘
        │
        ├──▶ Load SQLite preferences (sqlite_utils.py)
        │   └─▶ Create tables if needed
        │       ├─ postgres_conn
        │       ├─ settings
        │       ├─ keybindings
        │       └─ window_positions
        │
        ├──▶ Connect to PostgreSQL (DB connection)
        │   └─▶ Authenticate with stored credentials
        │
        ├──▶ Initialize constants.py
        │   ├─ Set global DB reference
        │   ├─ Load ACCOUNTS module
        │   └─ Start Broadcast system
        │       └─▶ LISTEN on PostgreSQL channels:
        │           ├─ products
        │           ├─ contacts
        │           ├─ accounts
        │           ├─ time_clock_entries
        │           ├─ invoices
        │           └─ purchase_orders
        │
        └──▶ Launch main_window.MainGUI()
            ├─▶ Load main_window.ui (Glade XML)
            ├─▶ Setup menu structure
            ├─▶ Load keybindings from SQLite
            ├─▶ Connect GTK signal handlers
            └─▶ Start GTK main loop
```

### 2. Invoice Creation Workflow

```
┌──────────┐
│   User   │ Clicks "New Invoice"
└────┬─────┘
     │
     ▼
┌──────────────────────┐
│ main_window.py       │ Opens invoice_window
└───────┬──────────────┘
        │
        ▼
┌──────────────────────┐
│ invoice_window.py    │
│ ┌──────────────────┐ │
│ │ Load .ui file    │ │
│ │ Connect signals  │ │
│ └──────────────────┘ │
└───────┬──────────────┘
        │
        │ 1. User selects customer
        ├──▶ Query contacts table
        ├──▶ Load tax exemptions
        ├──▶ Load payment terms
        └──▶ Load customer markup
        │
        │ 2. User adds products
        ├──▶ Query products table
        ├──▶ Calculate prices (with markup)
        ├──▶ Calculate taxes
        └──▶ Update totals
        │
        │ 3. User clicks "Post Invoice"
        ▼
┌──────────────────────────────────────────┐
│ invoice_create.py                        │
│ ┌──────────────────────────────────────┐ │
│ │ Validation                           │ │
│ │ - Check customer selected            │ │
│ │ - Check products added               │ │
│ │ - Verify calculations                │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ BEGIN TRANSACTION                        │
│ ┌──────────────────────────────────────┐ │
│ │ 1. INSERT INTO invoices              │ │
│ │    - customer_id                     │ │
│ │    - date_created                    │ │
│ │    - total_amount                    │ │
│ │    RETURNING invoice_id              │ │
│ │                                      │ │
│ │ 2. INSERT INTO invoice_items         │ │
│ │    - invoice_id (FK)                 │ │
│ │    - product_id (FK)                 │ │
│ │    - quantity, price, tax            │ │
│ │    (repeat for each line item)       │ │
│ │                                      │ │
│ │ 3. Call transactor for GL entries    │ │
│ └──────────────────────────────────────┘ │
└───────┬──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ db/transactor.py                         │
│ ┌──────────────────────────────────────┐ │
│ │ CustomerInvoice class                │ │
│ │                                      │ │
│ │ 1. INSERT gl_transactions            │ │
│ │    - date_inserted                   │ │
│ │    RETURNING transaction_id          │ │
│ │                                      │ │
│ │ 2. INSERT gl_entries (Debit)         │ │
│ │    - debit_account: Accounts Receivable│
│ │    - amount: total                   │ │
│ │    - gl_transaction_id               │ │
│ │                                      │ │
│ │ 3. INSERT gl_entries (Credit)        │ │
│ │    - credit_account: Revenue         │ │
│ │    - amount: total                   │ │
│ │    - gl_transaction_id               │ │
│ └──────────────────────────────────────┘ │
│ COMMIT TRANSACTION                       │
└───────┬──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ PostgreSQL                               │
│ NOTIFY invoices, 'invoice_id'            │
└───────┬──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ constants.Broadcast (All clients)        │
│ ┌──────────────────────────────────────┐ │
│ │ poll_connection()                    │ │
│ │ ├─ Receive NOTIFY from DB            │ │
│ │ └─ emit('invoices_changed', id)      │ │
│ └──────────────────────────────────────┘ │
└───────┬──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ Connected UI Modules                     │
│ - invoice_history.py (refresh list)      │
│ - unpaid_invoices.py (update totals)     │
│ - contact_history.py (update customer)   │
└──────────────────────────────────────────┘
```

### 3. Real-Time Broadcast System

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL LISTEN/NOTIFY                │
│                                                             │
│  ┌──────────────┐    NOTIFY    ┌──────────────────────┐   │
│  │  Client A    │────product──▶│   PostgreSQL         │   │
│  │ (Modifies    │              │   Notification       │   │
│  │  product)    │              │   Queue              │   │
│  └──────────────┘              └───┬──────────────────┘   │
│                                    │                       │
│                 ┌──────────────────┼──────────────────┐    │
│                 │                  │                  │    │
│          NOTIFY │           NOTIFY │           NOTIFY │    │
│          product│           product│           product│    │
│                 ▼                  ▼                  ▼    │
│        ┌──────────────┐   ┌──────────────┐  ┌──────────────┐
│        │  Client B    │   │  Client C    │  │  Client D    │
│        │ (Receives)   │   │ (Receives)   │  │ (Receives)   │
│        └──────────────┘   └──────────────┘  └──────────────┘
└─────────────────────────────────────────────────────────────┘

Implementation Flow:

1. Client A modifies a product:
   ├─▶ UPDATE products SET ... WHERE id = 123
   └─▶ NOTIFY products, '123'

2. PostgreSQL broadcasts to all listeners

3. Each client's Broadcast.poll_connection() (runs every 1 second):
   ├─▶ DB.poll()  # Check for notifications
   ├─▶ while DB.notifies:
   │   ├─ notify = DB.notifies.pop(0)
   │   ├─ if notify.channel == "products":
   │   └─▶ emit('products_changed')
   └─▶ GTK signals propagate to connected handlers

4. UI modules respond:
   └─▶ on_products_changed(self):
       └─▶ Refresh product list/data
```

### 4. Database Transaction Pattern

All accounting transactions follow this pattern:

```python
# Example: Customer Payment
class CustomerInvoicePayment:
    def __init__(self, date, total):
        # 1. Create transaction header
        c = DB.cursor()
        c.execute("INSERT INTO gl_transactions (date_inserted) VALUES (%s) RETURNING id", (date,))
        self.transaction_id = c.fetchone()[0]
        c.close()
        
    def bank_check(self, payment_id):
        # 2. Record double-entry
        # Debit: Check Clearing Account
        # Credit: Accounts Receivable
        c = DB.cursor()
        c.execute("""
            INSERT INTO gl_entries 
            (debit_account, credit_account, amount, gl_transaction_id)
            VALUES (
                (SELECT account FROM gl_account_flow WHERE function = 'check_payment'),
                (SELECT account FROM gl_account_flow WHERE function = 'post_invoice'),
                %s, %s
            ) RETURNING id
        """, (self.total, self.transaction_id))
        entry_id = c.fetchone()[0]
        c.close()
        return entry_id
```

**Key Principle:** Every financial transaction creates:
1. One `gl_transactions` record (header)
2. Multiple `gl_entries` records (debits and credits that balance)
3. Related business records (invoice, payment, etc.)

## Module Organization

### Core Modules

```
src/
├── main.py                 # Application entry point
├── main_window.py          # Primary GUI container
├── constants.py            # Global state (DB, broadcaster, flags)
├── sqlite_utils.py         # Local preferences (SQLite)
├── dateutils.py            # Date utilities
├── printing.py             # Print formatting
└── traceback_handler.py    # Error logging
```

### Business Domain Modules

#### Invoice Management
```
invoice/
├── invoice_create.py       # Invoice posting logic
├── invoice_template.py     # Template handling
└── ... (8 more modules)
```

#### Reports
```
reports/
├── aging_payables.py       # AP aging report
├── aging_receivables.py    # AR aging report
├── balance_sheet.py        # Balance sheet
├── profit_and_loss.py      # P&L statement
├── contact_history.py      # Customer/vendor history
└── ... (15+ more reports)
```

#### Administration
```
admin/
├── contact_import.py       # Bulk contact import
├── product_import.py       # Bulk product import
├── data_export.py          # Data export
├── duplicate_contact.py    # Deduplication
└── ... (4 more modules)
```

#### Database
```
db/
├── transactor.py           # Transaction factory classes
├── database_tools.py       # Admin tools
├── database_backup.py      # Backup utility
├── database_restore.py     # Restore utility
├── version.py              # Schema versioning
└── sql_window.py           # SQL query tool
```

## Data Flow Patterns

### 1. Read Pattern (Display Data)
```
User Action
    ↓
UI Module (e.g., invoice_window.py)
    ↓
SQL Query (SELECT)
    ↓
PostgreSQL
    ↓
psycopg2 cursor.fetchall()
    ↓
Populate GTK TreeView/ListStore
    ↓
Display to User
```

### 2. Write Pattern (Modify Data)
```
User Action
    ↓
UI Module validation
    ↓
Business Logic Module
    ↓
BEGIN TRANSACTION
    ├─ INSERT/UPDATE business tables
    ├─ Call transactor for GL entries
    └─ COMMIT
    ↓
NOTIFY appropriate channel
    ↓
Broadcast to all clients
    ↓
Connected UI modules refresh
```

### 3. Report Generation Pattern
```
User selects report
    ↓
Report Module (e.g., profit_and_loss.py)
    ↓
Query aggregated data (GROUP BY, SUM, etc.)
    ↓
Py3o Template Engine
    ↓
Load .odt template (templates/profit_loss.odt)
    ↓
Fill template with data
    ↓
LibreOffice UNO Bridge
    ↓
Convert to PDF/XLS
    ↓
Display/Print result
```

## Security Architecture

### Authentication & Authorization

```
┌──────────────────────────────────────────────────────────────┐
│                    Application Security                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Database Authentication (PostgreSQL)                     │
│     ├─ User credentials stored in SQLite                     │
│     ├─ Connection established at startup                     │
│     └─ All queries use authenticated connection              │
│                                                              │
│  2. Admin Mode Toggle (constants.is_admin)                   │
│     ├─ Separate login for admin functions                    │
│     ├─ Controlled via admin_utils.py                         │
│     └─ Restricts access to:                                  │
│        ├─ Data import/export                                 │
│        ├─ Database tools                                     │
│        ├─ GL entry editing                                   │
│        └─ User management                                    │
│                                                              │
│  3. Database-Level Security                                  │
│     ├─ PostgreSQL GRANT/REVOKE                               │
│     ├─ Row-level security (potential)                        │
│     └─ Audit logging (log schema)                            │
│                                                              │
│  4. File System Security                                     │
│     ├─ SQLite file permissions (user read/write)             │
│     ├─ Log files (restricted access)                         │
│     └─ Backup files (encrypted recommended)                  │
└──────────────────────────────────────────────────────────────┘
```

### Data Protection

- **Passwords:** Stored in SQLite (plain text - consider encryption)
- **Sensitive Data:** Protected by PostgreSQL access controls
- **Backups:** Database backup/restore utilities included
- **Audit Trail:** Log schema for tracking changes

## Performance Considerations

### Database Connection
- **Single Connection:** One PostgreSQL connection per application instance
- **No Connection Pool:** Not needed for desktop application
- **Auto-reconnect:** On connection loss (handled by psycopg2)

### Caching
- **Accounts List:** Cached in `constants.ACCOUNTS` module
- **UI State:** Cached in SQLite (window positions, filter states)
- **No Data Caching:** All data queried fresh from database

### Real-Time Updates
- **Poll Interval:** 1 second (Broadcast.poll_connection)
- **Selective Updates:** Only affected UI modules refresh
- **Efficient Queries:** Use of indexes on foreign keys

## Deployment Architecture

### Single-User Desktop

```
┌─────────────────────────────────────┐
│         User's Computer             │
│  ┌───────────────────────────────┐  │
│  │   PyGtk-Posting Application   │  │
│  │         (Python/GTK)          │  │
│  └──────────┬───────────┬────────┘  │
│             │           │            │
│      ┌──────▼────┐ ┌────▼──────┐    │
│      │PostgreSQL │ │  SQLite   │    │
│      │ (System)  │ │ (~/.local)│    │
│      └───────────┘ └───────────┘    │
└─────────────────────────────────────┘
```

### Multi-User Network

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   Workstation 1  │   │   Workstation 2  │   │   Workstation 3  │
│  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────┐  │
│  │ PyGtk App  │  │   │  │ PyGtk App  │  │   │  │ PyGtk App  │  │
│  └─────┬──────┘  │   │  └─────┬──────┘  │   │  └─────┬──────┘  │
│  ┌─────▼──────┐  │   │  ┌─────▼──────┐  │   │  ┌─────▼──────┐  │
│  │   SQLite   │  │   │  │   SQLite   │  │   │  │   SQLite   │  │
│  │(Local Prefs)│ │   │  │(Local Prefs)│ │   │  │(Local Prefs)│ │
│  └────────────┘  │   │  └────────────┘  │   │  └────────────┘  │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         │        Network (TCP/IP - Port 5432)         │
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Database Server     │
                    │  ┌─────────────────┐  │
                    │  │   PostgreSQL    │  │
                    │  │  (Shared Data)  │  │
                    │  └─────────────────┘  │
                    └───────────────────────┘
```

**Benefits:**
- Real-time synchronization via LISTEN/NOTIFY
- Concurrent access with ACID guarantees
- Centralized data storage and backups
- Multi-user collaboration

## Technology Stack Details

### Python Dependencies

**Core Libraries:**
- `psycopg2` - PostgreSQL adapter (v2.9+)
- `apsw` - SQLite wrapper (v3.x)
- `gi` - PyGObject/GTK3 bindings

**UI/Graphics:**
- `cairocffi` - Cairo graphics
- `matplotlib` - Charts and graphs

**Document Processing:**
- `genshi` - Template engine
- `lxml` - XML/HTML processing
- `py3o` - LibreOffice document generation

**Data Import/Export:**
- `xlrd` - Excel reading
- `xlsxwriter` - Excel writing

**System Integration:**
- `python3-uno` - LibreOffice UNO bridge
- `python3-sane` - Scanner support

### System Dependencies

**Required:**
- Python 3.6+
- PostgreSQL 10+
- GTK+ 3.x
- LibreOffice (for document generation)

**Optional:**
- Scanner (for document scanning)
- Barcode font (code128.ttf included)

## Scalability Considerations

### Current Limitations
- **Desktop Only:** Not web-accessible
- **Linux Only:** GTK3 dependency
- **Single Connection:** One connection per client
- **No Caching:** All queries hit database

### Potential Improvements
- **Web Interface:** Add REST API + web frontend
- **Connection Pooling:** For high-concurrency scenarios
- **Query Caching:** Redis for frequently accessed data
- **Background Jobs:** For long-running reports
- **Horizontal Scaling:** PostgreSQL replication

## Extension Points

### 1. Custom Reports
Add new reports by:
- Creating new module in `reports/`
- Adding menu item in `main_window.py`
- Creating .odt template in `templates/`

### 2. New Transaction Types
Extend accounting by:
- Adding new class in `db/transactor.py`
- Defining GL account routing in `gl_account_flow`
- Creating UI module for data entry

### 3. Additional Modules
Add features by:
- Creating new .py + .ui files
- Registering in `main_window.populate_modules()`
- Following existing module patterns

### 4. Custom Fields
Extend data model:
- Add columns to PostgreSQL tables
- Update UI definitions (.ui files)
- Add to queries in module code

## Conclusion

PyGtk-Posting uses a straightforward, maintainable architecture suitable for desktop accounting applications. The three-tier design provides clear separation between UI, business logic, and data access. The real-time broadcast system enables multi-user collaboration, while the transaction factory pattern ensures accounting integrity.

**Strengths:**
- Clear architectural layers
- Strong accounting domain modeling
- Real-time multi-user support
- Extensible design

**Future Enhancements:**
- Web API layer
- Improved caching strategy
- More comprehensive error handling
- Automated testing framework
