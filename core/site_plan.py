# ==========================================================
# FC Hub - Site Plan
# ----------------------------------------------------------
# Purpose:
# A persistent, freeform diagram for one Site - a backdrop image
# (hers, pasted in) plus rectangles, each one both a drawn structure
# AND a prospective Quote line item at once. Mapped out with Minette
# 2026-08-07: "each site is different... one may have 2 structures,
# another may have 40+", so this is drawn once and updated over time,
# never redrawn per visit.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

PORTRAIT = "portrait"
LANDSCAPE = "landscape"

GRID_TEMPLATES = {
    PORTRAIT: "site_plan_default_grid.png",
    LANDSCAPE: "site_plan_default_grid_landscape.png",
}


def grid_template_filename(orientation):
    """Asset filename for a grid orientation, falling back to portrait
    for anything unrecognised (an older row, or a hand-edited value)."""

    return GRID_TEMPLATES.get(orientation, GRID_TEMPLATES[PORTRAIT])


@dataclass
class SitePlan:

    id: str = ""
    site_id: str = ""
    backdrop_filename: str = ""
    backdrop_width: int = 0
    backdrop_height: int = 0
    # Which built-in grid template to fall back on when she has not
    # uploaded her own image. Most sites are car parks - wide, not tall
    # - so landscape matters; an uploaded backdrop ignores this.
    grid_orientation: str = PORTRAIT
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""


@dataclass
class SitePlanItem:
    """One rectangle on the plan - position/size as fractions
    (0.0-1.0) of the backdrop image, so it stays correctly placed
    however the canvas is displayed. Carries the same fields as a
    real Quote line item (see core/quote_line_item.py) on purpose -
    her words: "nothing changes on my side between drawing the site
    plan and doing the quote."."""

    id: str = ""
    site_plan_id: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # Degrees, about the rectangle's centre, measured in display-pixel
    # space - real parking bays are rarely square to the image (see
    # core/site_plan_geometry.py). 0 is the old axis-aligned behaviour,
    # so everything drawn before 2026-08-12 is unchanged.
    rotation: float = 0.0
    structure_type: str = ""
    car_bays: int = None
    description: str = ""
    quantity: float = 1
    unit_price_minor: int = 0
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""

    @property
    def amount_minor(self):
        return round(self.quantity * self.unit_price_minor)
