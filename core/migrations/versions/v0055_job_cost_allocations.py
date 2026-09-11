"""Migration v0055 — Job Cost Allocations

Adds a table for allocating ledger transactions (bank imports) and
payments to job cards, so Minette can see actual revenue and spend
per job and calculate real GP.
"""

from core.migrations.runner import Migration, migration_checksum

VERSION = 55
NAME = "job_cost_allocations"

CREATE_TABLE = """
CREATE TABLE job_cost_allocations (
    id TEXT PRIMARY KEY,
    job_card_id TEXT NOT NULL REFERENCES job_cards (id),
    ledger_transaction_id TEXT REFERENCES ledger_transactions (id),
    allocation_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    amount_minor INTEGER NOT NULL,
    cost_bucket TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
)
"""

IDX_JOB = "CREATE INDEX idx_jca_job ON job_cost_allocations (job_card_id)"
IDX_LEDGER = "CREATE INDEX idx_jca_ledger ON job_cost_allocations (ledger_transaction_id)"

STATEMENTS = (CREATE_TABLE, IDX_JOB, IDX_LEDGER)
PAYLOAD = "\n;\n".join(" ".join(s.split()) for s in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    cursor = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='job_cost_allocations'"
    )
    return cursor.fetchone() is not None


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
