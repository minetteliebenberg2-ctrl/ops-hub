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
