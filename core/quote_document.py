# ==========================================================
# FC Hub - Quote Document
# ----------------------------------------------------------
# Purpose:
# A Pro-Forma or Tax Invoice generated from an issued Quote.
# Snapshots the quote's totals at generation time.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

PRO_FORMA = "Pro-Forma"
TAX_INVOICE = "Tax Invoice"

# Split deposit / balance invoicing (invoice_part on quote_documents)
DEPOSIT = "deposit"
BALANCE = "balance"

# The deposit split used to be a hardcoded 65/35 constant. It is now a
# business setting (migration v0058) so it can be changed without a
# code change. These helpers are the single read path - never import a
# DEPOSIT_PERCENT constant again. The import is deferred to keep
# core.quote_document free of a settings/database dependency at import
# time, and every failure falls back to the old 65 so a missing or
# unmigrated settings row can never break invoicing.
DEFAULT_DEPOSIT_PERCENT = 65


def deposit_percent(settings_service=None):
    """The configured deposit %, 1-99, defaulting to 65."""

    try:
        if settings_service is None:
            from core.business_settings_service import BusinessSettingsService
            settings_service = BusinessSettingsService()
        value = int(settings_service.get_settings().deposit_percent or DEFAULT_DEPOSIT_PERCENT)
    except Exception:
        return DEFAULT_DEPOSIT_PERCENT
    return value if 1 <= value <= 99 else DEFAULT_DEPOSIT_PERCENT


def balance_percent(settings_service=None):
    """Always the remainder - deposit and balance sum to 100."""

    return 100 - deposit_percent(settings_service)


@dataclass
class QuoteDocument:

    id: str = ""
    quote_id: str = ""
    customer_id: str = ""
    doc_type: str = ""
    document_number: str = ""
    issue_date: str = ""
    due_date: str = ""
    po_number: str = ""
    vat_number: str = ""
    registration_number: str = ""
    bill_to_name: str = ""
    notes: str = ""
    status: str = "Issued"
    currency: str = "ZAR"
    subtotal_minor: int = 0
    vat_minor: int = 0
    total_minor: int = 0
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    invoice_part: str = ""
