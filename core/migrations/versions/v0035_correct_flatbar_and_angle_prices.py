"""Migration 0035: correct the 60mm flat bar and 70x60 angle iron costs.

v0031 seeded both at R1,200 per 6m. That came from a single answer
Minette gave to a question that covered the 152mm anchor pole, the flat
bar and the angle iron together - R1,200 is the pole's price, and it got
applied to all three.

It was clearly wrong next to comparable real stock: Chemvet's own
50x5mm flat bar is R212.75/6m incl VAT, and Steel & Pipes' 50x50x5mm
angle iron is R349/6m incl. A 60x5 flat bar at R1,380 (the VAT-inclusive
figure after v0034) was over six times its nearest comparable, and
between them the two lines carried R920 of a R4,882 Cantilever.

Corrected to Minette's own trade estimates (2026-08-08): R250/6m for the
flat bar and R550/6m for the angle iron, both VAT-inclusive per v0034's
true-cost basis. She will refine them in Settings once she has firm
supplier quotes - which is exactly what the editable table is for.
"""

import sqlite3

from core.migrations.runner import Migration, migration_checksum


VERSION = 35
NAME = "correct_flatbar_and_angle_prices"

# (item_name, corrected cost incl VAT, spec)
CORRECTIONS = (
    ("Cross Flat Bar 60mm", 250.00, "60mm x 5mm flat bar (trade estimate, refine in Settings)"),
    ("Lug Angle Iron 70x60mm", 550.00, "70mm x 60mm x 5mm angle iron (trade estimate, refine in Settings)"),
)

PAYLOAD = "correct:" + ",".join(f"{name}:{cost}" for name, cost, _spec in CORRECTIONS)


def apply(connection):
    for item_name, cost_rand, spec in CORRECTIONS:
        connection.execute(
            """
            UPDATE supplier_price_items
            SET cost_minor = ?, spec = ?, vat_inclusive = 1, updated_by = 'system'
            WHERE category = 'Steel' AND item_name = ?
            """,
            (round(cost_rand * 100), spec, item_name),
        )


def verify(connection):
    for item_name, cost_rand, _spec in CORRECTIONS:
        row = connection.execute(
            "SELECT cost_minor FROM supplier_price_items WHERE category = 'Steel' AND item_name = ?",
            (item_name,),
        ).fetchone()
        if row is None:
            continue
        if row[0] != round(cost_rand * 100):
            raise sqlite3.DatabaseError(
                f"Migration v0035 expected '{item_name}' at {round(cost_rand * 100)} minor units, found {row[0]}."
            )


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum(PAYLOAD),
    apply=apply,
    verify=verify,
)
