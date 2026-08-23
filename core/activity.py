# ==========================================================
# FC Hub - Activity
# ----------------------------------------------------------
# Purpose:
# Activity model for the CRM customer/contact/site timeline.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass


@dataclass
class Activity:

    id: str = ""
    customer_id: str = ""
    contact_id: str = ""
    site_id: str = ""
    source_entity_type: str = ""
    source_entity_id: str = ""
    activity_type: str = ""
    subject: str = ""
    activity_date: str = ""
    status: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    deleted_at: str = ""
    deleted_by: str = ""
