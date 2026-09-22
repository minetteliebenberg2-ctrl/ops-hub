"""Migration 0057: split deposit / balance Tax Invoices.

quotes.split_invoice   - per-quote tick box, default OFF (0).
quote_documents.invoice_part - '' (normal), 'deposit' or 'balance'.
"""

from core.migrations.runner import Migration, migration_checksum


VERSION = 57
NAME = "split_invoice"

PAYLOAD = (
    "ALTER TABLE quotes ADD COLUMN split_invoice INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE quote_documents ADD COLUMN invoice_part TEXT NOT NULL DEFAULT ''",
)


def apply(connection):
    for sql in PAYLOAD:
        connection.execute(sql)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(quotes)")}
    assert "split_invoice" in cols, "Column split_invoice missing from quotes"
    cols = {row[1] for row in connection.execute("PRAGMA table_info(quote_documents)")}
    assert "invoice_part" in cols, "Column invoice_part missing from quote_documents"


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum("\n".join(PAYLOAD)),
    apply=apply,
    verify=verify,
)
