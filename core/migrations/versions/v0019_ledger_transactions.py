"""Migration 0019: Ledger transactions (general accounting).

Phase 2 of the Accounting rebuild agreed 2026-08-04. Replaces the old
in-memory-only `Transaction` dataclass in `modules/accounting/services.py`
(never written to the database, lost on close) with a real persisted
ledger covering personal AND business transactions across a full
financial/calendar year - the general books, distinct from the
customer-invoice `payments` table added in v0018.

`account` is a free-text label (e.g. "Gold Business Account", "Personal
Account") rather than a foreign key - Minette runs personal and business
accounts side by side and categorizes/filters by account name, there's
no separate "accounts" entity to normalize against yet.

`source` + `import_batch` trace where a row came from ('Manual' vs
'Bank Import', with the imported filename) so bulk-imported data stays
distinguishable from hand-entered rows without a separate audit table.

No unique constraint on (account, date, amount_minor, description) -
that would incorrectly reject genuinely repeated same-day transactions
(e.g. two identical fuel purchases). Re-import de-duplication is handled
in the service layer by counting existing matches instead.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 19
NAME = "ledger_transactions"

CREATE_LEDGER_TRANSACTIONS = """
CREATE TABLE ledger_transactions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    amount_minor INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    account TEXT NOT NULL DEFAULT '',
    reference TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'Manual',
    import_batch TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
)
"""

INDEXES = (
    "CREATE INDEX idx_ledger_transactions_date ON ledger_transactions (date)",
    "CREATE INDEX idx_ledger_transactions_account ON ledger_transactions (account)",
    "CREATE INDEX idx_ledger_transactions_category ON ledger_transactions (category)",
    "CREATE INDEX idx_ledger_transactions_dedupe ON ledger_transactions (account, date, amount_minor, description)",
)

STATEMENTS = (CREATE_LEDGER_TRANSACTIONS,) + INDEXES

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ledger_transactions'"
    ).fetchone()
    if not exists:
        raise sqlite3.DatabaseError("Migration v0019 did not create 'ledger_transactions'.")

    required = {
        "id", "date", "description", "amount_minor", "transaction_type",
        "category", "account", "reference", "notes", "source", "import_batch",
        "created_at", "updated_at", "created_by",
    }
    present = {row[1] for row in connection.execute('PRAGMA table_info("ledger_transactions")')}
    missing = required - present
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0019 'ledger_transactions' is missing columns: {sorted(missing)}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
