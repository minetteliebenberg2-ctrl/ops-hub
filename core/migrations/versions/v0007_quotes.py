"""Migration 0007: quotes and quote line items.

Introduces the Quotes module's storage. A quote belongs to a customer and
optionally a site, is numbered per-customer (FAC-001-Q-001 pattern, per
CRM_MODULE_SPECIFICATION.md section 2/5 and business_commercial_terms),
and carries a snapshot of the customer's payment terms at issue time so a
later change to the customer's terms never rewrites a historical quote.

Money is stored in integer minor units (cents) per master spec 4.2 - never
floating point.
"""

from datetime import datetime, timezone
import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 7
NAME = "quotes"

CREATE_QUOTES = """
CREATE TABLE quotes (
    id TEXT PRIMARY KEY,
    quote_number TEXT,
    customer_id TEXT NOT NULL,
    site_id TEXT,
    status TEXT NOT NULL DEFAULT 'Draft',
    issue_date TEXT NOT NULL DEFAULT '',
    expiry_date TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'ZAR',
    payment_terms_snapshot TEXT NOT NULL DEFAULT '',
    deposit_percentage REAL,
    balance_percentage REAL,
    subtotal_minor INTEGER NOT NULL DEFAULT 0,
    vat_minor INTEGER NOT NULL DEFAULT 0,
    total_minor INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE SET NULL
)
"""

CREATE_QUOTE_LINE_ITEMS = """
CREATE TABLE quote_line_items (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    structure_type TEXT NOT NULL DEFAULT '',
    car_bays INTEGER,
    shape TEXT NOT NULL DEFAULT '',
    width_m REAL,
    projection_m REAL,
    height_m REAL,
    description TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 1,
    unit_price_minor INTEGER NOT NULL DEFAULT 0,
    amount_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (quote_id) REFERENCES quotes (id) ON DELETE CASCADE
)
"""

INDEX_STATEMENTS = (
    "CREATE UNIQUE INDEX idx_quotes_quote_number ON quotes (quote_number)",
    "CREATE INDEX idx_quotes_customer ON quotes (customer_id)",
    "CREATE INDEX idx_quotes_status ON quotes (status)",
    "CREATE INDEX idx_quote_line_items_quote ON quote_line_items (quote_id)",
)

STATEMENTS = (CREATE_QUOTES, CREATE_QUOTE_LINE_ITEMS) + INDEX_STATEMENTS

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table in ("quotes", "quote_line_items"):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            raise sqlite3.DatabaseError(f"Migration v0007 did not create '{table}'.")

    quote_fks = {row[3] for row in connection.execute('PRAGMA foreign_key_list("quotes")')}
    if not {"customer_id", "site_id"}.issubset(quote_fks):
        raise sqlite3.DatabaseError("quotes is missing expected foreign keys.")

    line_item_fks = {row[3] for row in connection.execute('PRAGMA foreign_key_list("quote_line_items")')}
    if "quote_id" not in line_item_fks:
        raise sqlite3.DatabaseError("quote_line_items is missing its quote_id foreign key.")


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
