"""Migration 0037: remember which grid template a Site Plan uses.

Most of Minette's sites are car parks - wide, not tall - but the only
built-in template was a portrait measurement sheet, which wasted more
than half the drawing canvas. "Use Grid Template" now toggles between
portrait and landscape, so the choice has to survive closing the
window (asked for 2026-08-12).

Only meaningful while the plan has no uploaded backdrop of her own;
an uploaded satellite screenshot brings its own dimensions.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 37
NAME = "site_plan_grid_orientation"

STATEMENTS = (
    "ALTER TABLE site_plans ADD COLUMN grid_orientation TEXT NOT NULL DEFAULT 'portrait'",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info("site_plans")')}
    if "grid_orientation" not in columns:
        raise sqlite3.DatabaseError("Migration v0037 did not add grid_orientation to site_plans.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
