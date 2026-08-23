from core.migrations.runner import Migration, migration_checksum

PAYLOAD = """
CREATE TABLE IF NOT EXISTS job_cost_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    cost_bucket TEXT NOT NULL DEFAULT 'labour',
    unit_price REAL NOT NULL DEFAULT 0.0,
    gp_percent REAL NOT NULL DEFAULT 45.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SEED = [
    ("Refit Net", "labour", 450.0, 45.0),
    ("Restitch Net", "labour", 1750.0, 45.0),
    ("Retensioning", "labour", 375.0, 45.0),
    ("Replace Cable", "cable", 500.0, 45.0),
    ("Repaint Structure", "labour", 1500.0, 45.0),
    ("Custom / Other Request", "labour", 0.0, 45.0),
    ("Transport / Call-out", "labour", 600.0, 45.0),
]


def apply(conn):
    conn.executescript(PAYLOAD)
    # Add unit_price column if upgrading from the original schema
    cols = [row[1] for row in conn.execute("PRAGMA table_info(job_cost_items)")]
    if "unit_price" not in cols:
        conn.execute("ALTER TABLE job_cost_items ADD COLUMN unit_price REAL NOT NULL DEFAULT 0.0")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    import uuid
    for name, bucket, price, gp in SEED:
        conn.execute(
            "INSERT OR IGNORE INTO job_cost_items (id, name, cost_bucket, unit_price, gp_percent, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (str(uuid.uuid4()), name, bucket, price, gp, now, now),
        )
    # Update existing rows that have unit_price=0 with default prices
    price_map = {name: price for name, _, price, _ in SEED}
    for name, price in price_map.items():
        if price > 0:
            conn.execute(
                "UPDATE job_cost_items SET unit_price=? WHERE name=? AND unit_price=0.0",
                (price, name),
            )


def verify(conn):
    cols = [row[1] for row in conn.execute("PRAGMA table_info(job_cost_items)")]
    return "unit_price" in cols


MIGRATION = Migration(
    version=47,
    name="job_cost_items",
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
