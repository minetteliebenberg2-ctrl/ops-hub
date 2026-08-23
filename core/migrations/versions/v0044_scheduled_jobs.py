"""v0044 – scheduled_jobs table for Calendar module."""

from core.migrations.runner import Migration, migration_checksum

VERSION = 44
NAME = "scheduled_jobs"

PAYLOAD = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    site_id TEXT NOT NULL DEFAULT '',
    quote_id TEXT NOT NULL DEFAULT '',
    job_card_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Scheduled',
    start_date TEXT NOT NULL DEFAULT '',
    end_date TEXT NOT NULL DEFAULT '',
    assigned_to TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
)
""".strip()


def apply(connection):
    connection.execute(PAYLOAD)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(scheduled_jobs)")}
    required = {"id", "customer_id", "title", "status", "start_date", "end_date"}
    missing = required - cols
    if missing:
        raise Exception(f"v0044: missing columns on scheduled_jobs: {missing}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
