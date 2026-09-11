"""Migration 0054: add per-quote address printing flags.

Controls which address types (billing, delivery, postal) appear on
the quote PDF. Default: billing only. The user ticks checkboxes on
the quote form to include delivery and/or postal.
"""

from core.migrations.runner import Migration, migration_checksum


VERSION = 54
NAME = "quote_print_address_flags"

PAYLOAD = (
    "ALTER TABLE quotes ADD COLUMN print_billing_address INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE quotes ADD COLUMN print_delivery_address INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE quotes ADD COLUMN print_postal_address INTEGER NOT NULL DEFAULT 0",
)


def apply(connection):
    for sql in PAYLOAD:
        connection.execute(sql)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(quotes)")}
    for col in ("print_billing_address", "print_delivery_address", "print_postal_address"):
        assert col in cols, f"Column {col} missing from quotes"


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum("\n".join(PAYLOAD)),
    apply=apply,
    verify=verify,
)
