# ==========================================================
# FC Hub - Structure Quote Calculator
# ----------------------------------------------------------
# Purpose:
# Turns a structure type + size + net choice into a real sell
# price: materials (live from Supplier Pricing) + labour +
# netting + stitching + delivery, then gross profit.
#
# Every cost is TRUE COST INCLUDING VAT - FacilitiesCo is not
# VAT registered, so input VAT is never reclaimable and is a
# real part of what a job costs (see migration v0034).
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

from core.structure_catalog import (
    CANTILEVER,
    STANDARD,
    structure_material_breakdown,
    structure_material_cost,
)

# Net length in linear metres of 3m-wide netting, by size.
# Confirmed by Minette 2026-08-08: the frame does not change between
# sizes, only the net does.
NET_LENGTHS_M = {
    "Single": 8,
    "Double": 12,
    "Triple": 16,
}

# Labour, confirmed by Minette 2026-08-08. Flat rates, never marked up.
HOOP_BENDING_PER_SET = 450.0      # 4 hoops = one set = one structure
POLE_WELD_EACH = 150.0
LEVER_WELD_PER_PAIR = 150.0       # per pair, not per lever (revised 2026-08-08)
CROSS_WELD_PER_STRUCTURE = 150.0

# Anchor poles and levers per structure type (drives weld counts).
POLES_PER_STRUCTURE = {CANTILEVER: 2, STANDARD: 4}
# Lever PAIRS per structure - a cantilever has a top pair and a bottom
# pair; a four-post has none.
LEVER_PAIRS_PER_STRUCTURE = {CANTILEVER: 2, STANDARD: 0}

# Stitching, confirmed by Minette 2026-08-08.
NEW_NET_STITCHING_MIN = 450.0     # per net
RESTITCH_SMALL_JOB = 800.0        # total, for fewer than 3 nets
RESTITCH_PER_NET = 300.0          # each, for 3 nets or more
RESTITCH_PER_NET_THRESHOLD = 3

# Paint, confirmed by Minette 2026-08-08: roughly 5 structures per 20L
# drum, and standard on all NEW installations - so it is included by
# default here. Repainting an existing structure is different: that is
# maintenance, quoted separately off the maintenance rate card.
STRUCTURES_PER_20L_DRUM = 5

# Cable and clamps, confirmed by Minette 2026-08-08. Toco 4mm 6x7
# fibre-core galvanised cable, plus two clamps per net.
#
# Cable is priced two different ways, and which one applies depends on
# the job - they are not alternatives to each other:
#
#   NEW INSTALL - material only, by run length. The cable is longer than
#   the net it tensions (18m / 22m / 28m for single / double / triple).
#
#   REPLACEMENT - a flat rate per net that also covers stripping the old
#   cable out and fitting the new one, which is most of the work. These
#   are the figures already used by modules/proposals/netting_quotes.py
#   (CABLE_COST_PER_NET, confirmed 2026-08-03) and they stay the source
#   of truth for replacement work.
CABLE_LENGTHS_M = {
    "Single": 18,
    "Double": 22,
    "Triple": 28,
}
CABLE_REPLACEMENT_FLAT = {
    "Single": 500.0,
    "Double": 550.0,
    "Triple": 600.0,
}
CLAMPS_PER_NET = 2

# Back-to-back structures share their anchor poles, so the steel for each
# one costs 10% less. Confirmed by Minette 2026-08-08 - steel only, not
# labour, netting or paint.
BACK_TO_BACK_STEEL_DISCOUNT = 0.10

# Knittex delivery, confirmed by Minette 2026-08-08.
KNITTEX_DELIVERY_FEE = 200.0
KNITTEX_FREE_DELIVERY_OVER = 3000.0

# Gross profit targets, confirmed by Minette 2026-08-08.
STRUCTURE_GP = 0.45
NETTING_GP = 0.45

STRUCTURE_GP_HIGH = 0.65
NETTING_GP_HIGH = 0.65

GP_OPTIONS = {"45%": 0.45, "65%": 0.65}


# The Quotes grid and Site Plan both store a car-bay count, while
# pricing talks in net sizes. 4 bays has no net length defined - Minette
# said 4-bay structures are rarely done ("they don't last"), so it is
# left unmapped rather than guessed at.
CAR_BAYS_TO_SIZE = {1: "Single", 2: "Double", 3: "Triple"}


def size_for_car_bays(car_bays):
    """Net size name for a car-bay count, or None if there isn't one."""

    return CAR_BAYS_TO_SIZE.get(car_bays)


def can_price(structure_type, car_bays):
    """True when quote_structure() can price this combination."""

    return (
        structure_type in (CANTILEVER, STANDARD)
        and size_for_car_bays(car_bays) is not None
    )


def labour_cost(structure_type):
    """Flat fabrication labour for one structure."""

    poles = POLES_PER_STRUCTURE.get(structure_type, 0)
    lever_pairs = LEVER_PAIRS_PER_STRUCTURE.get(structure_type, 0)

    return (
        HOOP_BENDING_PER_SET
        + poles * POLE_WELD_EACH
        + lever_pairs * LEVER_WELD_PER_PAIR
        + CROSS_WELD_PER_STRUCTURE
    )


def restitch_cost(net_count):
    """Restitching an existing net is priced by job size, not per structure."""

    if net_count <= 0:
        return 0.0
    if net_count < RESTITCH_PER_NET_THRESHOLD:
        return RESTITCH_SMALL_JOB
    return net_count * RESTITCH_PER_NET


def netting_cost(size, net_rate_per_lm, supplier_name="", new_net=True, net_count=1):
    """Netting for one structure: fabric + stitching + delivery.

    net_rate_per_lm is the true (VAT-inclusive) cost per linear metre of
    3m-wide netting, normally read from the Supplier Pricing table so it
    stays editable rather than hardcoded.
    """

    length_m = NET_LENGTHS_M.get(size)
    if length_m is None:
        raise ValueError(f"Unknown net size '{size}' - expected one of {sorted(NET_LENGTHS_M)}.")

    fabric = length_m * net_rate_per_lm
    stitching = NEW_NET_STITCHING_MIN * net_count if new_net else restitch_cost(net_count)

    delivery = 0.0
    if "knittex" in (supplier_name or "").lower() and fabric < KNITTEX_FREE_DELIVERY_OVER:
        delivery = KNITTEX_DELIVERY_FEE

    return {
        "length_m": length_m,
        "rate_per_lm": net_rate_per_lm,
        "fabric": round(fabric, 2),
        "stitching": round(stitching, 2),
        "delivery": round(delivery, 2),
        "total": round(fabric + stitching + delivery, 2),
    }


def _hardware_rate(item_name, pricing_service=None):
    """A live per-unit rate from the Hardware category, or None."""

    try:
        if pricing_service is None:
            from core.supplier_pricing_service import SupplierPricingService

            pricing_service = SupplierPricingService()

        for item in pricing_service.list_items("Hardware"):
            if item.item_name.lower() == item_name.lower():
                return item.cost_minor / 100
    except Exception:
        return None
    return None


def cable_and_clamps_cost(size, pricing_service=None, replacement=False):
    """Tensioning cable plus its clamps for one net.

    On a new install this is cable material by the metre. On a
    replacement it is the flat per-net rate, which already covers
    removing the old cable and fitting the new one - so it is far more
    than the wire alone, and correctly so.
    """

    if size not in CABLE_LENGTHS_M:
        raise ValueError(f"Unknown size '{size}' - expected one of {sorted(CABLE_LENGTHS_M)}.")

    clamp_rate = _hardware_rate("Hook/Eye Turnbuckle 10mm", pricing_service)
    if clamp_rate is None:
        return None
    clamps = CLAMPS_PER_NET * clamp_rate

    if replacement:
        cable = CABLE_REPLACEMENT_FLAT[size]
        return {
            "length_m": CABLE_LENGTHS_M[size],
            "rate_per_m": None,
            "cable": round(cable, 2),
            "clamps": round(clamps, 2),
            "total": round(cable + clamps, 2),
            "basis": "replacement flat rate (includes strip-out and refit)",
        }

    length_m = CABLE_LENGTHS_M[size]
    cable_rate = _hardware_rate("Cable 4mm Galvanised", pricing_service)
    if cable_rate is None:
        return None

    cable = length_m * cable_rate
    return {
        "length_m": length_m,
        "rate_per_m": cable_rate,
        "cable": round(cable, 2),
        "clamps": round(clamps, 2),
        "total": round(cable + clamps, 2),
        "basis": "new install, cable material by the metre",
    }


def paint_cost_per_structure(pricing_service=None):
    """Share of a 20L drum used by one structure, or None if paint has no
    active price. She buys 20L rather than 5L because it works out
    cheaper, and gets roughly 5 structures out of a drum."""

    try:
        if pricing_service is None:
            from core.supplier_pricing_service import SupplierPricingService

            pricing_service = SupplierPricingService()

        for item in pricing_service.list_items("Paint"):
            return round((item.cost_minor / 100) / STRUCTURES_PER_20L_DRUM, 2)
    except Exception:
        return None
    return None


def net_rate_for(supplier_name, pricing_service=None):
    """The live per-LM netting rate for a supplier, or None if that
    supplier has no active Netting row."""

    try:
        if pricing_service is None:
            from core.supplier_pricing_service import SupplierPricingService

            pricing_service = SupplierPricingService()

        for item in pricing_service.list_items("Netting"):
            if item.supplier_name.lower() == (supplier_name or "").lower():
                return item.cost_minor / 100
    except Exception:
        return None
    return None


def quote_structure(structure_type, size, net_supplier="Knittex Z25",
                    pricing_service=None, pole_price_key=None,
                    structure_gp=STRUCTURE_GP, netting_gp=NETTING_GP,
                    new_net=True, include_netting=True, include_paint=True,
                    back_to_back=False, include_structure=True):
    """Full costed quote for one structure.

    Returns cost and sell broken into structure (materials + labour) and
    netting, each marked up to its own gross profit target. Labour is
    included in the structure cost base and marked up with it; the flat
    supplier-side add-ons (hoop bending, welds) are what "flat" refers to
    - they are not themselves given a separate margin.

    Set include_structure=False with new_net=False to quote replacing a
    net on a structure that already stands - the common maintenance job.
    That charges netting, stitching and the flat replacement cable rate
    only, never the steel and fabrication again.

    Raises ValueError if a material price is missing, rather than
    returning a total that quietly understates the job.
    """

    materials = 0.0
    labour = 0.0
    paint = 0.0

    if include_structure:
        materials = structure_material_cost(structure_type, pricing_service, pole_price_key)
        if materials is None:
            raise ValueError(
                f"{structure_type} has unpriced materials - fill them in under "
                "Settings > Supplier Pricing before quoting."
            )
        labour = labour_cost(structure_type)

    if include_paint and include_structure:
        paint = paint_cost_per_structure(pricing_service)
        if paint is None:
            raise ValueError(
                "No active Paint price - add one under Settings > Supplier Pricing."
            )

    if back_to_back and include_structure:
        # Shared anchor poles between a back-to-back pair - steel only.
        materials = materials * (1 - BACK_TO_BACK_STEEL_DISCOUNT)

    structure_cost = materials + labour + paint
    structure_sell = structure_cost / (1 - structure_gp)

    netting = None
    netting_sell = 0.0
    if include_netting:
        rate = net_rate_for(net_supplier, pricing_service)
        if rate is None:
            raise ValueError(
                f"No active Netting price for '{net_supplier}' - add one under "
                "Settings > Supplier Pricing."
            )
        netting = netting_cost(size, rate, net_supplier, new_net=new_net)

        # A new net gets new cable priced as material; replacing a net
        # uses the flat rate that includes stripping the old one out.
        cable = cable_and_clamps_cost(size, pricing_service, replacement=not new_net)
        if cable is None:
            raise ValueError(
                "No active cable/clamp price - add them under Settings > Supplier Pricing."
            )
        netting["cable"] = cable
        netting["total"] = round(netting["total"] + cable["total"], 2)

        netting_sell = netting["total"] / (1 - netting_gp)

    total_cost = structure_cost + (netting["total"] if netting else 0.0)
    total_sell = structure_sell + netting_sell

    return {
        "structure_type": structure_type,
        "size": size,
        "net_supplier": net_supplier if include_netting else "",
        "materials": round(materials, 2),
        "labour": round(labour, 2),
        "paint": round(paint, 2),
        "structure_cost": round(structure_cost, 2),
        "structure_sell": round(structure_sell, 2),
        "netting": netting,
        "netting_sell": round(netting_sell, 2),
        "total_cost": round(total_cost, 2),
        "total_sell": round(total_sell, 2),
        "back_to_back": back_to_back,
        "include_structure": include_structure,
        "structure_gp": structure_gp,
        "netting_gp": netting_gp,
        "material_breakdown": structure_material_breakdown(
            structure_type, pricing_service, pole_price_key,
        ) if include_structure else [],
    }


__all__ = [
    "CAR_BAYS_TO_SIZE",
    "NET_LENGTHS_M",
    "can_price",
    "size_for_car_bays",
    "labour_cost",
    "restitch_cost",
    "netting_cost",
    "cable_and_clamps_cost",
    "CABLE_REPLACEMENT_FLAT",
    "net_rate_for",
    "paint_cost_per_structure",
    "quote_structure",
]
