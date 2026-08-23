"""Migration 0031: editable supplier pricing.

Minette asked (2026-08-08) for every supplier cost figure - steel,
netting, paint, hardware, labour add-ons - to be editable in the app
rather than hardcoded, since supplier costs change frequently. This
introduces `supplier_price_items`, seeded with the real, confirmed
figures gathered that session (Chemvet/Steel & Pipes steel, Knittex
Z25/Dri-Z/Extreme 32/Plusnet netting, Durapaints 20L enamel, Toco
cable/hardware, ready-mix concrete, and the three labour add-on rates).

Deliberately allows more than one row per item_name - e.g. "90% Shade
Netting" appears once under Knittex Z25 and once under Plusnet, so the
Suppliers/Quotes UI can offer a real supplier choice per item rather than
a single fixed price. Uniqueness is (category, item_name, supplier_name),
not (category, item_name).

This does NOT yet rewire modules/proposals/netting_quotes.py's existing
hardcoded constants (SUPPLIER_PRICES, CABLE_COST_PER_NET, PAINT_20L_COST)
to read from this table - that's a follow-up. This migration only adds
the editable store and seeds it with the same real numbers.
"""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.migrations.runner import Migration, migration_checksum


VERSION = 31
NAME = "supplier_pricing"

CREATE_TABLE = """
CREATE TABLE supplier_price_items (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    item_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    spec TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL,
    cost_minor INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    UNIQUE (category, item_name, supplier_name)
)
"""

INDEX_STATEMENT = "CREATE INDEX idx_supplier_price_items_category ON supplier_price_items (category)"

STATEMENTS = (CREATE_TABLE, INDEX_STATEMENT)

# (category, item_name, supplier_name, spec, unit, cost_rand)
# Seed data cleared for the Ops Hub template fork (2026-08-23) — the
# original figures were FacilitiesCo's real, confirmed supplier prices.
# Add the new business's own pricing via Settings -> Supplier Pricing.
SEED = ()


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)

    now = _timestamp()

    for offset, (category, item_name, supplier_name, spec, unit, cost_rand) in enumerate(SEED, start=1):
        connection.execute(
            """
            INSERT INTO supplier_price_items (
                id, category, item_name, supplier_name, spec, unit,
                cost_minor, sort_order, is_active, created_at, updated_at, updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'system')
            """,
            (
                str(uuid4()), category, item_name, supplier_name, spec, unit,
                round(cost_rand * 100), offset, now, now,
            ),
        )


def verify(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'supplier_price_items'"
    ).fetchone()
    if not exists:
        raise sqlite3.DatabaseError("Migration v0031 did not create 'supplier_price_items'.")

    count = connection.execute("SELECT COUNT(*) FROM supplier_price_items").fetchone()[0]
    if count != len(SEED):
        raise sqlite3.DatabaseError(
            f"Migration v0031 expected {len(SEED)} seeded supplier price items, found {count}."
        )


def _timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


PAYLOAD = "\n;\n".join(" ".join(s.split()) for s in STATEMENTS) + "\nseed:" + ",".join(
    f"{c}:{i}:{s}:{u}:{cost}" for c, i, s, _spec, u, cost in SEED
)

MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
