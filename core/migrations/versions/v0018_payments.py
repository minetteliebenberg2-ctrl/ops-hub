"""Migration 0018: Payments and payment allocations.

Phase 1 of linking incoming customer payments to the Tax Invoices they
settle (see the "Accounting" work agreed 2026-08-04). Manual entry only
for now - no bank-statement import or auto-matching yet, that's a later,
separately signed-off phase.

payments is one row per money-in event Minette records by hand
(customer, amount, date, reference, notes). payment_allocations is an
append-only join table linking a payment to the quote_documents row
(Tax Invoice) it settles, in any amount - one payment can spread across
several invoices, and several payments can accumulate onto one invoice.
"Un-allocating" writes a reversing row (negative amount_minor) rather
than deleting, so the allocation history is never lost - that's the
audit trail. A Tax Invoice's paid/balance status is always computed
from SUM(payment_allocations.amount_minor) against quote_documents.
total_minor, never stored redundantly, so the two numbers can't drift.

customer_id on payments is required (NOT NULL) - Phase 1 is manual
entry, so whoever logs the payment already knows who paid; a genuine
"unknown payer" suspense item is a bank-import-phase concern, not this
one.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 18
NAME = "payments"

CREATE_PAYMENTS = """
CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,
    date TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Unallocated',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
)
"""

CREATE_PAYMENT_ALLOCATIONS = """
CREATE TABLE payment_allocations (
    id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    quote_document_id TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (payment_id) REFERENCES payments (id) ON DELETE CASCADE,
    FOREIGN KEY (quote_document_id) REFERENCES quote_documents (id) ON DELETE CASCADE
)
"""

INDEXES = (
    "CREATE INDEX idx_payments_customer ON payments (customer_id)",
    "CREATE INDEX idx_payment_allocations_payment ON payment_allocations (payment_id)",
    "CREATE INDEX idx_payment_allocations_document ON payment_allocations (quote_document_id)",
)

STATEMENTS = (CREATE_PAYMENTS, CREATE_PAYMENT_ALLOCATIONS) + INDEXES

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for table in ("payments", "payment_allocations"):
        if table not in tables:
            raise sqlite3.DatabaseError(f"Migration v0018 did not create '{table}'.")

    payments_columns = {row[1] for row in connection.execute('PRAGMA table_info("payments")')}
    required_payments = {
        "id", "customer_id", "amount_minor", "date", "reference", "notes",
        "status", "created_at", "updated_at", "created_by",
    }
    missing = required_payments - payments_columns
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0018 'payments' is missing columns: {sorted(missing)}")

    allocations_columns = {row[1] for row in connection.execute('PRAGMA table_info("payment_allocations")')}
    required_allocations = {
        "id", "payment_id", "quote_document_id", "amount_minor", "notes",
        "created_at", "created_by",
    }
    missing = required_allocations - allocations_columns
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0018 'payment_allocations' is missing columns: {sorted(missing)}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
