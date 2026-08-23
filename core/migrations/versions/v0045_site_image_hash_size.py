from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
ALTER TABLE site_images ADD COLUMN file_hash TEXT DEFAULT '';
ALTER TABLE site_images ADD COLUMN file_size INTEGER DEFAULT 0;
"""


def apply(conn):
    for stmt in PAYLOAD.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def verify(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(site_images)").fetchall()]
    return "file_hash" in cols and "file_size" in cols


MIGRATION = Migration(
    version=45,
    name="site_image_hash_size",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
