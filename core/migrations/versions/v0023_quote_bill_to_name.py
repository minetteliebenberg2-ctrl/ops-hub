"""Migration 0023: quote-level "Bill To" name override.

Minette generally quotes a managing agent (e.g. "The Cavaleros Group")
and only learns which specific legal entity the final invoice must be
addressed to later - sometimes a different company entirely (e.g.
"Turtium Investments (Pty) Ltd") - because she gets invoicing details
late. Rather than a customer relationship, this is a per-document
override: a `bill_to_name` on `quotes` and `quote_documents`, editable
like vat_number/registration_number (v0022), defaulting to the
customer's name but never required to match it.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 23
NAME = "quote_bill_to_name"

STATEMENTS = (
    "ALTER TABLE quotes ADD COLUMN bill_to_name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quote_documents ADD COLUMN bill_to_name TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table in ("quotes", "quote_documents"):
        present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if "bill_to_name" not in present:
            raise sqlite3.DatabaseError(f"Migration v0023 did not add 'bill_to_name' to '{table}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
