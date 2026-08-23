"""v0041 – proposals table for persisting proposal documents."""

from core.migrations.runner import Migration, migration_checksum

VERSION = 41
NAME = "proposals"

STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS proposals (
        id            TEXT PRIMARY KEY,
        proposal_date TEXT NOT NULL,
        customer_id   TEXT,
        title         TEXT NOT NULL DEFAULT 'Proposal',
        data_json     TEXT NOT NULL DEFAULT '{}',
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_proposals_customer ON proposals (customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_date ON proposals (proposal_date)",
)

PAYLOAD = "\n;\n".join(s.strip() for s in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='proposals'"
    ).fetchone()
    if not row:
        raise Exception("v0041: proposals table was not created")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
