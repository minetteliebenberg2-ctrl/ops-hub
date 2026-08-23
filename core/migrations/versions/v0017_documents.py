"""Migration 0017: Documents module.

A place for the paperwork that isn't a Quote/Invoice: letters written on
the FacilitiesCo letterhead, and the compliance documents clients ask for
during tenders (Tax Compliance, COIDA, BEE affidavit, bank confirmation,
insurance certificates).

`expiry_date` is the point of the whole table. Tax Compliance PINs and
COIDA Letters of Good Standing expire, and the failure mode Minette
actually hits is being asked for one mid-tender and finding it lapsed -
so the Dashboard surfaces what's expiring rather than just listing files.

`stored_filename` is a name inside the documents root, not an absolute
path, so the root can be repointed (e.g. at OneDrive) without rewriting
every row. The root itself is an app setting, added here as
`documents_root` on business_settings.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 17
NAME = "documents"

STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Compliance',
        stored_filename TEXT NOT NULL,
        original_filename TEXT NOT NULL DEFAULT '',
        issue_date TEXT NOT NULL DEFAULT '',
        expiry_date TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)",
    "CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date)",
    "ALTER TABLE business_settings ADD COLUMN documents_root TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "documents" not in tables:
        raise sqlite3.DatabaseError("Migration v0017 did not create the 'documents' table.")

    required = {
        "id", "title", "category", "stored_filename", "original_filename",
        "issue_date", "expiry_date", "notes", "created_at", "updated_at", "updated_by",
    }
    present = {row[1] for row in connection.execute('PRAGMA table_info("documents")')}
    missing = required - present
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0017 'documents' is missing columns: {sorted(missing)}")

    settings_columns = {row[1] for row in connection.execute('PRAGMA table_info("business_settings")')}
    if "documents_root" not in settings_columns:
        raise sqlite3.DatabaseError("Migration v0017 did not add 'documents_root' to 'business_settings'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
