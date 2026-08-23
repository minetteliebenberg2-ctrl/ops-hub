"""Migration 0036: add rotation to site_plan_items.

Scoped with Minette 2026-08-12 from a satellite screenshot of
Cavaleros head office: the shade structures follow curved driveways at
half a dozen different angles, but a SitePlanItem could only ever be
axis-aligned, so a drawn box swallowed bays from the row next door.

Degrees, measured in display-pixel space (see core/site_plan_geometry.py
for why fraction space would skew the shape), applied about the
rectangle's centre. Defaulting to 0 leaves every structure she has
already drawn exactly where it is.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 36
NAME = "site_plan_item_rotation"

STATEMENTS = (
    "ALTER TABLE site_plan_items ADD COLUMN rotation REAL NOT NULL DEFAULT 0",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info("site_plan_items")')}
    if "rotation" not in columns:
        raise sqlite3.DatabaseError("Migration v0036 did not add rotation to site_plan_items.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
