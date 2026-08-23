"""Migration 0030: real Delete + Recycle Bin for core CRM entities.

Scoped with Minette 2026-08-07 (via AskUserQuestion): she wants a real
Delete option everywhere, not just Archive - triggered by wanting to
remove a throwaway test Site she'd created. Confirmed scope:

- Financial/audit-trail records (Invoices, Payments, Ledger
  transactions) stay archive-only, excluded from this - protects the
  accounting audit trail.
- Recycle bin sits until manually emptied (no auto-purge).
- Delete is BLOCKED if the record has children (not cascade-recycled
  as one unit) - she picked the safer option.

This migration covers the 5 core CRM entities: Customer, Contact,
Address, Site, Activity. `deleted_at`/`deleted_by` are a SEPARATE,
independent state from the existing `archived_at`/`archived_by`/
`archive_reason` - Archive still means "inactive but keep forever, no
confirmation, always reversible"; Delete means "move to the Recycle
Bin, hidden everywhere until Restored or Permanently Deleted."
customer_activities never had an archive concept at all (no
archived_at column) - it gains delete support fresh, no restore-from-
archive pattern to mirror there.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 30
NAME = "crm_soft_delete"

STATEMENTS = (
    "ALTER TABLE customers ADD COLUMN deleted_at TEXT",
    "ALTER TABLE customers ADD COLUMN deleted_by TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN deleted_at TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN deleted_by TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN deleted_at TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN deleted_by TEXT",
    "ALTER TABLE customer_sites ADD COLUMN deleted_at TEXT",
    "ALTER TABLE customer_sites ADD COLUMN deleted_by TEXT",
    "ALTER TABLE customer_activities ADD COLUMN deleted_at TEXT",
    "ALTER TABLE customer_activities ADD COLUMN deleted_by TEXT",
)

TABLE_COLUMNS = {
    "customers": ("deleted_at", "deleted_by"),
    "customer_contacts": ("deleted_at", "deleted_by"),
    "customer_addresses": ("deleted_at", "deleted_by"),
    "customer_sites": ("deleted_at", "deleted_by"),
    "customer_activities": ("deleted_at", "deleted_by"),
}

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table, expected_columns in TABLE_COLUMNS.items():
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        missing = set(expected_columns) - columns
        if missing:
            raise sqlite3.DatabaseError(f"Migration v0030 did not add {sorted(missing)} to {table}.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
