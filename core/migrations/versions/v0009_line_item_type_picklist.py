"""Migration 0009: configurable line item types.

Quote line items were limited to the three hardcoded structure types
(Cantilever, Standard, Shade Sail). Minette needs to add other kinds of
line item herself - maintenance call-outs, one-off client requests -
without a code change, the same way payment_terms and customer_type
are already user-managed via picklist_options (migration v0006).

Seeds the existing three structure types (so no existing quote's
dropdown value goes missing) plus two general-purpose starting points
she can rename/extend from Settings.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 9
NAME = "line_item_type_picklist"

LIST_NAME = "line_item_type"
SEED_VALUES = ("Cantilever", "Standard", "Shade Sail", "Maintenance", "Custom / Other Request")


def apply(connection):
    now = _timestamp()
    for index, value in enumerate(SEED_VALUES, start=1):
        connection.execute(
            """
            INSERT INTO picklist_options (
                id, list_name, value, deposit_percentage, balance_percentage,
                sort_order, is_active, created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, NULL, NULL, ?, 1, ?, ?, 'system')
            """,
            (str(uuid4()), LIST_NAME, value, index, now, now),
        )


def verify(connection):
    count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = ?",
        (LIST_NAME,),
    ).fetchone()[0]
    if count != len(SEED_VALUES):
        raise sqlite3.DatabaseError(
            f"Migration v0009 expected {len(SEED_VALUES)} '{LIST_NAME}' picklist options, found {count}."
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


PAYLOAD = f"seed:{LIST_NAME}:{','.join(SEED_VALUES)}"

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
