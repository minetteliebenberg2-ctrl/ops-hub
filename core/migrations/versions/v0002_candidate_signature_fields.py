"""Migration 0002: add signature-extracted fields to communication_candidates."""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 2
NAME = "candidate_signature_fields"

STATEMENTS = (
    "ALTER TABLE communication_candidates ADD COLUMN extracted_phone TEXT",
    "ALTER TABLE communication_candidates ADD COLUMN extracted_website TEXT",
    "ALTER TABLE communication_candidates ADD COLUMN extracted_vat_number TEXT",
    "ALTER TABLE communication_candidates ADD COLUMN extracted_company_name TEXT",
)

NEW_COLUMNS = (
    "extracted_phone",
    "extracted_website",
    "extracted_vat_number",
    "extracted_company_name",
)

PAYLOAD = "\n;\n".join(
    " ".join(statement.split())
    for statement in STATEMENTS
)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    columns = {
        row[1]
        for row in connection.execute(
            'PRAGMA table_info("communication_candidates")'
        )
    }
    missing = set(NEW_COLUMNS) - columns
    if missing:
        raise sqlite3.DatabaseError(
            "Signature field migration failed: missing columns "
            f"{sorted(missing)}."
        )


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
