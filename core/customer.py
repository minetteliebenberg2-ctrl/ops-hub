# ==========================================================
# FC Utilities - Customer
# ----------------------------------------------------------
# Purpose:
# Customer model for CRM.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class Customer:

    id: str = ""
    customer_number: str = ""
    name: str = ""
    customer_type: str = ""
    status: str = ""
    payment_terms: str = "Standard"
    email: str = ""
    phone: str = ""
    website: str = ""
    vat_number: str = ""
    registration_number: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    deleted_at: str = ""
    deleted_by: str = ""
