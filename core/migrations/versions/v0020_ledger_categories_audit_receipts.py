"""Migration 0020: Self-service categories, edit audit trail/undo,
receipt attachments, and bank reconciliation snapshots for the ledger.

Phase 3 of the Accounting rebuild agreed 2026-08-04, covering the gaps
Minette flagged after live-testing Phase 2:

- `ledger_categories` moves the category list out of hardcoded Python
  (core/ledger_service.py) into the database, so she can add/rename/
  retire her own categories from Settings without needing a code
  change. Seeded from the real category lists already in
  core/ledger_service.py (INCOME_CATEGORIES/EXPENSE_CATEGORIES) so
  nothing existing is lost - retiring hides a category from new-entry
  dropdowns without deleting it or breaking transactions that already
  use it.

- `ledger_transaction_edits` is an append-only log of every field
  change made to a ledger_transactions row (old value, new value, who,
  when). This is both the audit trail she asked for AND the mechanism
  behind "Undo last edit" in the new inline-editable ledger grid - undo
  reverts the most recent un-undone row in this table rather than
  keeping a separate in-memory stack, so the record survives an app
  restart and nothing is ever silently lost even beyond one undo.

- `receipt_filename` on ledger_transactions lets a transaction carry a
  supporting document, reusing the Documents module's existing
  `documents_root` setting (see v0017) rather than introducing a
  second configurable storage location - just a "Ledger Receipts"
  subfolder under the same root.

- `account_reconciliation_snapshots` stores the closing balance FNB's
  own CSV reports for an account on each import, so the ledger's own
  running total for that account can be compared against it and a
  mismatch surfaced - confirmed with Minette as "closing balance only",
  not a full per-transaction running-balance audit.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 20
NAME = "ledger_categories_audit_receipts"

CREATE_LEDGER_CATEGORIES = """
CREATE TABLE ledger_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
)
"""

CREATE_LEDGER_TRANSACTION_EDITS = """
CREATE TABLE ledger_transaction_edits (
    id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT NOT NULL DEFAULT '',
    new_value TEXT NOT NULL DEFAULT '',
    undone INTEGER NOT NULL DEFAULT 0,
    edited_at TEXT NOT NULL,
    edited_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (transaction_id) REFERENCES ledger_transactions (id) ON DELETE CASCADE
)
"""

CREATE_RECONCILIATION_SNAPSHOTS = """
CREATE TABLE account_reconciliation_snapshots (
    account TEXT PRIMARY KEY,
    statement_balance_minor INTEGER NOT NULL,
    statement_date TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

INDEXES = (
    "CREATE INDEX idx_ledger_categories_type ON ledger_categories (category_type)",
    "CREATE UNIQUE INDEX idx_ledger_categories_name ON ledger_categories (name)",
    "CREATE INDEX idx_ledger_transaction_edits_transaction ON ledger_transaction_edits (transaction_id)",
    "CREATE INDEX idx_ledger_transaction_edits_undone ON ledger_transaction_edits (undone)",
)

ALTER_RECEIPT_COLUMN = "ALTER TABLE ledger_transactions ADD COLUMN receipt_filename TEXT NOT NULL DEFAULT ''"

STATEMENTS = (
    CREATE_LEDGER_CATEGORIES,
    CREATE_LEDGER_TRANSACTION_EDITS,
    CREATE_RECONCILIATION_SNAPSHOTS,
    ALTER_RECEIPT_COLUMN,
) + INDEXES

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


# Seed data - the real category lists from core/ledger_service.py at
# the time this migration was written. The Python constants stay as
# documentation/fallback; the database row is what the app actually
# reads from after this migration.
INCOME_SEED = [
    "Sales Income",
    "Bank:  Inter-account Transfers",
    "Unassigned Receipts",
    "Sundry Income",
    "Other Income",
]

EXPENSE_SEED = [
    "General Expenses",
    "Direct Selling Costs",
    "Subcontract Costs",
    "Personal Expenses through Business Accounts",
    "Bank Charges",
    "Insurance / Security",
    "Groceries",
    "Op Cost: General Operating",
    "Payroll Expenses",
    "Business Insurance",
    "Entertainment & Meals",
    "Motor V: Fuel & Oil",
    "Motor Vehicle Expenses",
    "Motor V: Repairs & Maintenance",
    "Telephone / Fax / Internet",
    "Operating Costs",
    "Directors Fees & Remuneration",
    "Credit Card Expenses",
    "Repairs & Maintenance",
    "Cleaning & Gardening",
    "Bad Debts",
    "Unassigned Payments",
    "Subscriptions and membership fees",
    "Liabilities: Long Term",
    "Accounting",
    "Legal Fees",
    "Normal Taxation",
    "Share Holders/ Directors/ Members Loans",
    "Loans (Private) From:",
    "Loans (Private) To / (From):",
    "General Exp: Gifts",
    "Personal care / hygene / wellness",
    "Staff Welfare",
    "Security",
    "Dividends /  Pft/Loss Distribution",
    "Subcontractor Wages",
    "Office Supplies",
    "Miscellaneous",
]


def apply(connection):
    import uuid
    from datetime import datetime, timezone

    for statement in STATEMENTS:
        connection.execute(statement)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for name in INCOME_SEED:
        connection.execute(
            "INSERT INTO ledger_categories (id, name, category_type, active, created_at, updated_at) VALUES (?, ?, 'Income', 1, ?, ?)",
            (str(uuid.uuid4()), name, now, now),
        )
    for name in EXPENSE_SEED:
        connection.execute(
            "INSERT INTO ledger_categories (id, name, category_type, active, created_at, updated_at) VALUES (?, ?, 'Expense', 1, ?, ?)",
            (str(uuid.uuid4()), name, now, now),
        )


def verify(connection):
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for table in ("ledger_categories", "ledger_transaction_edits", "account_reconciliation_snapshots"):
        if table not in tables:
            raise sqlite3.DatabaseError(f"Migration v0020 did not create '{table}'.")

    columns = {row[1] for row in connection.execute('PRAGMA table_info("ledger_transactions")')}
    if "receipt_filename" not in columns:
        raise sqlite3.DatabaseError("Migration v0020 did not add 'receipt_filename' to 'ledger_transactions'.")

    count = connection.execute("SELECT COUNT(*) FROM ledger_categories").fetchone()[0]
    if count < len(INCOME_SEED) + len(EXPENSE_SEED):
        raise sqlite3.DatabaseError("Migration v0020 did not seed the expected categories.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
