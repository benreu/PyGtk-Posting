# PyGtk-Posting Codebase Analysis

**Analysis Date:** January 22, 2026  
**Version:** 0.5.34  
**Total Python Files:** 181  
**Total Lines of Code:** ~43,896 lines  
**UI Definition Files:** 141 (.ui Glade files)

---

## Executive Summary

PyGtk-Posting is a **comprehensive, feature-rich desktop accounting and business management system** for Linux, written in Python3 with GTK3 and PostgreSQL. It aims to be an open-source replacement for proprietary solutions like QuickBooks and Peachtree. The application is actively maintained and used in production by multiple businesses, though currently in alpha stage pending broader user adoption.

**Key Strengths:**
- Comprehensive feature set covering all aspects of business accounting
- Active development and real-world usage
- Strong domain modeling with proper double-entry accounting
- Real-time multi-user support via PostgreSQL LISTEN/NOTIFY
- Extensible reporting system using LibreOffice templates

**Key Areas for Improvement:**
- Limited automated testing infrastructure
- Potential SQL injection vulnerabilities in some modules
- Large monolithic files (1300+ lines in some modules)
- No comprehensive documentation for developers
- Limited error handling in some areas

---

## 1. Project Overview

### Purpose
An open-source accounting and business management system for Linux that handles:
- Invoicing and billing
- Purchase order management
- Inventory tracking and manufacturing
- Payroll processing
- Financial reporting and budgeting
- Customer relationship management
- Time tracking and resource scheduling

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.x |
| **GUI Framework** | GTK+ | 3.0 |
| **Primary Database** | PostgreSQL | 10+ |
| **Local Storage** | SQLite | via APSW |
| **Document Generation** | LibreOffice/py3o | - |
| **Charting** | matplotlib | - |
| **PDF Processing** | cairocffi | - |
| **Excel I/O** | xlrd, xlsxwriter | - |
| **Build System** | GNU Autotools | - |

---

## 2. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GTK3 Desktop UI                      │
│              (main_window.py + 140+ .ui)                │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              Business Logic Layer (Python)               │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐│
│  │ Invoice  │ Reports  │Inventory │  Admin   │ Payroll││
│  │  (10+)   │  (20+)   │   (8)    │   (8)    │   (7)  ││
│  └──────────┴──────────┴──────────┴──────────┴────────┘│
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌────────▼─────────┐
│  PostgreSQL    │         │     SQLite       │
│  (Business DB) │         │  (User Prefs)    │
│  - Accounts    │         │  - Settings      │
│  - Invoices    │         │  - Keybindings   │
│  - Contacts    │         │  - Connections   │
│  - Products    │         │  - UI State      │
│  - Payroll     │         └──────────────────┘
└────────────────┘
```

### Module Organization

The codebase is organized by business domain, with 181 Python files in the `src/` directory:

```
src/
├── main.py                    # Application entry point
├── main_window.py             # Primary GUI container (728 lines)
├── constants.py               # Global state and broadcast system
├── sqlite_utils.py            # Local preferences management
├── admin/                     # Data import/export, maintenance (8 modules)
├── db/                        # Database utilities (6 modules)
├── invoice/                   # Invoice creation and management (10 modules)
├── inventory/                 # Stock tracking (8 modules)
├── manufacturing/             # Production and assembly (12 modules)
├── payroll/                   # Employee and payroll (7 modules)
├── reports/                   # Financial and business reports (20+ modules)
├── resources/                 # Resource scheduling (7 modules)
└── [120+ feature modules]     # Individual business functions
```

**Largest Modules:**
1. `purchase_order_window.py` - 1,325 lines
2. `invoice_window.py` - 1,174 lines
3. `py3o/template/main.py` - 1,062 lines
4. `documents_window.py` - 827 lines
5. `db/transactor.py` - 763 lines

---

## 3. Database Architecture

### PostgreSQL Schema

The application uses a comprehensive PostgreSQL database with multiple schemas:

#### Core Tables (public schema)
- **Accounting:**
  - `gl_accounts` - Chart of accounts (assets, liabilities, equity, revenue, expenses)
  - `gl_transactions` - Transaction headers
  - `gl_entries` - Double-entry journal entries
  - `gl_account_flow` - Account routing rules for automated entries
  - `fiscal_years` - Accounting periods

- **Business Entities:**
  - `contacts` - Customers and vendors
  - `terms_and_discounts` - Payment terms
  - `customer_markup_percent` - Pricing overrides
  - `tax_rates` - Sales tax configuration
  - `locations` - Business locations

- **Products & Inventory:**
  - `products` - Product catalog
  - `product_location` - Inventory by location
  - `serial_numbers` - Serialized inventory tracking
  - `products_markup_prices` - Customer-specific pricing

- **Transactions:**
  - `invoices` / `invoice_items` - Customer invoices
  - `purchase_orders` / `purchase_order_items` - Vendor orders
  - `payments_incoming` / `payments_outgoing` - Payment records
  - `credit_memos` - Credit transactions

#### Payroll Schema
- `payroll.employee_info` - Employee master data
- `payroll.pay_stubs` - Payroll records
- `payroll.tax_table` - Tax rate configuration
- `payroll.emp_payments` - Payment tracking
- `payroll.time_clock_entries` - Time tracking

#### Manufacturing Schema
- `manufactured_products` - Assemblies and kits
- `assembly_components` - Bill of materials
- `serial_numbers` - Product serial numbers

### Real-Time Synchronization

The application uses PostgreSQL's **LISTEN/NOTIFY** mechanism for real-time updates across multiple users:

**Broadcast Channels:**
- `products` - Product catalog changes
- `contacts` - Customer/vendor updates
- `accounts` - Chart of accounts modifications
- `time_clock_entries` - Time clock events
- `invoices` - Invoice changes (with invoice_id payload)
- `purchase_orders` - PO changes (with po_id payload)

Implementation in `constants.py`:
```python
class Broadcast(GObject.GObject):
    def poll_connection(self):
        DB.poll()
        while DB.notifies:
            notify = DB.notifies.pop(0)
            if notify.channel == "products":
                self.emit('products_changed')
            # ... handle other channels
```

### SQLite Schema

Local user preferences stored in SQLite:

- **Connection Management:**
  - `postgres_conn` - Default database connection
  - `db_connections` - Multiple connection profiles

- **User Preferences:**
  - `settings` - Application configuration
  - `keybindings` - Keyboard shortcuts
  - Window sizes and positions
  - Filter states for invoices/POs
  - Print settings

---

## 4. Key Design Patterns

### 1. GTK Builder Pattern
Every UI module follows this pattern:
```python
class ModuleName(Gtk.Builder):
    def __init__(self):
        Gtk.Builder.__init__(self)
        self.add_from_file("module_name.ui")
        self.connect_signals(self)
        self.window = self.get_object("window")
```

### 2. Transaction Factory Pattern
The `db/transactor.py` module implements factory classes for accounting transactions:

```python
class Deposit:
    def __init__(self, date):
        # Create transaction header
        c = DB.cursor()
        c.execute("INSERT INTO gl_transactions (date_inserted) VALUES (%s) RETURNING id", (date,))
        self.transaction_id = c.fetchone()[0]
    
    def cash(self, amount, account):
        # Record cash component
        
    def bank(self, amount, account):
        # Record bank component
        return deposit_id
```

**Transaction Types:**
- `Deposit` - Bank deposits
- `CustomerInvoicePayment` - Customer payments
- `VendorPayment` - Vendor payments
- `LoanPayment` - Loan payments
- `Paycheck` - Employee payroll

### 3. Observer Pattern (Broadcaster)
The `constants.Broadcast` class implements a GTK-signal-based observer:
```python
# Publisher
DB.execute("NOTIFY products")

# Subscriber
constants.broadcaster.connect('products_changed', self.on_products_changed)
```

### 4. Singleton Pattern
Used for shared resources (e.g., `pyjon/utils/main.py` metaclass singleton)

---

## 5. Entry Points and Workflows

### Application Startup

1. **Shell Script:** `pygtk-posting` (wrapper script)
2. **Python Entry:** `src/main.py`
   - Load SQLite preferences
   - Connect to PostgreSQL
   - Initialize constants (DB, broadcaster, ACCOUNTS)
   - Launch main_window.MainGUI()
3. **Main Window:** `src/main_window.py`
   - Load main_window.ui (Glade XML)
   - Populate menu shortcuts
   - Initialize keybindings
   - Start GTK main loop

### Key User Workflows

**Invoice Creation Flow:**
```
User clicks "New Invoice"
    ↓
invoice_window.py loads
    ↓
User selects customer → loads contact details, tax info, payment terms
    ↓
User adds products → updates line items, recalculates totals
    ↓
User posts invoice → 
    - Inserts into invoices table
    - Creates gl_transaction + gl_entries (debit AR, credit Revenue)
    - NOTIFY invoices channel
    ↓
All connected clients receive update via broadcaster
```

**Payment Processing Flow:**
```
User enters payment
    ↓
customer_payment.py or vendor_payment.py
    ↓
Creates transactor instance (CustomerInvoicePayment or VendorPayment)
    ↓
Records:
    - Payment record (payments_incoming/outgoing)
    - GL transaction (debit Cash, credit AR/AP)
    - Updates invoice/PO paid status
    ↓
Generates payment receipt (optional)
```

---

## 6. Code Quality Analysis

### Positive Aspects

1. **Consistent Structure:** Every module follows the GTK Builder pattern
2. **Proper Licensing:** GPLv3/LGPLv3 headers on all files
3. **Separation of Concerns:** Clear division between UI (.ui) and logic (.py)
4. **Active Development:** Recent commits show ongoing maintenance
5. **Real Production Use:** Code is battle-tested in actual businesses

### Areas for Improvement

#### 1. **Limited Test Coverage**
- Only 2 test files: `py3o/template/tests/test_*.py`
- No unit tests for core business logic
- No integration tests for accounting transactions
- No UI/acceptance tests

**Impact:** High risk of regressions when making changes

**Recommendation:** 
- Add pytest framework
- Create unit tests for `db/transactor.py` classes
- Add integration tests for invoice/PO workflows
- Consider property-based testing for accounting rules

#### 2. **Potential SQL Injection Risks**
Found instances of string formatting in SQL queries:

Files with potential issues:
- `src/kit_products.py`
- `src/db/transactor.py`
- `src/purchase_ordering.py`
- `src/payroll/pay_stub.py`

**Example pattern to review:**
```python
cursor.execute("SELECT * FROM table WHERE id = %s" % user_input)  # UNSAFE
# Should be:
cursor.execute("SELECT * FROM table WHERE id = %s", (user_input,))  # SAFE
```

**Recommendation:** Audit all SQL queries and use parameterized queries consistently

#### 3. **Large Monolithic Files**
Several files exceed 1000 lines:
- `purchase_order_window.py` - 1,325 lines
- `invoice_window.py` - 1,174 lines

**Recommendation:** 
- Refactor into smaller, focused classes
- Extract common logic into shared utilities
- Consider separate classes for UI, business logic, and data access

#### 4. **Minimal Error Handling**
Only 5 exception handlers found across 181 files

**Recommendation:**
- Add try-except blocks around database operations
- Implement graceful error messages for users
- Add logging for debugging (already has `traceback_handler.py`)

#### 5. **No Type Hints**
Python 3 code lacks type annotations

**Recommendation:**
- Add type hints for function signatures
- Use mypy for static type checking
- Start with core modules (transactor, constants)

#### 6. **Password Storage**
Passwords stored in SQLite database (`postgres_conn.password`)

**Current:** Plain text storage in local SQLite
**Risk:** Low (file system permissions protect)
**Best Practice:** Use keyring/secrets manager

#### 7. **No Formal Documentation**
- README is minimal
- No developer guide
- No API documentation
- No architecture diagrams

**Recommendation:**
- Add docstrings to all classes and functions
- Create CONTRIBUTING.md
- Generate Sphinx/MkDocs documentation
- Document database schema

---

## 7. Security Considerations

### Current Security Measures
1. **Authentication:** PostgreSQL database-level authentication
2. **Admin Mode:** Separate admin login for sensitive operations
3. **File Permissions:** Relies on OS file system security for SQLite
4. **Input Validation:** GTK widgets provide some input constraints

### Security Risks

#### High Priority
1. **SQL Injection:** Potential vulnerabilities in dynamic SQL construction
2. **Credentials Storage:** Database passwords in plain SQLite file

#### Medium Priority
3. **Session Management:** No timeout/auto-logout for admin mode
4. **Audit Logging:** Limited audit trail for sensitive operations
5. **Data Export:** No encryption for exported financial data

#### Low Priority
6. **Dependency Vulnerabilities:** Should audit third-party library versions
7. **Input Sanitization:** Some user inputs may not be properly validated

### Recommendations
1. **Immediate:** Audit and fix SQL injection vulnerabilities
2. **Short-term:** Implement credential encryption (keyring)
3. **Medium-term:** Add comprehensive audit logging
4. **Long-term:** Security code review and penetration testing

---

## 8. Testing Infrastructure

### Current State
**Test Files:** 2 (both in `py3o/template/tests/`)
- `test_helpers.py` - 957 lines
- `test_templates.py` - Tests for template rendering

**Framework:** Python `unittest`

**Coverage:** Only py3o template engine is tested

### Recommended Test Strategy

#### 1. Unit Tests
**Priority modules to test:**
- `db/transactor.py` - Accounting transaction logic
- `dateutils.py` - Date calculations
- `printing.py` - Print formatting
- All calculation functions in invoice/PO modules

**Framework:** pytest (more Pythonic than unittest)

#### 2. Integration Tests
**Key workflows:**
- Create invoice → Post → Payment → GL entries verification
- Create PO → Receive → Payment → GL entries verification
- Payroll calculation → GL entries verification
- Inventory adjustment → GL entries verification

**Approach:** Use test database with rollback after each test

#### 3. Database Tests
**Verify:**
- Double-entry accounting (debits = credits)
- Referential integrity
- Trigger behavior
- LISTEN/NOTIFY functionality

#### 4. UI Tests (Optional)
**Framework:** pytest + GTK test utilities
**Coverage:** Critical paths (invoice creation, payment entry)

---

## 9. Build and Deployment

### Build System
**Autotools (GNU Build System):**
- `configure.ac` - Autoconf configuration
- `Makefile.am` - Automake template
- `install-sh` - Installation script

**Process:**
```bash
./configure
make
make install
```

### Package Distribution

#### 1. Debian Package
**Tools:** `create_deb.py` custom script
**Output:** `pygtk_posting_0.5.34-1.deb`
**Scripts:**
- `postinst` - Post-installation setup
- `prerm` - Pre-removal cleanup
- `control` - Package metadata

#### 2. Python Package
**Tools:** `setup.py` (setuptools)
**Command:** `python setup.py install`

#### 3. Source Distribution
**Output:** `pygtk_posting-0.5.34.tar.gz`

### Dependencies

**Runtime Dependencies (from requirements.txt):**
```
python3-apsw           # SQLite with advanced features
python3-cairocffi      # Cairo graphics bindings
python3-genshi         # Template engine
python3-lxml           # XML processing
python3-matplotlib     # Charting
python3-psycopg2       # PostgreSQL driver
python3-sane           # Scanner support
python3-tk             # Tkinter (calendar widget)
python3-uno            # LibreOffice UNO bridge
unoconv                # Document conversion
python3-xlrd           # Excel reading
python3-xlsxwriter     # Excel writing
gir1.2-goocanvas-2.0   # Canvas widget
```

**Development Dependencies:**
- Python 3.6+
- PostgreSQL 10+
- LibreOffice (for document generation)

---

## 10. Development Patterns and Best Practices

### Current Patterns

#### 1. File Structure
Every feature module typically includes:
- `module_name.py` - Python logic
- `module_name.ui` - Glade UI definition
- Class inherits from `Gtk.Builder`

#### 2. Database Access
**Pattern:** Direct SQL via psycopg2 cursors
```python
c = DB.cursor()
c.execute("SELECT ... FROM ... WHERE id = %s", (id,))
result = c.fetchone()
c.close()
```

**Note:** No ORM (SQLAlchemy/Django ORM) used

#### 3. Signal Handling
**GTK Signals:** Defined in .ui files or connected in Python
**Custom Signals:** Broadcast system for inter-module communication

#### 4. Date Handling
Custom `dateutils.py` module for date calculations and formatting

#### 5. Printing
Custom `printing.py` module wrapping Cairo graphics

### Recommended Improvements

#### 1. Add Context Managers
```python
# Current
c = DB.cursor()
c.execute(...)
c.close()

# Recommended
with DB.cursor() as c:
    c.execute(...)
```

#### 2. Configuration Management
Move hardcoded values to configuration:
- Report file paths
- Default values
- Business rules

#### 3. Logging Strategy
Standardize logging:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Invoice created: %s", invoice_id)
```

#### 4. Code Style
Apply consistent code style:
- Run `black` formatter
- Use `flake8` or `ruff` for linting
- Add `pre-commit` hooks

---

## 11. Known Issues and Technical Debt

### From TO_DO.md
1. ✓ Add paid/posted/canceled toggles to invoice history
2. ✓ Load canceled invoices in history
3. ⚠️ Finish inventory calculations for invoices/POs
4. ⚠️ Admin login state not clear in some cases
5. ⚠️ Admin should use PostgreSQL credentials
6. ✓ Add more window keybindings
7. ⚠️ PDF attachment output window scrolling issue
8. ⚠️ Add split entry feature for double-entry accounting

### Technical Debt Identified
1. **Large Files:** Refactor 1000+ line modules
2. **Duplicate Code:** Extract common patterns
3. **Global State:** Reduce reliance on `constants` module
4. **Error Handling:** Add comprehensive exception handling
5. **Documentation:** Add docstrings and comments
6. **Testing:** Build comprehensive test suite
7. **Type Safety:** Add type hints

---

## 12. Recommendations

### Immediate Priorities (Next Sprint)
1. ✅ **Security Audit:** Review and fix SQL injection risks
2. ✅ **Add .gitignore:** Exclude .pyc, __pycache__, build artifacts
3. ✅ **Document Database Schema:** Generate ER diagram
4. ✅ **Basic Unit Tests:** Add tests for transaction classes

### Short-term Goals (1-3 Months)
5. ✅ **Code Linting:** Set up black/flake8
6. ✅ **Error Handling:** Add try-except to database operations
7. ✅ **Logging Framework:** Standardize logging across modules
8. ✅ **Type Hints:** Add to core modules

### Medium-term Goals (3-6 Months)
9. ✅ **Refactor Large Files:** Break down 1000+ line modules
10. ✅ **Integration Tests:** Test key accounting workflows
11. ✅ **Developer Documentation:** Create comprehensive docs
12. ✅ **CI/CD Pipeline:** Set up automated testing

### Long-term Vision (6-12 Months)
13. ✅ **Web Interface:** Consider web frontend option
14. ✅ **REST API:** Expose accounting functions via API
15. ✅ **Mobile App:** True mobile support (not just flag)
16. ✅ **Plugin System:** Allow third-party extensions

---

## 13. Metrics and Statistics

### Code Metrics
- **Total Python Files:** 181
- **Total Lines of Code:** ~43,896
- **UI Definition Files:** 141
- **Modules by Domain:**
  - Reports: 20+
  - Manufacturing: 12
  - Invoice: 10
  - Inventory: 8
  - Admin: 8
  - Payroll: 7
  - Resources: 7
  - Database: 6
  - Core: 120+ individual feature modules

### Complexity Indicators
- **Largest File:** 1,325 lines (purchase_order_window.py)
- **Exception Handlers:** 5 (very low)
- **Test Coverage:** <5% (only py3o module)
- **TODO Comments:** Found in 10+ files

### Maintenance Indicators
- **Active Development:** Yes (recent commits)
- **Production Use:** Yes (multiple businesses)
- **Documentation:** Minimal
- **Community:** Small but growing

---

## 14. Conclusion

PyGtk-Posting is a **mature, feature-complete desktop accounting system** with strong domain modeling and real-world usage. The codebase demonstrates solid understanding of accounting principles and effective use of GTK/PostgreSQL technologies.

**Key Strengths:**
- Comprehensive feature set
- Proper double-entry accounting
- Real-time multi-user synchronization
- Active maintenance

**Primary Needs:**
- Testing infrastructure
- Security hardening
- Code documentation
- Refactoring for maintainability

The project is well-positioned for growth with the addition of modern development practices (testing, CI/CD, documentation) and security improvements.

**Overall Assessment:** ⭐⭐⭐⭐ (4/5)
- Production-ready for core features
- Needs improvement in testing and documentation
- Solid foundation for future enhancements

---

**Report Generated:** January 22, 2026  
**Analyst:** GitHub Copilot  
**Next Review:** Recommended in 6 months or after major refactoring
