"""Migration 0027: real Site diagram/plan.

Site Visit Phase 3, mapped out with Minette 2026-08-07 - the core of
Site Visit. Confirmed requirements:

- Persistent PER SITE, not redrawn each visit ("each site is
  different... one may have 2 structures, another may have 40+" -
  her words - so a fixed template or per-visit redraw would be
  impractical).
- Freeform - no fixed grid, she places a rectangle per structure
  ("like a landscaper").
- Backdrop image is hers (a pasted Google satellite screenshot) - no
  maps API, confirmed explicitly.
- Each rectangle carries the SAME fields as a real Quote line item
  (structure_type, description, quantity, unit_price) - not a
  separate simplified status system. Her words: "nothing changes on
  my side between drawing the site plan and doing the quote."

One `site_plans` row per Site (the backdrop image + its pixel
dimensions, needed to scale rectangle positions correctly regardless
of canvas zoom/window size). Many `site_plan_items` rows per plan -
each one IS a rectangle AND a prospective quote line item at once.
Position/size stored as fractions of the backdrop (0.0-1.0), not
pixels, so they stay correct however the canvas is displayed.

No archive/soft-delete on plan items - unlike business records
elsewhere in the app, a mis-drawn rectangle is just deleted outright,
same as a Quote line item.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 27
NAME = "site_plans"

CREATE_SITE_PLANS = """
CREATE TABLE site_plans (
    id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL UNIQUE,
    backdrop_filename TEXT NOT NULL DEFAULT '',
    backdrop_width INTEGER NOT NULL DEFAULT 0,
    backdrop_height INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (site_id) REFERENCES customer_sites (id) ON DELETE CASCADE
)
"""

CREATE_SITE_PLAN_ITEMS = """
CREATE TABLE site_plan_items (
    id TEXT PRIMARY KEY,
    site_plan_id TEXT NOT NULL,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    width REAL NOT NULL DEFAULT 0,
    height REAL NOT NULL DEFAULT 0,
    structure_type TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 1,
    unit_price_minor INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (site_plan_id) REFERENCES site_plans (id) ON DELETE CASCADE
)
"""

CREATE_INDEX = "CREATE INDEX idx_site_plan_items_plan ON site_plan_items (site_plan_id)"

STATEMENTS = (CREATE_SITE_PLANS, CREATE_SITE_PLAN_ITEMS, CREATE_INDEX)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "site_plans" not in tables or "site_plan_items" not in tables:
        raise sqlite3.DatabaseError("Migration v0027 did not create the site_plans/site_plan_items tables.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
