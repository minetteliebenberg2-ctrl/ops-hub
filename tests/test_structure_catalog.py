"""Tests for the shared size_options_for/size_label_for helpers -
used by both the Site Plan form and the Quotes grid's Car Bay
dropdown so they can't drift apart."""

import unittest

import pytest

from core.structure_catalog import CANTILEVER, REPLACE_CABLE, STANDARD, car_bay_options, size_label_for, size_options_for


class SizeOptionsForTests(unittest.TestCase):

    def test_cantilever_gets_real_car_bay_dimensions(self):
        options, by_label = size_options_for(CANTILEVER)

        self.assertEqual(options[0], "N/A")
        self.assertIn("1 Car — 3m x 5m", options)
        self.assertEqual(by_label["1 Car — 3m x 5m"], 1)
        self.assertIsNone(by_label["N/A"])

    def test_standard_gets_the_same_car_bay_dimensions_as_cantilever(self):
        cantilever_options, _ = size_options_for(CANTILEVER)
        standard_options, _ = size_options_for(STANDARD)

        self.assertEqual(cantilever_options, standard_options)

    def test_replace_cable_gets_single_double_triple(self):
        options, by_label = size_options_for(REPLACE_CABLE)

        self.assertEqual(options, ["N/A", "Single", "Double", "Triple"])
        self.assertEqual(by_label["Single"], 1)
        self.assertEqual(by_label["Double"], 2)
        self.assertEqual(by_label["Triple"], 3)

    def test_type_with_no_size_concept_only_has_na(self):
        # Was "Restitch Net" until 2026-08-12, when Minette asked for
        # netting to carry a Single/Double/Triple size like cable does.
        # A call-out genuinely has no size.
        options, by_label = size_options_for("Transport / Call-out")

        self.assertEqual(options, ["N/A"])
        self.assertEqual(by_label, {"N/A": None})

    def test_cantilever_and_cable_use_disjoint_label_sets(self):
        _, cantilever_by_label = size_options_for(CANTILEVER)
        _, cable_by_label = size_options_for(REPLACE_CABLE)

        self.assertNotIn("Single", cantilever_by_label)
        self.assertNotIn("1 Car — 3m x 5m", cable_by_label)


class SizeLabelForTests(unittest.TestCase):

    def test_none_car_bays_is_always_na(self):
        self.assertEqual(size_label_for(CANTILEVER, None), "N/A")
        self.assertEqual(size_label_for(REPLACE_CABLE, None), "N/A")
        self.assertEqual(size_label_for("Restitch Net", None), "N/A")

    def test_cantilever_car_bays_round_trips_through_options(self):
        options, by_label = size_options_for(CANTILEVER)
        label = size_label_for(CANTILEVER, 2)

        self.assertIn(label, options)
        self.assertEqual(by_label[label], 2)

    def test_cable_car_bays_maps_to_size_tier_words(self):
        self.assertEqual(size_label_for(REPLACE_CABLE, 1), "Single")
        self.assertEqual(size_label_for(REPLACE_CABLE, 2), "Double")
        self.assertEqual(size_label_for(REPLACE_CABLE, 3), "Triple")

    def test_unknown_car_bays_value_falls_back_to_na(self):
        self.assertEqual(size_label_for(REPLACE_CABLE, 99), "N/A")
        self.assertEqual(size_label_for(CANTILEVER, 99), "N/A")


if __name__ == "__main__":
    unittest.main()


# ------------------------------------------------------------------
# 2026-08-12: "4 Post" rename, and netting getting a real size
# ------------------------------------------------------------------

def test_the_four_post_structure_is_named_what_she_calls_it():
    """She calls it a 4 Post on site (four posts, versus a cantilever's
    posts down one side). Confirmed with her it is the SAME structure,
    so it was renamed rather than added alongside "Standard"."""

    from core.structure_catalog import STANDARD

    assert STANDARD == "4 Post"


def test_four_post_still_uses_real_car_bay_sizes():
    """The rename must not disturb its sizing - it is the same
    structure, just under the name she uses."""

    from core.structure_catalog import STANDARD, size_options_for

    options, by_label = size_options_for(STANDARD)

    assert any("1 Car" in option for option in options)
    assert by_label[[o for o in options if o.startswith("3 Car")][0]] == 3


def test_four_post_can_still_be_priced():
    """Pricing is keyed by structure type, so a rename that missed the
    BOM would silently stop quoting the most common structure."""

    from core.structure_catalog import STANDARD, STRUCTURE_BOM

    assert STANDARD in STRUCTURE_BOM


@pytest.mark.parametrize("net_type", [
    "Refit Net", "Restitch Net", "Retensioning",
    "New Net - Single", "New Net - Double", "New Net - Triple",
])
def test_netting_offers_single_double_triple(net_type):
    """Nets showed a blank size on the Site Plan and its export until
    2026-08-12; they use the same tiers as cable."""

    from core.structure_catalog import size_options_for

    options, by_label = size_options_for(net_type)

    assert options == ["N/A", "Single", "Double", "Triple"]
    assert by_label["Double"] == 2


@pytest.mark.parametrize("net_type, expected", [
    ("New Net - Single", "Single"),
    ("New Net - Double", "Double"),
    ("New Net - Triple", "Triple"),
])
def test_a_new_net_shows_the_size_already_in_its_name(net_type, expected):
    """"New Net - Double" already states its size - she should never
    have to pick it a second time, and the export should show it."""

    from core.structure_catalog import size_label_for

    assert size_label_for(net_type, None) == expected


def test_a_chosen_net_size_wins_over_the_implied_one():
    from core.structure_catalog import size_label_for

    assert size_label_for("New Net - Double", 3) == "Triple"


def test_refit_net_has_no_implied_size():
    """Only the "New Net - X" names carry their size; the others are a
    genuine choice."""

    from core.structure_catalog import size_label_for

    assert size_label_for("Refit Net", None) == "N/A"


def test_a_type_with_no_size_concept_is_unchanged():
    from core.structure_catalog import size_options_for

    assert size_options_for("Transport / Call-out") == (["N/A"], {"N/A": None})
