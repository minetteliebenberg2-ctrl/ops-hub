"""Structure material costing, and its connection to the editable
Supplier Pricing table.

The point of these tests is that costs must come from the DB Minette can
edit in Settings, not from the literals in core/structure_catalog.py -
those are only a fallback. A regression here would silently quote off
stale prices, which is exactly what the editable table exists to prevent.
"""

import unittest

from core.structure_catalog import (
    CANTILEVER,
    SHADE_SAIL,
    STANDARD,
    structure_bom,
    structure_material_breakdown,
    structure_material_cost,
)
from core.supplier_pricing import SupplierPriceItem


class FakePricingService:
    """Stands in for SupplierPricingService with a controlled price list."""

    def __init__(self, rows):
        self._rows = rows

    def list_items(self, category, include_inactive=False):
        return [item for item in self._rows if item.category == category]


def _item(category, item_name, supplier, cost_rand):
    return SupplierPriceItem(
        id=f"{category}-{item_name}-{supplier}",
        category=category,
        item_name=item_name,
        supplier_name=supplier,
        unit="per 6m",
        cost_minor=round(cost_rand * 100),
    )


def _full_price_list(pole_cost=1380.0):
    return FakePricingService([
        _item("Steel", "Anchor Pole 152mm", "Chemvet", pole_cost),
        _item("Steel", "Anchor Pole 76mm", "Steel & Pipes", 419.0),
        _item("Steel", "Anchor Pole 101.6mm", "Chemvet", 799.25),
        _item("Steel", "Hoop / Top Lever Tube 50.8mm", "Chemvet", 230.0),
        _item("Steel", "Bottom Lever Tube 57.1mm", "Chemvet", 258.75),
        _item("Steel", "Cross Flat Bar 60mm", "Chemvet", 1380.0),
        _item("Steel", "Lug Angle Iron 70x60mm", "Chemvet", 1380.0),
        _item("Steel", "Hoop Insert Tube 42mm", "Steel & Pipes", 243.0),
        _item("Steel", "Round Bar 8mm", "Steel & Pipes", 39.0),
        _item("Hardware", "Pole Cap", "Steel & Pipes", 30.0),
        _item("Hardware", "Ready-Mix Concrete", "Generic", 60.0),
    ])


class StructureCostingTests(unittest.TestCase):

    def test_every_bom_part_resolves_from_supplier_pricing(self):
        for structure_type in (CANTILEVER, STANDARD):
            breakdown = structure_material_breakdown(structure_type, _full_price_list())
            unresolved = [e["part"] for e in breakdown if e["source"] != "supplier pricing"]
            self.assertEqual(
                unresolved, [],
                f"{structure_type}: these parts did not resolve from the editable "
                f"price list and fell back to hardcoded values: {unresolved}",
            )

    def test_editing_a_price_changes_the_structure_cost(self):
        cheap = structure_material_cost(CANTILEVER, _full_price_list(pole_cost=1380.0))
        dear = structure_material_cost(CANTILEVER, _full_price_list(pole_cost=1680.0))

        # 2 poles x 4.2m off a 6m stock length = 1.4 stock lengths.
        self.assertAlmostEqual(dear - cheap, 1.4 * 300.0, places=2)

    def test_length_parts_are_pro_rated_off_the_stock_length(self):
        breakdown = structure_material_breakdown(CANTILEVER, _full_price_list())
        top_lever = next(e for e in breakdown if e["part"] == "Top lever")

        # 2 levers x 4m off a 6m length at R230 = R306.67, not 2 x R230.
        self.assertAlmostEqual(top_lever["line_cost"], round(2 * (4.0 / 6.0) * 230.0, 2), places=2)

    def test_count_parts_are_not_pro_rated(self):
        breakdown = structure_material_breakdown(CANTILEVER, _full_price_list())
        caps = next(e for e in breakdown if e["part"] == "Pole caps")
        self.assertEqual(caps["line_cost"], 60.0)

    def test_unpriced_part_makes_the_total_none_rather_than_understating_it(self):
        partial = FakePricingService([])  # nothing priced, and we blank the fallbacks

        original = structure_bom(CANTILEVER)[0]
        try:
            # Simulate a part with no fallback and no DB row.
            from core import structure_catalog

            structure_catalog.STRUCTURE_BOM[CANTILEVER][0] = (
                original[0], original[1], original[2], original[3], original[4],
                None, original[6], ("Steel", "Nonexistent Part"),
            )
            self.assertIsNone(structure_material_cost(CANTILEVER, partial))
        finally:
            from core import structure_catalog

            structure_catalog.STRUCTURE_BOM[CANTILEVER][0] = original

    def test_standard_defaults_to_76mm_but_honours_a_101mm_override(self):
        prices = _full_price_list()

        default_cost = structure_material_cost(STANDARD, prices)
        override_cost = structure_material_cost(
            STANDARD, prices, pole_price_key=("Steel", "Anchor Pole 101.6mm"),
        )

        # 4 poles x 3m off 6m = 2 stock lengths of the difference.
        self.assertAlmostEqual(override_cost - default_cost, 2 * (799.25 - 419.0), places=2)

    def test_cheapest_supplier_wins_when_an_item_has_several(self):
        rows = _full_price_list()._rows + [
            _item("Steel", "Anchor Pole 152mm", "Other Supplier", 900.0),
        ]
        breakdown = structure_material_breakdown(CANTILEVER, FakePricingService(rows))
        poles = next(e for e in breakdown if e["part"] == "Anchor poles")
        self.assertEqual(poles["unit_cost"], 900.0)

    def test_shade_sail_has_no_bom_and_no_material_total(self):
        self.assertEqual(structure_bom(SHADE_SAIL), [])
        self.assertIsNone(structure_material_cost(SHADE_SAIL))

    def test_falls_back_to_built_in_defaults_without_a_database(self):
        breakdown = structure_material_breakdown(CANTILEVER, FakePricingService([]))
        sources = {e["source"] for e in breakdown}
        self.assertEqual(sources, {"built-in default"})
        self.assertIsNotNone(structure_material_cost(CANTILEVER, FakePricingService([])))


if __name__ == "__main__":
    unittest.main()
