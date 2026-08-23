"""Migration 0025: client folder root + Site warranty date.

Mapped out with Minette 2026-08-07 as the foundation for Site Visit:
every real customer gets a real folder on disk
(FC Hub - Clients/[Customer]/{Paperwork,Images,Site Visit,Returned
Documents}), auto-created on save. `clients_root` mirrors
`documents_root` (v0017) exactly - a business_settings column so the
location is configurable (she can point it at OneDrive) without
rewriting anything.

Warranty is "3 years from installation" per her terms and conditions.
She confirmed it belongs on the Site (not a not-yet-built Job/
installation record) - one warranty clock per site, she updates
`warranty_installed_date` by hand when new work goes in. Expiry itself
is computed (installed + 3 years), not stored, matching how quote
totals are computed rather than duplicated.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 25
NAME = "client_folders_and_warranty"

STATEMENTS = (
    "ALTER TABLE business_settings ADD COLUMN clients_root TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE customer_sites ADD COLUMN warranty_installed_date TEXT NOT NULL DEFAULT ''",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    settings_columns = {row[1] for row in connection.execute('PRAGMA table_info("business_settings")')}
    if "clients_root" not in settings_columns:
        raise sqlite3.DatabaseError("Migration v0025 did not add 'clients_root' to 'business_settings'.")

    site_columns = {row[1] for row in connection.execute('PRAGMA table_info("customer_sites")')}
    if "warranty_installed_date" not in site_columns:
        raise sqlite3.DatabaseError("Migration v0025 did not add 'warranty_installed_date' to 'customer_sites'.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
