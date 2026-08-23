"""Migration 0011: real maintenance line item types with Standard/High rates.

v0009 seeded two placeholder line_item_type options ("Maintenance",
"Custom / Other Request") just so the dropdown wasn't empty. This
replaces "Maintenance" with the real, already-in-production tier
pricing from modules/proposals/netting_quotes.py's MAINTENANCE_ITEMS
(built and tested against actual Cavaleros quotes 2026-08-03) - Refit
Net, Restitch Net, Retensioning, Replace Cable, Repaint Structure, plus
a flat Transport/Call-out rate. These prices already include margin -
nothing further should be added on top in the Quotes module.

New nets (Knittex/Plusnet, by length + margin) are deliberately NOT
seeded here - that pricing is a live formula (wholesale rate x length +
cable + clamps, margin-adjustable per quote), already correctly served
by the "Shade Netting Quotes" tool in Proposals. Flattening it into a
static rate here would go stale and lose margin control.

Deactivates the "Maintenance" placeholder now that it's superseded -
deactivating rather than deleting so any quote line item already using
it keeps its stored value. "Custom / Other Request" stays active as
the true catch-all.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 11
NAME = "maintenance_line_item_types"

LIST_NAME = "line_item_type"
DEACTIVATED_VALUE = "Maintenance"

# (value, rate_standard_rand, rate_high_rand)
NEW_ITEMS = (
    ("Refit Net", 450, 513),
    ("Restitch Net", 1750, 1775),
    ("Retensioning", 375, 420),
    ("Replace Cable", 500, 600),
    ("Repaint Structure", 1500, 1750),
    ("Transport / Call-out", 600, 600),
)


NEW_COLUMNS = (
    "ALTER TABLE picklist_options ADD COLUMN rate_low_minor INTEGER",
    "ALTER TABLE picklist_options ADD COLUMN rate_standard_minor INTEGER",
    "ALTER TABLE picklist_options ADD COLUMN rate_high_minor INTEGER",
)


def apply(connection):
    for statement in NEW_COLUMNS:
        connection.execute(statement)

    now = _timestamp()

    next_sort_order = connection.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM picklist_options WHERE list_name = ?",
        (LIST_NAME,),
    ).fetchone()[0]

    for offset, (value, standard, high) in enumerate(NEW_ITEMS, start=1):
        connection.execute(
            """
            INSERT INTO picklist_options (
                id, list_name, value, deposit_percentage, balance_percentage,
                rate_low_minor, rate_standard_minor, rate_high_minor,
                sort_order, is_active, created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, NULL, NULL, NULL, ?, ?, ?, 1, ?, ?, 'system')
            """,
            (
                str(uuid4()), LIST_NAME, value,
                round(standard * 100), round(high * 100),
                next_sort_order + offset, now, now,
            ),
        )

    connection.execute(
        """
        UPDATE picklist_options
        SET is_active = 0, updated_at = ?, updated_by = 'system'
        WHERE list_name = ? AND value = ?
        """,
        (now, LIST_NAME, DEACTIVATED_VALUE),
    )


def verify(connection):
    present = {row[1] for row in connection.execute('PRAGMA table_info("picklist_options")')}
    missing = {"rate_low_minor", "rate_standard_minor", "rate_high_minor"} - present
    if missing:
        raise sqlite3.DatabaseError(f"Migration v0011 did not add columns {sorted(missing)} to picklist_options.")

    count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = ? AND value IN ({})".format(
            ",".join("?" for _ in NEW_ITEMS)
        ),
        (LIST_NAME, *[value for value, _, _ in NEW_ITEMS]),
    ).fetchone()[0]
    if count != len(NEW_ITEMS):
        raise sqlite3.DatabaseError(
            f"Migration v0011 expected {len(NEW_ITEMS)} new '{LIST_NAME}' options, found {count}."
        )

    is_active = connection.execute(
        "SELECT is_active FROM picklist_options WHERE list_name = ? AND value = ?",
        (LIST_NAME, DEACTIVATED_VALUE),
    ).fetchone()
    if is_active is not None and is_active[0] != 0:
        raise sqlite3.DatabaseError(
            f"Migration v0011 expected '{DEACTIVATED_VALUE}' to be deactivated."
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


PAYLOAD = "\n;\n".join(" ".join(s.split()) for s in NEW_COLUMNS) + "\nseed:{}:{}:deactivate:{}".format(
    LIST_NAME,
    ",".join(f"{v}:{s}:{h}" for v, s, h in NEW_ITEMS),
    DEACTIVATED_VALUE,
)

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
