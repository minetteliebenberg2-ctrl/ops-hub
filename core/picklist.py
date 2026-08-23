# ==========================================================
# FC Hub - Picklist Option
# ----------------------------------------------------------
# Purpose:
# User-configurable reference data (payment terms, customer
# types, and future lists). Minette manages these herself from
# Settings instead of them being fixed in code.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class PicklistOption:

    id: str = ""
    list_name: str = ""
    value: str = ""
    deposit_percentage: float = None
    balance_percentage: float = None
    rate_low_minor: int = None
    rate_standard_minor: int = None
    rate_high_minor: int = None
    sort_order: int = 0
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""
