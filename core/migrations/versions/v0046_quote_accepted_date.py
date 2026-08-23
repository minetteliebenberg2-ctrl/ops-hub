from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
ALTER TABLE quotes ADD COLUMN accepted_date TEXT DEFAULT '';
"""


def apply(conn):
    for stmt in PAYLOAD.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def verify(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(quotes)").fetchall()]
    return "accepted_date" in cols


MIGRATION = Migration(
    version=46,
    name="quote_accepted_date",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
