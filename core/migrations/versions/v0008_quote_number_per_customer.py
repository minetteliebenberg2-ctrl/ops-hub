"""Migration 0008: quote numbers unique per customer, not globally.

The Quote/Pro-Forma/Invoice/Statement numbering scheme was changed
(confirmed by Minette 2026-08-03) from a flat, globally-unique
FAC-001-Q-001 pattern to a per-customer, per-year pattern like
Q_26/001 (see core.numbering_service.NumberingService.allocate_yearly
and the "Master doc per client" plan). The customer number is no
longer embedded in the string, so different customers can legitimately
share the same quote_number (each client's numbers reset from 001 each
year, like the Excel workbook they're replacing) - quote_number only
needs to stay unique *within* a customer, not across the whole table.

Drops the old global-unique index and replaces it with a composite
unique index on (customer_id, quote_number).
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 8
NAME = "quote_number_per_customer"

STATEMENTS = (
    "DROP INDEX IF EXISTS idx_quotes_quote_number",
    "CREATE UNIQUE INDEX idx_quotes_quote_number ON quotes (customer_id, quote_number)",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    index = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_quotes_quote_number'"
    ).fetchone()
    if index is None:
        raise sqlite3.DatabaseError("Migration v0008 did not create idx_quotes_quote_number.")
    if "customer_id" not in index["sql"]:
        raise sqlite3.DatabaseError(
            "idx_quotes_quote_number must be scoped to (customer_id, quote_number) after migration v0008."
        )


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
