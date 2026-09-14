"""Migration 0056: user-configurable document/certificate categories.

Seeds a new 'document_category' picklist (same picklist_options table
already used for payment_terms/customer_type/line_item_type) so Minette
can add, rename, or delete document category types herself from Settings
instead of them being fixed in code. Used everywhere a document gets
filed — the Documents module's compliance library and the Annual
Compliance "Upload Certificate" flow both read from this one list.

Seeded with the categories already hardcoded in modules/documents and
the certificate types used by Annual Compliance, so nothing that already
existed moves or disappears on upgrade.

Renaming or deleting a category never rewrites historical documents rows
- documents.category stores the value text at the time it was filed, not
a foreign key, so a later rename/delete does not change what a past
document says (matches the existing picklist convention).
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 56
NAME = "document_category_picklist"

LIST_NAME = "document_category"

SEED = (
    "Compliance",
    "Letters",
    "Banking",
    "Insurance",
    "LOGS Certificate",
    "ROE Confirmation",
    "COIDA Letter of Good Standing",
    "Safety File",
    "Other",
)

PAYLOAD = "\n".join(SEED)


def apply(connection: sqlite3.Connection) -> None:
    now = _timestamp()
    for sort_order, value in enumerate(SEED, start=1):
        connection.execute(
            """
            INSERT INTO picklist_options (
                id, list_name, value, sort_order, is_active,
                created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, '')
            ON CONFLICT(list_name, value) DO NOTHING
            """,
            (str(uuid4()), LIST_NAME, value, sort_order, now, now),
        )


def verify(connection: sqlite3.Connection) -> bool:
    count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = ?", (LIST_NAME,)
    ).fetchone()[0]
    return count >= len(SEED)


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
