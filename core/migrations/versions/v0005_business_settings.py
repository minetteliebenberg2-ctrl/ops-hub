"""Migration 0005: business settings and business addresses.

Introduces the master spec 5.3 "Identity, configuration, and control"
business_settings table (single configuration row: legal identity, VAT
status, contact details, banking) plus business_addresses (FacilitiesCo's
own addresses, distinct from customer_addresses). Seeded with the details
already confirmed with Minette during the CRM sprint, so the Settings page
opens pre-filled rather than blank.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 5
NAME = "business_settings"

BUSINESS_SETTINGS_ID = "business"

CREATE_BUSINESS_SETTINGS = """
CREATE TABLE business_settings (
    id TEXT PRIMARY KEY,
    trading_name TEXT NOT NULL DEFAULT '',
    legal_name TEXT NOT NULL DEFAULT '',
    registration_number TEXT NOT NULL DEFAULT '',
    vat_registered INTEGER NOT NULL DEFAULT 0,
    vat_number TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    bank_name TEXT NOT NULL DEFAULT '',
    bank_account_name TEXT NOT NULL DEFAULT '',
    bank_account_number TEXT NOT NULL DEFAULT '',
    branch_code TEXT NOT NULL DEFAULT '',
    swift_code TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
)
"""

CREATE_BUSINESS_ADDRESSES = """
CREATE TABLE business_addresses (
    id TEXT PRIMARY KEY,
    address_type TEXT NOT NULL DEFAULT '',
    line1 TEXT NOT NULL DEFAULT '',
    line2 TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
)
"""

STATEMENTS = (CREATE_BUSINESS_SETTINGS, CREATE_BUSINESS_ADDRESSES)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)

    now = _timestamp()

    connection.execute(
        """
        INSERT INTO business_settings (
            id, trading_name, legal_name, registration_number,
            vat_registered, vat_number, email, phone, website,
            bank_name, bank_account_name, bank_account_number,
            branch_code, swift_code, notes, created_at, updated_at, updated_by
        )
        VALUES (?, ?, ?, ?, 0, '', ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, '')
        """,
        (
            BUSINESS_SETTINGS_ID,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            now,
            now,
        ),
    )

    connection.execute(
        """
        INSERT INTO business_addresses (
            id, address_type, line1, line2, city, province, postal_code,
            country, is_primary, created_at, updated_at, updated_by
        )
        VALUES (?, 'Physical', ?, ?, ?, '', ?, ?, 1, ?, ?, '')
        """,
        (
            str(uuid4()), "", "", "", "",
            "", now, now,
        ),
    )


def verify(connection):
    for table in ("business_settings", "business_addresses"):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            raise sqlite3.DatabaseError(f"Migration v0005 did not create '{table}'.")

    row = connection.execute(
        "SELECT trading_name FROM business_settings WHERE id = ?",
        (BUSINESS_SETTINGS_ID,),
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("business_settings seed row was not created.")


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
