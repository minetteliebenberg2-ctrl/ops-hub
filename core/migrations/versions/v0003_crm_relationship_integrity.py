"""Migration 0003: CRM relationship integrity, archive fields, and audit fields.

Implements CRM_MODULE_SPECIFICATION.md section 8, migration v0003:

- customer_sites and customer_activities gain a real, enforced foreign key
  on customer_id (previously unconstrained and defaulted to ''). Rows whose
  customer_id does not resolve to an existing customer are moved into a
  holding table instead of being dropped, so no data is silently discarded.
- customer_activities gains an optional contact_id foreign key (nulled, not
  dropped, when it does not resolve), an optional site_id foreign key, and
  generic source_entity_type/source_entity_id columns for future modules.
- customers, customer_contacts, customer_addresses, customer_sites, and
  customer_activities gain created_by/updated_by and archive fields.
- customer_contacts gains is_primary.
"""

from datetime import datetime, timezone
import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 3
NAME = "crm_relationship_integrity"

ADDITIVE_STATEMENTS = (
    "ALTER TABLE customers ADD COLUMN created_by TEXT",
    "ALTER TABLE customers ADD COLUMN updated_by TEXT",
    "ALTER TABLE customers ADD COLUMN archived_at TEXT",
    "ALTER TABLE customers ADD COLUMN archived_by TEXT",
    "ALTER TABLE customers ADD COLUMN archive_reason TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX idx_customers_status ON customers (status)",
    "ALTER TABLE customer_contacts ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE customer_contacts ADD COLUMN created_by TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN updated_by TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN archived_at TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN archived_by TEXT",
    "ALTER TABLE customer_contacts ADD COLUMN archive_reason TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE customer_addresses ADD COLUMN created_by TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN updated_by TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN archived_at TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN archived_by TEXT",
    "ALTER TABLE customer_addresses ADD COLUMN archive_reason TEXT NOT NULL DEFAULT ''",
)

CUSTOMER_COLUMNS = ("created_by", "updated_by", "archived_at", "archived_by", "archive_reason")
CONTACT_COLUMNS = ("is_primary",) + CUSTOMER_COLUMNS
ADDRESS_COLUMNS = CUSTOMER_COLUMNS

CREATE_SITES_ORPHANED = """
CREATE TABLE customer_sites_orphaned_v0003 (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    site_type TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    orphaned_at TEXT NOT NULL,
    orphaned_reason TEXT NOT NULL
)
"""

CREATE_SITES_REBUILT = """
CREATE TABLE customer_sites_v0003 (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    name TEXT NOT NULL,
    site_type TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT,
    updated_by TEXT,
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
)
"""

CREATE_ACTIVITIES_ORPHANED = """
CREATE TABLE customer_activities_orphaned_v0003 (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL DEFAULT '',
    contact_id TEXT NOT NULL DEFAULT '',
    activity_type TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL,
    activity_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    orphaned_at TEXT NOT NULL,
    orphaned_reason TEXT NOT NULL
)
"""

CREATE_ACTIVITIES_REBUILT = """
CREATE TABLE customer_activities_v0003 (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    contact_id TEXT,
    site_id TEXT,
    source_entity_type TEXT NOT NULL DEFAULT '',
    source_entity_id TEXT NOT NULL DEFAULT '',
    activity_type TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL,
    activity_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES customer_contacts (id) ON DELETE SET NULL,
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE SET NULL
)
"""

REBUILD_STATEMENTS = (
    CREATE_SITES_ORPHANED,
    CREATE_SITES_REBUILT,
    CREATE_ACTIVITIES_ORPHANED,
    CREATE_ACTIVITIES_REBUILT,
    "CREATE INDEX idx_customer_sites_customer ON customer_sites (customer_id)",
    "CREATE INDEX idx_customer_activities_customer ON customer_activities (customer_id)",
    "CREATE INDEX idx_customer_activities_activity_date ON customer_activities (activity_date)",
)

PAYLOAD = "\n;\n".join(
    " ".join(statement.split())
    for statement in ADDITIVE_STATEMENTS + REBUILD_STATEMENTS
)

SITE_ORPHAN_REASON = "customer_id did not match an existing customer at migration v0003"


def apply(connection):
    for statement in ADDITIVE_STATEMENTS:
        connection.execute(statement)

    now = _timestamp()
    _rebuild_sites(connection, now)
    _rebuild_activities(connection, now)


def _rebuild_sites(connection, now):
    connection.execute(CREATE_SITES_ORPHANED)
    connection.execute(CREATE_SITES_REBUILT)

    valid_customer_ids = {row[0] for row in connection.execute("SELECT id FROM customers")}
    for row in connection.execute("SELECT * FROM customer_sites").fetchall():
        if row["customer_id"] in valid_customer_ids:
            connection.execute(
                """
                INSERT INTO customer_sites_v0003 (
                    id, customer_id, name, site_type, address, city,
                    province, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"], row["customer_id"], row["name"], row["site_type"],
                    row["address"], row["city"], row["province"], row["notes"],
                    row["created_at"], row["updated_at"],
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO customer_sites_orphaned_v0003 (
                    id, customer_id, name, site_type, address, city,
                    province, notes, created_at, updated_at, orphaned_at,
                    orphaned_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"], row["customer_id"], row["name"], row["site_type"],
                    row["address"], row["city"], row["province"], row["notes"],
                    row["created_at"], row["updated_at"], now, SITE_ORPHAN_REASON,
                ),
            )

    connection.execute("DROP TABLE customer_sites")
    connection.execute("ALTER TABLE customer_sites_v0003 RENAME TO customer_sites")
    connection.execute("CREATE INDEX idx_customer_sites_customer ON customer_sites (customer_id)")


def _rebuild_activities(connection, now):
    connection.execute(CREATE_ACTIVITIES_ORPHANED)
    connection.execute(CREATE_ACTIVITIES_REBUILT)

    valid_customer_ids = {row[0] for row in connection.execute("SELECT id FROM customers")}
    valid_contact_ids = {row[0] for row in connection.execute("SELECT id FROM customer_contacts")}
    for row in connection.execute("SELECT * FROM customer_activities").fetchall():
        if row["customer_id"] not in valid_customer_ids:
            connection.execute(
                """
                INSERT INTO customer_activities_orphaned_v0003 (
                    id, customer_id, contact_id, activity_type, subject,
                    activity_date, status, notes, created_at, updated_at,
                    orphaned_at, orphaned_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"], row["customer_id"], row["contact_id"],
                    row["activity_type"], row["subject"], row["activity_date"],
                    row["status"], row["notes"], row["created_at"],
                    row["updated_at"], now,
                    "customer_id did not match an existing customer at migration v0003",
                ),
            )
            continue

        contact_id = row["contact_id"] or None
        if contact_id and contact_id not in valid_contact_ids:
            contact_id = None

        connection.execute(
            """
            INSERT INTO customer_activities_v0003 (
                id, customer_id, contact_id, site_id, source_entity_type,
                source_entity_id, activity_type, subject, activity_date,
                status, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, NULL, '', '', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["customer_id"], contact_id,
                row["activity_type"], row["subject"], row["activity_date"],
                row["status"], row["notes"], row["created_at"], row["updated_at"],
            ),
        )

    connection.execute("DROP TABLE customer_activities")
    connection.execute("ALTER TABLE customer_activities_v0003 RENAME TO customer_activities")
    connection.execute("CREATE INDEX idx_customer_activities_customer ON customer_activities (customer_id)")
    connection.execute("CREATE INDEX idx_customer_activities_activity_date ON customer_activities (activity_date)")


def verify(connection):
    _verify_columns(connection, "customers", CUSTOMER_COLUMNS)
    _verify_columns(connection, "customer_contacts", CONTACT_COLUMNS)
    _verify_columns(connection, "customer_addresses", ADDRESS_COLUMNS)
    _verify_columns(
        connection,
        "customer_sites",
        ("created_by", "updated_by", "archived_at", "archived_by", "archive_reason"),
    )
    _verify_columns(
        connection,
        "customer_activities",
        ("contact_id", "site_id", "source_entity_type", "source_entity_id", "created_by"),
    )

    site_fks = {row[3] for row in connection.execute('PRAGMA foreign_key_list("customer_sites")')}
    if "customer_id" not in site_fks:
        raise sqlite3.DatabaseError("customer_sites is missing its customer_id foreign key.")

    activity_fks = {row[3] for row in connection.execute('PRAGMA foreign_key_list("customer_activities")')}
    missing = {"customer_id", "contact_id", "site_id"} - activity_fks
    if missing:
        raise sqlite3.DatabaseError(f"customer_activities is missing foreign keys: {sorted(missing)}.")

    for table in ("customer_sites_orphaned_v0003", "customer_activities_orphaned_v0003"):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            raise sqlite3.DatabaseError(f"Expected holding table '{table}' was not created.")


def _verify_columns(connection, table, columns):
    present = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    missing = set(columns) - present
    if missing:
        raise sqlite3.DatabaseError(
            f"CRM relationship-integrity migration failed: '{table}' is missing columns {sorted(missing)}."
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
