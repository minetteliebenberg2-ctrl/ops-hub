"""Migration 0012: Purchase Order number on Quotes and generated documents.

Minette flagged that a client's PO number is missing from Quote/
Pro-Forma/Tax Invoice PDFs. Adds an editable po_number to quotes
(entered once the client supplies it, typically at acceptance) and
snapshots it onto quote_documents at Pro-Forma/Tax Invoice generation
time, the same way quote_documents already snapshots totals - so a
later change to the quote's PO number doesn't silently rewrite a
document that's already gone out.

Not added to statements: a statement can span multiple invoices,
potentially each with a different client PO number, so there's no
single PO number to show at that level.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 12
NAME = "purchase_order_number"

STATEMENTS = (
    "ALTER TABLE quotes ADD COLUMN po_number TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quote_documents ADD COLUMN po_number TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    for table, column in (("quotes", "po_number"), ("quote_documents", "po_number")):
        present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        if column not in present:
            raise sqlite3.DatabaseError(f"Migration v0012 did not add '{column}' to '{table}'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
