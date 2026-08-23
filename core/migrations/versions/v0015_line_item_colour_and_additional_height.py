"""Migration 0015: line item colour, and Additional Height as its own type.

Minette wants a single selectable Colour per line item (covering both
netting colour and paint colour - she'd rather combine them into one
column than run two), and wants the per-row Height field removed from
the Quotes grid entirely: any charge for height above the 2.1m standard
should be its own line item ("Additional Height"), not a field tucked
onto a structure row.

Adds quote_line_items.colour (free text - Knittex/paint colour names
are offered as suggestions in the UI, but nothing stops a custom
colour name). Also seeds "Additional Height" into the line_item_type
picklist (no rate - the upcharge for height above 2.1m is priced
per-job, not a flat rate card item, per structure_catalog.md).
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 15
NAME = "line_item_colour_and_additional_height"

LIST_NAME = "line_item_type"
NEW_VALUE = "Additional Height"


def apply(connection):
    connection.execute("ALTER TABLE quote_line_items ADD COLUMN colour TEXT NOT NULL DEFAULT ''")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    next_sort_order = connection.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM picklist_options WHERE list_name = ?",
        (LIST_NAME,),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO picklist_options (
            id, list_name, value, deposit_percentage, balance_percentage,
            rate_low_minor, rate_standard_minor, rate_high_minor,
            sort_order, is_active, created_at, updated_at, updated_by
        )
        VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, 1, ?, ?, 'system')
        """,
        (str(uuid4()), LIST_NAME, NEW_VALUE, next_sort_order + 1, now, now),
    )


def verify(connection):
    present = {row[1] for row in connection.execute('PRAGMA table_info("quote_line_items")')}
    if "colour" not in present:
        raise sqlite3.DatabaseError("Migration v0015 did not add 'colour' to quote_line_items.")

    count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = ? AND value = ?",
        (LIST_NAME, NEW_VALUE),
    ).fetchone()[0]
    if count != 1:
        raise sqlite3.DatabaseError(f"Migration v0015 expected exactly one '{NEW_VALUE}' option, found {count}.")


PAYLOAD = f"add_column:quote_line_items.colour;seed:{LIST_NAME}:{NEW_VALUE}"

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
