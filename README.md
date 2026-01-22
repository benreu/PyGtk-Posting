# PyGtk-Posting

A comprehensive open-source accounting and business management system for Linux, designed as a modern replacement for QuickBooks and Peachtree.

## Overview

PyGtk-Posting is a full-featured ERP (Enterprise Resource Planning) system that combines accounting, inventory management, payroll, and manufacturing capabilities into a single integrated application. Built with Python 3, GTK+ 3, and PostgreSQL, it provides a native Linux desktop experience with enterprise-grade functionality.

**Status:** Alpha (actively maintained and used in production by multiple businesses)  
**Version:** 0.5.34  
**License:** GPL v3

## Key Features

### 📊 Accounting & Finance
- **Double-entry accounting system** with general ledger
- **Bank reconciliation** for bank and credit card statements
- **Account management** with chart of accounts configuration
- **Budget tracking** and configuration
- **Financial reports** including profit & loss, net worth, and sales tax reports
- **Check writing** and payment processing

### 👥 Customer Management
- Complete customer database with contact information
- **Invoice creation** and management
- **Payment tracking** and receipt generation
- **Credit memos** and finance charges
- **Customer statements** with payment history
- **Job sheets** for project tracking
- Track unpaid invoices and aging

### 🏭 Vendor Management
- Vendor contact database
- **Purchase order** creation and management (draft, unprocessed, and completed)
- **Vendor payments** and history tracking
- Vendor statement reconciliation

### 📦 Inventory Management
- Complete product catalog with barcode support
- **Inventory tracking** with real-time quantity updates
- **Inventory adjustments** and counts
- **Product locations** and warehouse management
- **Inventory history** and audit trails
- **Kit products** with bill of materials

### 🔧 Manufacturing
- **Assembly management** with version control
- **Manufacturing projects** and work orders
- **Serial number tracking** for assembled products
- Bill of materials and component tracking
- Manufacturing history and reporting

### 💰 Payroll
- **Employee management** with contact information
- **Pay stub generation** and history
- Time tracking integration
- Payroll reporting

### 📈 Reporting & Analytics
- Comprehensive financial reports (profit/loss, balance sheet, net worth)
- Customer and vendor history reports
- Invoice and purchase order summaries
- Manufacturing and inventory reports
- **Banking reports** (deposits, credit card statements)
- **Charts and visualizations** using Matplotlib
- Export to **PDF and Excel** formats

### ⚙️ Additional Features
- **Time clock system** for employee tracking
- **Document management** with scanning support (SANE)
- **Barcode generation** and label printing
- **Complete search** functionality across all modules
- **Data import/export** tools
- **Database backup and restore**
- Multi-database support (PostgreSQL and SQLite for configuration)
- **Document templates** using LibreOffice format (.odt)
- Keyboard shortcuts and quick command system

## Technology Stack

### Core Technologies
- **Python 3** - Main programming language
- **GTK+ 3** (3.20+) - User interface toolkit
- **Glade** (3.38.2+) - UI design and layout
- **PostgreSQL 10+** - Primary database (for business data)
- **SQLite** - Configuration database

### Key Libraries
- **psycopg2** - PostgreSQL database adapter
- **APSW** - SQLite wrapper
- **Genshi** - Template engine for document generation
- **lxml** - XML processing
- **CairoCFFI** - Graphics rendering
- **Matplotlib** - Charts and graphs
- **XlsxWriter, xlrd** - Excel file handling
- **py3o** - LibreOffice template processing
- **python-sane** - Document scanning
- **unoconv** - Document format conversion
- **GooCanvas** - Canvas graphics for diagrams

## Requirements

### System Requirements
- Linux operating system
- Python 3.x
- PostgreSQL 10 or higher
- GTK+ 3.20 or higher
- Glade 3.38.2 or higher

### Python Dependencies
All required Python packages are listed in `requirements.txt`:
- python3-apsw
- python3-cairocffi
- python3-genshi
- python3-lxml
- python3-matplotlib
- python3-psycopg2
- python3-sane
- python3-tk
- python3-uno
- python3-xlrd
- python3-xlsxwriter
- gir1.2-goocanvas-2.0

## Installation

### From Debian Package
```bash
# Install the .deb package (replace <version> with the actual version number)
sudo dpkg -i pygtk_posting_<version>.deb

# Install any missing dependencies
sudo apt-get install -f
```

### From Source
```bash
# Clone the repository
git clone https://github.com/benreu/PyGtk-Posting.git
cd PyGtk-Posting

# Install dependencies (Debian/Ubuntu)
sudo apt-get install python3-apsw python3-cairocffi python3-genshi \
  python3-lxml python3-matplotlib python3-psycopg2 python3-sane \
  python3-tk python3-uno unoconv python3-xlrd python3-xlsxwriter \
  gir1.2-goocanvas-2.0

# Run the application
./pygtk-posting
```

## Getting Started

1. **First Launch**: On first run, PyGtk-Posting will create configuration directories in `~/.config/posting/`

2. **Database Setup**: Configure your PostgreSQL database connection through the initial setup wizard

3. **Company Setup**: Create your company profile with business information

4. **Chart of Accounts**: Configure your chart of accounts based on your business needs

5. **Start Using**: Begin entering customers, vendors, products, and transactions

## Database Configuration

PyGtk-Posting uses:
- **PostgreSQL** for all business data (transactions, customers, inventory, etc.)
- **SQLite** for application configuration stored in `~/.config/posting/`

See `POSTGRES_README` for detailed PostgreSQL setup instructions.

## Project Structure

```
PyGtk-Posting/
├── src/                    # Main source code
│   ├── admin/             # Administrative tools
│   ├── db/                # Database utilities (backup, restore, tools)
│   ├── inventory/         # Inventory management
│   ├── invoice/           # Invoicing system
│   ├── manufacturing/     # Manufacturing and assembly
│   ├── payroll/           # Payroll management
│   ├── reports/           # Reporting engine
│   └── *.py               # Core modules (accounts, customers, vendors, etc.)
├── templates/             # LibreOffice document templates (.odt)
├── help/                  # Help documentation
├── icons/                 # Application icons
└── pygtk-posting         # Main launcher script
```

## Documentation

- Help documentation is available within the application
- Additional documentation files: `INSTALL`, `POSTGRES_README`
- Screenshots available at: https://sourceforge.net/projects/pygtk-posting/

## Contributing

This is an open, user-driven project! Contributions are welcome:
- Submit bug reports and feature requests
- Contribute code via pull requests
- Help test and improve the application
- Submit patches and improvements

The project is actively maintained and used in production environments.

## License

PyGtk-Posting is released under the **GNU General Public License v3 (GPL-3.0)**.

See `LICENSE.md` and `COPYING` for full license text.

## Contact

- **Email**: pygtk.posting@gmail.com
- **GitHub**: https://github.com/benreu/PyGtk-Posting
- **SourceForge**: https://sourceforge.net/projects/pygtk-posting/

## Support

If you use PyGtk-Posting for your business, please consider:
- Contributing code or documentation
- Reporting bugs and suggesting features
- Sharing your experience with other users
- Testing new features and releases

---

**Note**: PyGtk-Posting is in active development and used by multiple businesses in production. While in alpha status, it provides a stable, feature-rich accounting solution for Linux users.