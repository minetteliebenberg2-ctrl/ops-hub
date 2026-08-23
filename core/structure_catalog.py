# ==========================================================
# FC Hub - Structure Catalog
# ----------------------------------------------------------
# Purpose:
# FacilitiesCo's real structure types, standard car-bay sizes,
# and shade sail options, confirmed directly by Minette
# 2026-07-29. Used by the Quotes line-item builder.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

CANTILEVER = "Cantilever"
# Renamed from "Standard" to "4 Post" 2026-08-12 - what she actually
# calls it on site (four posts, versus a cantilever's posts down one
# side). Migration v0038 renames the stored value too, so there is only
# ever one name for it. NOTE: unrelated to the "Standard"/"High"
# PRICING TIER in the Quotes grid, and to the "Standard" payment term.
STANDARD = "4 Post"
SHADE_SAIL = "Shade Sail"
REPLACE_CABLE = "Replace Cable"

STRUCTURE_TYPES = (CANTILEVER, STANDARD, SHADE_SAIL)

# Cable's "Single/Double/Triple" reuses the same car_bays integer field
# as Cantilever/Standard's real car-bay count (confirmed with Minette
# 2026-08-07: same mechanism, not a new named picklist variant) - it
# just means something different for cable (a size tier, not a
# physical bay count) and has no width/projection lookup attached.
CABLE_SIZE_LABELS = {1: "Single", 2: "Double", 3: "Triple"}

# Netting uses the same Single/Double/Triple tiers as cable (asked for
# 2026-08-12 - nets were showing a blank size on the Site Plan and its
# export). For "New Net - Double" and friends the tier is already in
# the name, so it is preselected rather than left for her to repeat.
NET_SIZE_LABELS = dict(CABLE_SIZE_LABELS)

REFIT_NET = "Refit Net"
RESTITCH_NET = "Restitch Net"
RETENSIONING = "Retensioning"
NEW_NET_PREFIX = "New Net - "

NET_TYPES = (
    REFIT_NET,
    RESTITCH_NET,
    RETENSIONING,
    f"{NEW_NET_PREFIX}Single",
    f"{NEW_NET_PREFIX}Double",
    f"{NEW_NET_PREFIX}Triple",
)

# Every type whose "size" is a Single/Double/Triple tier rather than a
# physical car-bay measurement.
SIZE_TIER_TYPES = (REPLACE_CABLE,) + NET_TYPES


def implied_net_size(structure_type):
    """car_bays tier implied by a "New Net - Double" style name, else
    None. The name already says the size; nothing should make her pick
    it twice."""

    if not structure_type or not structure_type.startswith(NEW_NET_PREFIX):
        return None
    tier = structure_type[len(NEW_NET_PREFIX):].strip()
    for cars, label in NET_SIZE_LABELS.items():
        if label.lower() == tier.lower():
            return cars
    return None

# Car bays -> (width_m, projection_m). Applies to both Cantilever and
# Standard. 4 cars is technically supported but Minette said they rarely
# do it because it "doesn't last" - flagged, not hidden.
CAR_BAY_SIZES = {
    1: (3.0, 5.0),
    2: (5.0, 5.0),
    3: (7.5, 5.0),
    4: (10.0, 5.0),
}

# The 3-car size has a client-requested extra projection option.
THREE_CAR_OPTIONAL_PROJECTION = 5.5

NOT_RECOMMENDED_CAR_BAYS = {4}

DEFAULT_HEIGHT_M = 2.1

# Cantilever's own arm geometry is fixed regardless of car bays.
CANTILEVER_TOP_LEVER_HEIGHT_M = 3.0
CANTILEVER_BOTTOM_LEVER_HEIGHT_M = 2.3

SHADE_SAIL_SHAPES = ("Triangle", "Rectangle", "Square")
SHADE_SAIL_MAX_HEIGHT_M = 5.0
SHADE_SAIL_POLE_DIAMETERS_MM = (152, 165)


# ==========================================================
# Per-structure material bill of materials (BOM)
# ----------------------------------------------------------
# Given verbatim by Minette 2026-08-08. Each part is:
#   (part, qty, spec, unit_length_m, stock_length_m,
#    cost_per_stock, note, price_key)
#
# All costs are TRUE COST INCLUDING VAT. FacilitiesCo is not
# VAT registered, so input VAT can never be reclaimed - the 15%
# is a real part of what a structure costs. Costing off ex-VAT
# figures would understate every quote (see migration v0034).
#
# cost_per_stock_ex_vat is a FALLBACK only - the live cost comes
# from the editable `supplier_price_items` table (Settings ->
# Supplier Pricing, migration v0031), looked up via price_key
# (category, item_name). Minette asked for every supplier price
# to be editable rather than hardcoded, so the DB always wins;
# these literals are just what to use before that table exists
# (e.g. a fresh database mid-migration) and to keep this module
# importable without a database.
#
# price_key of None means "deliberately unpriced" - the part
# needs a decision, not a lookup.
#
# The frame does NOT scale with car bays - Minette confirmed
# 2026-08-08 that a single, double and triple use the same steel;
# only the netting changes (8m / 12m / 16m of 3m-wide net).
#
# Standard/4-post anchor poles default to 76mm, which Minette
# confirmed is her standard; 101mm is used for larger or higher
# structures, difficult ground, or an explicit customer spec -
# her judgement per job, so it is a caller override
# (pole_price_key), not something derived from car-bay count.
# ==========================================================

# Confirmed by Minette 2026-08-08: R1200 per 6m ex-VAT, i.e. R1380
# including the 15% she cannot reclaim.
POLE_152MM_COST_PER_6M_EX_VAT = 1200.0
POLE_152MM_COST_PER_6M = 1380.0

STRUCTURE_BOM = {
    CANTILEVER: [
        ("Anchor poles", 2, "152mm round tube, 3mm wall", 4.2, 6.0, 1380.0, "R1,200/6m ex-VAT = R1,380 incl (confirmed 2026-08-08)", ("Steel", "Anchor Pole 152mm")),
        ("Hoops", 4, "50mm round tube, 2mm wall", 6.0, 6.0, 230.0, "Chemvet 50.8x2.0mm @ R200/6m ex-VAT = R230 incl", ("Steel", "Hoop / Top Lever Tube 50.8mm")),
        ("Cross bracing flat bar", 1, "60mm x 5mm flat bar", 2.0, 6.0, 250.0, "R250/6m incl (trade estimate - the R1,200 first given was the pole's price, not this)", ("Steel", "Cross Flat Bar 60mm")),
        ("Top lever", 2, "50mm round tube, 2mm wall", 4.0, 6.0, 230.0, "Chemvet 50.8x2.0mm @ R230/6m incl, pro-rated", ("Steel", "Hoop / Top Lever Tube 50.8mm")),
        ("Bottom lever", 2, "57mm round tube, 2mm wall", 6.0, 6.0, 258.75, "Chemvet 57.1x2.0mm @ R225/6m ex-VAT = R258.75 incl", ("Steel", "Bottom Lever Tube 57.1mm")),
        ("Hoop inserts", 4, "42mm round tube, 2mm wall", 0.1, 6.0, 243.0, "Steel & Pipes @ R243/6m incl; 1.9mm wall is the trade equivalent of 2mm", ("Steel", "Hoop Insert Tube 42mm")),
        ("Lug angle iron", 1, "70x60mm angle iron, 5mm", 2.0, 6.0, 550.0, "R550/6m incl (trade estimate - the R1,200 first given was the pole's price, not this)", ("Steel", "Lug Angle Iron 70x60mm")),
        ("Pole caps", 2, "-", None, None, 30.0, "R30 each", ("Hardware", "Pole Cap")),
        ("Ready-mix concrete", 3.5, "40kg bag", None, None, 60.0, "3.5 bags flat total per structure (not per hole)", ("Hardware", "Ready-Mix Concrete")),
    ],
    STANDARD: [
        ("Anchor poles", 4, "76mm round tube, 2mm wall (101mm on larger/higher structures)", 3.0, 6.0, 419.0, "76mm is standard; pass pole_price_key=(\"Steel\", \"Anchor Pole 101.6mm\") for larger/higher structures, poor ground, or a customer spec", ("Steel", "Anchor Pole 76mm")),
        ("Hoops", 4, "50mm round tube, 2mm wall", 6.0, 6.0, 230.0, "Chemvet 50.8x2.0mm @ R200/6m ex-VAT = R230 incl", ("Steel", "Hoop / Top Lever Tube 50.8mm")),
        ("Cross bracing flat bar", 1, "60mm x 5mm flat bar", 2.0, 6.0, 250.0, "R250/6m incl (same as Cantilever)", ("Steel", "Cross Flat Bar 60mm")),
        ("Hoop inserts", 4, "42mm round tube, 2mm wall", 0.1, 6.0, 243.0, "Steel & Pipes @ R243/6m incl; 1.9mm wall is the trade equivalent of 2mm", ("Steel", "Hoop Insert Tube 42mm")),
        ("Round bar per hoop", 4, "8mm round bar", 0.1, 6.0, 39.0, "Steel & Pipes 8mm round bar @ R39/6m incl", ("Steel", "Round Bar 8mm")),
        ("Ready-mix concrete", 8, "40kg bag", None, None, 60.0, "2 bags per pole x 4 poles = 8 bags total", ("Hardware", "Ready-Mix Concrete")),
    ],
}


def structure_bom(structure_type):
    """The per-structure material bill for Cantilever or Standard, or []
    for any type without a fixed BOM (e.g. Shade Sail, which is per-sqm)."""

    return STRUCTURE_BOM.get(structure_type, [])


def _live_prices(pricing_service=None):
    """{(category, item_name): cost_rand} from the editable Supplier
    Pricing table. Returns {} if that table isn't reachable, so this
    module stays importable and testable without a database.

    Where one item has several suppliers (Minette asked for more than one
    supplier option per item), the cheapest active row wins - a costing
    default she can override by deactivating the row she isn't using.
    """

    try:
        if pricing_service is None:
            from core.supplier_pricing_service import SupplierPricingService

            pricing_service = SupplierPricingService()

        from core.supplier_pricing_repository import CATEGORIES

        prices = {}
        for category in CATEGORIES:
            for item in pricing_service.list_items(category):
                key = (item.category, item.item_name)
                cost = item.cost_minor / 100
                if key not in prices or cost < prices[key]:
                    prices[key] = cost
        return prices
    except Exception:
        return {}


def structure_material_breakdown(structure_type, pricing_service=None, pole_price_key=None):
    """Per-part costing for one structure, showing where each price came
    from so nothing is hidden behind a single total.

    Each entry: {part, qty, spec, note, unit_cost, line_cost, source}
    where source is "supplier pricing" (live, editable), "built-in
    default" (no DB row matched), or "unpriced" (needs a decision).
    """

    bom = structure_bom(structure_type)
    if not bom:
        return []

    prices = _live_prices(pricing_service)
    breakdown = []

    for part, qty, spec, unit_length_m, stock_length_m, fallback_cost, note, price_key in bom:
        # Standard/4-post: 76mm is the default, but Minette picks 101mm
        # per job for larger/higher structures, difficult ground, or a
        # customer spec - so an explicit override always wins.
        key = pole_price_key if (pole_price_key and part == "Anchor poles" and structure_type == STANDARD) else price_key

        if key and key in prices:
            unit_cost, source = prices[key], "supplier pricing"
        elif fallback_cost is not None:
            unit_cost, source = fallback_cost, "built-in default"
        else:
            unit_cost, source = None, "unpriced"

        if unit_cost is None:
            line_cost = None
        elif unit_length_m and stock_length_m:
            line_cost = round(qty * (unit_length_m / stock_length_m) * unit_cost, 2)
        else:
            line_cost = round(qty * unit_cost, 2)

        breakdown.append({
            "part": part,
            "qty": qty,
            "spec": spec,
            "note": note,
            "unit_cost": unit_cost,
            "line_cost": line_cost,
            "source": source,
        })

    return breakdown


def structure_material_cost(structure_type, pricing_service=None, pole_price_key=None):
    """Total true (VAT-inclusive) material cost for one structure, or None if any part
    is still unpriced (so a caller never quietly under-quotes on a
    placeholder).

    Costs come from the editable Supplier Pricing table where a row
    matches, falling back to the built-in defaults otherwise - see
    structure_material_breakdown() for which was used per part.
    """

    breakdown = structure_material_breakdown(structure_type, pricing_service, pole_price_key)
    if not breakdown:
        return None

    total = 0.0
    for entry in breakdown:
        if entry["line_cost"] is None:
            return None
        total += entry["line_cost"]
    return round(total, 2)


def car_bay_size(car_bays):
    """Return (width_m, projection_m) for a given number of car bays, or
    None if it's not one of the standard sizes."""

    return CAR_BAY_SIZES.get(car_bays)


def car_bay_options():
    """Ordered (cars, label) pairs for a dropdown."""

    options = []
    for cars in sorted(CAR_BAY_SIZES):
        width, projection = CAR_BAY_SIZES[cars]
        label = f"{cars} Car — {width:g}m x {projection:g}m"
        if cars in NOT_RECOMMENDED_CAR_BAYS:
            label += " (not recommended)"
        options.append((cars, label))
    return options


def size_options_for(structure_type):
    """(ordered labels including "N/A", {label: car_bays or None}) for
    whatever size concept applies to this structure type - real car-bay
    dimensions for Cantilever/Standard, Single/Double/Triple tiers for
    Cable, or just ("N/A",) if the type has no size concept at all.
    Shared by the Site Plan form and the Quotes grid's Car Bay dropdown
    so they can never drift apart."""

    if structure_type in (CANTILEVER, STANDARD):
        options = ["N/A"] + [label for _cars, label in car_bay_options()]
        by_label = {"N/A": None}
        by_label.update({label: cars for cars, label in car_bay_options()})
        return options, by_label

    if structure_type in SIZE_TIER_TYPES:
        options = ["N/A"] + list(CABLE_SIZE_LABELS.values())
        by_label = {"N/A": None}
        by_label.update({label: cars for cars, label in CABLE_SIZE_LABELS.items()})
        return options, by_label

    return ["N/A"], {"N/A": None}


def size_label_for(structure_type, car_bays):
    """Inverse of size_options_for - the label to preselect for a given
    (structure_type, car_bays) pair."""

    if car_bays is None:
        # "New Net - Double" already states its own size, so show it
        # rather than a blank, even before she picks anything.
        implied = implied_net_size(structure_type)
        if implied is None:
            return "N/A"
        car_bays = implied

    if structure_type in (CANTILEVER, STANDARD):
        return dict(car_bay_options()).get(car_bays, "N/A")
    if structure_type in SIZE_TIER_TYPES:
        return CABLE_SIZE_LABELS.get(car_bays, "N/A")
    return "N/A"


# Kept so nothing breaks on the old name, but it never returned an ex-VAT
# figure after v0034 - costs are true (VAT-inclusive) cost throughout.
structure_material_cost_ex_vat = structure_material_cost
