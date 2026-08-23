"""Migration 0016: New Net line item types.

Minette flagged that "New Nets" (Single/Double/Triple) weren't
selectable in the Quotes grid's Structure dropdown - deliberately left
out in migration v0011 since new-net pricing is a live formula
(wholesale rate x length + cable + clamps, margin-adjustable), not a
flat rate. She wants them selectable anyway, so this seeds three
line_item_type options with reference Standard/High rates computed
from modules/proposals/netting_quotes.py at the confirmed defaults
(Knittex Z25, 45% margin, cable R500/R550/R600 per net) - these are a
sensible starting Unit Price like every other rate-carrying type in
the Quotes grid, not a replacement for the dedicated Shade Netting
Quotes tool, which stays the source of truth for margin-adjustable,
supplier-compared pricing.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 16
NAME = "new_net_line_item_types"

LIST_NAME = "line_item_type"

# (value, rate_standard_rand, rate_high_rand)
# Standard = Knittex Z25 quote_price at 45% margin (netting_quotes.py
# create_netting_quote). High = flat HIGH_TIER_PRICES (cable included).
NEW_ITEMS = (
    ("New Net - Single", 2524.55, 3200),
    ("New Net - Double", 3382.95, 3500),
    ("New Net - Triple", 4241.35, 4036),
)


def apply(connection):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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


def verify(connection):
    count = connection.execute(
        "SELECT COUNT(*) FROM picklist_options WHERE list_name = ? AND value IN ({})".format(
            ",".join("?" for _ in NEW_ITEMS)
        ),
        (LIST_NAME, *[value for value, _, _ in NEW_ITEMS]),
    ).fetchone()[0]
    if count != len(NEW_ITEMS):
        raise sqlite3.DatabaseError(
            f"Migration v0016 expected {len(NEW_ITEMS)} new '{LIST_NAME}' options, found {count}."
        )


PAYLOAD = "seed:{}:{}".format(LIST_NAME, ",".join(f"{v}:{s}:{h}" for v, s, h in NEW_ITEMS))

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
