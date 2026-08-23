"""v0039 – delete child rows whose parent customer was removed.

These orphans are left over from the PDF-import test-data wipe.
FK violations are harmless to the running app but the troubleshooter
flags them, so clean them up.
"""

from core.migrations.runner import Migration, migration_checksum

VERSION = 39
NAME = "purge_orphaned_child_rows"

STATEMENTS = (
    # customer_sites references customer_addresses (FK address_id); delete
    # sites first so the address rows are no longer referenced.
    "DELETE FROM customer_sites     WHERE customer_id NOT IN (SELECT id FROM customers)",
    "DELETE FROM customer_addresses WHERE customer_id NOT IN (SELECT id FROM customers)",
    "DELETE FROM customer_contacts  WHERE customer_id NOT IN (SELECT id FROM customers)",
    # site_images and site_visits have a direct customer_id FK too.
    "DELETE FROM site_images        WHERE customer_id NOT IN (SELECT id FROM customers)",
    "DELETE FROM site_visits        WHERE customer_id NOT IN (SELECT id FROM customers)",
)

PAYLOAD = "\n;\n".join(s.strip() for s in STATEMENTS)


def apply(connection):
    # Temporarily disable FK checks so we can delete in any order.
    # We're removing rows whose parent doesn't exist (safe); we're not
    # creating new violations.
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        for statement in STATEMENTS:
            connection.execute(statement)
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def verify(connection):
    tables = [
        ("customer_addresses", "customer_id"),
        ("customer_contacts",  "customer_id"),
        ("customer_sites",     "customer_id"),
        ("site_images",        "customer_id"),
        ("site_visits",        "customer_id"),
    ]
    for table, col in tables:
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} NOT IN (SELECT id FROM customers)"
        ).fetchone()[0]
        if count:
            raise Exception(f"v0039: {count} orphaned rows remain in {table}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
