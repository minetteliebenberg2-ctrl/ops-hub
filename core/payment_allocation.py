# ==========================================================
# FC Hub - Payment Allocation
# ----------------------------------------------------------
# Purpose:
# Links a Payment to a Tax Invoice (quote_documents row) it settles,
# in whole or in part. Append-only - reversing an allocation writes a
# new row with a negative amount rather than deleting the original, so
# the full history stays intact.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class PaymentAllocation:

    id: str = ""
    payment_id: str = ""
    quote_document_id: str = ""
    amount_minor: int = 0
    notes: str = ""
    created_at: str = ""
    created_by: str = ""
