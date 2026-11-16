"""Migration v0059 — plain_invoice flag on quotes

Adds a per-quote boolean so invoices can say "Invoice" instead of
"Tax Invoice" for clients who request it.
"""

from core.migrations.runner import Migration, migration_checksum

VERSION = 59
NAME = "plain_invoice"

SQL = "ALTER TABLE quotes ADD COLUMN plain_invoice INTEGER NOT NULL DEFAULT 0"


def apply(connection):
    connection.execute(SQL)


def verify(connection):
    row = connection.execute(
        "SELECT plain_invoice FROM quotes LIMIT 1"
    ).fetchone()
    return True


PAYLOAD = SQL

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
