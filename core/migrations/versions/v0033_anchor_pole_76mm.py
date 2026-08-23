"""Migration 0033: 76mm anchor pole and clearer wall-thickness notes.

Minette confirmed (2026-08-08) that **76mm is the standard anchor pole**
for Standard/4-post structures, with 101mm used for larger or higher
structures, difficult ground conditions, or an explicit customer spec -
her judgement per job, not something derivable from car-bay count.

v0031 seeded only the 101.6mm and 152mm poles, so the default size had
no price to look up at all. This adds it: Steel & Pipes 76mm round tube
at R419 per 6m length.

Also corrects the 42mm hoop-insert note. It was seeded flagging the
1.9mm wall as "2mm wall not yet confirmed", but Minette confirmed 1.9mm
IS the trade equivalent of 2mm - the same stock, not a placeholder. The
price was always right; only the caveat was wrong.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 33
NAME = "anchor_pole_76mm"

NEW_ITEM = ("Steel", "Anchor Pole 76mm", "Steel & Pipes", "76mm round tube, 1.9mm wall (trade 2mm)", "per 6m", 419.00)

CORRECTED_SPEC = "42mm round tube, 1.9mm wall (trade equivalent of 2mm)"
HOOP_INSERT_NAME = "Hoop Insert Tube 42mm"


def apply(connection):
    # Seed data cleared for the Ops Hub template fork (2026-08-23) — the
    # original figures were FacilitiesCo's real, confirmed supplier
    # prices. Add the new business's own pricing via Settings ->
    # Supplier Pricing. This migration is now a no-op, kept only to
    # preserve the version sequence.
    return


def verify(connection):
    return


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


PAYLOAD = "add:{}:{}:{}:{}\nrespec:{}:{}".format(
    NEW_ITEM[0], NEW_ITEM[1], NEW_ITEM[2], NEW_ITEM[5], HOOP_INSERT_NAME, CORRECTED_SPEC,
)

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
