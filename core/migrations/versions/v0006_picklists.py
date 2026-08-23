"""Migration 0006: user-configurable picklists.

Introduces picklist_options: a general-purpose reference-data table so
Minette can add, rename, or retire options herself from Settings, rather
than values being fixed in code. First consumers: payment_terms (with
real deposit/balance percentages she controls) and customer_type.

Renaming or retiring an option never rewrites historical customer rows -
customers.payment_terms/customer_type store the option's value text at the
time it was chosen, not a foreign key, so a later rename does not silently
change what a past customer record says.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 6
NAME = "picklists"

CREATE_PICKLIST_OPTIONS = """
CREATE TABLE picklist_options (
    id TEXT PRIMARY KEY,
    list_name TEXT NOT NULL,
    value TEXT NOT NULL,
    deposit_percentage REAL,
    balance_percentage REAL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    UNIQUE (list_name, value)
)
"""

INDEX_STATEMENT = "CREATE INDEX idx_picklist_options_list ON picklist_options (list_name)"

STATEMENTS = (CREATE_PICKLIST_OPTIONS, INDEX_STATEMENT)

PAYMENT_TERMS_SEED = (
    ("Standard", 65.0, 35.0, 1),
    ("Netting", 100.0, 0.0, 2),
)

CUSTOMER_TYPE_SEED = (
    ("Commercial", None, None, 1),
    ("Residential", None, None, 2),
    ("Body Corporate", None, None, 3),
    ("Government", None, None, 4),
    ("Other", None, None, 5),
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)

    now = _timestamp()

    for value, deposit, balance, sort_order in PAYMENT_TERMS_SEED:
        _insert(connection, "payment_terms", value, deposit, balance, sort_order, now)

    for value, deposit, balance, sort_order in CUSTOMER_TYPE_SEED:
        _insert(connection, "customer_type", value, deposit, balance, sort_order, now)


def _insert(connection, list_name, value, deposit, balance, sort_order, now):
    connection.execute(
        """
        INSERT INTO picklist_options (
            id, list_name, value, deposit_percentage, balance_percentage,
            sort_order, is_active, created_at, updated_at, updated_by
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, '')
        """,
        (str(uuid4()), list_name, value, deposit, balance, sort_order, now, now),
    )


def verify(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'picklist_options'"
    ).fetchone()
    if not exists:
        raise sqlite3.DatabaseError("Migration v0006 did not create 'picklist_options'.")

    payment_terms_count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = 'payment_terms'"
    ).fetchone()[0]
    if payment_terms_count < 2:
        raise sqlite3.DatabaseError("payment_terms picklist seed did not apply.")

    customer_type_count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = 'customer_type'"
    ).fetchone()[0]
    if customer_type_count < 5:
        raise sqlite3.DatabaseError("customer_type picklist seed did not apply.")


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
