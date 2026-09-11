"""Migration 0052: add net_measurements_json to site_plan_items.

Per-structure net measurements (back, left, right, front, diagonal in mm)
stored as a JSON blob — reference-only, NOT used for pricing.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 52
NAME = "site_plan_net_measurements"

STATEMENTS = (
    "ALTER TABLE site_plan_items ADD COLUMN net_measurements_json TEXT NOT NULL DEFAULT '{}'",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info("site_plan_items")')}
    if "net_measurements_json" not in columns:
        raise sqlite3.DatabaseError("Migration v0052 did not add net_measurements_json to site_plan_items.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
