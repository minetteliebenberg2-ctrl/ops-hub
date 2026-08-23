"""Migration 0029: Job Card - a per-job/PO work log.

Scoped with Minette 2026-08-07 from a real paper form
(C:\\For Claude\\Job Cardvfor PO8295.pdf): a Job Card is tied to
one job/PO, with dated work-log rows added as work happens over
its life. Confirmed:

- One Job Card per job/PO (not one persistent record per Site like
  the Site Plan - core/site_plan.py).
- Numbering follows the SAME yearly per-customer scheme as Quote/
  Pro-Forma/Invoice/Statement (J_26/001 style via
  NumberingService.allocate_yearly), since the header should visually
  match those document types.
- No live billing integration for v1 - her words: "leave amounts
  off". The paper form's REMITTANCE/Amount-Due/Balance section is
  deliberately not modelled here at all.
- No pricing on entries either - this is a work log, not a quote.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 29
NAME = "job_cards"

CREATE_JOB_CARDS = """
CREATE TABLE job_cards (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    job_card_number TEXT NOT NULL,
    purchase_order TEXT NOT NULL DEFAULT '',
    bill_to_name TEXT NOT NULL DEFAULT '',
    delivery_address TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE CASCADE
)
"""

CREATE_JOB_CARD_ENTRIES = """
CREATE TABLE job_card_entries (
    id TEXT PRIMARY KEY,
    job_card_id TEXT NOT NULL,
    entry_date TEXT NOT NULL DEFAULT '',
    work_type TEXT NOT NULL DEFAULT '',
    job_summary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    staff TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    director_signoff TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (job_card_id) REFERENCES job_cards (id) ON DELETE CASCADE
)
"""

INDEXES = (
    "CREATE UNIQUE INDEX idx_job_cards_customer_number ON job_cards (customer_id, job_card_number)",
    "CREATE INDEX idx_job_cards_customer ON job_cards (customer_id)",
    "CREATE INDEX idx_job_cards_site ON job_cards (site_id)",
    "CREATE INDEX idx_job_card_entries_card ON job_card_entries (job_card_id)",
)

STATEMENTS = (CREATE_JOB_CARDS, CREATE_JOB_CARD_ENTRIES) + INDEXES

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "job_cards" not in tables or "job_card_entries" not in tables:
        raise sqlite3.DatabaseError("Migration v0029 did not create the job_cards/job_card_entries tables.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
