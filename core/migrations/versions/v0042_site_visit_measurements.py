"""v0042 – measurements_json and checklist_json columns on site_visits."""

from core.migrations.runner import Migration, migration_checksum

VERSION = 42
NAME = "site_visit_measurements"

STATEMENTS = (
    "ALTER TABLE site_visits ADD COLUMN measurements_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE site_visits ADD COLUMN checklist_json TEXT NOT NULL DEFAULT '{}'",
)

PAYLOAD = "\n;\n".join(s.strip() for s in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(site_visits)")}
    missing = {"measurements_json", "checklist_json"} - cols
    if missing:
        raise Exception(f"v0042: missing columns on site_visits: {missing}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
