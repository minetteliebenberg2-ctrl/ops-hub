"""Structure quote calculator - materials + labour + netting -> sell price.

Includes Minette's own real-world benchmark (2026-08-08): a triple
cantilever with a new net and installation "shouldn't be more than
R13500 on low/normal pricing". That figure is the check on whether the
whole chain - supplier costs, BOM, labour, netting, GP - is sane.
"""

import unittest

from core.structure_catalog import CANTILEVER, STANDARD
from core.structure_quote import (
    CABLE_LENGTHS_M,
    NET_LENGTHS_M,
    cable_and_clamps_cost,
    labour_cost,
    net_rate_for,
    netting_cost,
    quote_structure,
    restitch_cost,
)
from core.supplier_pricing import SupplierPriceItem


def _item(category, item_name, supplier, cost_rand):
    return SupplierPriceItem(
        id=f"{category}-{item_name}-{supplier}",
        category=category, item_name=item_name, supplier_name=supplier,
        unit="per 6m", cost_minor=round(cost_rand * 100),
    )


class FakePricing:
    def __init__(self, rows):
        self._rows = rows

    def list_items(self, category, include_inactive=False):
        return [row for row in self._rows if row.category == category]


def _prices():
    return FakePricing([
        _item("Steel", "Anchor Pole 152mm", "Chemvet", 1380.0),
        _item("Steel", "Anchor Pole 76mm", "Steel & Pipes", 419.0),
        _item("Steel", "Hoop / Top Lever Tube 50.8mm", "Chemvet", 230.0),
        _item("Steel", "Bottom Lever Tube 57.1mm", "Chemvet", 258.75),
        _item("Steel", "Cross Flat Bar 60mm", "Chemvet", 250.0),
        _item("Steel", "Lug Angle Iron 70x60mm", "Chemvet", 550.0),
        _item("Steel", "Hoop Insert Tube 42mm", "Steel & Pipes", 243.0),
        _item("Steel", "Round Bar 8mm", "Steel & Pipes", 39.0),
        _item("Hardware", "Pole Cap", "Steel & Pipes", 30.0),
        _item("Hardware", "Ready-Mix Concrete", "Generic", 60.0),
        _item("Netting", "90% Shade Netting", "Knittex Z25", 121.36),
        _item("Netting", "90% Shade Netting", "Plusnet", 82.80),
        _item("Hardware", "Cable 4mm Galvanised", "Toco", 5.18),
        _item("Hardware", "Hook/Eye Turnbuckle 10mm", "Toco", 33.92),
    ])


class LabourTests(unittest.TestCase):

    def test_cantilever_labour_matches_her_rates(self):
        # 450 hoop set + 2 poles x 150 + 2 lever PAIRS x 150 + 150 cross
        self.assertEqual(labour_cost(CANTILEVER), 450 + 300 + 300 + 150)

    def test_standard_has_no_levers_but_four_poles(self):
        self.assertEqual(labour_cost(STANDARD), 450 + 600 + 0 + 150)


class StitchingTests(unittest.TestCase):

    def test_restitch_under_three_nets_is_a_flat_job_price(self):
        self.assertEqual(restitch_cost(1), 800.0)
        self.assertEqual(restitch_cost(2), 800.0)

    def test_restitch_three_or_more_is_per_net(self):
        self.assertEqual(restitch_cost(3), 900.0)
        self.assertEqual(restitch_cost(5), 1500.0)

    def test_no_nets_costs_nothing(self):
        self.assertEqual(restitch_cost(0), 0.0)


class NettingTests(unittest.TestCase):

    def test_net_lengths_are_her_confirmed_sizes(self):
        self.assertEqual(NET_LENGTHS_M, {"Single": 8, "Double": 12, "Triple": 16})

    def test_knittex_delivery_applies_under_the_threshold(self):
        cheap = netting_cost("Single", 100.0, "Knittex Z25")
        self.assertEqual(cheap["delivery"], 200.0)

    def test_knittex_delivery_falls_away_over_the_threshold(self):
        big = netting_cost("Triple", 250.0, "Knittex Z25")  # 16m x 250 = R4000
        self.assertEqual(big["delivery"], 0.0)

    def test_other_suppliers_have_no_delivery_fee(self):
        self.assertEqual(netting_cost("Single", 100.0, "Plusnet")["delivery"], 0.0)

    def test_new_net_uses_minimum_stitching(self):
        self.assertEqual(netting_cost("Single", 100.0, "Plusnet", new_net=True)["stitching"], 450.0)

    def test_unknown_size_is_rejected(self):
        with self.assertRaises(ValueError):
            netting_cost("Quadruple", 100.0, "Plusnet")


class QuoteTests(unittest.TestCase):

    def test_triple_cantilever_meets_her_real_world_benchmark(self):
        """Her benchmark: a triple cantilever, new net, installed, should
        land around R13,500 on low/normal pricing."""

        prices = FakePricing(_prices()._rows + [
            _item("Paint", "QD Enamel Paint 20L", "Durapaints", 1512.09),
        ])
        quote = quote_structure(CANTILEVER, "Triple", "Plusnet", prices)
        self.assertLess(
            abs(quote["total_sell"] - 13500), 1000,
            f"triple cantilever came out at R{quote['total_sell']:,.2f}, "
            "which is more than R1,000 off Minette's R13,500 benchmark",
        )

    def test_frame_cost_is_identical_across_sizes(self):
        """Confirmed 2026-08-08: only the net changes between sizes."""

        costs = {
            size: quote_structure(CANTILEVER, size, "Plusnet", _prices(), include_paint=False)["structure_cost"]
            for size in ("Single", "Double", "Triple")
        }
        self.assertEqual(len(set(costs.values())), 1, f"frame cost varied by size: {costs}")

    def test_bigger_net_costs_more(self):
        single = quote_structure(CANTILEVER, "Single", "Plusnet", _prices(), include_paint=False)
        triple = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        self.assertGreater(triple["total_sell"], single["total_sell"])

    def test_cheaper_net_supplier_produces_a_cheaper_quote(self):
        knittex = quote_structure(CANTILEVER, "Triple", "Knittex Z25", _prices(), include_paint=False)
        plusnet = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        self.assertLess(plusnet["total_sell"], knittex["total_sell"])

    def test_gross_profit_is_actually_achieved(self):
        quote = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), structure_gp=0.45, netting_gp=0.45, include_paint=False)
        achieved = (quote["total_sell"] - quote["total_cost"]) / quote["total_sell"]
        self.assertAlmostEqual(achieved, 0.45, places=4)

    def test_standard_is_cheaper_than_cantilever(self):
        cantilever = quote_structure(CANTILEVER, "Double", "Plusnet", _prices(), include_paint=False)
        standard = quote_structure(STANDARD, "Double", "Plusnet", _prices(), include_paint=False)
        self.assertLess(standard["total_sell"], cantilever["total_sell"])

    def test_falls_back_to_built_in_costs_when_the_price_table_is_empty(self):
        """An empty price table is not an error - the built-in defaults
        keep the app usable (e.g. a fresh database). It is a genuinely
        unpriced part, with no default either, that must refuse to quote."""

        quote = quote_structure(CANTILEVER, "Triple", "Plusnet", FakePricing([
            _item("Netting", "90% Shade Netting", "Plusnet", 82.80),
            _item("Hardware", "Cable 4mm Galvanised", "Toco", 5.18),
            _item("Hardware", "Hook/Eye Turnbuckle 10mm", "Toco", 33.92),
        ]), include_paint=False)
        self.assertGreater(quote["total_sell"], 0)
        sources = {entry["source"] for entry in quote["material_breakdown"]}
        self.assertEqual(sources, {"built-in default"})

    def test_a_part_with_no_price_anywhere_refuses_to_quote(self):
        from core import structure_catalog

        original = structure_catalog.STRUCTURE_BOM[CANTILEVER][0]
        try:
            structure_catalog.STRUCTURE_BOM[CANTILEVER][0] = (
                original[0], original[1], original[2], original[3], original[4],
                None, original[6], ("Steel", "Nonexistent Part"),
            )
            with self.assertRaises(ValueError):
                quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        finally:
            structure_catalog.STRUCTURE_BOM[CANTILEVER][0] = original

    def test_unknown_net_supplier_raises(self):
        with self.assertRaises(ValueError):
            quote_structure(CANTILEVER, "Triple", "Nonexistent Supplier", _prices(), include_paint=False)

    def test_structure_only_quote_excludes_netting(self):
        quote = quote_structure(CANTILEVER, "Triple", pricing_service=_prices(), include_netting=False, include_paint=False)
        self.assertIsNone(quote["netting"])
        self.assertEqual(quote["total_sell"], quote["structure_sell"])

    def test_net_rate_lookup_is_case_insensitive(self):
        self.assertEqual(net_rate_for("plusnet", _prices()), 82.80)


if __name__ == "__main__":
    unittest.main()


class PaintTests(unittest.TestCase):

    def test_paint_is_a_fifth_of_a_drum(self):
        from core.structure_quote import paint_cost_per_structure

        prices = FakePricing([_item("Paint", "QD Enamel Paint 20L", "Durapaints", 1500.0)])
        self.assertEqual(paint_cost_per_structure(prices), 300.0)

    def test_paint_is_included_by_default_on_new_installations(self):
        prices = FakePricing(_prices()._rows + [
            _item("Paint", "QD Enamel Paint 20L", "Durapaints", 1500.0),
        ])
        self.assertEqual(quote_structure(CANTILEVER, "Triple", "Plusnet", prices)["paint"], 300.0)

    def test_paint_can_be_left_out(self):
        quote = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        self.assertEqual(quote["paint"], 0.0)

    def test_including_paint_raises_the_cost(self):
        prices = FakePricing(_prices()._rows + [
            _item("Paint", "QD Enamel Paint 20L", "Durapaints", 1500.0),
        ])
        without = quote_structure(CANTILEVER, "Triple", "Plusnet", prices, include_paint=False)
        with_paint = quote_structure(CANTILEVER, "Triple", "Plusnet", prices, include_paint=True)
        self.assertEqual(with_paint["paint"], 300.0)
        self.assertGreater(with_paint["total_cost"], without["total_cost"])


class CableAndBackToBackTests(unittest.TestCase):

    def test_cable_lengths_are_her_confirmed_runs(self):
        self.assertEqual(CABLE_LENGTHS_M, {"Single": 18, "Double": 22, "Triple": 28})

    def test_cable_is_longer_than_the_net_it_tensions(self):
        for size in ("Single", "Double", "Triple"):
            self.assertGreater(CABLE_LENGTHS_M[size], NET_LENGTHS_M[size])

    def test_two_clamps_per_net(self):
        cable = cable_and_clamps_cost("Triple", _prices())
        self.assertEqual(cable["clamps"], 2 * 33.92)

    def test_cable_cost_scales_with_length(self):
        single = cable_and_clamps_cost("Single", _prices())
        triple = cable_and_clamps_cost("Triple", _prices())
        self.assertAlmostEqual(triple["cable"] - single["cable"], (28 - 18) * 5.18, places=2)

    def test_missing_cable_price_returns_none_rather_than_zero(self):
        self.assertIsNone(cable_and_clamps_cost("Triple", FakePricing([])))

    def test_back_to_back_takes_ten_percent_off_steel_only(self):
        normal = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        shared = quote_structure(
            CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False, back_to_back=True,
        )
        # Only the materials line moves; labour and netting are untouched.
        self.assertAlmostEqual(shared["materials"], round(normal["materials"] * 0.9, 2), places=2)
        self.assertEqual(shared["labour"], normal["labour"])
        self.assertEqual(shared["netting"]["total"], normal["netting"]["total"])

    def test_back_to_back_is_off_by_default(self):
        quote = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        self.assertFalse(quote["back_to_back"])


class ReplacementVsNewInstallTests(unittest.TestCase):
    """New installs and replacements price cable differently, and both are
    correct - the flat replacement rate covers stripping the old cable out
    and refitting, which is most of that job's work."""

    def test_replacement_cable_costs_more_than_new_cable_material(self):
        new = cable_and_clamps_cost("Triple", _prices())
        replacement = cable_and_clamps_cost("Triple", _prices(), replacement=True)
        self.assertGreater(replacement["cable"], new["cable"])

    def test_replacement_uses_the_flat_per_net_rate(self):
        from core.structure_quote import CABLE_REPLACEMENT_FLAT

        for size, flat in CABLE_REPLACEMENT_FLAT.items():
            self.assertEqual(cable_and_clamps_cost(size, _prices(), replacement=True)["cable"], flat)

    def test_replacement_flat_rates_match_the_existing_netting_quotes_tool(self):
        """These figures were confirmed 2026-08-03 and already live in
        modules/proposals/netting_quotes.py - the two must not drift."""

        from core.structure_quote import CABLE_REPLACEMENT_FLAT
        from modules.proposals.netting_quotes import CABLE_COST_PER_NET, NetType

        self.assertEqual(CABLE_REPLACEMENT_FLAT["Single"], CABLE_COST_PER_NET[NetType.SINGLE])
        self.assertEqual(CABLE_REPLACEMENT_FLAT["Double"], CABLE_COST_PER_NET[NetType.DOUBLE])
        self.assertEqual(CABLE_REPLACEMENT_FLAT["Triple"], CABLE_COST_PER_NET[NetType.TRIPLE])

    def test_net_replacement_never_recharges_for_the_structure(self):
        replacement = quote_structure(
            CANTILEVER, "Triple", "Plusnet", _prices(),
            new_net=False, include_structure=False, include_paint=False,
        )
        self.assertEqual(replacement["materials"], 0.0)
        self.assertEqual(replacement["labour"], 0.0)
        self.assertEqual(replacement["structure_sell"], 0.0)

    def test_a_net_replacement_is_far_cheaper_than_a_new_build(self):
        new_build = quote_structure(CANTILEVER, "Triple", "Plusnet", _prices(), include_paint=False)
        replacement = quote_structure(
            CANTILEVER, "Triple", "Plusnet", _prices(),
            new_net=False, include_structure=False, include_paint=False,
        )
        self.assertLess(replacement["total_sell"], new_build["total_sell"] / 2)

    def test_gross_profit_still_holds_on_a_replacement(self):
        replacement = quote_structure(
            CANTILEVER, "Triple", "Plusnet", _prices(),
            new_net=False, include_structure=False, include_paint=False, netting_gp=0.45,
        )
        achieved = (replacement["total_sell"] - replacement["total_cost"]) / replacement["total_sell"]
        self.assertAlmostEqual(achieved, 0.45, places=4)


class CarBayMappingTests(unittest.TestCase):
    """The contract between the UI (which stores a car-bay count) and the
    pricing engine (which talks in net sizes). The UI relies on can_price()
    to decide which rows it may fill in automatically, so a wrong answer
    here either silently mis-prices a job or refuses to price a valid one."""

    def test_one_to_three_bays_map_to_net_sizes(self):
        from core.structure_quote import size_for_car_bays

        self.assertEqual(size_for_car_bays(1), "Single")
        self.assertEqual(size_for_car_bays(2), "Double")
        self.assertEqual(size_for_car_bays(3), "Triple")

    def test_four_bays_has_no_net_size(self):
        """4-bay structures are rarely built ("they don't last") and have
        no net length on record, so they must not be auto-priced."""

        from core.structure_quote import can_price, size_for_car_bays

        self.assertIsNone(size_for_car_bays(4))
        self.assertFalse(can_price(CANTILEVER, 4))

    def test_missing_car_bays_cannot_be_priced(self):
        from core.structure_quote import can_price

        self.assertFalse(can_price(CANTILEVER, None))
        self.assertFalse(can_price(CANTILEVER, 0))

    def test_only_cantilever_and_standard_can_be_auto_priced(self):
        from core.structure_catalog import REPLACE_CABLE, SHADE_SAIL
        from core.structure_quote import can_price

        self.assertTrue(can_price(CANTILEVER, 2))
        self.assertTrue(can_price(STANDARD, 2))
        self.assertFalse(can_price(SHADE_SAIL, 2))
        self.assertFalse(can_price(REPLACE_CABLE, 2))
        self.assertFalse(can_price("Refit Net", 2))

    def test_every_priceable_combination_actually_prices(self):
        """can_price() must not promise more than quote_structure delivers."""

        from core.structure_quote import can_price

        for structure_type in (CANTILEVER, STANDARD):
            for bays in (1, 2, 3, 4, None):
                if not can_price(structure_type, bays):
                    continue
                quote = quote_structure(
                    structure_type, __import__(
                        "core.structure_quote", fromlist=["size_for_car_bays"]
                    ).size_for_car_bays(bays),
                    "Plusnet", _prices(), include_paint=False,
                )
                self.assertGreater(quote["total_sell"], 0)
