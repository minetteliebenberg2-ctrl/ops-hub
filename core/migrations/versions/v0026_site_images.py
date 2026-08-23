"""Migration 0026: real site_images table.

Site Visit Phase 2, mapped out with Minette 2026-08-07. Photos are
taken at ~99% of her site visits. Confirmed: auto rename, resize
for web, and structured tagging (caption now; linked to a specific
site-plan structure once Phase 3 exists - no structure_id column yet,
there is nothing to reference until that table exists). Images are
prepared for her to upload to her own website herself - FC Hub does
not publish/host them anywhere web-reachable.

Physical files live under the customer's own client folder
(ClientFolderService, migration v0025) - `stored_filename` here is a
name inside that customer's Images subfolder, not an absolute path,
matching the documents_root/site_visits precedent.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 26
NAME = "site_images"

CREATE_SITE_IMAGES = """
CREATE TABLE site_images (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    site_id TEXT,
    site_visit_id TEXT,
    stored_filename TEXT NOT NULL,
    original_filename TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    taken_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE SET NULL,
    FOREIGN KEY (site_visit_id) REFERENCES site_visits (id) ON DELETE SET NULL
)
"""

CREATE_INDEX = "CREATE INDEX idx_site_images_customer ON site_images (customer_id)"

STATEMENTS = (CREATE_SITE_IMAGES, CREATE_INDEX)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    present = {row[1] for row in connection.execute('PRAGMA table_info("site_images")')}
    required = {"customer_id", "site_id", "site_visit_id", "stored_filename", "caption", "width", "height", "taken_at"}
    if not required.issubset(present):
        raise sqlite3.DatabaseError("Migration v0026 did not create 'site_images' as expected.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
