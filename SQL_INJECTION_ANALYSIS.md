# SQL Injection Vulnerability Analysis

## Summary

This document identifies 4 SQL injection vulnerabilities found in the PyGtk-Posting codebase. All instances use Python's `%` string formatting to construct SQL queries with untrusted input, which can allow attackers to execute arbitrary SQL commands.

---

## Vulnerability Details

### 1. kit_products.py - Line 61

**File:** `src/kit_products.py`  
**Line:** 61  
**Severity:** HIGH

**Vulnerable Code:**
```python
def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
    return  # Note: This function has an early return, so not currently exploitable
    _list_ = data.get_text().split(' ')
    if len(_list_) != 2:
        return
    table, _id_ = _list_[0], _list_[1]
    self.cursor.execute("SELECT product, remark, cost FROM %s WHERE id = %s" % (table, _id_))
    for row in self.cursor.fetchall():
        product = row[0]
        remark = row[1]
        price = row[2]
```

**Issue:**
- Uses `%` string formatting to insert `table` and `_id_` directly into SQL query
- Both `table` (table name) and `_id_` come from drag-and-drop data that could be manipulated
- **Current Status:** Function has `return` on line 56, so code is not executed (dead code)
- **Risk if enabled:** An attacker could craft malicious drag data like:
  ```
  "products; DROP TABLE invoices; -- 123"
  ```

**Recommended Fix:**
```python
# For table names, use identifier quoting (but validate against whitelist first!)
from psycopg2 import sql

# Validate table name against whitelist
allowed_tables = ['products', 'invoice_items', 'purchase_order_items']
if table not in allowed_tables:
    return

# Use parameterized query for ID
self.cursor.execute(
    sql.SQL("SELECT product, remark, cost FROM {} WHERE id = %s").format(
        sql.Identifier(table)
    ),
    (_id_,)
)
```

---

### 2. documents_window.py - Line 112

**File:** `src/documents_window.py`  
**Line:** 112  
**Severity:** HIGH

**Vulnerable Code:**
```python
def on_drag_data_received(self, widget, drag_context, x,y, data,info, time):
    _list_ = data.get_text().split(' ')
    if len(_list_) != 2:
        return
    table, _id_ = _list_[0], _list_[1]
    self.cursor.execute("SELECT product, remark, price FROM %s WHERE id = %s" % (table, _id_))
    for row in self.cursor.fetchall():
        product = row[0]
        remark = row[1]
        price = row[2]
    print ("please implement me") #FIXME
```

**Issue:**
- Identical vulnerability to #1 above
- Uses `%` string formatting with untrusted drag-and-drop data
- Both `table` name and `_id_` are directly interpolated into the SQL query
- **Current Status:** Function is active (no early return)
- **Risk:** HIGH - Function is currently enabled and processes drag data

**Attack Example:**
```
Drag data: "products; DELETE FROM invoices WHERE 1=1; -- 123"
Result: All invoices could be deleted
```

**Recommended Fix:**
Same as #1 - use `psycopg2.sql.Identifier()` for table names with whitelist validation, and parameterized queries for values.

---

### 3. complete_search.py - Lines 90-91

**File:** `src/complete_search.py`  
**Line:** 90-91  
**Severity:** HIGH

**Vulnerable Code:**
```python
def treeview_row_activated (self, treeview, path, treeviewcolumn):
    schema = self.store[path][0]
    table = self.store[path][1]
    column = self.store[path][2]
    ctid = self.store[path][4]
    self.cursor.execute("SELECT * FROM %s.%s WHERE ctid = '%s'"%
                        (schema, table, ctid))
```

**Issue:**
- Uses `%` string formatting with three untrusted values: `schema`, `table`, and `ctid`
- Values come from a TreeView store that could potentially be manipulated
- The `ctid` (tuple ID) is particularly dangerous as it's used in a string comparison
- **Risk:** HIGH - Schema, table, and ctid all come from user-selectable data

**Attack Example:**
```
If an attacker can manipulate the TreeView store:
ctid = "' OR '1'='1"
Result: Query becomes: SELECT * FROM schema.table WHERE ctid = '' OR '1'='1'
This would return all rows instead of a specific one
```

**Recommended Fix:**
```python
from psycopg2 import sql

def treeview_row_activated(self, treeview, path, treeviewcolumn):
    schema = self.store[path][0]
    table = self.store[path][1]
    column = self.store[path][2]
    ctid = self.store[path][4]
    
    # Validate schema and table names against whitelist if possible
    # Use sql.Identifier for schema/table names and parameterized query for ctid
    self.cursor.execute(
        sql.SQL("SELECT * FROM {}.{} WHERE ctid = %s").format(
            sql.Identifier(schema),
            sql.Identifier(table)
        ),
        (ctid,)
    )
```

---

### 4. db/database_tools.py - Line 219

**File:** `src/db/database_tools.py`  
**Line:** 219  
**Severity:** MEDIUM

**Vulnerable Code:**
```python
try:
    self.cursor.execute("""CREATE DATABASE "%s";""" % db_name)
except Exception as e:
    print (e)
    if (e.pgcode == "42P04"):
        self.status_update("Database already exists!")
    return
```

**Issue:**
- Uses `%` string formatting to insert database name into CREATE DATABASE statement
- Database name likely comes from user input
- **Risk:** MEDIUM - PostgreSQL database names have restrictions, but an attacker could still:
  - Create databases with malicious names
  - Use special characters to break the query
  - Potentially inject additional SQL commands

**Note:** PostgreSQL's CREATE DATABASE cannot be parameterized (doesn't support placeholders). However, the database name should still be validated and properly quoted.

**Recommended Fix:**
```python
from psycopg2 import sql

# Validate database name (alphanumeric, underscore, max 63 chars)
import re
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', db_name):
    self.status_update("Invalid database name!")
    return

try:
    # Use sql.Identifier for proper quoting
    self.cursor.execute(
        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
    )
except Exception as e:
    print(e)
    if hasattr(e, 'pgcode') and e.pgcode == "42P04":
        self.status_update("Database already exists!")
    return
```

---

## False Positives (Not Vulnerabilities)

The following files were initially flagged but do NOT contain SQL injection vulnerabilities:

### src/db/transactor.py
- **Line 543:** `cursor.execute("UPDATE gl_entries SET amount = %s WHERE id = %s", ...)`
  - ✅ **SAFE:** Uses proper parameterized query with tuple

### src/purchase_ordering.py
- **Line 132:** `cursor.execute("SELECT format_date(%s), format_date(%s)", ...)`
  - ✅ **SAFE:** Uses proper parameterized query with tuple

### src/payroll/pay_stub.py
- **Lines 236, 239, 375, 399:** All use parameterized queries
  - ✅ **SAFE:** Uses proper parameterized query with tuple in all instances

---

## Summary Table

| File | Line | Severity | Status | Exploitable |
|------|------|----------|--------|-------------|
| src/kit_products.py | 61 | HIGH | Dead Code | No (has early return) |
| src/documents_window.py | 112 | HIGH | Active | Yes |
| src/complete_search.py | 90-91 | HIGH | Active | Yes |
| src/db/database_tools.py | 219 | MEDIUM | Active | Partially |

**Total Vulnerabilities:** 4  
**Currently Exploitable:** 3  
**Dead Code (not exploitable now):** 1

---

## Impact Assessment

### Potential Consequences

1. **Data Theft:** Attackers could read sensitive financial data, customer information, employee records
2. **Data Modification:** Attackers could modify invoices, payments, account balances
3. **Data Destruction:** Attackers could drop tables, delete records
4. **Privilege Escalation:** Attackers could potentially modify user permissions
5. **Business Disruption:** Database corruption could halt business operations

### Attack Vector

- **documents_window.py** and **kit_products.py**: Exploitable via drag-and-drop operations. An attacker would need to:
  1. Run the application
  2. Navigate to a window with drag-and-drop enabled
  3. Craft malicious drag data containing SQL injection payloads
  4. Drag the malicious data to trigger the vulnerable function

- **complete_search.py**: Exploitable if an attacker can manipulate the TreeView store data, possibly through:
  1. Database manipulation (if they already have some access)
  2. UI manipulation via accessibility tools
  3. Memory manipulation

- **database_tools.py**: Exploitable when creating a new database with a crafted name

---

## Remediation Priority

### Immediate (Fix Now)
1. ✅ **documents_window.py:112** - Active and exploitable via UI
2. ✅ **complete_search.py:90-91** - Active and exploitable

### High Priority (Fix Soon)
3. ✅ **db/database_tools.py:219** - Active but limited by PostgreSQL naming restrictions
4. ✅ **kit_products.py:61** - Currently dead code, but should be fixed if ever re-enabled

---

## General Recommendations

### 1. Code-wide SQL Query Audit
Conduct a comprehensive audit of all SQL queries using automated tools:
```bash
# Search for potential SQL injection patterns
grep -r "execute.*%.*%" src/
grep -r "execute.*\.format" src/
grep -r 'execute.*f"' src/
```

### 2. Establish Secure Coding Guidelines
- **Always use parameterized queries** for values: `cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))`
- **Use psycopg2.sql.Identifier()** for dynamic table/column names with whitelist validation
- **Never** use string formatting (`%`, `.format()`, f-strings) to build SQL queries
- **Validate all input** from users, even if it comes from UI widgets

### 3. Implement Code Review Process
- Require peer review for all database query changes
- Use static analysis tools (e.g., Bandit, Semgrep) in CI/CD pipeline
- Add pre-commit hooks to catch dangerous patterns

### 4. Security Testing
- Add security-focused unit tests that attempt SQL injection
- Consider penetration testing by security professionals
- Implement input validation testing in QA process

### 5. Defense in Depth
- Use PostgreSQL role-based access control (RBAC)
- Run application with least-privilege database user
- Enable PostgreSQL audit logging
- Regular database backups

---

## References

- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [psycopg2 SQL Composition](https://www.psycopg.org/docs/sql.html)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/sql-syntax.html)
- [CWE-89: SQL Injection](https://cwe.mitre.org/data/definitions/89.html)

---

**Document Version:** 1.0  
**Analysis Date:** January 22, 2026  
**Analyst:** GitHub Copilot
