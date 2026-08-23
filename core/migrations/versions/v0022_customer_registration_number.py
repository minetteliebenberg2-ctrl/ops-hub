"""Migration 0022: customer registration number, snapshotted onto quotes.

Minette found (2026-08-05, testing the PDF-import feature) that a
client's own company registration number - "YOUR REG" in her legacy
Estimate/Invoice template, distinct from their VAT number - had
nowhere to live in FC Hub and so never made it onto a generated quote.
Mirrors the existing vat_number pattern exactly: a permanent field on
`customers` (editable in CRM), snapshotted onto `quotes` and
`quote_documents` at creation time (still per-quote/editable after,
same as vat_number - a client's registration number can be confirmed
later even if it's on file by then).
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 22
NAME = "customer_registration_number"

STATEMENTS = (
    "ALTER TABLE customers ADD COLUMN registration_number TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quotes ADD COLUMN registration_number TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quote_documents ADD COLUMN registration_number TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table in ("customers", "quotes", "quote_documents"):
        present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if "registration_number" not in present:
            raise sqlite3.DatabaseError(f"Migration v0022 did not add 'registration_number' to '{table}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
