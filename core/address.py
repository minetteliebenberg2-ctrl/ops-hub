# ==========================================================
# FC Utilities - Address
# ----------------------------------------------------------
# Purpose:
# Address model for CRM.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class Address:

    id: str = ""
    customer_id: str = ""
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
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    deleted_at: str = ""
    deleted_by: str = ""
