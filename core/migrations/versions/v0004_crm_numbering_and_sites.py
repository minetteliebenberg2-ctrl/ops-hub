"""Migration 0004: customer numbering and structured site addresses.

Implements CRM_MODULE_SPECIFICATION.md section 8, migration v0004:

- Creates ``numbering_sequences`` (master spec 5.5) and uses it to allocate
  a ``FAC-###`` customer_number to every existing customer, continuing the
  same sequence future customers will draw from at runtime.
- Adds ``payment_terms`` to customers (``Standard`` 65/35 deposit/balance,
  or ``Netting`` 100% upfront, confirmed 2026-07-28).
- Adds a structured ``address_id`` to customer_sites, backfilling one
  ``customer_addresses`` row per existing site from its legacy free-text
  address/city/province (address_type='Site'). The legacy columns are kept,
  frozen, per the section-12 decision to freeze now and drop later once the
  backfill is confirmed correct against production data.

No site_number is added. Minette confirmed (2026-07-28) that a formatted
per-site number is not needed: multiple installation sites for one customer
(e.g. a landlord with several tenanted properties) commonly share one
billing address, and distinguishing sites is handled by their own
structured address, not a separate identifier. This is a deliberate
reduction in scope from the original CRM_MODULE_SPECIFICATION.md section
4.4/5, which proposed a site_number; the spec is amended accordingly.

Deliberate deviation from the specification's literal "NOT NULL" wording:
``customers.customer_number`` and ``customer_sites.address_id`` are added
as nullable columns backed by a UNIQUE index (customer_number) and an
inline ``REFERENCES`` clause (address_id), not a rebuilt table with a hard
NOT NULL constraint. Testing this migration against a copy of the schema
showed that SQLite's ``ON DELETE CASCADE`` fires on ``DROP TABLE`` of the
referenced parent, so rebuilding ``customers`` (or a second rebuild of
``customer_sites``) the way v0003 rebuilt tables with no incoming foreign
keys would cascade-delete every contact, address, site, and activity row.
Uniqueness and the foreign key are still enforced by SQLite; "always
populated" is guaranteed by the service layer, which allocates the number
in the same transaction as every insert.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 4
NAME = "crm_numbering_and_sites"

CUSTOMER_PREFIX = "FAC"
CUSTOMER_PADDING = 3

CREATE_NUMBERING_SEQUENCES = """
CREATE TABLE numbering_sequences (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL DEFAULT '',
    prefix TEXT NOT NULL,
    padding INTEGER NOT NULL,
    next_value INTEGER NOT NULL,
    yearly_reset INTEGER NOT NULL DEFAULT 0,
    last_reset_year INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (document_type, scope, scope_id)
)
"""

ADDITIVE_STATEMENTS = (
    CREATE_NUMBERING_SEQUENCES,
    "ALTER TABLE customers ADD COLUMN customer_number TEXT",
    "ALTER TABLE customers ADD COLUMN payment_terms TEXT NOT NULL DEFAULT 'Standard'",
    "ALTER TABLE customer_sites ADD COLUMN address_id TEXT REFERENCES customer_addresses (id)",
)

INDEX_STATEMENTS = (
    "CREATE UNIQUE INDEX idx_customers_customer_number ON customers (customer_number)",
    "CREATE INDEX idx_customer_sites_address ON customer_sites (address_id)",
)

PAYLOAD = "\n;\n".join(
    " ".join(statement.split())
    for statement in ADDITIVE_STATEMENTS + INDEX_STATEMENTS
)


def apply(connection):
    for statement in ADDITIVE_STATEMENTS:
        connection.execute(statement)

    _backfill_customer_numbers(connection)
    _backfill_site_addresses(connection)

    for statement in INDEX_STATEMENTS:
        connection.execute(statement)


def _backfill_customer_numbers(connection):
    now = _timestamp()
    customers = connection.execute(
        "SELECT id FROM customers ORDER BY created_at, id"
    ).fetchall()

    for index, row in enumerate(customers, start=1):
        number = f"{CUSTOMER_PREFIX}-{index:0{CUSTOMER_PADDING}d}"
        connection.execute(
            "UPDATE customers SET customer_number = ? WHERE id = ?",
            (number, row["id"]),
        )

    connection.execute(
        """
        INSERT INTO numbering_sequences (
            id, document_type, scope, scope_id, prefix, padding,
            next_value, yearly_reset, last_reset_year, created_at, updated_at
        )
        VALUES (?, 'customer', 'global', '', ?, ?, ?, 0, NULL, ?, ?)
        """,
        (
            str(uuid4()), CUSTOMER_PREFIX, CUSTOMER_PADDING,
            len(customers) + 1, now, now,
        ),
    )


def _backfill_site_addresses(connection):
    for site in connection.execute("SELECT * FROM customer_sites").fetchall():
        address_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO customer_addresses (
                id, customer_id, address_type, line1, line2, city,
                province, postal_code, country, is_primary,
                created_at, updated_at
            )
            VALUES (?, ?, 'Site', ?, '', ?, ?, '', '', 0, ?, ?)
            """,
            (
                address_id, site["customer_id"], site["address"], site["city"],
                site["province"], site["created_at"], site["updated_at"],
            ),
        )
        connection.execute(
            "UPDATE customer_sites SET address_id = ? WHERE id = ?",
            (address_id, site["id"]),
        )


def verify(connection):
    _verify_columns(connection, "customers", ("customer_number", "payment_terms"))
    _verify_columns(connection, "customer_sites", ("address_id",))

    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'numbering_sequences'"
    ).fetchone()
    if not exists:
        raise sqlite3.DatabaseError("numbering_sequences table was not created.")

    total_customers, numbered_customers, distinct_numbers = connection.execute(
        """
        SELECT COUNT(*),
               COUNT(customer_number),
               COUNT(DISTINCT customer_number)
        FROM customers
        """
    ).fetchone()
    if not (total_customers == numbered_customers == distinct_numbers):
        raise sqlite3.DatabaseError(
            "Every existing customer must have a unique customer_number after migration v0004."
        )

    unresolved_sites = connection.execute(
        """
        SELECT COUNT(*)
        FROM customer_sites
        WHERE address_id IS NULL
           OR address_id NOT IN (SELECT id FROM customer_addresses)
        """
    ).fetchone()[0]
    if unresolved_sites:
        raise sqlite3.DatabaseError(
            "Every existing site must resolve to a structured address after migration v0004."
        )

    sequence_next_value = connection.execute(
        """
        SELECT next_value FROM numbering_sequences
        WHERE document_type = 'customer' AND scope = 'global'
        """
    ).fetchone()
    if sequence_next_value is None or sequence_next_value[0] != total_customers + 1:
        raise sqlite3.DatabaseError(
            "numbering_sequences customer counter does not match the backfilled customer count."
        )


def _verify_columns(connection, table, columns):
    present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    missing = set(columns) - present
    if missing:
        raise sqlite3.DatabaseError(
            f"CRM numbering migration failed: '{table}' is missing columns {sorted(missing)}."
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
