"""Migration 0024: real site_visits table.

Site Visit (modules/site_visit) was pure UI wireframe - every
meaningful button ("Add Measurements", "Start Checklist", "Complete")
just showed a "(placeholder)" message box, and its SiteVisitService
kept everything in an in-memory dict, lost on window close. Minette
confirmed (2026-08-07) a small real first pass: schedule a visit
against a real customer/site, see a real list, mark it complete.
Deliberately minimal - no measurements/checklist/photos/sign-off yet
(deferred to a dedicated future session, see the workflow-audit
memory), no job_id (that's the separate, also-unbuilt Calendar/Jobs
concept).
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 24
NAME = "site_visits"

CREATE_SITE_VISITS = """
CREATE TABLE site_visits (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    site_id TEXT,
    visit_date TEXT NOT NULL DEFAULT '',
    visit_time TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Scheduled',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE SET NULL
)
"""

CREATE_INDEX = "CREATE INDEX idx_site_visits_customer ON site_visits (customer_id)"

STATEMENTS = (CREATE_SITE_VISITS, CREATE_INDEX)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    present = {row[1] for row in connection.execute('PRAGMA table_info("site_visits")')}
    required = {"customer_id", "site_id", "visit_date", "visit_time", "notes", "status"}
    if not required.issubset(present):
        raise sqlite3.DatabaseError("Migration v0024 did not create 'site_visits' as expected.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
