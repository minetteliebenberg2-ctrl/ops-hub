import os
import tempfile

import pytest

from core.database import Database
from core.picklist_repository import PicklistOptionRepository
from core.picklist_service import LINE_ITEM_TYPE, PicklistService
from core.quote_line_item import QuoteLineItem
from core.quote_pdf import format_line_item_description
from core.structure_catalog import CANTILEVER, SHADE_SAIL, STANDARD


@pytest.fixture
def picklist_service():
    db_path = tempfile.mktemp(suffix=".db")
    database = Database(db_path)
    database.initialize()
    yield PicklistService(repository=PicklistOptionRepository(db=database))
    if os.path.exists(db_path):
        os.remove(db_path)


def test_structural_types_have_no_flat_rate(picklist_service):
    options = {o.value: o for o in picklist_service.list_options(LINE_ITEM_TYPE, include_inactive=True)}

    # Constants, not literals, so a rename of the type (Standard ->
    # 4 Post, 2026-08-12) is followed rather than silently missed.
    for structural in (CANTILEVER, STANDARD, SHADE_SAIL):
        assert options[structural].rate_standard_minor is None


def test_maintenance_items_have_standard_and_high_rates(picklist_service):
    options = {o.value: o for o in picklist_service.list_options(LINE_ITEM_TYPE, include_inactive=True)}

    expected = {
        "Refit Net": (45000, 51300),
        "Restitch Net": (175000, 177500),
        "Retensioning": (37500, 42000),
        "Replace Cable": (50000, 60000),
        "Repaint Structure": (150000, 175000),
        "Transport / Call-out": (60000, 60000),
    }
    for value, (standard, high) in expected.items():
        assert options[value].rate_standard_minor == standard
        assert options[value].rate_high_minor == high
        assert options[value].is_active is True


def test_generic_maintenance_placeholder_is_deactivated(picklist_service):
    options = {o.value: o for o in picklist_service.list_options(LINE_ITEM_TYPE, include_inactive=True)}

    assert options["Maintenance"].is_active is False
    # Deactivated options are excluded from the default (active-only) list
    # used to populate the Quote grid's dropdown.
    active_values = picklist_service.list_values(LINE_ITEM_TYPE)
    assert "Maintenance" not in active_values


def test_custom_catch_all_stays_active_with_no_rate(picklist_service):
    options = {o.value: o for o in picklist_service.list_options(LINE_ITEM_TYPE, include_inactive=True)}

    option = options["Custom / Other Request"]
    assert option.is_active is True
    assert option.rate_standard_minor is None


def test_non_structural_description_omits_leftover_structural_detail():
    """A Maintenance-style line item has no real height/car-bay - the
    auto-generated description must not claim one (regression test for
    the "Maintenance (2.1m height)" bug)."""

    item = QuoteLineItem(
        structure_type="Refit Net",
        car_bays=None,
        shape="",
        width_m=None,
        projection_m=None,
        height_m=2.1,
        description="",
        quantity=2,
        unit_price_minor=45000,
    )

    assert format_line_item_description(item) == "Refit Net"


def test_description_prefers_typed_text_then_item_type():
    """Ops Hub is generic: the PDF description is the typed description,
    else the item type, never shade-structure detail."""
    item = QuoteLineItem(structure_type="Consulting", description="")
    assert format_line_item_description(item) == "Consulting"
    item.description = "Two days on site"
    assert format_line_item_description(item) == "Two days on site"
