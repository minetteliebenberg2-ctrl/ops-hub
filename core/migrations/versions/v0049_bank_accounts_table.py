from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
CREATE TABLE IF NOT EXISTS bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO bank_accounts (name)
    SELECT DISTINCT account FROM ledger_transactions
    WHERE account != '' AND account IS NOT NULL;
"""


def apply(connection):
    for statement in PAYLOAD.strip().split(";"):
        sql = statement.strip()
        if sql:
            connection.execute(sql)


def verify(connection):
    row = connection.execute(
        "SELECT COUNT(*) FROM bank_accounts"
    ).fetchone()
    assert row[0] >= 0, "bank_accounts table not created"


MIGRATION = Migration(
    version=49,
    name="bank_accounts_table",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
