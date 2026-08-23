# ==========================================================
# FC Hub - Payment
# ----------------------------------------------------------
# Purpose:
# A customer payment (receipt) logged manually against one or more
# Tax Invoices.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

UNALLOCATED = "Unallocated"
PARTIALLY_ALLOCATED = "Partially Allocated"
ALLOCATED = "Allocated"


@dataclass
class Payment:

    id: str = ""
    customer_id: str = ""
    amount_minor: int = 0
    date: str = ""
    reference: str = ""
    notes: str = ""
    status: str = UNALLOCATED
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
