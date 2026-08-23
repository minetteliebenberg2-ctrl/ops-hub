"""Migration 0013: Quote revisions.

Minette flagged that editing an already-issued Quote (to reflect a
client-requested change) silently rewrites the document a client may
already have - what she needs instead is a revision: a new editable
copy that keeps the *same* quote number but is tracked as a distinct
version (displayed as "Q_26/001 (Rev 1)"), leaving the original
untouched.

Adds revision_of_quote_id (the quote this one revises, NULL for an
original) and revision_number (0 = original, 1/2/3... for each
subsequent revision) to quotes. Because a revision intentionally
reuses its original's quote_number, the per-customer uniqueness
constraint from migration v0008 must widen to
(customer_id, quote_number, revision_number) - two rows can now
legitimately share a quote_number as long as their revision_number
differs.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 13
NAME = "quote_revisions"

STATEMENTS = (
    "ALTER TABLE quotes ADD COLUMN revision_of_quote_id TEXT REFERENCES quotes (id)",
    "ALTER TABLE quotes ADD COLUMN revision_number INTEGER NOT NULL DEFAULT 0",
    "DROP INDEX IF EXISTS idx_quotes_quote_number",
    "CREATE UNIQUE INDEX idx_quotes_quote_number ON quotes (customer_id, quote_number, revision_number)",
    "CREATE INDEX idx_quotes_revision_of ON quotes (revision_of_quote_id)",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    present = {row[1] for row in connection.execute('PRAGMA table_info("quotes")')}
    missing = {"revision_of_quote_id", "revision_number"} - present
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0013 did not add columns {sorted(missing)} to quotes.")

    index = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_quotes_quote_number'"
    ).fetchone()
    if index is None or "revision_number" not in index["sql"]:
        raise sqlite3.DatabaseError(
            "idx_quotes_quote_number must be scoped to (customer_id, quote_number, revision_number) after migration v0013."
        )


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
