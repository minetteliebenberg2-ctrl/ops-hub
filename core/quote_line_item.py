# ==========================================================
# FC Hub - Quote Line Item
# ----------------------------------------------------------
# Purpose:
# One structure (or other) line on a quote.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class QuoteLineItem:

    id: str = ""
    quote_id: str = ""
    sort_order: int = 0
    structure_type: str = ""
    car_bays: int = None
    shape: str = ""
    width_m: float = None
    projection_m: float = None
    height_m: float = None
    colour: str = ""
    description: str = ""
    quantity: float = 1
    unit_price_minor: int = 0
    amount_minor: int = 0
    created_at: str = ""
    updated_at: str = ""
