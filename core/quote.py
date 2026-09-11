# ==========================================================
# FC Hub - Quote
# ----------------------------------------------------------
# Purpose:
# Quote model. A quote belongs to a customer and optionally a
# site, and is numbered per-customer (FAC-001-Q-001).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class Quote:

    id: str = ""
    quote_number: str = ""
    customer_id: str = ""
    site_id: str = ""
    status: str = "Draft"
    issue_date: str = ""
    expiry_date: str = ""
    currency: str = "ZAR"
    payment_terms_snapshot: str = ""
    deposit_percentage: float = None
    balance_percentage: float = None
    subtotal_minor: int = 0
    vat_minor: int = 0
    total_minor: int = 0
    po_number: str = ""
    vat_number: str = ""
    registration_number: str = ""
    bill_to_name: str = ""
    print_billing_address: bool = True
    print_delivery_address: bool = False
    print_postal_address: bool = False
    notes: str = ""
    revision_of_quote_id: str = ""
    revision_number: int = 0
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    accepted_date: str = ""


def format_quote_number(quote):
    """Human-facing quote number, e.g. 'Q_26/001' for the original or
    'Q_26/001 (Rev 1)' for a revision. Revisions share the original's
    immutable number rather than drawing a new one - a changed quote
    is a new version of the same document, not a different document."""

    if not quote.quote_number:
        return "DRAFT"
    if quote.revision_number:
        return f"{quote.quote_number} (Rev {quote.revision_number})"
    return quote.quote_number
