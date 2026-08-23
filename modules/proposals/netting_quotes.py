# ==========================================================
# FC Hub - Netting Quotes Service
# ----------------------------------------------------------
# Shade netting quote generation with adjustable margins
# Supports Knittex Z25, DriZ, Plusnet suppliers
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List


class NetType(Enum):
    SINGLE = (8, "Single")
    DOUBLE = (12, "Double")
    TRIPLE = (16, "Triple")

    def __init__(self, length_m, display_name):
        self.length_m = length_m
        self.display_name = display_name


class Supplier(Enum):
    KNITTEX_Z25 = "Knittex Z25"
    KNITTEX_DRIZ = "Knittex DriZ"
    PLUSNET = "Plusnet"


class QuoteBlock(Enum):
    BLOCK_A = "Block A - New Nets"
    BLOCK_B = "Block B - Painting & Cable"
    BLOCK_F = "Block F - Maintenance"


# ==========================================================
# SUPPLIER PRICING DATA
# ==========================================================

SUPPLIER_PRICES = {
    Supplier.KNITTEX_Z25: {
        "wholesale_per_lm": 105.53,
        "colors": {
            "Arizona": {"uv": 92, "shade": 84},
            "Black": {"uv": 96, "shade": 95},
            "Bush Khaki": {"uv": 93, "shade": 89},
            "Charcoal": {"uv": 95, "shade": 94},
            "Chocolate": {"uv": 93, "shade": 92},
            "Desert Sand": {"uv": 92, "shade": 80},
            "Mulberry": {"uv": 91, "shade": 90},
            "Navy Blue": {"uv": 94, "shade": 90},
            "R/Forest Green": {"uv": 96, "shade": 89},
            "Red": {"uv": 92, "shade": 91},
            "Royal Blue": {"uv": 94, "shade": 86},
            "Rust Gold": {"uv": 94, "shade": 90},
            "Silver": {"uv": 93, "shade": 88},
            "Terracotta": {"uv": 90, "shade": 84},
            "Turquoise": {"uv": 92, "shade": 83},
            "Yellow": {"uv": 94, "shade": 70},
        }
    },
    Supplier.KNITTEX_DRIZ: {
        "wholesale_per_lm": 183.68,
        "colors": {
            "Royal Blue": {"uv": 88, "shade": 94},
            "Rain Forest": {"uv": 96, "shade": 90},
            "Silver": {"uv": 93, "shade": 89},
            "Desert Sand": {"uv": 92, "shade": 80},
            "Rust Gold": {"uv": 94, "shade": 92},
            "Terracotta": {"uv": 90, "shade": 84},
            "Red": {"uv": 92, "shade": 91},
            "Charcoal": {"uv": 95, "shade": 94},
            "Chocolate": {"uv": 93, "shade": 93},
        }
    },
    Supplier.PLUSNET: {
        "wholesale_per_lm": 72.00,
        "colors": {
            "Charcoal": {"uv": 0, "shade": 0},
            "Silver": {"uv": 0, "shade": 0},
            "Black": {"uv": 0, "shade": 0},
        }
    }
}

# SUPPLY COSTS (nett prices after trade discounts)
CLAMP_COST = 22.13  # 10MM Hook/Eye Turnbuckles (nett after 25% discount)
CLAMPS_PER_NET = 2

# Cable cost per net (Toco, confirmed 2026-08-03) - flat per net, not per
# metre. Replaces the earlier CABLE_COST_PER_M x CABLE_LENGTHS estimate.
CABLE_COST_PER_NET = {
    NetType.SINGLE: 500,
    NetType.DOUBLE: 550,
    NetType.TRIPLE: 600,
}

# Cable per metre is still used for Block B's standalone "New Cable" line
# (buying surplus cable stock, not attached to a specific net) - see
# create_painting_cable_quote.
CABLE_COST_PER_M = 3.75  # Galvanised 4MM 6x7 (nett after 25% discount from R5.00)

# HIGH TIER - flat final quote prices confirmed 2026-08-03, cable already
# included, working off a ~65% markup. Same price regardless of supplier
# (Knittex vs Plusnet only affects the Standard tier's cost-plus-margin
# calculation below).
HIGH_TIER_PRICES = {
    NetType.SINGLE: 3200,
    NetType.DOUBLE: 3500,
    NetType.TRIPLE: 4036,
}

# PAINT COSTS
PAINT_20L_COST = 1314.86  # QD Enamel 20L (Durapaints)
PAINT_COLORS = ["White", "Black", "Light Grey", "Dark Grey", "Navy Blue", "Other"]

# MAINTENANCE ITEMS - STANDARD & HIGH TIERS (prices already include margin)
MAINTENANCE_ITEMS = {
    "refit_net": {
        "description": "Refit net each",
        "standard": 450,
        "high": 513,
    },
    "restitch_net": {
        "description": "Restitch net",
        "standard": 1750,
        "high": 1775,
    },
    "retensioning": {
        "description": "Retensioning/Tighten only",
        "standard": 375,
        "high": 420,
    },
    "replace_cable": {
        "description": "Replace cable per unit",
        "standard": 500,  # estimated, adjust as needed
        "high": 600,
    },
    "repaint_structure": {
        "description": "Repaint structure",
        "standard": 1500,
        "high": 1750,
    },
}

# DELIVERY
DELIVERY_CHARGE = 250
DELIVERY_THRESHOLD = 3000  # Orders under this amount incur delivery charge


# ==========================================================
# QUOTE CALCULATION
# ==========================================================

@dataclass
class NettingQuoteItem:
    """Single netting quote line item"""
    net_type: NetType
    supplier: Supplier
    color: str
    length_m: int
    qty: int = 1
    description: str = ""

    def calculate_supply_cost(self) -> float:
        """Calculate total supply cost (before margin)"""
        unit_price = SUPPLIER_PRICES[self.supplier]["wholesale_per_lm"]

        cable_cost = CABLE_COST_PER_NET[self.net_type]
        clamps_cost = CLAMPS_PER_NET * CLAMP_COST
        netting_cost = self.length_m * unit_price

        total_per_unit = netting_cost + cable_cost + clamps_cost
        return total_per_unit * self.qty

    def calculate_quote_price(self, margin_percent: float) -> float:
        """Calculate final quote price with margin

        margin_percent: desired gross profit margin (e.g., 45 for 45%)
        Formula: Cost / (1 - Margin%) = Price
        Example: R1000 cost with 45% margin = R1000 / 0.55 = R1818.18
        """
        cost = self.calculate_supply_cost()
        margin_decimal = margin_percent / 100
        return cost / (1 - margin_decimal)

    def high_tier_price(self) -> float:
        """Flat High-tier price - cable already included, confirmed
        2026-08-03. Same for either supplier; use whichever wholesale
        cost/color combination is relevant for the breakdown display."""

        return HIGH_TIER_PRICES[self.net_type] * self.qty


@dataclass
class QuoteSet:
    """Complete quote with both suppliers for comparison"""
    block: QuoteBlock
    net_type: NetType
    color: str
    qty: int = 1
    margin_percent: float = 45.0
    include_delivery: bool = False

    def generate_comparison(self) -> Dict:
        """Generate side-by-side pricing for both suppliers"""

        knittex_item = NettingQuoteItem(
            net_type=self.net_type,
            supplier=Supplier.KNITTEX_Z25,
            color=self.color,
            length_m=self.net_type.length_m,
            qty=self.qty
        )

        plusnet_item = NettingQuoteItem(
            net_type=self.net_type,
            supplier=Supplier.PLUSNET,
            color=self.color,
            length_m=self.net_type.length_m,
            qty=self.qty
        )

        knittex_cost = knittex_item.calculate_supply_cost()
        knittex_price = knittex_item.calculate_quote_price(self.margin_percent)

        plusnet_cost = plusnet_item.calculate_supply_cost()
        plusnet_price = plusnet_item.calculate_quote_price(self.margin_percent)

        # Calculate delivery
        knittex_delivery = DELIVERY_CHARGE if (self.include_delivery and knittex_price < DELIVERY_THRESHOLD) else 0
        plusnet_delivery = DELIVERY_CHARGE if (self.include_delivery and plusnet_price < DELIVERY_THRESHOLD) else 0

        knittex_final = knittex_price + knittex_delivery
        plusnet_final = plusnet_price + plusnet_delivery

        margin_diff = knittex_final - plusnet_final

        return {
            "net_type": f"{self.net_type.display_name} ({self.net_type.length_m}m)",
            "qty": self.qty,
            "color": self.color,
            "margin_percent": self.margin_percent,
            "knittex_z25": {
                "supplier": Supplier.KNITTEX_Z25.value,
                "supply_cost": round(knittex_cost, 2),
                "quote_price": round(knittex_price, 2),
                "delivery": round(knittex_delivery, 2),
                "final_price": round(knittex_final, 2),
            },
            "plusnet": {
                "supplier": Supplier.PLUSNET.value,
                "supply_cost": round(plusnet_cost, 2),
                "quote_price": round(plusnet_price, 2),
                "delivery": round(plusnet_delivery, 2),
                "final_price": round(plusnet_final, 2),
            },
            "margin_difference": round(margin_diff, 2),
            "high_tier_price": round(HIGH_TIER_PRICES[self.net_type] * self.qty, 2),
        }


class NettingQuoteService:
    """Service for generating netting quotes"""

    def __init__(self):
        self.quotes = []

    def get_colors_for_supplier(self, supplier: Supplier) -> List[str]:
        """Get available colors for a supplier"""
        return list(SUPPLIER_PRICES[supplier]["colors"].keys())

    def get_high_tier_price(self, net_type: NetType, qty: int = 1) -> float:
        """Flat High-tier price (cable included, ~65% markup, confirmed
        2026-08-03) - same regardless of supplier."""
        return round(HIGH_TIER_PRICES[net_type] * qty, 2)

    def create_netting_quote(self, net_type: NetType, supplier: Supplier,
                            color: str, qty: int = 1,
                            margin_percent: float = 45.0) -> Dict:
        """Create a single netting quote"""

        if supplier not in SUPPLIER_PRICES:
            raise ValueError(f"Unknown supplier: {supplier}")

        if color not in SUPPLIER_PRICES[supplier]["colors"]:
            raise ValueError(f"Color '{color}' not available for {supplier.value}")

        item = NettingQuoteItem(
            net_type=net_type,
            supplier=supplier,
            color=color,
            length_m=net_type.length_m,
            qty=qty
        )

        cost = item.calculate_supply_cost()
        price = item.calculate_quote_price(margin_percent)

        return {
            "net_type": f"{net_type.display_name} {net_type.length_m}m",
            "supplier": supplier.value,
            "color": color,
            "qty": qty,
            "supply_cost": round(cost, 2),
            "margin_percent": margin_percent,
            "quote_price": round(price, 2),
            "high_tier_price": round(item.high_tier_price(), 2),
            "breakdown": {
                "netting": round(net_type.length_m * SUPPLIER_PRICES[supplier]["wholesale_per_lm"] * qty, 2),
                "cable": round(CABLE_COST_PER_NET[net_type] * qty, 2),
                "clamps": round(CLAMPS_PER_NET * CLAMP_COST * qty, 2),
            }
        }

    def create_comparison_quote(self, net_type: NetType, color: str,
                               qty: int = 1, margin_percent: float = 45.0) -> Dict:
        """Create side-by-side comparison for both suppliers"""

        quote_set = QuoteSet(
            block=QuoteBlock.BLOCK_A,
            net_type=net_type,
            color=color,
            qty=qty,
            margin_percent=margin_percent,
            include_delivery=True
        )

        return quote_set.generate_comparison()

    def calculate_paint_cost(self, num_structures: int,
                            margin_percent: float = 60.0) -> Dict:
        """Calculate paint cost divided by number of structures"""

        cost_per_structure = PAINT_20L_COST / num_structures
        price_per_structure = cost_per_structure / (1 - (margin_percent / 100))

        return {
            "description": "20L Enamel Paint (Light Grey)",
            "num_structures": num_structures,
            "cost_per_structure": round(cost_per_structure, 2),
            "margin_percent": margin_percent,
            "price_per_structure": round(price_per_structure, 2),
            "total_price": round(price_per_structure * num_structures, 2),
        }

    def get_maintenance_options(self) -> Dict:
        """Get available maintenance options"""
        return MAINTENANCE_ITEMS

    def create_painting_cable_quote(self, num_structures: int,
                                    cable_meters: Optional[int] = None,
                                    margin_percent: float = 60.0) -> Dict:
        """Create Block B quote: Painting + New Cable

        num_structures: number of structures for paint allocation
        cable_meters: linear meters of new cable needed (optional)
        margin_percent: desired margin for painting (default 60%)
        """

        paint_cost = PAINT_20L_COST / num_structures
        paint_price = paint_cost / (1 - (margin_percent / 100))

        line_items = [
            {
                "description": "20L Enamel Paint - Light Grey (per structure)",
                "unit_price": round(paint_price, 2),
                "qty": num_structures,
                "total": round(paint_price * num_structures, 2),
            }
        ]

        total_cost = PAINT_20L_COST
        total_price = paint_price * num_structures

        # Add cable if specified
        if cable_meters and cable_meters > 0:
            cable_cost = cable_meters * CABLE_COST_PER_M
            cable_price = cable_cost / (1 - (margin_percent / 100))

            line_items.append({
                "description": f"New Cable - 4MM 6x7 Galv ({cable_meters}m)",
                "unit_price": round(CABLE_COST_PER_M, 2),
                "qty": cable_meters,
                "total": round(cable_price, 2),
            })

            total_cost += cable_cost
            total_price += cable_price

        return {
            "block": QuoteBlock.BLOCK_B.value,
            "line_items": line_items,
            "num_structures": num_structures,
            "cable_meters": cable_meters or 0,
            "total_cost": round(total_cost, 2),
            "margin_percent": margin_percent,
            "total_price": round(total_price, 2),
        }

    def create_maintenance_quote(self, items: Dict[str, int],
                                tier: str = "standard") -> Dict:
        """Create Block F quote: Maintenance items

        items: dict like {"refit_net": 2, "restitch_net": 1}
        tier: "standard" or "high" (prices already include margin)
        """

        if tier not in ["standard", "high"]:
            tier = "standard"

        total_price = sum(
            MAINTENANCE_ITEMS[key][tier] * qty
            for key, qty in items.items()
            if key in MAINTENANCE_ITEMS
        )

        line_items = [
            {
                "description": f"{MAINTENANCE_ITEMS[key]['description']} x{qty}",
                "unit_price": MAINTENANCE_ITEMS[key][tier],
                "qty": qty,
                "total": MAINTENANCE_ITEMS[key][tier] * qty,
            }
            for key, qty in items.items()
            if key in MAINTENANCE_ITEMS
        ]

        return {
            "block": QuoteBlock.BLOCK_F.value,
            "tier": tier,
            "line_items": line_items,
            "total_price": round(total_price, 2),
        }
