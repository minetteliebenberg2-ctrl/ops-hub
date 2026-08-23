"""Migration 0032: persistent auto-category rules for the ledger.

Minette (2026-08-08): "if I change the category for one transaction, the
system needs to apply a filter and load similar transactions and apply
the same change for eg. Kwikspar = Groceries ... otherwise it's useless
and we have [to] rewrite accounting."

Two halves to that ask, and this table is the second one:
  1. Apply the change to existing matching transactions - a bulk update,
     no schema needed.
  2. Remember the decision so future imports categorise themselves -
     this table.

`match_key` holds a normalised merchant identity from
core/merchant_key.py (e.g. "KWIKSPAR HOMESTEAD"), not the raw statement
description, so one rule covers every dated/card-masked variant of the
same payee. LedgerService._auto_category consults these rules before
falling back to the hardcoded AUTO_CATEGORY_RULES list.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 32
NAME = "ledger_category_rules"

CREATE_TABLE = """
CREATE TABLE ledger_category_rules (
    id TEXT PRIMARY KEY,
    match_key TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    transaction_type TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
)
"""

INDEX_STATEMENT = "CREATE INDEX idx_ledger_category_rules_key ON ledger_category_rules (match_key)"

STATEMENTS = (CREATE_TABLE, INDEX_STATEMENT)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ledger_category_rules'"
    ).fetchone()
    if not exists:
        raise sqlite3.DatabaseError("Migration v0032 did not create 'ledger_category_rules'.")

    columns = {row[1] for row in connection.execute('PRAGMA table_info("ledger_category_rules")')}
    missing = {"match_key", "category", "transaction_type", "is_active"} - columns
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0032 is missing columns {sorted(missing)}.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
