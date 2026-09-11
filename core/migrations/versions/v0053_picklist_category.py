"""Migration 0053: add category column to picklist_options.

Allows line item types to be grouped by category (Structure, Netting,
Steel, Paint, Maintenance, Other) for easier management.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 53
NAME = "picklist_category"

STATEMENTS = (
    "ALTER TABLE picklist_options ADD COLUMN category TEXT DEFAULT ''",
)

CATEGORY_MAP = {
    "Cantilever": "Structure",
    "4 Post": "Structure",
    "Shade Sail": "Structure",
    "Netting - Plusnet (per LM)": "Netting",
    "Netting - Knittex Z25 (per LM)": "Netting",
    "Side Net - Plusnet (per LM)": "Netting",
    "Side Net - Knittex (per LM)": "Netting",
    "Side Net": "Netting",
    "New Net - Single": "Netting",
    "New Net - Double": "Netting",
    "New Net - Triple": "Netting",
    "Refit Net": "Netting",
    "Restitch Net": "Netting",
    "Retensioning": "Netting",
    "50mm Round Tubing": "Steel",
    "Repair 76mm Pole": "Steel",
    "Additional Height": "Steel",
    "Repaint Structure": "Paint",
    "Replace Cable": "Maintenance",
    "Transport / Call-out": "Maintenance",
    "Cleaning of Structure": "Maintenance",
    "Pulley": "Maintenance",
    "Maintenance": "Other",
    "Custom / Other Request": "Other",
    "Other": "Other",
}


PAYLOAD = "\n".join(STATEMENTS)


def apply(connection: sqlite3.Connection) -> None:
    for statement in STATEMENTS:
        connection.execute(statement)
    for value, category in CATEGORY_MAP.items():
        connection.execute(
            "UPDATE picklist_options SET category = ? WHERE list_name = 'line_item_type' AND value = ?",
            (category, value),
        )


def verify(connection: sqlite3.Connection) -> bool:
    columns = [
        row[1]
        for row in connection.execute("PRAGMA table_info(picklist_options)").fetchall()
    ]
    return "category" in columns


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
