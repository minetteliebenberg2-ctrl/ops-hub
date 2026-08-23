"""Migration 0038: rename the "Standard" structure to "4 Post".

Minette calls it a 4 Post on site - four posts, versus a cantilever's
posts down one side - and asked for the app to match (2026-08-12).
Confirmed with her that it is the SAME structure, not a new type, so
this renames rather than adding a second name for one thing.

Deliberately scoped: "Standard" is also a PAYMENT TERM
(picklist_options.list_name = 'payment_terms', 65/35 split) and a
PRICING TIER in the Quotes grid ("Standard"/"High"). Neither is
touched - only the line_item_type picklist and the two columns that
store a structure type.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 38
NAME = "rename_standard_to_four_post"

OLD_VALUE = "Standard"
NEW_VALUE = "4 Post"

STATEMENTS = (
    """
    UPDATE picklist_options
    SET value = '4 Post'
    WHERE list_name = 'line_item_type' AND value = 'Standard'
    """,
    "UPDATE quote_line_items SET structure_type = '4 Post' WHERE structure_type = 'Standard'",
    "UPDATE site_plan_items SET structure_type = '4 Post' WHERE structure_type = 'Standard'",
)

PAYLOAD = "\n;\n".join(" ".join(statement.split()) for statement in STATEMENTS)


def apply(connection):
    for statement in STATEMENTS:
        connection.execute(statement)


def verify(connection):
    leftover = connection.execute(
        """
        SELECT COUNT(*) FROM picklist_options
        WHERE list_name = 'line_item_type' AND value = ?
        """,
        (OLD_VALUE,),
    ).fetchone()[0]
    if leftover:
        raise sqlite3.DatabaseError("Migration v0038 left a 'Standard' line_item_type behind.")

    for table in ("quote_line_items", "site_plan_items"):
        remaining = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE structure_type = ?", (OLD_VALUE,),
        ).fetchone()[0]
        if remaining:
            raise sqlite3.DatabaseError(f"Migration v0038 left 'Standard' rows in {table}.")

    # The payment term must survive untouched.
    payment_term = connection.execute(
        """
        SELECT COUNT(*) FROM picklist_options
        WHERE list_name = 'payment_terms' AND value = ?
        """,
        (OLD_VALUE,),
    ).fetchone()[0]
    if not payment_term:
        raise sqlite3.DatabaseError("Migration v0038 wrongly renamed the 'Standard' payment term.")


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
