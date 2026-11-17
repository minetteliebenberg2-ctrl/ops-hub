"""Migration 0060: bi-annual provisional tax return dates.

Provisional tax (IRP6) runs two periods per tax year - the first falls
due at the end of August, the second at the end of February - and the
annual ITR14 follows. One row per (tax_year, period) so she can record
the due date, when it actually went in, the amount and a note.

Nothing here feeds pricing or any client-facing document; it is a
reminder table she edits in Settings.
"""

import sqlite3
from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
CREATE TABLE IF NOT EXISTS tax_return_dates (
    id TEXT PRIMARY KEY,
    tax_year TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    submitted_date TEXT NOT NULL DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    paid INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tax_return_dates_year
    ON tax_return_dates (tax_year, period);
"""


def apply(connection):
    connection.executescript(PAYLOAD)


def verify(connection):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tax_return_dates'"
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Migration v0060: tax_return_dates table missing")
    cols = {r["name"] for r in connection.execute("PRAGMA table_info(tax_return_dates)")}
    missing = {"id", "tax_year", "period", "due_date", "submitted_date",
               "amount", "paid", "notes"} - cols
    if missing:
        raise sqlite3.DatabaseError(
            "Migration v0060: missing columns: " + ", ".join(sorted(missing))
        )


MIGRATION = Migration(
    version=60,
    name="tax_return_dates",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
