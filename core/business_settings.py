# ==========================================================
# FC Hub - Business Settings
# ----------------------------------------------------------
# Purpose:
# FacilitiesCo's own business identity, contact, and banking
# details, and its own addresses. Distinct from CRM customer
# data (core/customer.py, core/address.py).
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class BusinessSettings:

    id: str = "business"
    trading_name: str = ""
    legal_name: str = ""
    registration_number: str = ""
    vat_registered: bool = False
    vat_number: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    bank_name: str = ""
    bank_account_name: str = ""
    bank_account_number: str = ""
    branch_code: str = ""
    swift_code: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""


@dataclass
class BusinessAddress:

    id: str = ""
    address_type: str = ""
    line1: str = ""
    line2: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""
    country: str = ""
    is_primary: bool = False
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = ""
