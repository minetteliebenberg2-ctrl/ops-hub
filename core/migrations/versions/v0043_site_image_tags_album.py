"""v0043 – tags and album columns on site_images, for Gallery module."""

from core.migrations.runner import Migration, migration_checksum

VERSION = 43
NAME = "site_image_tags_album"

STATEMENTS = (
    "ALTER TABLE site_images ADD COLUMN tags TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE site_images ADD COLUMN album TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(s.strip() for s in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(site_images)")}
    missing = {"tags", "album"} - cols
    if missing:
        raise Exception(f"v0043: missing columns on site_images: {missing}")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
