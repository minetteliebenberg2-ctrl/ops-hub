"""Migration 0034: store supplier costs as true (VAT-inclusive) cost.

FacilitiesCo is **not VAT registered** (see business identity notes), so
input VAT on materials can never be reclaimed - the VAT Minette pays is
a real, unrecoverable part of what a structure costs her. Costing off
ex-VAT figures would understate every quote by 15%.

v0031 seeded a mix without recording which basis each figure came from:

  * Chemvet came from a real quote footed "Amount Excl Tax"  -> ex-VAT
  * Steel & Pipes came from a price list headed "INCL. 15% VAT"
  * Knittex / Durapaints / Toco / Plusnet are quoted ex-VAT
    (confirmed by Minette 2026-08-08)

This adds `vat_inclusive` so each row records its basis, then grosses up
every ex-VAT row by 15% so all `cost_minor` values mean the same thing:
what she actually pays. Rows already inclusive are left untouched, and
in-house labour has no VAT to add.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 34
NAME = "supplier_pricing_vat_basis"

VAT_RATE = 0.15

ADD_COLUMN = "ALTER TABLE supplier_price_items ADD COLUMN vat_inclusive INTEGER NOT NULL DEFAULT 1"

# Suppliers whose seeded figures were ex-VAT and must be grossed up.
EX_VAT_SUPPLIERS = (
    "Chemvet",
    "Knittex Z25",
    "Knittex Dri-Z",
    "Knittex Extreme 32",
    "Plusnet",
    "Durapaints",
    "Toco",
)

STATEMENTS = (ADD_COLUMN,)

PAYLOAD = " ".join(ADD_COLUMN.split()) + "\ngross_up:{}:{}".format(
    VAT_RATE, ",".join(EX_VAT_SUPPLIERS)
)


def apply(connection):
    connection.execute(ADD_COLUMN)

    placeholders = ",".join("?" for _ in EX_VAT_SUPPLIERS)
    connection.execute(
        f"""
        UPDATE supplier_price_items
        SET cost_minor = CAST(ROUND(cost_minor * {1 + VAT_RATE}) AS INTEGER),
            vat_inclusive = 1,
            updated_by = 'system'
        WHERE supplier_name IN ({placeholders})
        """,
        EX_VAT_SUPPLIERS,
    )


def verify(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info("supplier_price_items")')}
    if "vat_inclusive" not in columns:
        raise sqlite3.DatabaseError("Migration v0034 did not add 'vat_inclusive'.")

    # The 152mm pole was seeded at R1200 ex-VAT; it must now read R1380.
    row = connection.execute(
        """
        SELECT cost_minor FROM supplier_price_items
        WHERE category = 'Steel' AND item_name = 'Anchor Pole 152mm'
        """
    ).fetchone()
    if row is not None and row[0] != 138000:
        raise sqlite3.DatabaseError(
            f"Migration v0034 expected the 152mm pole at 138000 minor units, found {row[0]}."
        )

    # Steel & Pipes was already inclusive - the 76mm pole must stay R419.
    row = connection.execute(
        """
        SELECT cost_minor FROM supplier_price_items
        WHERE category = 'Steel' AND item_name = 'Anchor Pole 76mm'
        """
    ).fetchone()
    if row is not None and row[0] != 41900:
        raise sqlite3.DatabaseError(
            f"Migration v0034 should not have changed the 76mm pole; found {row[0]}."
        )


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
