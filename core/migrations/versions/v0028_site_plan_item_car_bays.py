"""Migration 0028: add car_bays to site_plan_items.

Follow-up from Minette testing the Site Plan canvas (2026-08-07): the
"New Structure" form had no size field at all, but real Cantilever/
Standard structures need one - confirmed she wants it to reuse the
SAME Car Bay concept already used in the main Quotes grid
(core/structure_catalog.py), not new named picklist variants like
Netting's "New Net - Single/Double/Triple". Mirrors
QuoteLineItem.car_bays exactly.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 28
NAME = "site_plan_item_car_bays"

STATEMENTS = (
    "ALTER TABLE site_plan_items ADD COLUMN car_bays INTEGER",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info("site_plan_items")')}
    if "car_bays" not in columns:
        raise sqlite3.DatabaseError("Migration v0028 did not add car_bays to site_plan_items.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
