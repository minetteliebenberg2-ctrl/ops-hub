# ==========================================================
# FC Hub - Site Visit
# ----------------------------------------------------------
# Purpose:
# Site Visit model - a scheduled/completed visit against a real
# customer (and optionally one of their Sites). Deliberately minimal
# first pass: no measurements/checklist/photos/sign-off yet.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

SCHEDULED = "Scheduled"
COMPLETED = "Completed"


@dataclass
class SiteVisit:

    id: str = ""
    customer_id: str = ""
    site_id: str = ""
    visit_date: str = ""
    visit_time: str = ""
    notes: str = ""
    status: str = SCHEDULED
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""
    measurements_json: str = "{}"
    checklist_json: str = "{}"
