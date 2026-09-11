"""Migration v0050 — no-op placeholder.

bank_accounts table was already created in v0049 for Ops Hub.
This migration keeps the version sequence contiguous.
"""

from core.migrations.runner import Migration, migration_checksum

VERSION = 50
NAME = "bank_accounts_noop"
PAYLOAD = "SELECT 1"


def apply(connection):
    pass


def verify(connection):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='bank_accounts'"
    ).fetchone()
    return row is not None


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
