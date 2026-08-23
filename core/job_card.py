# ==========================================================
# FC Hub - Job Card
# ----------------------------------------------------------
# Purpose:
# A per-job/PO work log, separate from Site Visit scheduling.
# Scoped with Minette 2026-08-07 from a real paper form (a
# Job Card tied to one PO, with dated rows added as work
# happens over that job's life, plus staff/completion/
# director sign-off per row). One Job Card per job/PO, NOT a
# persistent per-Site record like the Site Plan.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass

OPEN = "Open"
CLOSED = "Closed"


@dataclass
class JobCard:

    id: str = ""
    customer_id: str = ""
    site_id: str = ""
    job_card_number: str = ""
    purchase_order: str = ""
    bill_to_name: str = ""
    delivery_address: str = ""
    status: str = OPEN
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    updated_by: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""


@dataclass
class JobCardEntry:
    """One dated row of work against a Job Card - date, type of work,
    a short job summary, description, who worked it, whether it's
    done, and a director sign-off. No pricing here on purpose - she
    said to leave amounts off the Job Card for v1."""

    id: str = ""
    job_card_id: str = ""
    entry_date: str = ""
    work_type: str = ""
    job_summary: str = ""
    description: str = ""
    staff: str = ""
    completed: bool = False
    director_signoff: str = ""
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""
