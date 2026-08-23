# ==========================================================
# FC Hub - Supplier Price Item
# ----------------------------------------------------------
# Purpose:
# One supplier's cost for one material/labour item - user-
# editable from Settings so costs never go stale in code.
# More than one row can share an item_name (e.g. "90% Shade
# Netting" under both Knittex Z25 and Plusnet) so the Quotes/
# Suppliers UI can offer a real supplier choice.
#
# Author: Minette & Claude
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class SupplierPriceItem:

    id: str = ""
    category: str = ""
    item_name: str = ""
    supplier_name: str = ""
    spec: str = ""
    unit: str = ""
    cost_minor: int = 0
    sort_order: int = 0
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""
