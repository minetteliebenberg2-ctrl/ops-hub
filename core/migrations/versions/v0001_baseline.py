"""Migration 0001: the approved pre-migration FC Hub schema."""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 1
NAME = "baseline"

STATEMENTS = (
    """
    CREATE TABLE customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        customer_type TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        vat_number TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE customer_contacts (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        name TEXT NOT NULL,
        job_title TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        mobile TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (customer_id)
            REFERENCES customers (id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE customer_addresses (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
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
        FOREIGN KEY (customer_id)
            REFERENCES customers (id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE customer_sites (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL DEFAULT '',
        name TEXT NOT NULL,
        site_type TEXT NOT NULL DEFAULT '',
        address TEXT NOT NULL DEFAULT '',
        city TEXT NOT NULL DEFAULT '',
        province TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE customer_activities (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL DEFAULT '',
        contact_id TEXT NOT NULL DEFAULT '',
        activity_type TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL,
        activity_date TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE communication_candidates (
        normalized_email TEXT PRIMARY KEY,
        original_email TEXT,
        display_name TEXT,
        classification TEXT,
        classification_reason TEXT,
        existing_match_status TEXT,
        review_status TEXT,
        ignore_status TEXT,
        occurrences INTEGER,
        first_seen TEXT,
        last_seen TEXT,
        inbound_count INTEGER,
        outbound_count INTEGER,
        source_mailbox TEXT,
        source_folder TEXT,
        source_header_types TEXT,
        source_message_ids TEXT,
        imported INTEGER DEFAULT 0,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE communication_occurrences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        normalized_email TEXT,
        source_message_id TEXT,
        header_source TEXT,
        source_mailbox TEXT,
        message_date TEXT,
        UNIQUE (
            normalized_email,
            source_message_id,
            header_source,
            source_mailbox
        )
    )
    """,
    """
    CREATE TABLE communication_ignore_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_type TEXT,
        value TEXT,
        reason TEXT,
        created_date TEXT,
        active INTEGER DEFAULT 1,
        UNIQUE (entry_type, value)
    )
    """,
    """
    CREATE TABLE communication_import_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        normalized_email TEXT,
        import_date TEXT,
        selected_action TEXT,
        crm_customer_id TEXT,
        crm_contact_id TEXT,
        import_status TEXT,
        error_message TEXT
    )
    """,
    "CREATE INDEX idx_customers_name ON customers (name)",
    """
    CREATE INDEX idx_customer_contacts_customer
        ON customer_contacts (customer_id)
    """,
    """
    CREATE INDEX idx_customer_addresses_customer
        ON customer_addresses (customer_id)
    """,
    """
    CREATE INDEX idx_customer_sites_customer
        ON customer_sites (customer_id)
    """,
    """
    CREATE INDEX idx_customer_activities_customer
        ON customer_activities (customer_id)
    """,
)

PAYLOAD = "\n;\n".join(
    " ".join(statement.split())
    for statement in STATEMENTS
)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    actual = schema_signature(connection)
    expected = expected_signature()
    if actual != expected:
        raise sqlite3.DatabaseError(
            "Baseline schema verification failed."
        )


def matches_legacy(connection):
    return schema_signature(connection) == expected_signature()


def schema_signature(connection):
    tables = {}
    for table in _TABLES:
        if not _table_exists(connection, table):
            return {}
        columns = tuple(
            tuple(row[1:6])
            for row in connection.execute(
                f'PRAGMA table_info("{table}")'
            )
        )
        foreign_keys = tuple(
            tuple(row[2:8])
            for row in connection.execute(
                f'PRAGMA foreign_key_list("{table}")'
            )
        )
        indexes = []
        for row in connection.execute(f'PRAGMA index_list("{table}")'):
            if row[3] == "pk":
                continue
            index_columns = tuple(
                item[2]
                for item in connection.execute(
                    f'PRAGMA index_info("{row[1]}")'
                )
            )
            indexes.append((row[1], row[2], row[3], index_columns))
        tables[table] = (
            columns,
            foreign_keys,
            tuple(sorted(indexes)),
        )
    extra = _application_tables(connection) - set(_TABLES)
    if extra:
        return {}
    return tables


def expected_signature():
    connection = sqlite3.connect(":memory:")
    try:
        apply(connection)
        return schema_signature(connection)
    finally:
        connection.close()


def _table_exists(connection, table):
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone() is not None


def _application_tables(connection):
    return {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                AND name != 'schema_migrations'
            """
        )
    }


_TABLES = (
    "customers",
    "customer_contacts",
    "customer_addresses",
    "customer_sites",
    "customer_activities",
    "communication_candidates",
    "communication_occurrences",
    "communication_ignore_list",
    "communication_import_history",
)

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
    matches_legacy=matches_legacy,
)
