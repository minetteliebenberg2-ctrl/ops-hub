"""Migration 0010: Pro-Forma / Tax Invoice / Statement storage.

Implements the "Master doc per client" flow confirmed 2026-08-03:
Quote -> Pro-Forma -> Tax Invoice -> Statement, sharing one numbering
family (Q_/PF_/I_/STA_, see NumberingService.allocate_yearly) and each
document generated from real data rather than typed by hand.

quote_documents holds Pro-Forma and Tax Invoice records. Both are
generated from an existing (issued) quote and snapshot that quote's
totals at generation time - the source quote can later be re-issued or
its line items changed without silently rewriting a Pro-Forma/Invoice
that's already gone out to a client, matching how quote_number itself
is never rewritten after issue.

statements are per-customer, per-period documents that reference the
Tax Invoices issued to that customer in the period (see the
statement_line_items join table) with a snapshotted total. No payments
/ receipts table exists yet, so a statement currently lists invoices
raised, not amounts paid.

document_number is unique per customer (not globally), same reasoning
as migration v0008 for quotes.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 10
NAME = "quote_documents_and_statements"

CREATE_QUOTE_DOCUMENTS = """
CREATE TABLE quote_documents (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    document_number TEXT NOT NULL,
    issue_date TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Issued',
    currency TEXT NOT NULL DEFAULT 'ZAR',
    subtotal_minor INTEGER NOT NULL DEFAULT 0,
    vat_minor INTEGER NOT NULL DEFAULT 0,
    total_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (quote_id) REFERENCES quotes (id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
)
"""

CREATE_STATEMENTS = """
CREATE TABLE statements (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    document_number TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'ZAR',
    total_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
)
"""

CREATE_STATEMENT_LINE_ITEMS = """
CREATE TABLE statement_line_items (
    id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL,
    quote_document_id TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements (id) ON DELETE CASCADE,
    FOREIGN KEY (quote_document_id) REFERENCES quote_documents (id) ON DELETE CASCADE
)
"""

INDEX_STATEMENTS = (
    "CREATE UNIQUE INDEX idx_quote_documents_customer_number ON quote_documents (customer_id, document_number)",
    "CREATE INDEX idx_quote_documents_quote ON quote_documents (quote_id)",
    "CREATE INDEX idx_quote_documents_customer ON quote_documents (customer_id)",
    "CREATE UNIQUE INDEX idx_statements_customer_number ON statements (customer_id, document_number)",
    "CREATE INDEX idx_statement_line_items_statement ON statement_line_items (statement_id)",
)

STATEMENTS = (CREATE_QUOTE_DOCUMENTS, CREATE_STATEMENTS, CREATE_STATEMENT_LINE_ITEMS) + INDEX_STATEMENTS

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table in ("quote_documents", "statements", "statement_line_items"):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            raise sqlite3.DatabaseError(f"Migration v0010 did not create '{table}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
