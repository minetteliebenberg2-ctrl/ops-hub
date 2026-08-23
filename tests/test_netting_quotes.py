from modules.proposals.netting_quotes import (
    MAINTENANCE_ITEMS,
    NetType,
    NettingQuoteService,
    Supplier,
)


def test_comparison_quote_totals_scale_with_quantity():
    """Base quote_price (before delivery) should scale linearly with
    qty - final_price can't, since delivery only applies below
    DELIVERY_THRESHOLD (see the dedicated delivery test below)."""
    service = NettingQuoteService()

    single = service.create_comparison_quote(net_type=NetType.DOUBLE, color="Charcoal", qty=1, margin_percent=45)
    double = service.create_comparison_quote(net_type=NetType.DOUBLE, color="Charcoal", qty=2, margin_percent=45)

    assert double["plusnet"]["quote_price"] == round(single["plusnet"]["quote_price"] * 2, 2)
    assert double["qty"] == 2


def test_comparison_quote_waives_delivery_above_threshold():
    service = NettingQuoteService()

    small = service.create_comparison_quote(net_type=NetType.SINGLE, color="Charcoal", qty=1, margin_percent=45)
    large = service.create_comparison_quote(net_type=NetType.TRIPLE, color="Charcoal", qty=3, margin_percent=45)

    assert small["plusnet"]["quote_price"] < 3000
    assert small["plusnet"]["delivery"] > 0
    assert large["plusnet"]["quote_price"] >= 3000
    assert large["plusnet"]["delivery"] == 0


def test_comparison_quote_rejects_unknown_color():
    service = NettingQuoteService()

    try:
        service.create_netting_quote(NetType.DOUBLE, Supplier.PLUSNET, "Not A Real Color", qty=1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_painting_cable_quote_includes_cable_line_only_when_requested():
    service = NettingQuoteService()

    no_cable = service.create_painting_cable_quote(num_structures=2, cable_meters=None)
    assert len(no_cable["line_items"]) == 1

    with_cable = service.create_painting_cable_quote(num_structures=2, cable_meters=50)
    assert len(with_cable["line_items"]) == 2
    assert with_cable["total_price"] > no_cable["total_price"]


def test_maintenance_quote_only_includes_requested_items():
    service = NettingQuoteService()

    quote = service.create_maintenance_quote(items={"refit_net": 2, "restitch_net": 1}, tier="standard")

    descriptions = [item["description"] for item in quote["line_items"]]
    assert len(quote["line_items"]) == 2
    assert any("Refit" in d for d in descriptions)
    assert any("Restitch" in d for d in descriptions)
    expected_total = MAINTENANCE_ITEMS["refit_net"]["standard"] * 2 + MAINTENANCE_ITEMS["restitch_net"]["standard"] * 1
    assert quote["total_price"] == expected_total


def test_maintenance_quote_high_tier_is_more_expensive():
    service = NettingQuoteService()

    standard = service.create_maintenance_quote(items={"repaint_structure": 1}, tier="standard")
    high = service.create_maintenance_quote(items={"repaint_structure": 1}, tier="high")

    assert high["total_price"] > standard["total_price"]
