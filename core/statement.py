# ==========================================================
# FC Hub - Statement
# ----------------------------------------------------------
# Purpose:
# A per-customer, per-period statement listing the Tax Invoices
# issued to that customer in the period.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class Statement:

    id: str = ""
    customer_id: str = ""
    document_number: str = ""
    period_start: str = ""
    period_end: str = ""
    notes: str = ""
    currency: str = "ZAR"
    total_minor: int = 0
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
