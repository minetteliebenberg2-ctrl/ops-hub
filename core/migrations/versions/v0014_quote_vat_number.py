"""Migration 0014: quote-level VAT number, shown as a permanent PDF field.

Minette wants PO Number and Customer VAT to always appear in the meta
block (QUOTE #, DATE, VALID UNTIL, ...) on Quote/Pro-Forma/Tax Invoice
PDFs - not only when set, defaulting to N/A/TBC so it's visibly a
deliberate choice, not a missing field. po_number already exists
(migration v0012); this adds a matching vat_number to quotes and
quote_documents, editable per-quote rather than only via the customer's
CRM record - a quote's VAT number is often "TBC" at draft time even
when the eventual customer record will carry the confirmed one.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 14
NAME = "quote_vat_number"

STATEMENTS = (
    "ALTER TABLE quotes ADD COLUMN vat_number TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quote_documents ADD COLUMN vat_number TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table in ("quotes", "quote_documents"):
        present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if "vat_number" not in present:
            raise sqlite3.DatabaseError(f"Migration v0014 did not add 'vat_number' to '{table}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
