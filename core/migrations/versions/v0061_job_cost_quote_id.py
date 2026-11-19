"""Migration v0061 — Allow job cost allocations against quotes

Adds quote_id column so accepted quotes without job cards can still
have cost allocations tracked against them.  job_card_id becomes nullable.
"""

from core.migrations.runner import Migration, migration_checksum

VERSION = 61
NAME = "job_cost_quote_id"

SQL = """\
ALTER TABLE job_cost_allocations ADD COLUMN quote_id TEXT DEFAULT '';
"""

PAYLOAD = SQL


def apply(connection):
    for stmt in SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            connection.execute(stmt)


def verify(connection):
    cols = {
        row[1]
        for row in connection.execute('PRAGMA table_info("job_cost_allocations")')
    }
    assert "quote_id" in cols, "quote_id column missing"


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
